"""Unit tests for :class:`CompanyRepository`.

These are unit tests — ``get_redis`` and ``get_session`` are patched at
the module level so they run without live Redis or Postgres. The
adversarial Tester will additionally exercise the repo against a real
one-off Postgres + Redis as part of the integration round-trip for
US-009 / US-010; see ``jojo/progress.txt`` for the environment pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.company import Company


@pytest.fixture
def mock_redis():
    with patch("app.repositories.base.get_redis") as gr:
        client = MagicMock()
        # Default: cache miss on every GET
        client.get.return_value = None
        gr.return_value = client
        yield client


@pytest.fixture
def mock_session():
    """Patch ``get_session`` inside company_repo to return a MagicMock.

    The mock session's ``query().filter_by().first()`` / ``.all()``
    chain is configured per test.
    """
    with patch("app.repositories.company_repo.get_session") as gs:
        session = MagicMock()
        gs.return_value = session
        yield session


def _orm_row(**kwargs):
    """Build an ORM-shaped MagicMock so ``Company.model_validate`` works.

    Pydantic's ``from_attributes=True`` path uses ``getattr`` on the
    source object, so a plain MagicMock with the right ``.ticker``,
    ``.name`` etc. attributes is indistinguishable from a real ORM row.
    """
    row = MagicMock()
    # Pydantic walks every field on the model when from_attributes=True
    # so we need to seed all fields — default to None for optional ones.
    defaults = {
        "ticker": "AAPL",
        "cik": None,
        "name": "Apple Inc.",
        "exchange": None,
        "sector": None,
        "industry": None,
        "country": None,
        "currency": None,
        "description": None,
        "website": None,
        "employee_count": None,
        "founded_year": None,
        "ipo_date": None,
        "is_active": True,
        "created_at": None,
        "updated_at": None,
        "delisted_at": None,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# get + cache-aside
# ---------------------------------------------------------------------------


def test_get_cache_miss_queries_db_and_populates_cache(mock_redis, mock_session):
    from app.repositories.company_repo import CompanyRepository

    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        _orm_row(ticker="AAPL", name="Apple Inc.")
    )

    repo = CompanyRepository()
    result = repo.get("aapl")

    assert result is not None
    assert result.ticker == "AAPL"
    assert result.name == "Apple Inc."
    # Cache miss → a SETEX must have happened with the master key.
    mock_redis.setex.assert_called_once()
    args, _ = mock_redis.setex.call_args
    assert args[0] == "company:AAPL:master"


def test_get_cache_hit_skips_db(mock_redis, mock_session):
    from app.repositories.company_repo import CompanyRepository

    cached = Company(ticker="AAPL", name="Apple Inc.").model_dump_json().encode()
    mock_redis.get.return_value = cached

    repo = CompanyRepository()
    result = repo.get("AAPL")

    assert result is not None and result.ticker == "AAPL"
    # DB must not be consulted on hit.
    mock_session.query.assert_not_called()


def test_get_missing_ticker_returns_none_and_does_not_cache(mock_redis, mock_session):
    from app.repositories.company_repo import CompanyRepository

    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    repo = CompanyRepository()
    result = repo.get("ZZZZ")
    assert result is None
    # Negative results must not populate Redis — avoid sticky misses.
    mock_redis.setex.assert_not_called()


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


def test_upsert_insert_path_invalidates_cache(mock_redis, mock_session):
    from app.repositories.company_repo import CompanyRepository

    # No existing row → insert path
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    # After commit+refresh, the session "has" the newly inserted row.
    # We simulate refresh() being a no-op and rely on the ORM row we add.
    added_rows = []

    def _add(row):
        added_rows.append(row)
        # Ensure Pydantic can model_validate() the object post-commit.
        # Fill in the fields model_validate will read.
        row.ticker = "AAPL"
        row.name = "Apple Inc."
        row.cik = None
        row.exchange = None
        row.sector = None
        row.industry = None
        row.country = None
        row.currency = None
        row.description = None
        row.website = None
        row.employee_count = None
        row.founded_year = None
        row.ipo_date = None
        row.is_active = True
        row.created_at = None
        row.updated_at = None
        row.delisted_at = None

    mock_session.add.side_effect = _add

    repo = CompanyRepository()
    c = Company(ticker="AAPL", name="Apple Inc.")
    result = repo.upsert(c)

    assert result.ticker == "AAPL"
    mock_session.commit.assert_called_once()
    # Cache invalidated after write.
    mock_redis.delete.assert_called_once_with("company:AAPL:master")


def test_upsert_update_path_mutates_existing_row_and_invalidates(
    mock_redis, mock_session
):
    from app.repositories.company_repo import CompanyRepository

    existing = _orm_row(ticker="AAPL", name="Apple Inc.")
    mock_session.query.return_value.filter_by.return_value.first.return_value = existing

    repo = CompanyRepository()
    updated = Company(ticker="AAPL", name="Apple Inc.", sector="Technology")
    result = repo.upsert(updated)

    # The ORM row was mutated in place; session.add was NOT called.
    assert existing.sector == "Technology"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_called_once()
    mock_redis.delete.assert_called_once_with("company:AAPL:master")
    assert result.sector == "Technology"


def test_upsert_then_get_reflects_update(mock_redis, mock_session):
    """Integration-flavored sequence: upsert → get should return the new value.

    Simulates the cache-aside invariant: after upsert invalidates the
    cache key, the subsequent get misses, queries the DB, and returns
    the updated row.
    """
    from app.repositories.company_repo import CompanyRepository

    existing = _orm_row(ticker="AAPL", name="Apple Inc.")
    mock_session.query.return_value.filter_by.return_value.first.return_value = existing

    repo = CompanyRepository()
    repo.upsert(Company(ticker="AAPL", name="Apple Inc.", sector="Technology"))

    # invalidate was called — simulate Redis now returning None for next GET
    mock_redis.get.return_value = None
    result = repo.get("AAPL")
    assert result is not None
    assert result.sector == "Technology"


# ---------------------------------------------------------------------------
# list_by_sector
# ---------------------------------------------------------------------------


def test_list_by_sector_returns_pydantic_models(mock_redis, mock_session):
    from app.repositories.company_repo import CompanyRepository

    mock_session.query.return_value.filter_by.return_value.all.return_value = [
        _orm_row(ticker="AAPL", name="Apple Inc.", sector="Technology"),
        _orm_row(ticker="MSFT", name="Microsoft Corp.", sector="Technology"),
    ]

    repo = CompanyRepository()
    rows = repo.list_by_sector("Technology")

    assert len(rows) == 2
    assert all(isinstance(r, Company) for r in rows)
    assert {r.ticker for r in rows} == {"AAPL", "MSFT"}
