"""Tests for market data API endpoints (US-010)."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.models import User
from app.services.feed_parser import utc_iso


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


def _create_user(db_session, tier="pro"):
    now = utc_iso(datetime.now(timezone.utc))
    user = User(
        firebase_uid="market-test-uid",
        email="market@example.com",
        display_name="Market Tester",
        tier=tier,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestMarketSnapshotAuth:
    """Authentication requirements for /api/market/<symbol>."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/market/AAPL")
        assert resp.status_code == 401

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_authenticated_returns_200(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session, tier="pro")
        mock_polygon.enabled = True
        mock_polygon.get_ticker_snapshot.return_value = {
            "symbol": "AAPL",
            "price": 150.25,
            "change": 1.75,
            "change_percent": 1.18,
            "volume": 50000000,
            "vwap": 149.80,
        }
        resp = client.get("/api/market/AAPL", headers=_auth_headers())
        assert resp.status_code == 200


class TestMarketDetailsAuth:
    """Authentication requirements for /api/market/<symbol>/details."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/market/AAPL/details")
        assert resp.status_code == 401


class TestMarketSnapshot:
    """Snapshot endpoint response format and error handling."""

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_snapshot_response_fields(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_snapshot.return_value = {
            "symbol": "AAPL",
            "price": 150.25,
            "change": 1.75,
            "change_percent": 1.18,
            "volume": 50000000,
            "vwap": 149.80,
        }
        resp = client.get("/api/market/AAPL", headers=_auth_headers())
        data = resp.get_json()
        for field in ("symbol", "price", "change", "change_percent", "volume", "vwap", "updated_at"):
            assert field in data, f"Missing field: {field}"
        assert data["symbol"] == "AAPL"
        assert data["price"] == 150.25

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_snapshot_404_unknown_ticker(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_snapshot.return_value = None
        resp = client.get("/api/market/ZZZZZ", headers=_auth_headers())
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert "ZZZZZ" in data["message"]

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_snapshot_503_when_disabled(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = False
        resp = client.get("/api/market/AAPL", headers=_auth_headers())
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "60"
        data = resp.get_json()
        assert "error" in data


class TestMarketDetails:
    """Details endpoint response format and error handling."""

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_details_response_fields(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_details.return_value = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 3000000000000,
            "logo_url": "https://example.com/logo.png",
            "description": "Apple Inc. designs consumer electronics.",
            "homepage_url": "https://apple.com",
        }
        resp = client.get("/api/market/AAPL/details", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        for field in ("symbol", "name", "sector", "market_cap", "logo_url", "description", "homepage_url"):
            assert field in data, f"Missing field: {field}"
        assert data["name"] == "Apple Inc."

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_details_404_unknown_ticker(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_details.return_value = None
        resp = client.get("/api/market/ZZZZZ/details", headers=_auth_headers())
        assert resp.status_code == 404

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_details_503_when_disabled(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = False
        resp = client.get("/api/market/AAPL/details", headers=_auth_headers())
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "60"


class TestMarketRateLimit:
    """Rate limiting for market endpoints."""

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_rate_limit_header_present(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "market-test-uid",
            "email": "market@example.com",
            "name": "Market Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_snapshot.return_value = {
            "symbol": "AAPL", "price": 150.0, "change": 0,
            "change_percent": 0, "volume": 0, "vwap": 0,
        }
        resp = client.get("/api/market/AAPL", headers=_auth_headers())
        assert resp.status_code == 200
        # Flask-Limiter sets rate limit headers when RATELIMIT_HEADERS_ENABLED=True
        assert resp.headers.get("X-RateLimit-Limit") is not None
