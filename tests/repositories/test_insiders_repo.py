"""Unit tests for :class:`InsidersRepository`."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.insiders import InsiderTransaction


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
    with patch("app.repositories.insiders_repo.get_session") as gs:
        session = MagicMock()
        gs.return_value = session
        yield session


def _orm_row(**kwargs):
    row = MagicMock()
    defaults = {
        "id": 1,
        "ticker": "AAPL",
        "insider_name": "Timothy Cook",
        "insider_title": "CEO",
        "transaction_date": date.today() - timedelta(days=5),
        "transaction_type": "SELL",
        "shares": 10000,
        "price_per_share": Decimal("200.00"),
        "total_value": 2_000_000,
        "shares_owned_after": 3_000_000,
        "filing_date": date.today() - timedelta(days=3),
        "form_type": "Form 4",
        "sec_url": None,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def test_get_recent_cache_miss_queries_db(mock_redis, mock_session):
    from app.repositories.insiders_repo import InsidersRepository

    q = mock_session.query.return_value
    q.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        _orm_row(transaction_date=date.today() - timedelta(days=2)),
        _orm_row(transaction_date=date.today() - timedelta(days=10)),
    ]

    repo = InsidersRepository()
    rows = repo.get_recent("AAPL", days=30)
    assert len(rows) == 2
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:AAPL:insiders:30d"
    assert args[1] == 900  # TTL["insiders"]


def test_append_success_invalidates_pattern(mock_redis, mock_session):
    from app.repositories.insiders_repo import InsidersRepository

    mock_redis.scan_iter.return_value = iter(
        [b"company:AAPL:insiders:30d", b"company:AAPL:insiders:90d"]
    )
    # Post-commit lookup returns the newly inserted row.
    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        _orm_row(id=42)
    )

    repo = InsidersRepository()
    result = repo.append(
        InsiderTransaction(
            ticker="AAPL",
            insider_name="Timothy Cook",
            insider_title="CEO",
            transaction_date=date.today() - timedelta(days=1),
            transaction_type="SELL",
            shares=10000,
            price_per_share=Decimal("200.00"),
            form_type="Form 4",
        )
    )
    assert result is not None
    assert result.id == 42
    # Two keys matched the pattern — two deletes.
    assert mock_redis.delete.call_count == 2


def test_append_dedup_returns_none_no_invalidation(mock_redis, mock_session):
    """Duplicate filing (IntegrityError on commit) → returns None, no invalidate."""
    from sqlalchemy.exc import IntegrityError

    from app.repositories.insiders_repo import InsidersRepository

    mock_session.commit.side_effect = IntegrityError("dup", {}, Exception())

    repo = InsidersRepository()
    result = repo.append(
        InsiderTransaction(
            ticker="AAPL",
            insider_name="Timothy Cook",
            transaction_date=date.today(),
            transaction_type="SELL",
            shares=1000,
            form_type="Form 4",
        )
    )
    assert result is None
    # Nothing cached → invalidate_pattern must not run scan_iter.
    mock_redis.scan_iter.assert_not_called()
