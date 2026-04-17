"""Unit tests for :class:`FinancialsRepository`."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.models.financials import Financials


@pytest.fixture
def mock_redis():
    with patch("app.repositories.base.get_redis") as gr:
        client = MagicMock()
        client.get.return_value = None
        gr.return_value = client
        yield client


@pytest.fixture
def mock_session():
    with patch("app.repositories.financials_repo.get_session") as gs:
        session = MagicMock()
        # Default dialect = sqlite so append takes the portable fallback path.
        session.bind.dialect.name = "sqlite"
        gs.return_value = session
        yield session


def _orm_row(**kwargs):
    row = MagicMock()
    defaults = {
        "ticker": "AAPL",
        "period_end": date(2025, 3, 31),
        "period_type": "Q1",
        "fiscal_year": 2025,
        "revenue": None,
        "gross_profit": None,
        "operating_income": None,
        "net_income": None,
        "eps_basic": None,
        "eps_diluted": None,
        "total_assets": None,
        "total_liabilities": None,
        "total_equity": None,
        "cash_equivalents": None,
        "long_term_debt": None,
        "operating_cf": None,
        "investing_cf": None,
        "financing_cf": None,
        "free_cash_flow": None,
        "filing_date": None,
        "source": None,
        "ingested_at": None,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def test_get_latest_cache_miss_queries_db(mock_redis, mock_session):
    from app.repositories.financials_repo import FinancialsRepository

    q = mock_session.query.return_value
    q.filter_by.return_value.order_by.return_value.first.return_value = _orm_row(
        ticker="AAPL", period_end=date(2025, 3, 31), revenue=100
    )

    repo = FinancialsRepository()
    result = repo.get_latest("aapl")

    assert result is not None
    assert result.ticker == "AAPL"
    assert result.revenue == 100
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:AAPL:financials:latest"
    assert args[1] == 3600  # TTL["financials_latest"]


def test_get_latest_cache_hit_skips_db(mock_redis, mock_session):
    from app.repositories.financials_repo import FinancialsRepository

    f = Financials(
        ticker="AAPL",
        period_end=date(2025, 3, 31),
        period_type="Q1",
        fiscal_year=2025,
        revenue=100,
    )
    mock_redis.get.return_value = f.model_dump_json().encode()

    repo = FinancialsRepository()
    result = repo.get_latest("AAPL")
    assert result is not None and result.revenue == 100
    mock_session.query.assert_not_called()


def test_get_range_queries_db(mock_redis, mock_session):
    from app.repositories.financials_repo import FinancialsRepository

    q = mock_session.query.return_value
    q.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        _orm_row(period_end=date(2025, 3, 31)),
        _orm_row(period_end=date(2024, 12, 31), period_type="Q4"),
    ]

    repo = FinancialsRepository()
    rows = repo.get_range("AAPL", date(2024, 1, 1), date(2025, 12, 31))
    assert len(rows) == 2


def test_append_invalidates_latest_cache(mock_redis, mock_session):
    from app.repositories.financials_repo import FinancialsRepository

    # After add+commit, the follow-up SELECT should return the inserted row.
    inserted = _orm_row(
        ticker="AAPL",
        period_end=date(2025, 3, 31),
        period_type="Q1",
        revenue=100,
    )
    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        inserted
    )

    repo = FinancialsRepository()
    f = Financials(
        ticker="AAPL",
        period_end=date(2025, 3, 31),
        period_type="Q1",
        fiscal_year=2025,
        revenue=100,
    )
    result = repo.append(f)

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called()
    mock_redis.delete.assert_called_with("company:AAPL:financials:latest")
    assert result.revenue == 100


def test_append_on_conflict_updates_in_place(mock_redis, mock_session):
    """Dup filing — IntegrityError on add, then UPDATE path runs."""
    from sqlalchemy.exc import IntegrityError

    from app.repositories.financials_repo import FinancialsRepository

    # First commit raises (duplicate), rollback, then lookup returns the
    # existing row which we mutate in place.
    existing = _orm_row(revenue=90)
    call_state = {"commits": 0}

    def _commit():
        call_state["commits"] += 1
        if call_state["commits"] == 1:
            raise IntegrityError("duplicate", {}, Exception())

    mock_session.commit.side_effect = _commit

    # Two distinct filter_by calls happen in the UPDATE path: the
    # post-rollback lookup + the final "re-read" lookup. Both should
    # return the existing row.
    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        existing
    )

    repo = FinancialsRepository()
    f = Financials(
        ticker="AAPL",
        period_end=date(2025, 3, 31),
        period_type="Q1",
        fiscal_year=2025,
        revenue=101,
    )
    result = repo.append(f)
    # Row mutated in place
    assert existing.revenue == 101
    # Cache invalidated
    mock_redis.delete.assert_called_with("company:AAPL:financials:latest")
    assert result is not None
