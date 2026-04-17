"""Admin metrics blueprint.

Exposes two endpoints used by the admin monitoring dashboard:

- POST /admin/api/metrics/cloudwatch — proxy for CloudWatch GetMetricData so the
  frontend can request multi-metric time-series in a single call without holding
  IAM credentials.
- GET  /admin/api/metrics/cost       — authoritative spend figures (AWS Cost
  Explorer daily totals + X API monthly usage). Cost Explorer calls cost
  $0.01 per request so responses are cached aggressively.

Both endpoints reuse the existing ``require_admin`` decorator from
``app.admin.auth`` and depend on the IAM policy added in US-002
(``cloudwatch:GetMetricData``, ``cloudwatch:ListMetrics``, ``ce:GetCostAndUsage``,
``ce:GetDimensionValues``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3  # type: ignore[import-untyped]
import requests  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from flask import Blueprint, jsonify, request

from app.admin.auth import require_admin

logger = logging.getLogger("signal.admin.metrics")

metrics_bp = Blueprint("admin_metrics", __name__, url_prefix="/admin/api/metrics")


# ── Range resolution ────────────────────────────────────────────────

_VALID_RANGES = ("1h", "24h", "7d")


def _resolve_range(range_key: str) -> Tuple[datetime, datetime, int]:
    """Return (start, end, period_seconds) for one of the allowed range keys."""
    end = datetime.now(timezone.utc)
    if range_key == "1h":
        return end - timedelta(hours=1), end, 60
    if range_key == "24h":
        return end - timedelta(hours=24), end, 60
    if range_key == "7d":
        return end - timedelta(days=7), end, 3600
    raise ValueError(f"invalid range: {range_key!r}")


# ── In-memory TTL cache ─────────────────────────────────────────────

class _TTLCache:
    """Thread-safe in-memory TTL cache.

    Values are stored as ``(value, expires_at_monotonic)``. Expired entries
    are purged lazily on get and opportunistically on set.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            self._data[key] = (value, expires_at)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cloudwatch_cache = _TTLCache()
_cost_cache = _TTLCache()
_x_usage_cache = _TTLCache()

_CLOUDWATCH_CACHE_TTL_SECONDS = 60.0
_COST_CACHE_TTL_SECONDS = 3600.0
_X_USAGE_CACHE_TTL_SECONDS = 300.0

# Batch cap from AWS: GetMetricData accepts up to 500 MetricDataQueries per call.
_MAX_QUERIES_PER_CALL = 500

# Dollars per tweet post billed on Basic tier ($0.005). Used only when the X
# /2/usage/tweets endpoint is unavailable and we fall back to summing the
# ``InstantNews/Twitter.TweetsBilled`` metric ourselves.
_X_POST_COST_DOLLARS = 0.005


# ── boto3 client factories (override in tests) ──────────────────────

def _cloudwatch_client() -> Any:
    return boto3.client("cloudwatch")


def _ce_client() -> Any:
    return boto3.client("ce")


# ── US-006: POST /admin/api/metrics/cloudwatch ──────────────────────

@metrics_bp.route("/cloudwatch", methods=["POST"])
@require_admin
def cloudwatch_metrics():
    """Proxy cloudwatch:GetMetricData for the admin dashboard.

    Request body::

        {
          "range": "1h" | "24h" | "7d",
          "queries": [
            {"id": "q1", "namespace": "InstantNews/Ingestion",
             "metric": "NewItems", "dimensions": {"Source": "SeekingAlpha"},
             "stat": "Sum"}
          ]
        }

    Response::

        {"series": {"q1": {"timestamps": [int, ...], "values": [float, ...]}}}
    """
    body = request.get_json(silent=True) or {}
    range_key = body.get("range")
    queries = body.get("queries")

    if range_key not in _VALID_RANGES:
        return jsonify({
            "error": "invalid range",
            "allowed": list(_VALID_RANGES),
        }), 400

    if not isinstance(queries, list) or len(queries) == 0:
        return jsonify({"error": "queries must be a non-empty list"}), 400

    if len(queries) > _MAX_QUERIES_PER_CALL:
        return jsonify({
            "error": f"queries exceeds batch cap ({_MAX_QUERIES_PER_CALL})",
        }), 400

    for i, q in enumerate(queries):
        if not isinstance(q, dict):
            return jsonify({"error": f"queries[{i}] is not an object"}), 400
        for required in ("id", "namespace", "metric", "stat"):
            if not q.get(required):
                return jsonify({
                    "error": f"queries[{i}] missing required field '{required}'",
                }), 400

    # Cache key: stable hash of the canonical payload.
    cache_key = hashlib.sha256(
        json.dumps({"range": range_key, "queries": queries},
                   sort_keys=True).encode("utf-8")
    ).hexdigest()

    cached = _cloudwatch_cache.get(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        resp.headers["X-Cache"] = "HIT"
        return resp, 200

    start, end, period = _resolve_range(range_key)

    metric_data_queries: List[Dict[str, Any]] = []
    for q in queries:
        dims_raw = q.get("dimensions") or {}
        dims = [
            {"Name": k, "Value": str(v)}
            for k, v in dims_raw.items()
        ]
        metric_data_queries.append({
            "Id": q["id"],
            "MetricStat": {
                "Metric": {
                    "Namespace": q["namespace"],
                    "MetricName": q["metric"],
                    "Dimensions": dims,
                },
                "Period": period,
                "Stat": q["stat"],
            },
            "ReturnData": True,
        })

    try:
        client = _cloudwatch_client()
        cw_resp = client.get_metric_data(
            MetricDataQueries=metric_data_queries,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampAscending",
        )
    except ClientError as e:
        logger.warning("cloudwatch get_metric_data failed", extra={
            "event": "admin_metrics_cloudwatch_error",
            "error": str(e),
        })
        return jsonify({"error": "cloudwatch call failed", "detail": str(e)}), 502

    series: Dict[str, Dict[str, List[Any]]] = {}
    for result in cw_resp.get("MetricDataResults", []) or []:
        rid = result.get("Id")
        if not rid:
            continue
        ts = [
            int(t.timestamp()) if hasattr(t, "timestamp") else int(t)
            for t in (result.get("Timestamps") or [])
        ]
        values = list(result.get("Values") or [])
        series[rid] = {"timestamps": ts, "values": values}

    # Fill empty series for queries CloudWatch didn't echo back (defensive).
    for q in queries:
        series.setdefault(q["id"], {"timestamps": [], "values": []})

    payload = {"series": series}
    _cloudwatch_cache.set(cache_key, payload, _CLOUDWATCH_CACHE_TTL_SECONDS)

    resp = jsonify(payload)
    resp.headers["X-Cache"] = "MISS"
    return resp, 200


# ── US-007: GET /admin/api/metrics/cost ─────────────────────────────

def _cost_range(range_key: str) -> Tuple[str, str]:
    """Resolve a range key to Cost Explorer (Start, End) dates.

    CE's DAILY granularity excludes ``End``; for a "last 7 days" view we ask
    for ``[today-7, today]`` which yields 7 buckets ending yesterday.
    """
    today = datetime.now(timezone.utc).date()
    if range_key == "7d":
        start = today - timedelta(days=7)
    elif range_key == "24h":
        start = today - timedelta(days=1)
    elif range_key == "30d":
        start = today - timedelta(days=30)
    else:
        start = today - timedelta(days=7)
    return start.isoformat(), today.isoformat()


def _fetch_aws_cost(range_key: str) -> Dict[str, Any]:
    """Run two Cost Explorer queries (daily totals + by-service) and shape the
    payload the dashboard expects."""
    start_date, end_date = _cost_range(range_key)
    ce = _ce_client()

    # 1. Daily totals — no grouping, one number per day.
    totals_resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_date},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
    )
    daily_totals: List[Dict[str, Any]] = []
    for bucket in totals_resp.get("ResultsByTime", []) or []:
        date = ((bucket.get("TimePeriod") or {}).get("Start")) or ""
        amount_raw = (
            (bucket.get("Total") or {}).get("UnblendedCost") or {}
        ).get("Amount", "0")
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = 0.0
        daily_totals.append({"date": date, "cost": amount})

    # 2. By-service — DAILY grouped by SERVICE, then sum across days per service.
    services_resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_date},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    service_totals: Dict[str, float] = {}
    for bucket in services_resp.get("ResultsByTime", []) or []:
        for grp in bucket.get("Groups", []) or []:
            keys = grp.get("Keys") or []
            name = keys[0] if keys else "Unknown"
            amount_raw = (
                (grp.get("Metrics") or {}).get("UnblendedCost") or {}
            ).get("Amount", "0")
            try:
                amount = float(amount_raw)
            except (TypeError, ValueError):
                amount = 0.0
            service_totals[name] = service_totals.get(name, 0.0) + amount

    by_service = [
        {"service": name, "cost": round(cost, 6)}
        for name, cost in sorted(
            service_totals.items(), key=lambda kv: kv[1], reverse=True
        )
    ]

    return {"by_service": by_service, "daily_totals": daily_totals}


def _month_window_utc() -> Tuple[datetime, datetime, datetime]:
    """Return (month_start, now, next_month_start) in UTC."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    _days_in_month = monthrange(now.year, now.month)[1]  # noqa: F841 (debug aid)
    if now.month == 12:
        next_month_start = month_start.replace(year=now.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=now.month + 1)
    return month_start, now, next_month_start


def _fetch_x_api_usage(
    bearer_token: str,
    http_get: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Try the official /2/usage/tweets endpoint.

    If it returns 200 with ``project_cap`` + ``project_usage`` + ``cap_reset_day``,
    we return those fields directly. If the endpoint is unavailable on our tier
    (404) or the token can't access it (403), we raise ``_XUsageUnavailable``
    so the caller can fall back to the CloudWatch-derived estimate.
    """
    session_get = http_get or requests.get
    headers = {"Authorization": f"Bearer {bearer_token}"}
    url = "https://api.x.com/2/usage/tweets"

    resp = session_get(url, headers=headers, timeout=10)
    status = getattr(resp, "status_code", 0)

    if status == 200:
        data = resp.json() or {}
        inner = data.get("data") or data  # some docs wrap under "data"
        quota = inner.get("project_cap")
        used = inner.get("project_usage")
        reset_day = inner.get("cap_reset_day")

        month_start, now, next_month_start = _month_window_utc()
        if reset_day is not None:
            try:
                day = int(reset_day)
                reset_at = next_month_start.replace(
                    day=min(day, monthrange(
                        next_month_start.year, next_month_start.month,
                    )[1])
                )
            except (TypeError, ValueError):
                reset_at = next_month_start
        else:
            reset_at = next_month_start

        try:
            used_int = int(used) if used is not None else 0
        except (TypeError, ValueError):
            used_int = 0
        try:
            quota_int = int(quota) if quota is not None else 0
        except (TypeError, ValueError):
            quota_int = 0

        return {
            "used_this_month": used_int,
            "quota": quota_int,
            "reset_at": reset_at.replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
        }

    if status in (401, 403, 404):
        raise _XUsageUnavailable(f"x usage endpoint status={status}")

    raise _XUsageUnavailable(f"x usage endpoint unexpected status={status}")


class _XUsageUnavailable(RuntimeError):
    """Raised when /2/usage/tweets is unavailable so callers can fall back."""


def _estimate_x_api_usage_from_cloudwatch() -> Dict[str, Any]:
    """Sum ``InstantNews/Twitter.TweetsBilled`` for the current calendar month
    and return an ``estimated=true`` payload."""
    month_start, now, _ = _month_window_utc()
    client = _cloudwatch_client()

    stats = client.get_metric_statistics(
        Namespace="InstantNews/Twitter",
        MetricName="TweetsBilled",
        Dimensions=[{"Name": "Endpoint", "Value": "search_recent"}],
        StartTime=month_start,
        EndTime=now,
        Period=86400,
        Statistics=["Sum"],
    )
    total = 0
    for dp in stats.get("Datapoints", []) or []:
        try:
            total += int(dp.get("Sum", 0) or 0)
        except (TypeError, ValueError):
            continue

    return {
        "estimated": True,
        "used_this_month": total,
        "estimated_cost_usd": round(total * _X_POST_COST_DOLLARS, 4),
    }


@metrics_bp.route("/cost", methods=["GET"])
@require_admin
def cost_metrics():
    """Return AWS Cost Explorer totals + X API monthly usage.

    Query string::

        ?range=7d   (default)

    Response::

        {
          "aws": {
            "by_service": [{"service": "...", "cost": 12.34}, ...],
            "daily_totals": [{"date": "2026-04-10", "cost": 3.45}, ...]
          },
          "x_api": {"used_this_month": ..., "quota": ..., "reset_at": ...}
                   OR {"estimated": true, "used_this_month": ...}
        }
    """
    range_key = request.args.get("range", "7d")
    if range_key not in ("24h", "7d", "30d"):
        return jsonify({
            "error": "invalid range",
            "allowed": ["24h", "7d", "30d"],
        }), 400

    cache_key = f"cost:{range_key}"
    cached = _cost_cache.get(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        resp.headers["X-Cache"] = "HIT"
        return resp, 200

    # AWS Cost Explorer
    try:
        aws_payload = _fetch_aws_cost(range_key)
    except ClientError as e:
        logger.warning("cost explorer call failed", extra={
            "event": "admin_metrics_cost_error",
            "error": str(e),
        })
        return jsonify({"error": "cost explorer call failed",
                        "detail": str(e)}), 502

    # X API usage (separate 5-min cache so CE cache doesn't drag a stale
    # monthly-usage figure forward for a full hour).
    x_cache_key = "x_usage"
    x_cached = _x_usage_cache.get(x_cache_key)
    if x_cached is not None:
        x_api_payload = x_cached
    else:
        bearer = os.environ.get("X_API_BEARER_TOKEN", "") or ""
        if not bearer:
            # Fall back to the CloudWatch estimate; we still have a valid answer.
            try:
                x_api_payload = _estimate_x_api_usage_from_cloudwatch()
            except ClientError:
                x_api_payload = {"estimated": True, "used_this_month": 0,
                                 "estimated_cost_usd": 0.0}
        else:
            try:
                x_api_payload = _fetch_x_api_usage(bearer)
            except _XUsageUnavailable:
                try:
                    x_api_payload = _estimate_x_api_usage_from_cloudwatch()
                except ClientError:
                    x_api_payload = {"estimated": True, "used_this_month": 0,
                                     "estimated_cost_usd": 0.0}
            except requests.RequestException as e:
                logger.warning("x api usage request failed", extra={
                    "event": "admin_metrics_x_usage_error",
                    "error": str(e),
                })
                try:
                    x_api_payload = _estimate_x_api_usage_from_cloudwatch()
                except ClientError:
                    x_api_payload = {"estimated": True, "used_this_month": 0,
                                     "estimated_cost_usd": 0.0}
        _x_usage_cache.set(x_cache_key, x_api_payload,
                           _X_USAGE_CACHE_TTL_SECONDS)

    payload = {"aws": aws_payload, "x_api": x_api_payload}
    _cost_cache.set(cache_key, payload, _COST_CACHE_TTL_SECONDS)

    resp = jsonify(payload)
    resp.headers["X-Cache"] = "MISS"
    return resp, 200
