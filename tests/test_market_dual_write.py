"""US-013 dual-write integration tests.

Verifies that when the existing ``/api/market/<symbol>/*`` routes fall
through to the Polygon/EDGAR clients, the mapped payload is also
persisted into the new normalized repositories. Response shape is
asserted to match the pre-refactor format — the terminal frontend reads
the same keys.

These tests use the default ``conftest`` in-memory SQLite stack + mocked
upstream clients, and patch ``get_redis`` so Redis is never actually
touched. The SQLite engine lets the repo ``upsert`` / ``append`` logic
run for real, proving the dual-write actually writes something.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import User
from app.services.feed_parser import utc_iso


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


def _create_user(db_session, tier="pro"):
    now = utc_iso(datetime.now(timezone.utc))
    user = User(
        firebase_uid="dual-write-uid",
        email="dual@example.com",
        display_name="Dual Write",
        tier=tier,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def mock_redis():
    """Patch get_redis in every repository and service module."""
    client = MagicMock()
    client.get.return_value = None  # force cache miss on reads
    client.setex.return_value = True
    client.delete.return_value = 1
    client.scan_iter.return_value = iter([])
    patches = [
        patch("app.repositories.base.get_redis", return_value=client),
    ]
    for p in patches:
        p.start()
    yield client
    for p in patches:
        p.stop()


class TestDetailsDualWrite:
    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_details_response_shape_preserved(
        self, mock_polygon, mock_verify, mock_redis, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "dual-write-uid",
            "email": "dual@example.com",
            "name": "Dual Write",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_details.return_value = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 3_000_000_000_000,
            "logo_url": "https://example.com/logo.png",
            "description": "Apple Inc. designs electronics.",
            "homepage_url": "https://apple.com",
        }
        resp = client.get("/api/market/AAPL/details", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        # Pre-refactor keys preserved exactly.
        for field in (
            "symbol", "name", "sector", "market_cap",
            "logo_url", "description", "homepage_url",
        ):
            assert field in data, f"missing legacy field: {field}"
        assert data["symbol"] == "AAPL"

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_details_dual_write_populates_companies_table(
        self, mock_polygon, mock_verify, mock_redis, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "dual-write-uid",
            "email": "dual@example.com",
            "name": "Dual Write",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_details.return_value = {
            "symbol": "NEWTICK",
            "name": "New Ticker Corp.",
            "sector": "Industrials",
            "market_cap": 1_000_000,
            "logo_url": "",
            "description": "Brand new listing.",
            "homepage_url": "https://newtick.example",
        }

        # Precondition: companies table empty for NEWTICK.
        from app.repositories.company_repo import CompanyRepository
        repo = CompanyRepository()
        assert repo.get("NEWTICK") is None

        resp = client.get("/api/market/NEWTICK/details", headers=_auth_headers())
        assert resp.status_code == 200

        # Dual-write: ``companies`` now has NEWTICK row.
        master = repo.get("NEWTICK")
        assert master is not None
        assert master.ticker == "NEWTICK"
        assert master.name == "New Ticker Corp."


class TestCompetitorsDualWrite:
    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.market._polygon")
    def test_competitors_response_shape_preserved(
        self, mock_polygon, mock_verify, mock_redis, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "dual-write-uid",
            "email": "dual@example.com",
            "name": "Dual Write",
        }
        _create_user(db_session)
        mock_polygon.enabled = True
        mock_polygon.get_ticker_details.return_value = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 3e12,
            "logo_url": "",
            "description": "",
            "homepage_url": "",
        }
        mock_polygon.get_related_companies.return_value = [
            {"symbol": "MSFT", "name": "Microsoft", "market_cap": 3e12, "price": 420, "change_percent": 1.0},
            {"symbol": "GOOG", "name": "Alphabet", "market_cap": 2e12, "price": 175, "change_percent": -0.5},
        ]

        resp = client.get("/api/market/AAPL/competitors", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbol"] == "AAPL"
        assert len(data["competitors"]) == 2
        assert data["competitors"][0]["symbol"] == "MSFT"

        # Dual-write: the new repo has 2 edges for AAPL.
        from app.repositories.competitors_repo import CompetitorsRepository
        repo = CompetitorsRepository()
        edges = repo.get_top("AAPL", n=10)
        syms = {e.competitor_ticker for e in edges}
        assert syms == {"MSFT", "GOOG"}
