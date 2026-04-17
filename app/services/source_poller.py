"""Per-source poller threads — one independent loop per feed/social source.

Each poller owns its own fetch interval so slow sources can't starve fast ones.
New rows are written directly to the News table (via existing `_store_items`),
and their IDs are pushed onto the AI queue for asynchronous labeling.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from app.services.feed_parser import fetch_feed, utc_iso
from app.services.feed_refresh import _store_items
from app.services.ai_pipeline import enqueue_for_analysis

logger = logging.getLogger("signal.poller")


@dataclass
class SourceSpec:
    """Declarative description of a source the worker should poll."""
    name: str
    interval_seconds: int
    fetch: Callable[[], List[dict]]  # returns News-ready dicts
    label: str = ""  # freeform tag for logging


def _run_once(spec: SourceSpec, session_factory, results_sink: dict,
              results_lock: threading.Lock) -> None:
    try:
        items = spec.fetch()
    except Exception:
        logger.exception("[%s] fetch failed", spec.name)
        return
    if not items:
        return
    now_utc = utc_iso(datetime.now(timezone.utc))
    count, new_ids = _store_items(session_factory, items, now_utc)
    with results_lock:
        results_sink[spec.name] = results_sink.get(spec.name, 0) + count
    if new_ids:
        enqueue_for_analysis(new_ids)
    if count:
        logger.info("[%s] stored %d new items (fetched %d)", spec.name, count, len(items))


def start_source_thread(spec: SourceSpec, session_factory,
                        results_sink: dict, results_lock: threading.Lock,
                        stop_event: threading.Event) -> threading.Thread:
    """Start a daemon thread that polls a single source on its own interval."""

    def loop() -> None:
        logger.info("poller start name=%s interval=%ds", spec.name, spec.interval_seconds)
        # Stagger initial polls across sources by a small jitter so they
        # don't all fire together at startup.
        time.sleep(min(spec.interval_seconds, 3))
        while not stop_event.is_set():
            t0 = time.monotonic()
            _run_once(spec, session_factory, results_sink, results_lock)
            elapsed = time.monotonic() - t0
            remain = max(0.1, spec.interval_seconds - elapsed)
            stop_event.wait(remain)
        logger.info("poller stop name=%s", spec.name)

    t = threading.Thread(target=loop, name=f"poller-{spec.name}", daemon=True)
    t.start()
    return t


def build_rss_spec(source_name: str, url: str, config, interval_seconds: int) -> SourceSpec:
    def _fetch() -> List[dict]:
        return fetch_feed(source_name, url, config.USER_AGENT, config.FETCH_TIMEOUT) or []
    return SourceSpec(name=source_name, interval_seconds=interval_seconds, fetch=_fetch, label="rss")


def build_twitter_spec(config, interval_seconds: int) -> SourceSpec:
    from app.services.diplomatic_watchlist import twitter_handles
    from app.services.twitter_source import fetch_diplomatic_tweets

    handles = twitter_handles()
    bearer = getattr(config, "X_API_BEARER_TOKEN", "") or ""

    def _fetch() -> List[dict]:
        if not bearer or not handles:
            return []
        return fetch_diplomatic_tweets(bearer, handles,
                                       max_results=getattr(config, "TWITTER_MAX_RESULTS_PER_RUN", 100))
    return SourceSpec(name="Twitter", interval_seconds=interval_seconds, fetch=_fetch, label="social")


def build_truth_social_spec(config, interval_seconds: int) -> SourceSpec:
    from app.services.truth_social_source import fetch_truth_social_posts

    def _fetch() -> List[dict]:
        return fetch_truth_social_posts(
            timeout_seconds=max(config.FETCH_TIMEOUT * 3, 15),
            max_posts=100,
        )
    return SourceSpec(name="TruthSocial", interval_seconds=interval_seconds, fetch=_fetch, label="social")
