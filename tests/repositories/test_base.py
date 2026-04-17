"""Unit tests for ``BaseRepository`` cache-aside behavior.

The Redis client is mocked at the module level so these tests can run
without a live Redis. Each test case exercises one branch of the
cache-aside state machine:

* cache HIT  → DB loader must not be called
* cache MISS → DB loader runs and the result is written back via ``SETEX``
* Redis ERR  → DB loader runs (Redis is non-critical per spec §US-008)

The tests deliberately use a minimal Pydantic model defined inline so
they don't couple to any real domain schema.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.repositories.base import BaseRepository


class _T(BaseModel):
    """Minimal Pydantic model for testing cache round-trips."""

    ticker: str
    value: int = 0


@pytest.fixture
def mock_redis():
    """Patch ``get_redis`` inside base.py to return a MagicMock."""
    with patch("app.repositories.base.get_redis") as gr:
        client = MagicMock()
        gr.return_value = client
        yield client


# ---------------------------------------------------------------------------
# cached_get
# ---------------------------------------------------------------------------


def test_cached_get_cache_hit_skips_db_loader(mock_redis):
    cached_payload = _T(ticker="AAPL", value=42).model_dump_json().encode()
    mock_redis.get.return_value = cached_payload

    repo = BaseRepository(_T)
    db_loader = MagicMock()

    result = repo.cached_get("company:AAPL:master", ttl=60, db_loader=db_loader)

    assert result == _T(ticker="AAPL", value=42)
    db_loader.assert_not_called()
    mock_redis.setex.assert_not_called()


def test_cached_get_cache_miss_calls_db_loader_and_populates(mock_redis):
    mock_redis.get.return_value = None
    loaded = _T(ticker="MSFT", value=7)

    repo = BaseRepository(_T)
    result = repo.cached_get(
        "company:MSFT:master", ttl=120, db_loader=lambda: loaded
    )

    assert result == loaded
    mock_redis.setex.assert_called_once()
    # Inspect args: (key, ttl, payload)
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:MSFT:master"
    assert args[1] == 120
    # Payload is serialized JSON for the model
    assert b"MSFT" in args[2].encode() if isinstance(args[2], str) else b"MSFT" in args[2]


def test_cached_get_cache_miss_none_result_does_not_cache(mock_redis):
    """A loader that returns None must not populate Redis (avoids sticky negatives)."""
    mock_redis.get.return_value = None
    repo = BaseRepository(_T)
    result = repo.cached_get(
        "company:ZZZ:master", ttl=60, db_loader=lambda: None
    )
    assert result is None
    mock_redis.setex.assert_not_called()


def test_cached_get_redis_exception_falls_through_to_db_loader(mock_redis):
    mock_redis.get.side_effect = RuntimeError("boom")
    loaded = _T(ticker="GOOG", value=99)

    repo = BaseRepository(_T)
    result = repo.cached_get(
        "company:GOOG:master", ttl=60, db_loader=lambda: loaded
    )

    # Even though GET raised, the DB loader still ran and returned the value.
    assert result == loaded
    # setex may or may not succeed; don't over-specify — just verify we got data.


def test_cached_get_redis_setex_exception_is_swallowed(mock_redis):
    mock_redis.get.return_value = None
    mock_redis.setex.side_effect = RuntimeError("write failed")
    loaded = _T(ticker="NFLX", value=1)

    repo = BaseRepository(_T)
    # Must not raise — Redis is non-critical.
    result = repo.cached_get(
        "company:NFLX:master", ttl=60, db_loader=lambda: loaded
    )
    assert result == loaded


# ---------------------------------------------------------------------------
# cached_get_list
# ---------------------------------------------------------------------------


def test_cached_get_list_cache_hit_parses_each_item(mock_redis):
    import json

    payload = json.dumps(
        [{"ticker": "AAPL", "value": 1}, {"ticker": "MSFT", "value": 2}]
    )
    mock_redis.get.return_value = payload.encode()

    repo = BaseRepository(_T)
    db_loader = MagicMock()
    result = repo.cached_get_list(
        "company:sector:tech", ttl=60, db_loader=db_loader
    )

    assert result == [_T(ticker="AAPL", value=1), _T(ticker="MSFT", value=2)]
    db_loader.assert_not_called()


def test_cached_get_list_cache_miss_populates_redis(mock_redis):
    mock_redis.get.return_value = None
    items = [_T(ticker="AAPL", value=1), _T(ticker="MSFT", value=2)]

    repo = BaseRepository(_T)
    result = repo.cached_get_list(
        "company:sector:tech", ttl=60, db_loader=lambda: items
    )

    assert result == items
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:sector:tech"
    assert args[1] == 60


def test_cached_get_list_redis_exception_falls_through(mock_redis):
    mock_redis.get.side_effect = RuntimeError("boom")
    items = [_T(ticker="AAPL", value=1)]

    repo = BaseRepository(_T)
    result = repo.cached_get_list(
        "company:sector:tech", ttl=60, db_loader=lambda: items
    )
    assert result == items


# ---------------------------------------------------------------------------
# invalidate / invalidate_pattern
# ---------------------------------------------------------------------------


def test_invalidate_deletes_key(mock_redis):
    repo = BaseRepository(_T)
    repo.invalidate("company:AAPL:master")
    mock_redis.delete.assert_called_once_with("company:AAPL:master")


def test_invalidate_swallows_exception(mock_redis):
    mock_redis.delete.side_effect = RuntimeError("boom")
    repo = BaseRepository(_T)
    # Must not raise.
    repo.invalidate("company:AAPL:master")


def test_invalidate_pattern_scans_and_deletes(mock_redis):
    mock_redis.scan_iter.return_value = iter(
        [b"company:AAPL:competitors:top10", b"company:AAPL:competitors:top20"]
    )
    repo = BaseRepository(_T)
    n = repo.invalidate_pattern("company:AAPL:competitors:top*")
    assert n == 2
    assert mock_redis.delete.call_count == 2


def test_invalidate_pattern_swallows_exception(mock_redis):
    mock_redis.scan_iter.side_effect = RuntimeError("boom")
    repo = BaseRepository(_T)
    # Must not raise; returns 0.
    assert repo.invalidate_pattern("company:AAPL:*") == 0
