"""Tests for company financials API (US-013)."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.models import User
from app.services.feed_parser import utc_iso
from app.services.market_data import PolygonClient


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


def _create_user(db_session, tier="pro"):
    now = utc_iso(datetime.now(timezone.utc))
    user = User(
        firebase_uid="financials-test-uid",
        email="financials@example.com",
        display_name="Financials Tester",
        tier=tier,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    return user


# --- Polygon response fixtures ---

POLYGON_FINANCIALS_RESPONSE = {
    "results": [
        {
            "fiscal_period": "Q1",
            "fiscal_year": "2024",
            "financials": {
                "income_statement": {
                    "revenues": {"value": 119575000000, "unit": "USD"},
                    "net_income_loss": {"value": 33916000000, "unit": "USD"},
                    "basic_earnings_per_share": {"value": 2.19, "unit": "USD/shares"},
                }
            },
        },
        {
            "fiscal_period": "Q4",
            "fiscal_year": "2023",
            "financials": {
                "income_statement": {
                    "revenues": {"value": 117200000000, "unit": "USD"},
                    "net_income_loss": {"value": 30000000000, "unit": "USD"},
                    "basic_earnings_per_share": {"value": 2.10, "unit": "USD/shares"},
                }
            },
        },
        {
            "fiscal_period": "Q3",
            "fiscal_year": "2023",
            "financials": {
                "income_statement": {
                    "revenues": {"value": 89500000000, "unit": "USD"},
                    "net_income_loss": {"value": 22960000000, "unit": "USD"},
                    "basic_earnings_per_share": {"value": 1.46, "unit": "USD/shares"},
                }
            },
        },
        {
            "fiscal_period": "Q2",
            "fiscal_year": "2023",
            "financials": {
                "income_statement": {
                    "revenues": {"value": 81797000000, "unit": "USD"},
                    "net_income_loss": {"value": 19881000000, "unit": "USD"},
                    "basic_earnings_per_share": {"value": 1.26, "unit": "USD/shares"},
                }
            },
        },
    ],
    "status": "OK",
    "request_id": "test-123",
}

POLYGON_EMPTY_FINANCIALS = {
    "results": [],
    "status": "OK",
    "request_id": "test-456",
}


class TestPolygonClientGetFinancials:
    """PolygonClient.get_financials() unit tests."""

    def test_get_financials_disabled(self):
        client = PolygonClient(api_key="")
        result = client.get_financials("AAPL")
        assert result is None

    @patch("app.services.market_data.requests.Session")
    def test_get_financials_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        # financials endpoint response
        financials_resp = MagicMock()
        financials_resp.json.return_value = POLYGON_FINANCIALS_RESPONSE
        financials_resp.raise_for_status.return_value = None
        # snapshot endpoint response (for P/E calculation)
        snapshot_resp = MagicMock()
        snapshot_resp.json.return_value = {
            "results": [{
                "session": {
                    "price": 185.0,
                    "close": 185.0,
                    "previous_close": 183.0,
                    "change": 2.0,
                    "change_percent": round((2.0 / 183.0) * 100, 4),
                    "volume": 50000000,
                    "vwap": 184.5,
                },
            }],
        }
        snapshot_resp.raise_for_status.return_value = None
        mock_session.get.side_effect = [financials_resp, snapshot_resp]

        client = PolygonClient(api_key="test-key")
        result = client.get_financials("AAPL")

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["fiscal_period"] == "Q1"
        assert result["fiscal_year"] == "2024"
        assert result["revenue"] == 119575000000
        assert result["net_income"] == 33916000000
        assert result["eps"] == 2.19
        # TTM EPS = 2.19 + 2.10 + 1.46 + 1.26 = 7.01
        # P/E = 185.0 / 7.01 = 26.39
        assert result["pe_ratio"] == round(185.0 / 7.01, 2)

    @patch("app.services.market_data.requests.Session")
    def test_get_financials_empty_results(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = POLYGON_EMPTY_FINANCIALS
        resp.raise_for_status.return_value = None
        mock_session.get.return_value = resp

        client = PolygonClient(api_key="test-key")
        result = client.get_financials("XYZZY")

        assert result is not None
        assert result["symbol"] == "XYZZY"
        assert result["revenue"] is None
        assert result["net_income"] is None
        assert result["eps"] is None
        assert result["pe_ratio"] is None

    @patch("app.services.market_data.requests.Session")
    def test_get_financials_cache(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = POLYGON_EMPTY_FINANCIALS
        resp.raise_for_status.return_value = None
        mock_session.get.return_value = resp

        client = PolygonClient(api_key="test-key")
        result1 = client.get_financials("AAPL")
        result2 = client.get_financials("AAPL")
        assert result1 == result2
        # Should only call API once due to cache
        assert mock_session.get.call_count == 1


class TestPolygonClientGetEarnings:
    """PolygonClient.get_earnings() unit tests."""

    def test_get_earnings_disabled(self):
        client = PolygonClient(api_key="")
        result = client.get_earnings("AAPL")
        assert result is None

    @patch("app.services.market_data.requests.Session")
    def test_get_earnings_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = POLYGON_FINANCIALS_RESPONSE
        resp.raise_for_status.return_value = None
        mock_session.get.return_value = resp

        client = PolygonClient(api_key="test-key")
        result = client.get_earnings("AAPL")

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert len(result["earnings"]) == 4
        assert result["earnings"][0]["fiscal_period"] == "Q1"
        assert result["earnings"][0]["actual_eps"] == 2.19
        assert result["earnings"][0]["estimated_eps"] is None
        assert result["earnings"][3]["actual_eps"] == 1.26

    @patch("app.services.market_data.requests.Session")
    def test_get_earnings_empty(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = POLYGON_EMPTY_FINANCIALS
        resp.raise_for_status.return_value = None
        mock_session.get.return_value = resp

        client = PolygonClient(api_key="test-key")
        result = client.get_earnings("XYZZY")

        assert result is not None
        assert result["symbol"] == "XYZZY"
        assert result["earnings"] == []

    @patch("app.services.market_data.requests.Session")
    def test_get_earnings_cache(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = POLYGON_FINANCIALS_RESPONSE
        resp.raise_for_status.return_value = None
        mock_session.get.return_value = resp

        client = PolygonClient(api_key="test-key")
        result1 = client.get_earnings("AAPL")
        result2 = client.get_earnings("AAPL")
        assert result1 == result2
        assert mock_session.get.call_count == 1


class TestFinancialsEndpointAuth:
    """Authentication for /api/market/<symbol>/financials."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/market/AAPL/financials")
        assert resp.status_code == 401


class TestFinancialsEndpoint:
    """GET /api/market/<symbol>/financials response and error handling."""

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_financials_response_fields(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "financials-test-uid",
            "email": "financials@example.com",
            "name": "Financials Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_financials.return_value = {
            "symbol": "AAPL",
            "fiscal_period": "Q1",
            "fiscal_year": "2024",
            "revenue": 119575000000,
            "net_income": 33916000000,
            "eps": 2.19,
            "pe_ratio": 26.39,
        }
        mock_polygon.get_earnings.return_value = {
            "symbol": "AAPL",
            "earnings": [
                {"fiscal_period": "Q1", "fiscal_year": "2024", "actual_eps": 2.19, "estimated_eps": None},
                {"fiscal_period": "Q4", "fiscal_year": "2023", "actual_eps": 2.10, "estimated_eps": None},
            ],
        }
        resp = client.get("/api/market/AAPL/financials", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbol"] == "AAPL"
        assert data["financials"]["revenue"] == 119575000000
        assert data["financials"]["eps"] == 2.19
        assert data["financials"]["pe_ratio"] == 26.39
        assert len(data["earnings"]) == 2
        assert data["earnings"][0]["actual_eps"] == 2.19

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_financials_404_unknown_ticker(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "financials-test-uid",
            "email": "financials@example.com",
            "name": "Financials Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_financials.return_value = None
        mock_polygon.get_earnings.return_value = None
        resp = client.get("/api/market/ZZZZZ/financials", headers=_auth_headers())
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert "ZZZZZ" in data["message"]

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_financials_503_when_disabled(self, mock_polygon, mock_verify, client, db_session):
        mock_verify.return_value = {
            "uid": "financials-test-uid",
            "email": "financials@example.com",
            "name": "Financials Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = False
        resp = client.get("/api/market/AAPL/financials", headers=_auth_headers())
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "60"

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_financials_graceful_empty_data(self, mock_polygon, mock_verify, client, db_session):
        """When financials returns data but earnings returns None, response is still valid."""
        mock_verify.return_value = {
            "uid": "financials-test-uid",
            "email": "financials@example.com",
            "name": "Financials Tester",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_financials.return_value = {
            "symbol": "SPY",
            "fiscal_period": None,
            "fiscal_year": None,
            "revenue": None,
            "net_income": None,
            "eps": None,
            "pe_ratio": None,
        }
        mock_polygon.get_earnings.return_value = None
        resp = client.get("/api/market/SPY/financials", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["financials"]["revenue"] is None
        assert data["earnings"] == []
