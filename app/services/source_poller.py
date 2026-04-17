"""Per-source poller threads — one independent loop per feed/social source.

Each poller owns its own fetch interval so slow sources can't starve fast ones.
New rows are written directly to the News table (via existing `_store_items`),
and their IDs are pushed onto the AI queue for asynchronous labeling.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from app.services.feed_parser import fetch_feed, utc_iso
from app.services.feed_refresh import _store_items
from app.services.ai_pipeline import enqueue_for_analysis
from app.services.metrics import emit_metric, emit_metrics

logger = logging.getLogger("signal.poller")

_INGESTION_NAMESPACE = "InstantNews/Ingestion"


@dataclass
class SourceSpec:
    """Declarative description of a source the worker should poll."""
    name: str
    interval_seconds: int
    fetch: Callable[[], List[dict]]  # returns News-ready dicts
    label: str = ""  # freeform tag for logging


def _parse_iso_utc(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (UTC) produced by feed_parser.utc_iso.

    Accepts the canonical ``...+00:00`` form and also a trailing ``Z`` form
    that some sources emit.  Returns ``None`` on any parse failure so the
    caller can skip the row without blowing up the ingestion tick.
    """
    if not ts:
        return None
    candidate = ts.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except (ValueError, TypeError):
        return None


def _median_ingest_latency_seconds(items: List[dict], fetched_at_iso: str) -> Optional[float]:
    """Return the median (fetched_at - published) latency in seconds.

    We compute this over *all* items handed to ``_store_items`` on the
    assumption that the returned ``count`` reflects new-only rows and that
    item order is stable enough for a median to be representative.  If a
    row's timestamps can't be parsed we skip it rather than error.  Returns
    ``None`` if no parseable rows remain.
    """
    fetched_dt = _parse_iso_utc(fetched_at_iso)
    if fetched_dt is None:
        return None
    latencies: List[float] = []
    for item in items:
        pub_dt = _parse_iso_utc(str(item.get("published") or ""))
        if pub_dt is None:
            continue
        # Both are TZ-aware UTC after _parse_iso_utc.
        delta = (fetched_dt - pub_dt).total_seconds()
        # Clamp to 0 so a slightly future-dated item (clock skew) doesn't
        # pull the median negative.
        latencies.append(max(0.0, delta))
    if not latencies:
        return None
    return float(statistics.median(latencies))


def _run_once(spec: SourceSpec, session_factory, results_sink: dict,
              results_lock: threading.Lock) -> None:
    dims = {"Source": spec.name, "SourceType": spec.label}
    fetch_start = time.monotonic()
    try:
        items = spec.fetch()
    except Exception as exc:
        logger.exception("[%s] fetch failed", spec.name)
        emit_metric(
            namespace=_INGESTION_NAMESPACE,
            metric_name="FetchErrors",
            value=1,
            unit="Count",
            dimensions={**dims, "ErrorType": exc.__class__.__name__},
        )
        return
    fetch_duration_ms = (time.monotonic() - fetch_start) * 1000.0

    now_utc = utc_iso(datetime.now(timezone.utc))
    if not items:
        # Successful tick with zero rows — still emit so the dashboard can
        # distinguish "source is alive but quiet" from "source is dead".
        emit_metrics(
            namespace=_INGESTION_NAMESPACE,
            metrics=[
                {"name": "NewItems", "value": 0, "unit": "Count"},
                {"name": "FetchDurationMs", "value": fetch_duration_ms, "unit": "Milliseconds"},
            ],
            dimensions=dims,
        )
        return

    count, new_ids = _store_items(session_factory, items, now_utc)
    with results_lock:
        results_sink[spec.name] = results_sink.get(spec.name, 0) + count
    if new_ids:
        enqueue_for_analysis(new_ids)
    if count:
        logger.info("[%s] stored %d new items (fetched %d)", spec.name, count, len(items))

    metric_payload: List[dict] = [
        {"name": "NewItems", "value": count, "unit": "Count"},
        {"name": "FetchDurationMs", "value": fetch_duration_ms, "unit": "Milliseconds"},
    ]
    if count > 0:
        # Only emit latency when there ARE new rows — latency-of-nothing is
        # undefined and a zero would pollute the p50/p95 aggregations.
        median_latency = _median_ingest_latency_seconds(items, now_utc)
        if median_latency is not None:
            metric_payload.append({
                "name": "IngestLatencySeconds",
                "value": median_latency,
                "unit": "Seconds",
            })
    emit_metrics(
        namespace=_INGESTION_NAMESPACE,
        metrics=metric_payload,
        dimensions=dims,
    )


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
