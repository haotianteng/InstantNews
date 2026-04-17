"""Tests for POST /admin/api/metrics/cloudwatch (US-006)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.models import User
from app.services.feed_parser import utc_iso
from tests.test_auth import MOCK_DECODED_TOKEN, VERIFY_PATCH


@pytest.fixture(autouse=True)
def _clear_metrics_cache():
    """Flush both TTL caches before every test so ordering doesn't matter."""
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
    """Insert a DB user with role='admin' matching the mocked Firebase uid."""
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


# ── Mocked cloudwatch client ────────────────────────────────────────


class _FakeCloudWatchClient:
    def __init__(self, response):
        self._response = response
        self.call_count = 0
        self.last_kwargs = None

    def get_metric_data(self, **kwargs):
        self.call_count += 1
        self.last_kwargs = kwargs
        return self._response


def _fake_cw_response():
    return {
        "MetricDataResults": [
            {
                "Id": "q1",
                "Label": "NewItems",
                "Timestamps": [
                    datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
                    datetime(2026, 4, 17, 12, 1, tzinfo=timezone.utc),
                ],
                "Values": [3.0, 5.0],
                "StatusCode": "Complete",
            }
        ]
    }


# ── Tests ───────────────────────────────────────────────────────────


class TestCloudWatchEndpoint:
    def test_happy_path_returns_series(self, client, session_factory):
        _seed_admin_user(session_factory)
        fake = _FakeCloudWatchClient(_fake_cw_response())
        body = {
            "range": "1h",
            "queries": [{
                "id": "q1",
                "namespace": "InstantNews/Ingestion",
                "metric": "NewItems",
                "dimensions": {"Source": "SeekingAlpha"},
                "stat": "Sum",
            }],
        }
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._cloudwatch_client", return_value=fake):
            resp = client.post(
                "/admin/api/metrics/cloudwatch",
                json=body,
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()
        assert "series" in data
        assert "q1" in data["series"]
        ts = data["series"]["q1"]["timestamps"]
        vals = data["series"]["q1"]["values"]
        assert len(ts) == 2
        assert all(isinstance(t, int) for t in ts)
        assert ts[0] == int(datetime(2026, 4, 17, 12, 0,
                                     tzinfo=timezone.utc).timestamp())
        assert vals == [3.0, 5.0]
        assert resp.headers.get("X-Cache") == "MISS"
        # Verify the boto3 call carried the right shape.
        sent = fake.last_kwargs["MetricDataQueries"][0]
        assert sent["Id"] == "q1"
        assert sent["MetricStat"]["Metric"]["Namespace"] == "InstantNews/Ingestion"
        assert sent["MetricStat"]["Stat"] == "Sum"
        assert sent["MetricStat"]["Period"] == 60
        assert sent["MetricStat"]["Metric"]["Dimensions"] == [
            {"Name": "Source", "Value": "SeekingAlpha"},
        ]

    def test_missing_auth_returns_401(self, client):
        resp = client.post(
            "/admin/api/metrics/cloudwatch",
            json={"range": "1h", "queries": [{
                "id": "q1", "namespace": "NS", "metric": "M", "stat": "Sum",
            }]},
        )
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, client, session_factory):
        _seed_regular_user(session_factory)
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN):
            resp = client.post(
                "/admin/api/metrics/cloudwatch",
                json={"range": "1h", "queries": [{
                    "id": "q1", "namespace": "NS", "metric": "M", "stat": "Sum",
                }]},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403

    def test_invalid_range_returns_400(self, client, session_factory):
        _seed_admin_user(session_factory)
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN):
            resp = client.post(
                "/admin/api/metrics/cloudwatch",
                json={"range": "30d", "queries": [{
                    "id": "q1", "namespace": "NS", "metric": "M", "stat": "Sum",
                }]},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 400
        assert "range" in (resp.get_json().get("error") or "").lower()

    def test_empty_queries_returns_400(self, client, session_factory):
        _seed_admin_user(session_factory)
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN):
            resp = client.post(
                "/admin/api/metrics/cloudwatch",
                json={"range": "1h", "queries": []},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 400

    def test_missing_query_field_returns_400(self, client, session_factory):
        _seed_admin_user(session_factory)
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN):
            resp = client.post(
                "/admin/api/metrics/cloudwatch",
                json={"range": "1h", "queries": [{
                    "id": "q1", "namespace": "NS", "metric": "M",
                    # missing 'stat'
                }]},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 400

    def test_cache_hit_within_60s_skips_boto3(self, client, session_factory):
        _seed_admin_user(session_factory)
        fake = _FakeCloudWatchClient(_fake_cw_response())
        body = {
            "range": "1h",
            "queries": [{
                "id": "q1", "namespace": "InstantNews/Ingestion",
                "metric": "NewItems", "stat": "Sum",
            }],
        }
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._cloudwatch_client", return_value=fake):
            r1 = client.post("/admin/api/metrics/cloudwatch", json=body,
                             headers={"Authorization": "Bearer token"})
            r2 = client.post("/admin/api/metrics/cloudwatch", json=body,
                             headers={"Authorization": "Bearer token"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.get_json() == r2.get_json()
        assert fake.call_count == 1  # second call served from cache
        assert r1.headers.get("X-Cache") == "MISS"
        assert r2.headers.get("X-Cache") == "HIT"

    def test_7d_range_uses_3600_period(self, client, session_factory):
        _seed_admin_user(session_factory)
        fake = _FakeCloudWatchClient(_fake_cw_response())
        body = {
            "range": "7d",
            "queries": [{
                "id": "q1", "namespace": "NS", "metric": "M", "stat": "Sum",
            }],
        }
        with patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN), \
             patch("app.admin.metrics._cloudwatch_client", return_value=fake):
            resp = client.post("/admin/api/metrics/cloudwatch", json=body,
                               headers={"Authorization": "Bearer token"})
        assert resp.status_code == 200
        assert fake.last_kwargs["MetricDataQueries"][0]["MetricStat"]["Period"] == 3600
