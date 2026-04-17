"""Unit tests for :class:`FundamentalsRepository`.

A full SCD-2 round-trip (insert v1 → update to v2 → ``get_at(v1_ts)``
returns v1) requires the real Postgres trigger, so that assertion is
gated on the ``INTEGRATION_TEST=1`` env var. The Tester runs the
integration path against the one-off Postgres per the US-002 pattern.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.fundamentals import Fundamentals, FundamentalsHistory


@pytest.fixture
def mock_redis():
    with patch("app.repositories.base.get_redis") as gr:
        client = MagicMock()
        client.get.return_value = None
        gr.return_value = client
        yield client


@pytest.fixture
def mock_session():
    with patch("app.repositories.fundamentals_repo.get_session") as gs:
        session = MagicMock()
        session.bind.dialect.name = "sqlite"
        gs.return_value = session
        yield session


def _current_row(**kwargs):
    row = MagicMock()
    defaults = {
        "ticker": "AAPL",
        "market_cap": None,
        "shares_outstanding": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "ev_ebitda": None,
        "dividend_yield": None,
        "beta": None,
        "next_earnings_date": None,
        "next_earnings_time": None,
        "analyst_rating": None,
        "price_target_mean": None,
        "updated_at": datetime(2025, 1, 1),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _history_row(**kwargs):
    row = MagicMock()
    defaults = {
        "ticker": "AAPL",
        "market_cap": None,
        "shares_outstanding": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "ev_ebitda": None,
        "dividend_yield": None,
        "beta": None,
        "next_earnings_date": None,
        "next_earnings_time": None,
        "analyst_rating": None,
        "price_target_mean": None,
        "updated_at": datetime(2025, 1, 1),
        "valid_from": datetime(2025, 1, 1),
        "valid_to": datetime(2025, 2, 1),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def test_get_cache_miss_queries_db(mock_redis, mock_session):
    from app.repositories.fundamentals_repo import FundamentalsRepository

    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        _current_row(pe_ratio=Decimal("30.00"))
    )

    repo = FundamentalsRepository()
    result = repo.get("AAPL")
    assert result is not None
    assert result.pe_ratio == Decimal("30.00")
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:AAPL:fundamentals"
    assert args[1] == 300


def test_get_cache_hit_skips_db(mock_redis, mock_session):
    from app.repositories.fundamentals_repo import FundamentalsRepository

    f = Fundamentals(ticker="AAPL", pe_ratio=Decimal("25.00"))
    mock_redis.get.return_value = f.model_dump_json().encode()

    repo = FundamentalsRepository()
    assert repo.get("AAPL").pe_ratio == Decimal("25.00")
    mock_session.query.assert_not_called()


def test_upsert_insert_path(mock_redis, mock_session):
    from app.repositories.fundamentals_repo import FundamentalsRepository

    # No existing row — INSERT path.
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    # Make session.add() finalize the row fields so model_validate works.

    def _add(row):
        row.ticker = "AAPL"
        row.pe_ratio = Decimal("30.00")
        for attr in (
            "market_cap",
            "shares_outstanding",
            "pb_ratio",
            "ev_ebitda",
            "dividend_yield",
            "beta",
            "next_earnings_date",
            "next_earnings_time",
            "analyst_rating",
            "price_target_mean",
        ):
            setattr(row, attr, None)
        row.updated_at = datetime(2025, 1, 1)

    mock_session.add.side_effect = _add

    repo = FundamentalsRepository()
    result = repo.upsert(Fundamentals(ticker="AAPL", pe_ratio=Decimal("30.00")))
    assert result.pe_ratio == Decimal("30.00")
    mock_redis.delete.assert_called_with("company:AAPL:fundamentals")


def test_upsert_update_path_on_sqlite_writes_history_snapshot(
    mock_redis, mock_session
):
    """Non-Postgres dialects emulate the SCD-2 trigger manually."""
    from app.repositories.fundamentals_repo import FundamentalsRepository

    existing = _current_row(pe_ratio=Decimal("30.00"), updated_at=datetime(2025, 1, 1))
    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        existing
    )

    repo = FundamentalsRepository()
    repo.upsert(Fundamentals(ticker="AAPL", pe_ratio=Decimal("32.00")))

    # Two add() calls: one for the history snapshot (inside UPDATE path)
    # and the trigger emulation. Current row is mutated in place.
    assert existing.pe_ratio == Decimal("32.00")
    # Verify a history snapshot was added via session.add
    assert mock_session.add.called
    mock_redis.delete.assert_called_with("company:AAPL:fundamentals")


def test_get_at_queries_history(mock_redis, mock_session):
    from app.repositories.fundamentals_repo import FundamentalsRepository

    q = mock_session.query.return_value
    q.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = (
        _history_row(pe_ratio=Decimal("30.00"))
    )

    repo = FundamentalsRepository()
    result = repo.get_at("AAPL", datetime(2025, 1, 15))
    assert result is not None
    assert isinstance(result, FundamentalsHistory)
    assert result.pe_ratio == Decimal("30.00")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("INTEGRATION_TEST"),
    reason="Requires real Postgres with SCD-2 trigger",
)
def test_scd2_roundtrip_against_postgres():
    """Integration: insert v1 → update to v2 → get_at(v1_ts) returns v1.

    Requires ``INTEGRATION_TEST=1`` and a live ``DATABASE_URL`` pointing
    at Postgres with migrations applied through 019. The Tester runs
    this against the one-off ``signal-postgres-impl`` container.
    """
    import time

    from app.database import init_db
    from app.models import Company as CompanyORM
    from app.repositories.company_repo import CompanyRepository
    from app.repositories.fundamentals_repo import FundamentalsRepository

    db_url = os.environ["DATABASE_URL"]
    init_db(db_url)

    # Ensure master row exists (FK RESTRICT).
    CompanyRepository().upsert(
        __import__("app.models.company", fromlist=["Company"]).Company(
            ticker="SCDT", name="SCD Test Corp"
        )
    )

    repo = FundamentalsRepository()
    # v1
    repo.upsert(Fundamentals(ticker="SCDT", pe_ratio=Decimal("30.00")))
    v1 = repo.get("SCDT")
    assert v1 is not None and v1.pe_ratio == Decimal("30.00")
    v1_ts = v1.updated_at
    assert v1_ts is not None

    # Small gap so the trigger assigns a later timestamp.
    time.sleep(1.1)

    # v2
    repo.upsert(Fundamentals(ticker="SCDT", pe_ratio=Decimal("32.00")))
    v2 = repo.get("SCDT")
    assert v2 is not None and v2.pe_ratio == Decimal("32.00")

    # A query at v1_ts should hit the snapshot with pe_ratio = 30.
    hist = repo.get_at("SCDT", v1_ts)
    assert hist is not None
    assert hist.pe_ratio == Decimal("30.00")
