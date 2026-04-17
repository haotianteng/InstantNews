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

import requests

from app.services.feed_parser import utc_iso
from datetime import datetime, timezone

logger = logging.getLogger("signal.twitter")

X_API_BASE = "https://api.x.com/2"
RECENT_SEARCH_PATH = "/tweets/search/recent"
USER_LOOKUP_PATH = "/users/by/username"
USER_TIMELINE_PATH = "/users/{id}/tweets"


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
        for chunk in _chunk_by_query_length(usernames, max_chars=450):
            query = " OR ".join(f"from:{u}" for u in chunk)
            params = {
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
                break
            if code != 200:
                logger.warning("X API search/recent status=%s body=%s",
                               code, (resp.text or "")[:200])
                continue
            data = resp.json()
            # Build id -> username from the expansions.includes.users[] payload
            id_to_username: Dict[str, str] = {}
            for u in (data.get("includes") or {}).get("users", []) or []:
                uid = str(u.get("id", ""))
                uname = u.get("username", "")
                if uid and uname:
                    id_to_username[uid] = uname

            # Fold into persistent cache so subsequent calls also benefit
            self._user_id_cache.update({v: k for k, v in id_to_username.items()})

            for tw in data.get("data", []) or []:
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
        return all_tweets


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
    """Public entry-point called by feed_refresh. Returns News-ready dicts."""
    client = TwitterClient(bearer_token)
    if not client.enabled:
        logger.info("Twitter disabled (no bearer token)")
        return []
    if not handles:
        return []
    t0 = time.time()
    raw = client.search_recent(handles, max_results=max_results)
    rows = [tweet_to_news_row(t) for t in raw]
    logger.info("Twitter fetch: %d handles -> %d tweets in %.2fs",
                len(handles), len(rows), time.time() - t0)
    return rows
