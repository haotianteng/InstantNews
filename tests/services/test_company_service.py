"""Unit tests for :class:`app.services.company_service.CompanyService`.

These tests exercise the 5 cases mandated by US-011's ``test_assertions``
without hitting live Redis / Postgres / Polygon / EDGAR:

(a) all 6 fields populated when data exists in cache/DB
(b) graceful degradation when one repo raises AND upstream also fails
(c) parallel execution: repo reads with 100ms sleep return in <200ms
(d) on-demand backfill: empty repo → upstream returns data → repo
    upsert_batch called and data surfaced
(e) mutex: 5 concurrent threads → upstream called exactly once

All repos are injected via constructor kwargs (the service supports this
explicitly for testability) and the Redis client is patched at the
``app.services.company_service.get_redis`` module symbol.
"""

from __future__ import annotations

import threading
import time
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.company import Company
from app.models.competitors import Competitor
from app.models.financials import Financials
from app.models.fundamentals import Fundamentals
from app.models.insiders import InsiderTransaction
from app.models.institutions import InstitutionalHolder


def _fake_redis_always_acquires() -> MagicMock:
    """A Redis mock whose ``set(..., nx=True, ex=...)`` always returns True."""
    r = MagicMock()
    r.set.return_value = True
    r.delete.return_value = 1
    return r


def _build_service(**overrides):
    """Build a CompanyService with all six repos + clients mocked."""
    from app.services.company_service import CompanyService

    defaults = dict(
        company_repo=MagicMock(),
        fundamentals_repo=MagicMock(),
        financials_repo=MagicMock(),
        competitors_repo=MagicMock(),
        institutions_repo=MagicMock(),
        insiders_repo=MagicMock(),
        polygon=MagicMock(),
        edgar=MagicMock(),
    )
    # Default repo returns — empty. Individual tests override.
    defaults["company_repo"].get.return_value = None
    defaults["fundamentals_repo"].get.return_value = None
    defaults["financials_repo"].get_latest.return_value = None
    defaults["competitors_repo"].get_top.return_value = []
    defaults["institutions_repo"].get_top.return_value = []
    defaults["insiders_repo"].get_recent.return_value = []
    # Default upstream returns — empty so backfill is a no-op.
    defaults["polygon"].get_ticker_details.return_value = None
    defaults["polygon"].get_financials.return_value = None
    defaults["polygon"].get_related_companies.return_value = None
    defaults["edgar"].get_institutional_holders.return_value = None
    defaults["edgar"].get_insider_transactions.return_value = None
    defaults.update(overrides)
    return CompanyService(**defaults)


# ---------------------------------------------------------------------------
# (a) all 6 fields populated from cache
# ---------------------------------------------------------------------------


def test_all_six_fields_populated_from_cache_no_backfill():
    """AC-a: when every repo returns data, service surfaces it and does
    NOT touch upstream clients."""

    company = Company(ticker="AAPL", name="Apple Inc.")
    fundamentals = Fundamentals(ticker="AAPL", market_cap=3_000_000_000_000)
    financials = Financials(
        ticker="AAPL", period_end=date(2025, 9, 30),
        period_type="Q3", fiscal_year=2025, revenue=90000,
    )
    competitor = Competitor(
        ticker="AAPL", competitor_ticker="MSFT",
        similarity_score=Decimal("0.9"),
    )
    holder = InstitutionalHolder(
        ticker="AAPL", report_date=date(2025, 6, 30),
        institution_name="Vanguard", shares_held=100,
    )
    insider = InsiderTransaction(
        ticker="AAPL", transaction_date=date(2025, 9, 1),
        insider_name="Tim Cook", transaction_type="SELL", shares=1000,
    )

    svc = _build_service()
    svc.company_repo.get.return_value = company
    svc.fundamentals_repo.get.return_value = fundamentals
    svc.financials_repo.get_latest.return_value = financials
    svc.competitors_repo.get_top.return_value = [competitor]
    svc.institutions_repo.get_top.return_value = [holder]
    svc.insiders_repo.get_recent.return_value = [insider]

    with patch("app.services.company_service.get_redis",
               return_value=_fake_redis_always_acquires()):
        profile = svc.get_full_profile("AAPL")

    assert profile.company is not None and profile.company.ticker == "AAPL"
    assert profile.fundamentals is not None
    assert profile.fundamentals.market_cap == 3_000_000_000_000
    assert profile.latest_financials is not None
    assert len(profile.competitors) == 1
    assert profile.competitors[0].competitor_ticker == "MSFT"
    assert len(profile.top_institutions) == 1
    assert len(profile.recent_insiders) == 1
    assert profile.partial is False

    # Zero upstream calls — every domain was a cache/DB hit.
    svc.polygon.get_ticker_details.assert_not_called()
    svc.polygon.get_financials.assert_not_called()
    svc.polygon.get_related_companies.assert_not_called()
    svc.edgar.get_institutional_holders.assert_not_called()
    svc.edgar.get_insider_transactions.assert_not_called()


# ---------------------------------------------------------------------------
# (b) graceful degradation: one repo raises + upstream fails → partial=True
# ---------------------------------------------------------------------------


def test_graceful_degradation_marks_partial_when_repo_raises_and_upstream_fails():
    company = Company(ticker="AAPL", name="Apple Inc.")
    fundamentals = Fundamentals(ticker="AAPL", market_cap=1_000_000_000_000)

    svc = _build_service()
    svc.company_repo.get.return_value = company
    svc.fundamentals_repo.get.return_value = fundamentals
    # Financials repo raises unconditionally.
    svc.financials_repo.get_latest.side_effect = RuntimeError("db boom")
    # Upstream fetch also returns None.
    svc.polygon.get_financials.return_value = None
    # Other lists empty → also trigger backfill attempts which return []
    svc.competitors_repo.get_top.return_value = [
        Competitor(
            ticker="AAPL", competitor_ticker="MSFT",
            similarity_score=Decimal("0.9"),
        ),
    ]
    svc.institutions_repo.get_top.return_value = [
        InstitutionalHolder(
            ticker="AAPL", report_date=date(2025, 6, 30),
            institution_name="Vanguard", shares_held=100,
        ),
    ]
    svc.insiders_repo.get_recent.return_value = [
        InsiderTransaction(
            ticker="AAPL", transaction_date=date(2025, 9, 1),
            insider_name="Tim Cook",
        ),
    ]

    with patch("app.services.company_service.get_redis",
               return_value=_fake_redis_always_acquires()):
        profile = svc.get_full_profile("AAPL")

    assert profile.company is not None
    assert profile.fundamentals is not None
    assert profile.latest_financials is None  # the failed domain
    assert profile.partial is True


# ---------------------------------------------------------------------------
# (c) parallel execution: 6 × 100ms sleep → total <200ms
# ---------------------------------------------------------------------------


def test_fan_out_is_parallel_total_time_under_200ms():
    """AC-c: six 100ms sleeps, run serially that's 600ms; with 6 workers
    it must be <200ms (leaves ample margin for thread startup jitter)."""

    def slow_get(_ticker):
        time.sleep(0.1)
        return Company(ticker="AAPL", name="Apple Inc.")

    def slow_fundamentals(_ticker):
        time.sleep(0.1)
        return Fundamentals(ticker="AAPL")

    def slow_financials(_ticker):
        time.sleep(0.1)
        return Financials(
            ticker="AAPL", period_end=date(2025, 9, 30),
            period_type="Q3", fiscal_year=2025,
        )

    def slow_competitors(_ticker, n=10):
        time.sleep(0.1)
        return [Competitor(
            ticker="AAPL", competitor_ticker="MSFT",
            similarity_score=Decimal("0.9"),
        )]

    def slow_institutions(_ticker, n=20, as_of=None):
        time.sleep(0.1)
        return [InstitutionalHolder(
            ticker="AAPL", report_date=date(2025, 6, 30),
            institution_name="Vanguard",
        )]

    def slow_insiders(_ticker, days=90):
        time.sleep(0.1)
        return [InsiderTransaction(
            ticker="AAPL", transaction_date=date(2025, 9, 1),
            insider_name="Tim Cook",
        )]

    svc = _build_service()
    svc.company_repo.get.side_effect = slow_get
    svc.fundamentals_repo.get.side_effect = slow_fundamentals
    svc.financials_repo.get_latest.side_effect = slow_financials
    svc.competitors_repo.get_top.side_effect = slow_competitors
    svc.institutions_repo.get_top.side_effect = slow_institutions
    svc.insiders_repo.get_recent.side_effect = slow_insiders

    with patch("app.services.company_service.get_redis",
               return_value=_fake_redis_always_acquires()):
        t0 = time.monotonic()
        profile = svc.get_full_profile("AAPL")
        elapsed = time.monotonic() - t0

    assert profile.company is not None
    # Serial would be ~600ms; parallel with 6 workers should be ~100ms +
    # small overhead. 200ms gives generous room for GC / executor startup.
    assert elapsed < 0.2, f"expected <200ms parallel exec, got {elapsed * 1000:.0f}ms"


# ---------------------------------------------------------------------------
# (d) on-demand backfill: empty DB + upstream data → repo upsert called
# ---------------------------------------------------------------------------


def test_backfill_persists_competitors_on_cache_miss():
    """AC-d: empty competitors repo → Polygon returns competitors →
    service returns them AND competitors_repo.upsert_batch was called
    with ticker='AAPL'."""

    svc = _build_service()
    # Minimal AAPL master row so the FK bootstrap inside the service is a no-op.
    svc.company_repo.get.return_value = Company(ticker="AAPL", name="Apple Inc.")
    # Keep other repos populated so the test is focused on competitors.
    svc.fundamentals_repo.get.return_value = Fundamentals(
        ticker="AAPL", market_cap=1,
    )
    svc.financials_repo.get_latest.return_value = Financials(
        ticker="AAPL", period_end=date(2025, 9, 30),
        period_type="Q3", fiscal_year=2025,
    )
    svc.institutions_repo.get_top.return_value = [
        InstitutionalHolder(
            ticker="AAPL", report_date=date(2025, 6, 30),
            institution_name="V",
        ),
    ]
    svc.insiders_repo.get_recent.return_value = [
        InsiderTransaction(
            ticker="AAPL", transaction_date=date(2025, 9, 1),
        ),
    ]

    # Competitors cold — repo empty, Polygon returns 2 related tickers.
    svc.competitors_repo.get_top.return_value = []
    svc.polygon.get_related_companies.return_value = [
        {"symbol": "MSFT", "name": "Microsoft", "market_cap": 3e12},
        {"symbol": "GOOG", "name": "Alphabet", "market_cap": 2e12},
    ]
    # upsert_batch echo-returns the Pydantic list.
    def _upsert_batch(ticker, comps):
        return comps
    svc.competitors_repo.upsert_batch.side_effect = _upsert_batch

    with patch("app.services.company_service.get_redis",
               return_value=_fake_redis_always_acquires()):
        profile = svc.get_full_profile("AAPL")

    # Competitors surface through the profile.
    assert len(profile.competitors) == 2
    syms = {c.competitor_ticker for c in profile.competitors}
    assert syms == {"MSFT", "GOOG"}

    # upsert_batch was called with ticker='AAPL'.
    svc.competitors_repo.upsert_batch.assert_called_once()
    call_args = svc.competitors_repo.upsert_batch.call_args
    assert call_args.args[0] == "AAPL"
    passed_comps = call_args.args[1]
    assert {c.competitor_ticker for c in passed_comps} == {"MSFT", "GOOG"}


# ---------------------------------------------------------------------------
# (e) mutex behavior: 5 concurrent threads → upstream called exactly once
# ---------------------------------------------------------------------------


class _FakeRedisMutex:
    """Redis mock implementing SETNX semantics for the mutex test.

    The first caller to ``set(key, val, nx=True)`` returns True and the
    key is considered held; subsequent callers get False until the
    holder ``delete``s the key.
    """

    def __init__(self):
        self._store: dict[bytes, bytes] = {}
        self._lock = threading.Lock()

    def set(self, key, value, nx=False, ex=None):
        k = key if isinstance(key, bytes) else str(key).encode()
        with self._lock:
            if nx and k in self._store:
                return False
            self._store[k] = value if isinstance(value, bytes) else str(value).encode()
            return True

    def delete(self, key):
        k = key if isinstance(key, bytes) else str(key).encode()
        with self._lock:
            return 1 if self._store.pop(k, None) is not None else 0


def test_mutex_ensures_upstream_called_exactly_once_for_5_concurrent_threads():
    """AC-e: 5 concurrent ``get_full_profile`` calls for the same ticker
    with empty cache+DB should trigger exactly one Polygon related-companies
    call (the one that holds the mutex) — the other 4 wait, poll the repo,
    and eventually pick up the persisted result."""

    fake_redis = _FakeRedisMutex()

    # Shared state the fake repo + upstream client close over.
    stored_competitors: list[Competitor] = []
    upstream_call_count = threading.Event()  # just a flag
    upstream_calls = {"n": 0}
    upstream_lock = threading.Lock()

    # Fake competitors_repo.get_top — returns whatever is in stored_competitors.
    def fake_get_top(ticker, n=10):
        # Snapshot — return a copy so caller mutations don't affect.
        return list(stored_competitors)

    def fake_upsert_batch(ticker, comps):
        stored_competitors.extend(comps)
        return list(stored_competitors)

    # Fake Polygon.get_related_companies — sleeps 1s to widen the window
    # where concurrent callers observe the held lock.
    def slow_polygon_related(symbol):
        with upstream_lock:
            upstream_calls["n"] += 1
        time.sleep(1.0)
        return [{"symbol": "MSFT", "name": "Microsoft", "market_cap": 3e12}]

    svc = _build_service()
    # Every other domain short-circuits via cache so only competitors races.
    svc.company_repo.get.return_value = Company(ticker="XYZ", name="Xyz Inc.")
    svc.fundamentals_repo.get.return_value = Fundamentals(
        ticker="XYZ", market_cap=1,
    )
    svc.financials_repo.get_latest.return_value = Financials(
        ticker="XYZ", period_end=date(2025, 9, 30),
        period_type="Q3", fiscal_year=2025,
    )
    svc.institutions_repo.get_top.return_value = [
        InstitutionalHolder(
            ticker="XYZ", report_date=date(2025, 6, 30),
            institution_name="V",
        ),
    ]
    svc.insiders_repo.get_recent.return_value = [
        InsiderTransaction(
            ticker="XYZ", transaction_date=date(2025, 9, 1),
        ),
    ]
    svc.competitors_repo.get_top.side_effect = fake_get_top
    svc.competitors_repo.upsert_batch.side_effect = fake_upsert_batch
    svc.polygon.get_related_companies.side_effect = slow_polygon_related

    results: list = []
    errors: list = []

    def worker():
        try:
            with patch(
                "app.services.company_service.get_redis",
                return_value=fake_redis,
            ):
                p = svc.get_full_profile("XYZ")
                results.append(p)
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"worker errors: {errors}"
    assert len(results) == 5
    # The core invariant: upstream was hit exactly once.
    assert upstream_calls["n"] == 1, (
        f"expected exactly 1 upstream call, got {upstream_calls['n']}"
    )


# ---------------------------------------------------------------------------
# Aggregate schema sanity
# ---------------------------------------------------------------------------


def test_company_profile_fields_include_all_required_keys():
    """US-011 AC: ``CompanyProfile`` exposes the 6 domain fields plus
    ``partial`` + ``fetched_at``."""
    from app.models.company_profile import CompanyProfile

    fields = set(CompanyProfile.model_fields.keys())
    required = {
        "company", "fundamentals", "latest_financials",
        "competitors", "top_institutions", "recent_insiders",
        "partial", "fetched_at",
    }
    assert required <= fields
