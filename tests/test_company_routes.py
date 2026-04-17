"""Tests for the GET /api/company/<ticker>/profile endpoint (US-012).

The endpoint is a thin Flask wrapper around
:class:`CompanyService.get_full_profile`; these tests patch the
module-level ``_service`` so we exercise the route's HTTP behavior
without hitting live Redis / Postgres / upstream APIs.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from app.models import User
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.fundamentals import Fundamentals
from app.services.feed_parser import utc_iso


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


def _create_user(db_session, tier="pro"):
    now = utc_iso(datetime.now(timezone.utc))
    user = User(
        firebase_uid="company-test-uid",
        email="company@example.com",
        display_name="Company Tester",
        tier=tier,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestCompanyProfileAuth:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/company/AAPL/profile")
        assert resp.status_code == 401

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.company._service")
    def test_authenticated_returns_200(
        self, mock_service, mock_verify, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "company-test-uid",
            "email": "company@example.com",
            "name": "Company Tester",
        }
        _create_user(db_session)
        mock_service.get_full_profile.return_value = CompanyProfile(
            company=Company(ticker="AAPL", name="Apple Inc."),
            fundamentals=Fundamentals(ticker="AAPL", market_cap=1),
            partial=False,
        )
        resp = client.get("/api/company/AAPL/profile", headers=_auth_headers())
        assert resp.status_code == 200


class TestCompanyProfileResponseShape:
    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.company._service")
    def test_response_has_all_required_fields(
        self, mock_service, mock_verify, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "company-test-uid",
            "email": "company@example.com",
            "name": "Company Tester",
        }
        _create_user(db_session)
        mock_service.get_full_profile.return_value = CompanyProfile(
            company=Company(ticker="AAPL", name="Apple Inc."),
            partial=False,
        )
        resp = client.get("/api/company/AAPL/profile", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        required = {
            "company", "fundamentals", "latest_financials",
            "competitors", "top_institutions", "recent_insiders",
            "partial", "fetched_at",
        }
        assert required <= set(data.keys())
        assert data["company"]["ticker"] == "AAPL"

    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.company._service")
    def test_cache_control_header_present(
        self, mock_service, mock_verify, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "company-test-uid",
            "email": "company@example.com",
            "name": "Company Tester",
        }
        _create_user(db_session)
        mock_service.get_full_profile.return_value = CompanyProfile(
            company=Company(ticker="AAPL", name="Apple Inc."),
        )
        resp = client.get("/api/company/AAPL/profile", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.headers.get("Cache-Control") == "private, max-age=60"


class TestCompanyProfile404:
    @patch("app.auth.firebase.verify_id_token")
    @patch("app.routes.company._service")
    def test_unknown_ticker_returns_404(
        self, mock_service, mock_verify, client, db_session,
    ):
        mock_verify.return_value = {
            "uid": "company-test-uid",
            "email": "company@example.com",
            "name": "Company Tester",
        }
        _create_user(db_session)
        # Empty profile — no master row, no fundamentals, no lists → 404
        mock_service.get_full_profile.return_value = CompanyProfile(
            company=None, fundamentals=None, latest_financials=None,
            competitors=[], top_institutions=[], recent_insiders=[],
            partial=True,
        )
        resp = client.get("/api/company/ZZZZZ/profile", headers=_auth_headers())
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert data["ticker"] == "ZZZZZ"
