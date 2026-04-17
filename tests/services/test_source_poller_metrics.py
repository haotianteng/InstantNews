"""Unit tests for EMF metric emission in :mod:`app.services.source_poller` (US-003).

These tests do NOT hit the database or network.  They patch
``_store_items`` and ``spec.fetch`` so ``_run_once`` is exercised purely
in-process, and they capture stdout to assert exactly one EMF JSON line
per tick (or one error-counter line on fetch failure).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.services import source_poller


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_emf_lines(captured: str) -> list[dict[str, Any]]:
    """Parse every non-blank line of captured stdout as JSON."""
    return [
        json.loads(ln) for ln in captured.splitlines() if ln.strip()
    ]


def _make_spec(
    fetch_result: list[dict] | Exception,
    name: str = "SeekingAlpha",
    label: str = "rss",
) -> source_poller.SourceSpec:
    """Build a SourceSpec whose ``fetch()`` returns (or raises) the given value."""
    def _fetch() -> list[dict]:
        if isinstance(fetch_result, Exception):
            raise fetch_result
        return fetch_result
    return source_poller.SourceSpec(
        name=name,
        interval_seconds=30,
        fetch=_fetch,
        label=label,
    )


# ---------------------------------------------------------------------------
# Test 1 — happy path: 2 items, 2 new rows stored
# ---------------------------------------------------------------------------


def test_run_once_emits_newitems_latency_duration(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A successful tick with 2 new rows emits ONE multi-metric EMF line.

    Fixes ``datetime.now`` (inside source_poller) so fetched_at is
    deterministic, and mocks _store_items to claim it stored both.
    """
    # Published timestamps: 30s and 90s before the fixed "now".
    fixed_now = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
    pub_old = (fixed_now - timedelta(seconds=90)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )
    pub_new = (fixed_now - timedelta(seconds=30)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )
    items = [
        {"title": "a", "link": "u1", "source": "SeekingAlpha",
         "published": pub_old, "summary": "s", "sentiment_score": 0.0,
         "sentiment_label": "neutral"},
        {"title": "b", "link": "u2", "source": "SeekingAlpha",
         "published": pub_new, "summary": "s", "sentiment_score": 0.0,
         "sentiment_label": "neutral"},
    ]

    # Pin the "now" used inside _run_once via the datetime in source_poller's
    # module namespace (imported at top-level from datetime).
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(source_poller, "datetime", _FrozenDatetime)
    # Replace _store_items with a stub that returns (2, [101, 102]).
    monkeypatch.setattr(
        source_poller,
        "_store_items",
        lambda sf, its, now: (2, [101, 102]),
    )
    # enqueue_for_analysis would hit the AI queue — stub it out.
    monkeypatch.setattr(
        source_poller,
        "enqueue_for_analysis",
        lambda ids: None,
    )

    spec = _make_spec(items, name="SeekingAlpha", label="rss")
    lock = threading.Lock()
    sink: dict = {}
    source_poller._run_once(spec, session_factory=None,
                            results_sink=sink, results_lock=lock)

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    assert len(lines) == 1, f"expected exactly 1 EMF line, got {len(lines)}: {lines!r}"
    line = lines[0]

    # Directive shape
    directive = line["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "InstantNews/Ingestion"
    metric_names = {m["Name"] for m in directive["Metrics"]}
    assert metric_names == {"NewItems", "FetchDurationMs", "IngestLatencySeconds"}

    # Dimensions
    assert set(directive["Dimensions"][0]) == {"Source", "SourceType"}
    assert line["Source"] == "SeekingAlpha"
    assert line["SourceType"] == "rss"

    # Values
    assert line["NewItems"] == 2
    assert line["FetchDurationMs"] >= 0
    # Latencies are 90s and 30s → median = 60s.
    assert line["IngestLatencySeconds"] == pytest.approx(60.0, abs=1.5)

    # Sink updated with the new-row count
    assert sink["SeekingAlpha"] == 2


# ---------------------------------------------------------------------------
# Test 2 — fetch exception emits FetchErrors
# ---------------------------------------------------------------------------


def test_run_once_emits_fetch_errors_on_exception(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Exception from spec.fetch emits exactly one FetchErrors=1 EMF line."""
    # Stubs for _store_items / enqueue_for_analysis — should NOT be called,
    # but patch defensively so we don't accidentally hit prod code paths.
    monkeypatch.setattr(source_poller, "_store_items",
                        lambda *a, **k: pytest.fail("_store_items should not be called"))
    monkeypatch.setattr(source_poller, "enqueue_for_analysis",
                        lambda ids: pytest.fail("enqueue_for_analysis should not be called"))

    spec = _make_spec(RuntimeError("nope"), name="SeekingAlpha", label="rss")
    lock = threading.Lock()
    source_poller._run_once(spec, session_factory=None,
                            results_sink={}, results_lock=lock)

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    assert len(lines) == 1, f"expected 1 error-counter line, got {len(lines)}: {lines!r}"
    line = lines[0]

    directive = line["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "InstantNews/Ingestion"
    assert directive["Metrics"] == [{"Name": "FetchErrors", "Unit": "Count"}]
    assert set(directive["Dimensions"][0]) == {"Source", "SourceType", "ErrorType"}
    assert line["FetchErrors"] == 1
    assert line["Source"] == "SeekingAlpha"
    assert line["SourceType"] == "rss"
    assert line["ErrorType"] == "RuntimeError"


# ---------------------------------------------------------------------------
# Test 3 — zero-item successful tick: emit NewItems=0 + FetchDurationMs, no latency
# ---------------------------------------------------------------------------


def test_run_once_emits_zero_items_without_latency(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Successful tick with no items: NewItems=0, FetchDurationMs, no IngestLatencySeconds."""
    monkeypatch.setattr(source_poller, "_store_items",
                        lambda *a, **k: pytest.fail("_store_items should not be called on empty fetch"))
    monkeypatch.setattr(source_poller, "enqueue_for_analysis", lambda ids: None)

    spec = _make_spec([], name="EDGAR", label="rss")
    source_poller._run_once(spec, session_factory=None,
                            results_sink={}, results_lock=threading.Lock())

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    assert len(lines) == 1
    line = lines[0]
    metric_names = {m["Name"] for m in line["_aws"]["CloudWatchMetrics"][0]["Metrics"]}
    assert metric_names == {"NewItems", "FetchDurationMs"}
    assert line["NewItems"] == 0
    assert line["Source"] == "EDGAR"
    assert line["SourceType"] == "rss"
