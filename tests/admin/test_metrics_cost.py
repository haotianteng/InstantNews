"""Tests for GET /admin/api/metrics/cost (US-007)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import User
from app.services.feed_parser import utc_iso
from tests.test_auth import MOCK_DECODED_TOKEN, VERIFY_PATCH


@pytest.fixture(autouse=True)
def _clear_metrics_cache():
    from app.admin import metrics as m
    m._cloudwatch_cache.clear()
    m._cost_cache.clear()
    m._x_usage_cache.clear()
    yield
    m._cloudwatch_cache.clear()
    m._cost_cache.clear()
    m._x_usage_cache.clear()


def _seed_admin_user(session_factory, uid: str = "firebase-test-uid-123",
                     email: str = "test@example.com") -> int:
    session = session_factory()
    try:
        now = utc_iso(datetime.now(timezone.utc))
        user = User(
            firebase_uid=uid,
            email=email,
            display_name="Admin",
            tier="free",
            role="admin",
            auth_method="google",
            email_verified=True,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.commit()
        return user.id
    finally:
        session.close()


def _seed_regular_user(session_factory, uid: str = "firebase-test-uid-123",
                       email: str = "user@example.com") -> int:
    session = session_factory()
    try:
        now = utc_iso(datetime.now(timezone.utc))
        user = User(
            firebase_uid=uid,
            email=email,
            display_name="User",
            tier="free",
            role="user",
            auth_method="google",
            email_verified=True,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.commit()
        return user.id
    finally:
        session.close()


# ── Fake CE / CloudWatch clients ────────────────────────────────────


def _fake_ce_client(daily=None, by_service=None):
    daily = daily if daily is not None else {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-04-10", "End": "2026-04-11"},
                "Total": {"UnblendedCost": {"Amount": "3.45", "Unit": "USD"}},
            },
            {
                "TimePeriod": {"Start": "2026-04-11", "End": "2026-04-12"},
                "Total": {"UnblendedCost": {"Amount": "2.10", "Unit": "USD"}},
            },
        ]
    }
    by_service = by_service if by_service is not None else {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-04-10", "End": "2026-04-11"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                        "Metrics": {"UnblendedCost": {"Amount": "2.00"}},
                    },
                    {
                        "Keys": ["Amazon CloudWatch"],
                        "Metrics": {"UnblendedCost": {"Amount": "1.45"}},
                    },
                ],
            },
            {
                "TimePeriod": {"Start": "2026-04-11", "End": "2026-04-12"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                        "Metrics": {"UnblendedCost": {"Amount": "1.80"}},
                    },
                ],
            },
        ]
    }

    client = MagicMock()
    client.get_cost_and_usage.side_effect = [daily, by_service]
    return client


class _FakeXResp:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


# ── Tests ───────────────────────────────────────────────────────────


class TestCostEndpoint:
    def test_happy_path_with_x_api_200(self, client, session_factory):
        _seed_admin_user(session_factory)
        ce = _fake_ce_client()
        x_resp = _FakeXResp(200, {
            "data": {
                "project_cap": 10000,
                "project_usage": 4321,
                "cap_reset_day": 1,
            }
        })

        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._ce_client", return_value=ce), \
             patch("app.admin.metrics._fetch_x_api_usage",
                   return_value={
                       "used_this_month": 4321,
                       "quota": 10000,
                       "reset_at": "2026-05-01T00:00:00Z",
                   }), \
             patch.dict("os.environ", {"X_API_BEARER_TOKEN": "tok"}, clear=False):
            resp = client.get(
                "/admin/api/metrics/cost?range=7d",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()
        assert "aws" in data and "x_api" in data
        assert "by_service" in data["aws"]
        assert "daily_totals" in data["aws"]
        # Two CE buckets, two daily totals
        assert len(data["aws"]["daily_totals"]) == 2
        # Three (deduped) service entries
        services = {row["service"] for row in data["aws"]["by_service"]}
        assert "Amazon Elastic Compute Cloud - Compute" in services
        assert "Amazon CloudWatch" in services
        # EC2 cost summed across days: 2.00 + 1.80 = 3.80
        ec2 = next(r for r in data["aws"]["by_service"]
                   if r["service"] == "Amazon Elastic Compute Cloud - Compute")
        assert abs(ec2["cost"] - 3.80) < 1e-6
        # by_service is sorted desc by cost
        costs = [row["cost"] for row in data["aws"]["by_service"]]
        assert costs == sorted(costs, reverse=True)
        # X API proxy result
        assert data["x_api"]["used_this_month"] == 4321
        assert data["x_api"]["quota"] == 10000
        assert data["x_api"]["reset_at"] == "2026-05-01T00:00:00Z"
        assert resp.headers.get("X-Cache") == "MISS"

    def test_missing_auth_returns_401(self, client):
        resp = client.get("/admin/api/metrics/cost?range=7d")
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, client, session_factory):
        _seed_regular_user(session_factory)
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN):
            resp = client.get(
                "/admin/api/metrics/cost?range=7d",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403

    def test_x_usage_404_falls_back_to_cloudwatch_estimate(
        self, client, session_factory,
    ):
        _seed_admin_user(session_factory)
        ce = _fake_ce_client()

        # CloudWatch GetMetricStatistics mock — returns two daily datapoints
        # summing to 5500.
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": datetime(2026, 4, 1, tzinfo=timezone.utc),
                 "Sum": 2500.0, "Unit": "Count"},
                {"Timestamp": datetime(2026, 4, 10, tzinfo=timezone.utc),
                 "Sum": 3000.0, "Unit": "Count"},
            ]
        }

        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._ce_client", return_value=ce), \
             patch("app.admin.metrics._cloudwatch_client", return_value=cw), \
             patch("app.admin.metrics.requests.get",
                   return_value=_FakeXResp(404)), \
             patch.dict("os.environ", {"X_API_BEARER_TOKEN": "tok"}, clear=False):
            resp = client.get(
                "/admin/api/metrics/cost?range=7d",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()
        assert data["x_api"].get("estimated") is True
        assert data["x_api"]["used_this_month"] == 5500
        # Cost = 5500 * $0.005 = 27.5
        assert abs(data["x_api"]["estimated_cost_usd"] - 27.5) < 1e-6

    def test_cache_hit_returns_hit_header(self, client, session_factory):
        _seed_admin_user(session_factory)
        ce = _fake_ce_client()
        fake_x = {
            "used_this_month": 1,
            "quota": 10000,
            "reset_at": "2026-05-01T00:00:00Z",
        }
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._ce_client", return_value=ce), \
             patch("app.admin.metrics._fetch_x_api_usage",
                   return_value=fake_x), \
             patch.dict("os.environ", {"X_API_BEARER_TOKEN": "tok"}, clear=False):
            r1 = client.get("/admin/api/metrics/cost?range=7d",
                            headers={"Authorization": "Bearer token"})
            r2 = client.get("/admin/api/metrics/cost?range=7d",
                            headers={"Authorization": "Bearer token"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.get_json() == r2.get_json()
        assert r1.headers.get("X-Cache") == "MISS"
        assert r2.headers.get("X-Cache") == "HIT"
        # Only one pair of CE calls across the two requests (daily + by_service)
        assert ce.get_cost_and_usage.call_count == 2

    def test_invalid_range_returns_400(self, client, session_factory):
        _seed_admin_user(session_factory)
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN):
            resp = client.get(
                "/admin/api/metrics/cost?range=1y",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 400

    def test_no_bearer_token_uses_cloudwatch_estimate(
        self, client, session_factory,
    ):
        _seed_admin_user(session_factory)
        ce = _fake_ce_client()
        cw = MagicMock()
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._ce_client", return_value=ce), \
             patch("app.admin.metrics._cloudwatch_client", return_value=cw), \
             patch.dict("os.environ", {"X_API_BEARER_TOKEN": ""}, clear=False):
            resp = client.get(
                "/admin/api/metrics/cost?range=7d",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["x_api"].get("estimated") is True
        assert data["x_api"]["used_this_month"] == 0
