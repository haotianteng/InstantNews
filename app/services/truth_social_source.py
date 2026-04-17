"""Truth Social fetcher — Donald Trump posts via CNN's public mirror.

The CNN live archive at https://ix.cnn.io/data/truth-social/truth_archive.json
is refreshed every ~5 minutes and requires no authentication. Each post becomes
a News row with source "TruthSocial/@realDonaldTrump" and a deterministic link
(UNIQUE, for dedup).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import List

import requests

from app.services.feed_parser import utc_iso

logger = logging.getLogger("signal.truth_social")

CNN_TRUTH_ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
AUTHOR = "realDonaldTrump"
SOURCE_NAME = f"TruthSocial/@{AUTHOR}"


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def _post_link(post: dict) -> str:
    """Prefer the post's canonical URL; fall back to a synthetic, deterministic one."""
    url = (post.get("url") or "").strip()
    if url:
        return url
    pid = str(post.get("id", "")).strip()
    if pid:
        return f"https://truthsocial.com/@{AUTHOR}/posts/{pid}"
    # Last-resort synthetic — include timestamp so it stays unique
    return f"https://truthsocial.com/@{AUTHOR}/post/{int(time.time()*1000)}"


def fetch_truth_social_posts(timeout_seconds: int = 15, max_posts: int = 100) -> List[dict]:
    """Fetch recent Trump posts from CNN mirror and return News-ready dicts.

    The CNN mirror returns the full archive (~25k posts). We cap to the `max_posts`
    most recent entries per run — the UNIQUE constraint on (title, source) still
    dedups across runs.
    """
    try:
        resp = requests.get(CNN_TRUTH_ARCHIVE_URL, timeout=timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Truth Social mirror fetch failed: %s", e)
        return []

    if not isinstance(data, list):
        logger.warning("Truth Social mirror returned unexpected shape: %s", type(data).__name__)
        return []

    # Sort by created_at DESC so "most recent" is first
    def _key(p: dict) -> str:
        return str(p.get("created_at") or "")
    data = sorted((p for p in data if isinstance(p, dict)), key=_key, reverse=True)

    rows: List[dict] = []
    for post in data[: max_posts * 2]:  # oversample a bit in case some are empty
        text = _strip_html(post.get("content") or "")
        if not text:
            continue
        snippet = text[:80] + ("..." if len(text) > 80 else "")
        link = _post_link(post)
        published = post.get("created_at") or utc_iso(datetime.now(timezone.utc))
        rows.append({
            "title": f"@{AUTHOR} (Truth Social): {snippet}",
            "link": link,
            "source": SOURCE_NAME,
            "published": published,
            "summary": text,
            "sentiment_score": 0.0,
            "sentiment_label": "neutral",
        })
        if len(rows) >= max_posts:
            break
    logger.info("Truth Social fetch: %d posts (capped at %d)", len(rows), max_posts)
    return rows
