"""Unit tests for :class:`InstitutionsRepository`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.institutions import InstitutionalHolder


@pytest.fixture
def mock_redis():
    with patch("app.repositories.base.get_redis") as gr:
        client = MagicMock()
        client.get.return_value = None
        client.scan_iter.return_value = iter([])
        gr.return_value = client
        yield client


@pytest.fixture
def mock_session():
    with patch("app.repositories.institutions_repo.get_session") as gs:
        session = MagicMock()
        session.bind.dialect.name = "sqlite"
        gs.return_value = session
        yield session


def _orm_row(**kwargs):
    row = MagicMock()
    defaults = {
        "id": 1,
        "ticker": "AAPL",
        "institution_cik": "0001067983",
        "institution_name": "Berkshire Hathaway",
        "report_date": date(2025, 3, 31),
        "shares_held": 1000000,
        "market_value": 200_000_000,
        "pct_of_portfolio": Decimal("0.1200"),
        "pct_of_company": Decimal("0.0500"),
        "change_shares": 10000,
        "filing_date": date(2025, 4, 15),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def test_get_top_without_as_of_resolves_latest_and_caches(mock_redis, mock_session):
    from app.repositories.institutions_repo import InstitutionsRepository

    # First: latest report_date lookup
    q = mock_session.query.return_value
    # The first call — `.query(HolderORM.report_date)` returns a result where
    # .filter_by.order_by.first gives (date,).
    latest_result = MagicMock()
    latest_result.filter_by.return_value.order_by.return_value.first.return_value = (
        date(2025, 3, 31),
    )

    # Second: the actual SELECT by (ticker, report_date)
    rows_result = MagicMock()
    rows_result.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        _orm_row(institution_name="Vanguard", market_value=300_000_000),
        _orm_row(institution_name="BlackRock", market_value=250_000_000),
    ]

    # Return latest-result first, then rows-result for the 2 .query() calls.
    mock_session.query.side_effect = [latest_result, rows_result]

    repo = InstitutionsRepository()
    rows = repo.get_top("AAPL", n=2)
    assert len(rows) == 2
    assert rows[0].institution_name == "Vanguard"
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:AAPL:institutions:top2"
    assert args[1] == 21600  # TTL["institutions"]


def test_get_top_with_as_of_is_not_cached(mock_redis, mock_session):
    from app.repositories.institutions_repo import InstitutionsRepository

    rows_result = MagicMock()
    rows_result.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        _orm_row(institution_name="Vanguard"),
    ]
    mock_session.query.return_value = rows_result

    repo = InstitutionsRepository()
    rows = repo.get_top("AAPL", n=20, as_of=date(2024, 12, 31))
    assert len(rows) == 1
    # No Redis write for date-pinned queries.
    mock_redis.setex.assert_not_called()


def test_append_batch_invalidates_pattern_per_ticker(mock_redis, mock_session):
    from app.repositories.institutions_repo import InstitutionsRepository

    mock_redis.scan_iter.return_value = iter(
        [b"company:AAPL:institutions:top20"]
    )

    repo = InstitutionsRepository()
    count = repo.append_batch(
        [
            InstitutionalHolder(
                ticker="AAPL",
                institution_cik="0001067983",
                institution_name="Berkshire",
                report_date=date(2025, 3, 31),
                shares_held=1000,
                market_value=200_000,
            )
        ]
    )
    assert count == 1
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called()
    # One key deleted for one ticker
    assert mock_redis.delete.call_count == 1


def test_append_batch_empty_is_noop(mock_redis, mock_session):
    from app.repositories.institutions_repo import InstitutionsRepository

    repo = InstitutionsRepository()
    assert repo.append_batch([]) == 0
    mock_session.add.assert_not_called()
