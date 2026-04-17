"""CloudWatch Embedded Metric Format (EMF) helper.

This module exposes three public helpers used across the codebase to emit
CloudWatch metrics *without* any SDK calls.  Each helper prints a single
JSON line to stdout that conforms to the EMF specification:

    https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html

CloudWatch Logs (via the ECS awslogs driver) auto-parses any stdout line
whose JSON root contains an ``_aws`` member and extracts the metrics
referenced in ``_aws.CloudWatchMetrics[*].Metrics``.  Nothing else is
required — no boto3, no PutMetricData, no sidecar.

Usage
-----

Single metric::

    from app.services.metrics import emit_metric

    emit_metric(
        "InstantNews/Ingestion",
        "NewItems",
        3,
        unit="Count",
        dimensions={"Source": "SeekingAlpha", "SourceType": "rss"},
        feed_url="https://...",  # extra top-level field (not a dimension)
    )

Multiple metrics in one log line (preferred — keeps log volume low)::

    from app.services.metrics import emit_metrics

    emit_metrics(
        "InstantNews/Ingestion",
        metrics=[
            {"name": "NewItems", "value": 3, "unit": "Count"},
            {"name": "IngestLatencySeconds", "value": 1.4, "unit": "Seconds"},
            {"name": "FetchDurationMs", "value": 812, "unit": "Milliseconds"},
        ],
        dimensions={"Source": "SeekingAlpha", "SourceType": "rss"},
    )

Wall-time measurement::

    from app.services.metrics import timed

    with timed(
        "InstantNews/AIPipeline",
        "BatchDurationMs",
        dimensions={"Backend": "claude"},
    ):
        run_batch()

Design notes
------------

* **stdlib-only.**  The module imports nothing outside the standard library
  so it can be called from any layer without pulling in heavy deps.
* **Dimensions are always stringified.**  CloudWatch requires string
  dimension values; ints/floats/bools are coerced via ``str()``.
* **Empty dimension set is allowed.**  Passing ``dimensions=None`` or
  ``{}`` emits ``"Dimensions": [[]]`` which the EMF spec permits
  (DimensionSet ``minItems: 0``).  The outer Dimensions array still has
  length ≥ 1 as required by the spec.
* **Timestamp is integer ms since epoch.**  We call ``time.time()`` at
  emit time, not at function-entry, so latency in the caller is not
  counted.
* **One print per emit.**  We use ``print(..., flush=True)`` so the line
  reaches the CloudWatch Logs agent even if the process crashes.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_ms() -> int:
    """Return the current Unix time in milliseconds (integer)."""
    return int(time.time() * 1000)


def _stringify_dimensions(
    dimensions: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Coerce all dimension values to strings.

    EMF requires dimension *values* to be strings (JSON strings at the
    root level).  Callers frequently pass ints or floats — silently cast
    so they don't blow up at ingestion time.
    """
    if not dimensions:
        return {}
    return {str(k): str(v) for k, v in dimensions.items()}


def _build_emf_payload(
    namespace: str,
    metrics: Sequence[Mapping[str, Any]],
    dimensions: Mapping[str, str],
    extra_fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble a single EMF-compliant dict ready for ``json.dumps``.

    Parameters
    ----------
    namespace:
        CloudWatch metric namespace (e.g. ``"InstantNews/Ingestion"``).
    metrics:
        Sequence of ``{"name": str, "value": float, "unit": str}``
        dicts.  Each becomes one MetricDefinition *and* one root-level
        target member (``root[name] = value``).
    dimensions:
        Already-stringified dimension map.  May be empty.
    extra_fields:
        Additional root-level members the caller wants attached (e.g.
        ``feed_url="https://..."``).  Merged last so they cannot clobber
        the spec-mandated members, but they *can* collide with metric
        names or dimension names — callers must avoid that.
    """
    # MetricDefinition[] — only Name and Unit belong here.
    metric_defs: list[dict[str, Any]] = []
    # Top-level target members for metric values.
    metric_values: dict[str, Any] = {}

    for m in metrics:
        name = m["name"]
        value = m["value"]
        unit = m.get("unit", "Count")
        metric_defs.append({"Name": name, "Unit": unit})
        metric_values[name] = value

    # DimensionSet: a single set containing all dimension keys.  Empty
    # set is valid per the EMF spec (DimensionSet minItems = 0) as long
    # as the outer Dimensions array has at least one entry.
    dimension_set: list[str] = list(dimensions.keys())

    payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": _now_ms(),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [dimension_set],
                    "Metrics": metric_defs,
                }
            ],
        },
    }

    # Root-level target members: dimension values + metric values +
    # caller-supplied extras.  Order of update matters only for
    # collisions; we document that callers must avoid them.
    payload.update(dimensions)
    payload.update(metric_values)
    for k, v in extra_fields.items():
        payload[k] = v

    return payload


def _emit(payload: Mapping[str, Any]) -> None:
    """Serialize ``payload`` as compact JSON and print one line to stdout."""
    line = json.dumps(payload, separators=(",", ":"), default=str)
    print(line, flush=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_metric(
    namespace: str,
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: Mapping[str, Any] | None = None,
    **extra_fields: Any,
) -> None:
    """Emit a single CloudWatch metric as one EMF JSON line to stdout.

    Parameters
    ----------
    namespace:
        CloudWatch namespace, e.g. ``"InstantNews/Ingestion"``.
    metric_name:
        Metric name, e.g. ``"NewItems"``.  Must match the key of the
        top-level target member in the emitted payload.
    value:
        Numeric metric value.  Ints are preserved; floats are preserved.
    unit:
        CloudWatch unit string (``"Count"``, ``"Seconds"``,
        ``"Milliseconds"``, etc.).  Defaults to ``"Count"``.
    dimensions:
        Optional mapping of dimension-name → dimension-value.  Values
        are coerced to strings.  Pass ``None`` or ``{}`` to emit without
        dimensions.
    **extra_fields:
        Any additional top-level fields to include in the log line
        (useful for structured search in CloudWatch Logs Insights; these
        are *not* surfaced as metrics or dimensions).
    """
    dims = _stringify_dimensions(dimensions)
    payload = _build_emf_payload(
        namespace=namespace,
        metrics=[{"name": metric_name, "value": value, "unit": unit}],
        dimensions=dims,
        extra_fields=extra_fields,
    )
    _emit(payload)


def emit_metrics(
    namespace: str,
    metrics: Sequence[Mapping[str, Any]],
    dimensions: Mapping[str, Any] | None = None,
    **extra_fields: Any,
) -> None:
    """Emit multiple CloudWatch metrics in a single EMF log line.

    Preferred over repeated :func:`emit_metric` calls when several
    metrics share the same dimensions and timestamp — one log line is
    cheaper than N and they share a single sampled timestamp.

    Parameters
    ----------
    namespace:
        CloudWatch namespace.
    metrics:
        A sequence of ``{"name": str, "value": float, "unit": str}``
        dicts.  ``unit`` defaults to ``"Count"`` if omitted.  Must
        contain at least one metric (CloudWatch rejects empty
        ``Metrics`` arrays).
    dimensions:
        Shared dimensions applied to every metric in this line.  Values
        are coerced to strings.
    **extra_fields:
        Additional top-level fields.
    """
    if not metrics:
        raise ValueError(
            "emit_metrics() requires at least one metric; got an empty sequence"
        )
    dims = _stringify_dimensions(dimensions)
    payload = _build_emf_payload(
        namespace=namespace,
        metrics=metrics,
        dimensions=dims,
        extra_fields=extra_fields,
    )
    _emit(payload)


@contextmanager
def timed(
    namespace: str,
    metric_name: str,
    dimensions: Mapping[str, Any] | None = None,
    unit: str = "Milliseconds",
    **extra_fields: Any,
) -> Iterator[None]:
    """Measure wall-clock duration of the ``with`` block and emit on exit.

    The metric is emitted **even if the block raises** so we can still
    see latency for failing operations.  The exception is re-raised
    after emission.

    Parameters
    ----------
    namespace:
        CloudWatch namespace.
    metric_name:
        Metric name for the duration measurement.
    dimensions:
        Optional shared dimensions.
    unit:
        Unit of the emitted duration.  Defaults to ``"Milliseconds"``;
        if set to ``"Seconds"`` the measured duration is divided by
        1000 before emission.
    **extra_fields:
        Additional top-level fields.

    Examples
    --------
    >>> with timed("InstantNews/AIPipeline", "BatchDurationMs",
    ...            {"Backend": "claude"}):  # doctest: +SKIP
    ...     run_batch()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if unit == "Seconds":
            value: float = elapsed_ms / 1000.0
        elif unit == "Microseconds":
            value = elapsed_ms * 1000.0
        else:
            # Default: emit in milliseconds for Milliseconds and any
            # other unit the caller specified (CloudWatch is permissive).
            value = elapsed_ms
        emit_metric(
            namespace=namespace,
            metric_name=metric_name,
            value=value,
            unit=unit,
            dimensions=dimensions,
            **extra_fields,
        )


__all__ = ["emit_metric", "emit_metrics", "timed"]
