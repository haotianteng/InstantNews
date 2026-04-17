"""Unit tests for :class:`CompetitorsRepository`."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.competitors import Competitor


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
    with patch("app.repositories.competitors_repo.get_session") as gs:
        session = MagicMock()
        gs.return_value = session
        yield session


def _orm_row(**kwargs):
    row = MagicMock()
    defaults = {
        "ticker": "AAPL",
        "competitor_ticker": "MSFT",
        "similarity_score": Decimal("0.800"),
        "source": "polygon",
        "updated_at": None,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def test_get_top_cache_miss_queries_db(mock_redis, mock_session):
    from app.repositories.competitors_repo import CompetitorsRepository

    q = mock_session.query.return_value
    q.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
        _orm_row(competitor_ticker="MSFT", similarity_score=Decimal("0.900")),
        _orm_row(competitor_ticker="GOOG", similarity_score=Decimal("0.800")),
    ]

    repo = CompetitorsRepository()
    rows = repo.get_top("AAPL", n=2)
    assert len(rows) == 2
    assert rows[0].competitor_ticker == "MSFT"
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:AAPL:competitors:top2"
    assert args[1] == 86400


def test_get_top_cache_hit_skips_db(mock_redis, mock_session):
    import json

    from app.repositories.competitors_repo import CompetitorsRepository

    payload = json.dumps(
        [
            {
                "ticker": "AAPL",
                "competitor_ticker": "MSFT",
                "similarity_score": "0.900",
                "source": "polygon",
                "updated_at": None,
            }
        ]
    )
    mock_redis.get.return_value = payload.encode()

    repo = CompetitorsRepository()
    rows = repo.get_top("AAPL", n=10)
    assert len(rows) == 1 and rows[0].competitor_ticker == "MSFT"
    mock_session.query.assert_not_called()


def test_upsert_batch_replaces_and_invalidates_pattern(mock_redis, mock_session):
    from app.repositories.competitors_repo import CompetitorsRepository

    # After commit+requery, return the newly inserted competitors.
    q = mock_session.query.return_value
    q.filter_by.return_value.order_by.return_value.all.return_value = [
        _orm_row(competitor_ticker="MSFT", similarity_score=Decimal("0.900")),
        _orm_row(competitor_ticker="GOOG", similarity_score=Decimal("0.800")),
    ]

    # SCAN returns two cached top-N variants to be deleted.
    mock_redis.scan_iter.return_value = iter(
        [b"company:AAPL:competitors:top10", b"company:AAPL:competitors:top20"]
    )

    repo = CompetitorsRepository()
    result = repo.upsert_batch(
        "AAPL",
        [
            Competitor(ticker="AAPL", competitor_ticker="MSFT", similarity_score=Decimal("0.900")),
            Competitor(ticker="AAPL", competitor_ticker="GOOG", similarity_score=Decimal("0.800")),
        ],
    )
    assert len(result) == 2
    # The filter_by(ticker=AAPL).delete() call was issued.
    q.filter_by.return_value.delete.assert_called_once()
    mock_session.commit.assert_called()
    # Pattern-invalidation fired twice (one per scan_iter result).
    assert mock_redis.delete.call_count == 2
