"""Twitter/X fetcher for the diplomatic watchlist.

Uses the X API v2 `/tweets/search/recent` endpoint to pull recent tweets from
a list of @handles in one call. Polling only — no filtered streaming — since
feed_refresh already runs on a short interval.

Each tweet becomes a News row with:
  source = f"Twitter/@{handle}"
  link   = f"https://x.com/{handle}/status/{tweet_id}"  (UNIQUE, dedup)
  title  = f"@{handle}: <first 80 chars>"
  summary = full tweet text
The Bedrock pipeline (feed_refresh._run_bedrock_analysis) then fills sentiment,
ticker, tradeable on the News row.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests  # type: ignore[import-untyped]

from app.services.feed_parser import utc_iso
from app.services.metrics import emit_metric, emit_metrics
from datetime import datetime, timezone

logger = logging.getLogger("signal.twitter")

X_API_BASE = "https://api.x.com/2"
RECENT_SEARCH_PATH = "/tweets/search/recent"
USER_LOOKUP_PATH = "/users/by/username"
USER_TIMELINE_PATH = "/users/{id}/tweets"
_TWITTER_NAMESPACE = "InstantNews/Twitter"


def _header_int(resp, key: str) -> Optional[int]:
    """Parse a numeric X API rate-limit header, returning ``None`` on any failure."""
    try:
        raw = resp.headers.get(key)
    except AttributeError:
        return None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@dataclass
class RawTweet:
    id: str
    text: str
    author_username: str
    created_at: str
    url: str = ""
    metrics: Dict = field(default_factory=dict)


class TwitterClient:
    """Thin X API v2 client. One instance per process — reuses a requests.Session."""

    def __init__(self, bearer_token: str, timeout_seconds: int = 15):
        self._bearer = bearer_token.strip() if bearer_token else ""
        self._timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self._bearer}"})
        self._user_id_cache: Dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._bearer)

    def _get(self, path: str, params: Optional[dict] = None):
        url = X_API_BASE + path
        try:
            resp = self._session.get(url, params=params or {}, timeout=self._timeout)
        except requests.RequestException as e:
            logger.warning("X API request error path=%s err=%s", path, e)
            return None, 0
        return resp, resp.status_code

    def resolve_user_id(self, username: str) -> Optional[str]:
        if username in self._user_id_cache:
            return self._user_id_cache[username]
        resp, code = self._get(f"{USER_LOOKUP_PATH}/{username}")
        if resp is None:
            return None
        if code == 200:
            uid = (resp.json().get("data") or {}).get("id")
            if uid:
                self._user_id_cache[username] = uid
                return uid
        elif code == 429:
            logger.warning("X API 429 (rate limit) on user lookup @%s", username)
        else:
            logger.warning("X API user lookup @%s status=%s body=%s",
                           username, code, (resp.text or "")[:200])
        return None

    def search_recent(
        self,
        usernames: List[str],
        max_results: int = 100,
        since_id: Optional[str] = None,
    ) -> List[RawTweet]:
        """One API call fetching tweets from up to ~40 usernames via `from:` OR.

        Uses `expansions=author_id` + `user.fields=username` so we get each tweet's
        author username in the same response — avoids the aggressively rate-limited
        /users/by/username lookup endpoint.

        X v2 caps search query length at 512 chars, so we chunk if needed.
        """
        if not usernames or not self.enabled:
            return []

        all_tweets: List[RawTweet] = []
        max_newest_id = None
        for chunk in _chunk_by_query_length(usernames, max_chars=3800):
            query = " OR ".join(f"from:{u}" for u in chunk)
            params: Dict = {
                "query": query,
                "max_results": max(10, min(100, max_results)),
                "tweet.fields": "created_at,public_metrics,text,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            }
            if since_id:
                params["since_id"] = since_id
            resp, code = self._get(RECENT_SEARCH_PATH, params=params)
            if resp is None:
                continue
            if code == 429:
                logger.warning("X API 429 on search/recent — stopping chunk loop")
                emit_metric(
                    namespace=_TWITTER_NAMESPACE,
                    metric_name="RateLimited",
                    value=1,
                    unit="Count",
                    dimensions={"Endpoint": "search_recent"},
                )
                break
            if code != 200:
                logger.warning("X API search/recent status=%s body=%s",
                               code, (resp.text or "")[:200])
                continue
            data = resp.json()
            # Emit one EMF line per successful search/recent call so the
            # dashboard can chart rate-limit headroom + billable counts.
            tweets_billed = len(data.get("data", []) or [])
            users_billed = len((data.get("includes") or {}).get("users", []) or [])
            rl_remaining = _header_int(resp, "x-rate-limit-remaining")
            rl_limit = _header_int(resp, "x-rate-limit-limit")
            metrics_payload: List[dict] = [
                {"name": "TweetsBilled", "value": tweets_billed, "unit": "Count"},
                {"name": "UsersBilled", "value": users_billed, "unit": "Count"},
            ]
            if rl_remaining is not None:
                metrics_payload.append(
                    {"name": "RateLimitRemaining", "value": rl_remaining, "unit": "Count"}
                )
            if rl_limit is not None:
                metrics_payload.append(
                    {"name": "RateLimitLimit", "value": rl_limit, "unit": "Count"}
                )
            emit_metrics(
                namespace=_TWITTER_NAMESPACE,
                metrics=metrics_payload,
                dimensions={"Endpoint": "search_recent"},
            )
            # Build id -> username from the expansions.includes.users[] payload
            id_to_username: Dict[str, str] = {}
            for u in (data.get("includes") or {}).get("users", []) or []:
                uid = str(u.get("id", ""))
                uname = u.get("username", "")
                if uid and uname:
                    id_to_username[uid] = uname

            # Fold into persistent cache so subsequent calls also benefit
            self._user_id_cache.update({v: k for k, v in id_to_username.items()})

            chunk_newest = (data.get("meta") or {}).get("newest_id")
            if chunk_newest and (max_newest_id is None or int(chunk_newest) > int(max_newest_id)):
                max_newest_id = chunk_newest

            for tw in data.get("data", []) or []:
                # Filter inclusive since_id quirk: X returns tweets WITH id == since_id
                # even though the doc says "greater than". Skip any id <= since_id.
                if since_id:
                    try:
                        if int(tw["id"]) <= int(since_id):
                            continue
                    except (ValueError, TypeError):
                        pass
                author_id = str(tw.get("author_id", ""))
                username = id_to_username.get(author_id) or f"uid:{author_id}"
                all_tweets.append(RawTweet(
                    id=str(tw["id"]),
                    text=tw.get("text", "") or "",
                    author_username=username,
                    created_at=tw.get("created_at") or utc_iso(datetime.now(timezone.utc)),
                    url=f"https://x.com/{username}/status/{tw['id']}",
                    metrics=tw.get("public_metrics", {}) or {},
                ))
        # Expose the max newest_id to the caller via instance attr for persistence
        self._last_max_newest_id = max_newest_id
        return all_tweets


SINCE_ID_REDIS_KEY = "twitter:since_id:diplomatic"
SINCE_ID_TTL_SECONDS = 7 * 24 * 3600  # roll forward from scratch if we haven't polled in a week


def _load_since_id() -> Optional[str]:
    try:
        from app.cache.redis_client import get_redis
        v = get_redis().get(SINCE_ID_REDIS_KEY)
        if v is None:
            return None
        return v.decode() if isinstance(v, bytes) else str(v)
    except Exception as e:
        logger.warning("since_id load failed: %s", e)
        return None


def _store_since_id(newest_id: str) -> None:
    try:
        from app.cache.redis_client import get_redis
        # X snowflake IDs are numeric strings; we store as-is.
        get_redis().setex(SINCE_ID_REDIS_KEY, SINCE_ID_TTL_SECONDS, newest_id)
    except Exception as e:
        logger.warning("since_id store failed: %s", e)


def _bump_since_id(max_seen: str) -> str:
    """X treats since_id as inclusive (confirmed via live probe). Adding 1 makes the
    next call exclusive of the ID we've already seen, which is what the caller wants.
    Snowflake IDs are monotonically increasing so max_seen+1 is a valid lower bound."""
    try:
        return str(int(max_seen) + 1)
    except (ValueError, TypeError):
        return max_seen


def _chunk_by_query_length(usernames: List[str], max_chars: int) -> List[List[str]]:
    """Split usernames into chunks whose ` OR `-joined `from:` query stays under max_chars."""
    chunks: List[List[str]] = []
    current: List[str] = []
    current_len = 0
    for u in usernames:
        piece = (5 + len(u)) + (4 if current else 0)  # "from:<u>" plus " OR "
        if current_len + piece > max_chars and current:
            chunks.append(current)
            current, current_len = [], 0
        current.append(u)
        current_len += piece
    if current:
        chunks.append(current)
    return chunks


def tweet_to_news_row(tw: RawTweet) -> dict:
    """Convert a RawTweet to the dict shape feed_refresh._store_items expects."""
    text = tw.text.strip()
    snippet = text[:80] + ("..." if len(text) > 80 else "")
    return {
        "title": f"@{tw.author_username}: {snippet}",
        "link": tw.url,
        "source": f"Twitter/@{tw.author_username}",
        "published": tw.created_at or utc_iso(datetime.now(timezone.utc)),
        "summary": text,
        "sentiment_score": 0.0,
        "sentiment_label": "neutral",
    }


def fetch_diplomatic_tweets(bearer_token: str, handles: List[str], max_results: int = 100) -> List[dict]:
    """Public entry-point. Uses Redis-persisted since_id to fetch only new tweets."""
    client = TwitterClient(bearer_token)
    if not client.enabled:
        logger.info("Twitter disabled (no bearer token)")
        return []
    if not handles:
        return []
    t0 = time.time()
    stored = _load_since_id()
    since_id = _bump_since_id(stored) if stored else None
    raw = client.search_recent(handles, max_results=max_results, since_id=since_id)
    rows = [tweet_to_news_row(t) for t in raw]
    # Persist the max newest_id we saw this run (across all chunks) for next call.
    new_max = getattr(client, "_last_max_newest_id", None)
    if new_max:
        _store_since_id(new_max)
    logger.info("Twitter fetch: %d handles -> %d tweets in %.2fs since_id=%s new_max=%s",
                len(handles), len(rows), time.time() - t0, since_id or '-', new_max or '-')
    return rows
