"""Unit tests for :mod:`app.services.metrics` (US-001).

These tests do NOT import boto3; they capture stdout produced by the
module and parse each line as JSON to assert EMF conformance.
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from app.services.metrics import emit_metric, emit_metrics, timed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_single_line(captured: str) -> dict[str, Any]:
    """Strip trailing newlines and parse exactly one JSON object."""
    lines = [ln for ln in captured.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one JSON line, got {len(lines)}: {lines!r}"
    return json.loads(lines[0])


# ---------------------------------------------------------------------------
# Test 1 — emit_metric basic shape
# ---------------------------------------------------------------------------


def test_emit_metric_basic_shape(capfd: pytest.CaptureFixture[str]) -> None:
    """emit_metric writes a single EMF JSON line with all required members."""
    before = int(time.time() * 1000)
    emit_metric(
        "NS",
        "M1",
        1.5,
        "Seconds",
        {"A": "b"},
        foo="bar",
    )
    after = int(time.time() * 1000)

    out, _err = capfd.readouterr()
    d = _parse_single_line(out)

    # Root structure
    assert "_aws" in d
    aws = d["_aws"]
    assert isinstance(aws["Timestamp"], int)
    assert before - 1 <= aws["Timestamp"] <= after + 1

    # MetricDirective
    assert len(aws["CloudWatchMetrics"]) == 1
    directive = aws["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "NS"
    assert directive["Dimensions"] == [["A"]]
    assert directive["Metrics"] == [{"Name": "M1", "Unit": "Seconds"}]

    # Root-level target members
    assert d["A"] == "b"          # dimension value
    assert d["M1"] == 1.5         # metric value
    assert d["foo"] == "bar"      # extra field


# ---------------------------------------------------------------------------
# Test 2 — emit_metrics multi-metric variant
# ---------------------------------------------------------------------------


def test_emit_metrics_multi(capfd: pytest.CaptureFixture[str]) -> None:
    """emit_metrics puts all metric names in Metrics[] and all values at root."""
    emit_metrics(
        "NS",
        [
            {"name": "A", "value": 1, "unit": "Count"},
            {"name": "B", "value": 2.5, "unit": "Seconds"},
        ],
        {"K": "v"},
    )
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)

    directive = d["_aws"]["CloudWatchMetrics"][0]
    metric_names = [m["Name"] for m in directive["Metrics"]]
    assert set(metric_names) == {"A", "B"}
    # Units preserved
    units = {m["Name"]: m["Unit"] for m in directive["Metrics"]}
    assert units == {"A": "Count", "B": "Seconds"}

    # Values at top level
    assert d["A"] == 1
    assert d["B"] == 2.5
    # Dimension value at top level
    assert d["K"] == "v"


def test_emit_metrics_rejects_empty() -> None:
    """emit_metrics() with no metrics raises — CloudWatch requires >= 1."""
    with pytest.raises(ValueError):
        emit_metrics("NS", [], {"K": "v"})


# ---------------------------------------------------------------------------
# Test 3 — timed context manager
# ---------------------------------------------------------------------------


def test_timed_emits_elapsed_ms(capfd: pytest.CaptureFixture[str]) -> None:
    """timed() measures wall-time and emits a Milliseconds metric >= sleep."""
    with timed("NS", "Dur", {"K": "v"}):
        time.sleep(0.05)
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)

    # The sleep is 50ms; allow a small tolerance for sleep-precision
    # on busy CI runners (time.sleep guarantees *at least* the duration
    # but very light under-shoot has been observed on some platforms).
    assert d["Dur"] >= 45, f"expected Dur >= 45ms, got {d['Dur']}"
    # It definitely should not blow up to seconds territory.
    assert d["Dur"] < 5000, f"Dur suspiciously large: {d['Dur']}"

    directive = d["_aws"]["CloudWatchMetrics"][0]
    assert directive["Metrics"] == [{"Name": "Dur", "Unit": "Milliseconds"}]
    assert d["K"] == "v"


def test_timed_emits_even_on_exception(capfd: pytest.CaptureFixture[str]) -> None:
    """timed() still emits when the block raises; the exception propagates."""
    with pytest.raises(RuntimeError, match="boom"):
        with timed("NS", "Dur"):
            raise RuntimeError("boom")
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)
    assert "Dur" in d
    assert d["Dur"] >= 0


def test_timed_seconds_unit_converts(capfd: pytest.CaptureFixture[str]) -> None:
    """unit='Seconds' emits the duration in seconds (i.e. ms / 1000)."""
    with timed("NS", "DurSec", unit="Seconds"):
        time.sleep(0.05)
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)
    # 50ms == 0.05s; allow tolerance both sides
    assert 0.04 <= d["DurSec"] < 5.0, f"unexpected DurSec: {d['DurSec']}"
    directive = d["_aws"]["CloudWatchMetrics"][0]
    assert directive["Metrics"] == [{"Name": "DurSec", "Unit": "Seconds"}]


# ---------------------------------------------------------------------------
# Test 4 — empty dimensions
# ---------------------------------------------------------------------------


def test_emit_metric_without_dimensions(capfd: pytest.CaptureFixture[str]) -> None:
    """dimensions=None emits Dimensions=[[]] — valid per EMF spec."""
    emit_metric("NS", "M", 1.0)
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)
    assert d["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [[]]
    # No dimension keys at root
    assert d["M"] == 1.0


def test_emit_metric_with_empty_dict_dimensions(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """dimensions={} is equivalent to dimensions=None."""
    emit_metric("NS", "M", 1.0, dimensions={})
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)
    assert d["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [[]]


# ---------------------------------------------------------------------------
# Test 5 — non-string dimension values are coerced
# ---------------------------------------------------------------------------


def test_dimension_values_coerced_to_string(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Ints/floats/bools in dimensions are stringified before emission."""
    emit_metric(
        "NS",
        "M",
        1.0,
        dimensions={"Ticker": "AAPL", "Count": 5, "Flag": True, "Ratio": 1.5},
    )
    out, _err = capfd.readouterr()
    d = _parse_single_line(out)

    # All dimension values at root are strings
    assert d["Ticker"] == "AAPL"
    assert d["Count"] == "5"
    assert d["Flag"] == "True"
    assert d["Ratio"] == "1.5"

    # And the DimensionSet contains all four keys
    dim_set = d["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]
    assert set(dim_set) == {"Ticker", "Count", "Flag", "Ratio"}


# ---------------------------------------------------------------------------
# Bonus — sanity-check: JSON is single-line / compact
# ---------------------------------------------------------------------------


def test_output_is_single_compact_line(capfd: pytest.CaptureFixture[str]) -> None:
    """Serialized EMF must be one line (no embedded newlines) and compact."""
    emit_metric("NS", "M", 1.0, dimensions={"A": "b"}, note="x y z")
    out, _err = capfd.readouterr()
    # Exactly one newline at the end (from print); no newlines inside.
    assert out.count("\n") == 1
    # Compact separators — no ", " or ": ".
    line = out.rstrip("\n")
    assert ", " not in line
    assert ": " not in line
