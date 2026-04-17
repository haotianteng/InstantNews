"""CompanyService — parallel-fan-out aggregator for the 6 company-info domains.

Wires the repository layer (:mod:`app.repositories`) and the upstream
clients (:mod:`app.services.market_data`, :mod:`app.services.edgar_client`)
into a single ``get_full_profile(ticker)`` call that:

1. Fires 6 repo reads in parallel via ``ThreadPoolExecutor(max_workers=6)``.
2. On a cache+DB miss for any domain, acquires a per-(ticker, domain)
   Redis mutex (``lock:company:{TICKER}:{domain}``, SETNX + 30s TTL),
   fetches from upstream, persists via the repo's ``upsert`` / ``append``
   helper, and returns the freshly-fetched data.
3. If another process holds the mutex, the caller polls the same repo
   for up to 5s at 200ms intervals to pick up the lock-holder's result.
   If still empty, the domain is returned as ``None`` / ``[]`` and the
   aggregate's ``partial`` flag is set to ``True``.
4. Releases every lock in ``finally`` — even on exception.

This is the single entry point the ``GET /api/company/<ticker>/profile``
route (US-012) calls. The ``/api/market/<symbol>/*`` routes (US-013) still
call individual repos directly so they can preserve their legacy response
shapes during the 7-day dual-write soak.

Design notes
------------
* **Synchronous throughout.** The Flask app is sync; ``ThreadPoolExecutor``
  gives us 6-way parallelism on the I/O-bound repo reads without changing
  the call contract. A future async migration can swap to ``asyncio.gather``
  without touching the caller.
* **Defensive mapping.** Upstream dict → Pydantic model conversions all
  catch ``KeyError`` / ``ValueError`` / ``TypeError``. A malformed
  upstream payload degrades that single domain to ``partial=True``, not a
  500 for the whole request.
* **Sticky-negative avoidance preserved.** When the backfill can't find
  data upstream (``None`` from Polygon, empty list from EDGAR), the
  service returns the empty result without writing it to the repo's
  cache. Individual repos handle their own caching; we don't second-guess
  them.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, List, Optional, TypeVar

from app.cache.cache_keys import company_lock
from app.cache.redis_client import get_redis
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.competitors import Competitor
from app.models.financials import Financials
from app.models.fundamentals import Fundamentals
from app.models.insiders import InsiderTransaction
from app.models.institutions import InstitutionalHolder
from app.repositories.company_repo import CompanyRepository
from app.repositories.competitors_repo import CompetitorsRepository
from app.repositories.financials_repo import FinancialsRepository
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.repositories.insiders_repo import InsidersRepository
from app.repositories.institutions_repo import InstitutionsRepository
from app.services.edgar_client import EdgarClient
from app.services.market_data import PolygonClient

logger = logging.getLogger("signal.service.company")

MUTEX_TTL_SECONDS = 30
MUTEX_WAIT_SECONDS = 5.0
MUTEX_POLL_INTERVAL = 0.2
FETCH_TIMEOUT_SECONDS = 30

T = TypeVar("T")


def _is_empty(value: Any) -> bool:
    """Return True if ``value`` should be treated as a repo miss.

    Either ``None`` or an empty ``list``. A non-empty list is a
    legitimate "we have data" answer even if its contents are sparse.
    """
    if value is None:
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _to_decimal(val: Any) -> Optional[Decimal]:
    """Best-effort float / int / str → Decimal conversion."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _period_end_from(fiscal_period: Any, fiscal_year: Any) -> Optional[date]:
    """Derive a ``period_end`` ``date`` from Polygon's fiscal metadata.

    Polygon's flat financials response doesn't include ``period_end``
    directly — derive it from ``fiscal_year`` + ``fiscal_period``:

    * ``Q1`` → Mar 31  / ``Q2`` → Jun 30 / ``Q3`` → Sep 30
    * ``Q4`` / ``FY`` / ``annual`` → Dec 31

    Returns ``None`` if either field is missing or un-parseable — the
    caller treats that as "skip persist, but still surface the
    upstream payload" via the normal mapping path.
    """
    try:
        year = int(str(fiscal_year).strip())
    except (ValueError, TypeError):
        return None
    period = str(fiscal_period or "").upper().strip()
    if period == "Q1":
        return date(year, 3, 31)
    if period == "Q2":
        return date(year, 6, 30)
    if period == "Q3":
        return date(year, 9, 30)
    if period in ("Q4", "FY", "ANNUAL"):
        return date(year, 12, 31)
    return None


class CompanyService:
    """Parallel aggregator over the 6 company-info repositories."""

    def __init__(
        self,
        company_repo: Optional[CompanyRepository] = None,
        fundamentals_repo: Optional[FundamentalsRepository] = None,
        financials_repo: Optional[FinancialsRepository] = None,
        competitors_repo: Optional[CompetitorsRepository] = None,
        institutions_repo: Optional[InstitutionsRepository] = None,
        insiders_repo: Optional[InsidersRepository] = None,
        polygon: Optional[PolygonClient] = None,
        edgar: Optional[EdgarClient] = None,
    ) -> None:
        # Allow callers (tests) to inject mocks; default to real singletons.
        self.company_repo = company_repo or CompanyRepository()
        self.fundamentals_repo = fundamentals_repo or FundamentalsRepository()
        self.financials_repo = financials_repo or FinancialsRepository()
        self.competitors_repo = competitors_repo or CompetitorsRepository()
        self.institutions_repo = institutions_repo or InstitutionsRepository()
        self.insiders_repo = insiders_repo or InsidersRepository()
        self.polygon = polygon or PolygonClient()
        self.edgar = edgar or EdgarClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_full_profile(self, ticker: str) -> CompanyProfile:
        """Return the full :class:`CompanyProfile` for ``ticker``.

        Runs 6 domain fetches in parallel (``ThreadPoolExecutor``).
        Each per-domain future wraps both the cache-aside read and the
        on-demand backfill. A failure in one domain does not fail the
        whole request — it marks the aggregate ``partial=True`` and
        surfaces ``None`` / ``[]`` for that field.
        """
        up = ticker.upper()
        partial = False
        results: dict[str, Any] = {}
        start = time.monotonic()

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {
                "company": ex.submit(
                    self._fetch_with_backfill,
                    up,
                    "master",
                    self._load_company,
                    self._backfill_company,
                ),
                "fundamentals": ex.submit(
                    self._fetch_with_backfill,
                    up,
                    "fundamentals",
                    self._load_fundamentals,
                    self._backfill_fundamentals,
                ),
                "financials": ex.submit(
                    self._fetch_with_backfill,
                    up,
                    "financials",
                    self._load_financials,
                    self._backfill_financials,
                ),
                "competitors": ex.submit(
                    self._fetch_with_backfill,
                    up,
                    "competitors",
                    self._load_competitors,
                    self._backfill_competitors,
                ),
                "institutions": ex.submit(
                    self._fetch_with_backfill,
                    up,
                    "institutions",
                    self._load_institutions,
                    self._backfill_institutions,
                ),
                "insiders": ex.submit(
                    self._fetch_with_backfill,
                    up,
                    "insiders",
                    self._load_insiders,
                    self._backfill_insiders,
                ),
            }

            for name, fut in futures.items():
                try:
                    val = fut.result(timeout=FETCH_TIMEOUT_SECONDS)
                except Exception as e:
                    logger.warning(
                        "profile fetch failed ticker=%s domain=%s err=%s",
                        up, name, e,
                    )
                    val = None
                    partial = True
                results[name] = val
                if _is_empty(val):
                    # Missing scalar domains (company/fundamentals/financials)
                    # mean we couldn't serve that field — surface as partial.
                    # Empty list domains (competitors/institutions/insiders)
                    # are legitimate "no data" answers for unknown/new tickers
                    # but we still flag partial when the scalar "company"
                    # master row itself is missing below.
                    if name in ("company", "fundamentals", "financials"):
                        partial = True

        # Special-case: if we have ZERO signal at all — no master row and
        # no list items anywhere — this is a ghost ticker. The caller (the
        # /profile route) turns that into a 404.
        elapsed_ms = int((time.monotonic() - start) * 1000)
        any_scalar = any(
            results.get(k) is not None
            for k in ("company", "fundamentals", "financials")
        )
        any_list = any(
            isinstance(results.get(k), list) and len(results[k]) > 0
            for k in ("competitors", "institutions", "insiders")
        )
        if not any_scalar and not any_list:
            partial = True

        logger.info(
            "profile assembled ticker=%s partial=%s ms=%d",
            up, partial, elapsed_ms,
        )

        return CompanyProfile(
            company=results.get("company"),
            fundamentals=results.get("fundamentals"),
            latest_financials=results.get("financials"),
            competitors=results.get("competitors") or [],
            top_institutions=results.get("institutions") or [],
            recent_insiders=results.get("insiders") or [],
            partial=partial,
            fetched_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Core fetch-with-backfill machinery
    # ------------------------------------------------------------------

    def _fetch_with_backfill(
        self,
        ticker: str,
        domain: str,
        loader: Callable[[str], Any],
        backfill: Callable[[str], Any],
    ) -> Any:
        """Repo read; on miss, acquire mutex and backfill from upstream.

        The mutex is scoped to (ticker, domain) via a Redis SETNX key
        (``lock:company:{TICKER}:{domain}``) with a 30s TTL. If another
        caller holds the lock we poll the repo up to 5s at 200ms
        intervals for their result; if still empty we return the empty
        value and let the caller mark the aggregate partial.
        """
        t0 = time.monotonic()
        try:
            value = loader(ticker)
        except Exception as e:
            logger.warning(
                "repo load raised ticker=%s domain=%s err=%s",
                ticker, domain, e,
            )
            value = None

        if not _is_empty(value):
            logger.info(
                "profile domain=hit ticker=%s domain=%s ms=%d",
                ticker, domain, int((time.monotonic() - t0) * 1000),
            )
            return value

        # Cache+DB miss → take the mutex and fetch upstream.
        lock_key = company_lock(ticker, domain)
        acquired = False
        r = None
        try:
            try:
                r = get_redis()
                acquired = bool(
                    r.set(lock_key, b"1", nx=True, ex=MUTEX_TTL_SECONDS)
                )
            except Exception as e:
                logger.warning(
                    "redis mutex acquire failed ticker=%s domain=%s err=%s",
                    ticker, domain, e,
                )
                # Redis down → fall through to upstream directly. Same
                # semantics as "we got the lock" for a single caller;
                # thundering herd is unlikely when Redis is down anyway.
                acquired = True
                r = None

            if not acquired:
                # Another process owns the fetch — poll for their result.
                deadline = time.monotonic() + MUTEX_WAIT_SECONDS
                while time.monotonic() < deadline:
                    time.sleep(MUTEX_POLL_INTERVAL)
                    try:
                        v2 = loader(ticker)
                    except Exception:
                        v2 = None
                    if not _is_empty(v2):
                        logger.info(
                            "profile domain=lock_wait_hit ticker=%s domain=%s ms=%d",
                            ticker, domain, int((time.monotonic() - t0) * 1000),
                        )
                        return v2
                logger.info(
                    "profile domain=lock_timeout ticker=%s domain=%s ms=%d",
                    ticker, domain, int((time.monotonic() - t0) * 1000),
                )
                return value  # still empty → caller flags partial

            # We own the lock. Fetch + persist.
            try:
                fetched = backfill(ticker)
            except Exception as e:
                logger.warning(
                    "backfill raised ticker=%s domain=%s err=%s",
                    ticker, domain, e,
                )
                return value

            logger.info(
                "profile domain=cold_backfill ticker=%s domain=%s ms=%d",
                ticker, domain, int((time.monotonic() - t0) * 1000),
            )
            return fetched
        finally:
            if acquired and r is not None:
                try:
                    r.delete(lock_key)
                except Exception as e:
                    logger.warning(
                        "redis mutex release failed ticker=%s domain=%s err=%s",
                        ticker, domain, e,
                    )

    # ------------------------------------------------------------------
    # Loaders — repo reads (cache-aside already built in)
    # ------------------------------------------------------------------

    def _load_company(self, ticker: str) -> Optional[Company]:
        return self.company_repo.get(ticker)

    def _load_fundamentals(self, ticker: str) -> Optional[Fundamentals]:
        return self.fundamentals_repo.get(ticker)

    def _load_financials(self, ticker: str) -> Optional[Financials]:
        return self.financials_repo.get_latest(ticker)

    def _load_competitors(self, ticker: str) -> List[Competitor]:
        return self.competitors_repo.get_top(ticker, n=10)

    def _load_institutions(self, ticker: str) -> List[InstitutionalHolder]:
        return self.institutions_repo.get_top(ticker, n=20)

    def _load_insiders(self, ticker: str) -> List[InsiderTransaction]:
        return self.insiders_repo.get_recent(ticker, days=90)

    # ------------------------------------------------------------------
    # Backfillers — upstream fetch + persist
    # ------------------------------------------------------------------

    def _backfill_company(self, ticker: str) -> Optional[Company]:
        raw = self.polygon.get_ticker_details(ticker)
        if not raw:
            return None
        company = self._map_company(raw, ticker)
        if company is None:
            return None
        try:
            return self.company_repo.upsert(company)
        except Exception as e:
            logger.warning(
                "company upsert failed ticker=%s err=%s", ticker, e,
            )
            return company

    def _backfill_fundamentals(self, ticker: str) -> Optional[Fundamentals]:
        raw = self.polygon.get_ticker_details(ticker)
        if not raw:
            return None
        fund = self._map_fundamentals(raw, ticker)
        if fund is None:
            return None
        # Fundamentals has a FK to companies(ticker) — make sure the master
        # row exists before we upsert. Best-effort: call company backfill
        # sync if needed (it's cheap + shares the same Polygon payload).
        try:
            if self.company_repo.get(ticker) is None:
                mapped = self._map_company(raw, ticker)
                if mapped is not None:
                    self.company_repo.upsert(mapped)
            return self.fundamentals_repo.upsert(fund)
        except Exception as e:
            logger.warning(
                "fundamentals upsert failed ticker=%s err=%s", ticker, e,
            )
            return fund

    def _backfill_financials(self, ticker: str) -> Optional[Financials]:
        raw = self.polygon.get_financials(ticker)
        if not raw:
            return None
        fin = self._map_financials(raw, ticker)
        if fin is None:
            # Upstream returned a payload but it lacks period_end/fiscal_year
            # — we can't persist to the normalized table. Nothing to serve.
            return None
        try:
            if self.company_repo.get(ticker) is None:
                # Best-effort master-row bootstrap so the FK doesn't blow up.
                details = self.polygon.get_ticker_details(ticker)
                if details:
                    mapped = self._map_company(details, ticker)
                    if mapped is not None:
                        self.company_repo.upsert(mapped)
            return self.financials_repo.append(fin)
        except Exception as e:
            logger.warning(
                "financials append failed ticker=%s err=%s", ticker, e,
            )
            return fin

    def _backfill_competitors(self, ticker: str) -> List[Competitor]:
        raw = self.polygon.get_related_companies(ticker)
        if not raw:
            return []
        comps = self._map_competitors(raw, ticker)
        if not comps:
            return []
        try:
            if self.company_repo.get(ticker) is None:
                details = self.polygon.get_ticker_details(ticker)
                if details:
                    mapped = self._map_company(details, ticker)
                    if mapped is not None:
                        self.company_repo.upsert(mapped)
            return self.competitors_repo.upsert_batch(ticker, comps)
        except Exception as e:
            logger.warning(
                "competitors upsert failed ticker=%s err=%s", ticker, e,
            )
            return comps

    def _backfill_institutions(self, ticker: str) -> List[InstitutionalHolder]:
        raw = self.edgar.get_institutional_holders(ticker)
        if not raw:
            return []
        holders = self._map_institutions(raw, ticker)
        if not holders:
            return []
        try:
            if self.company_repo.get(ticker) is None:
                details = self.polygon.get_ticker_details(ticker)
                if details:
                    mapped = self._map_company(details, ticker)
                    if mapped is not None:
                        self.company_repo.upsert(mapped)
            self.institutions_repo.append_batch(holders)
        except Exception as e:
            logger.warning(
                "institutions append_batch failed ticker=%s err=%s",
                ticker, e,
            )
        return holders[:20]

    def _backfill_insiders(self, ticker: str) -> List[InsiderTransaction]:
        raw = self.edgar.get_insider_transactions(ticker)
        if not raw:
            return []
        txns = self._map_insiders(raw, ticker)
        if not txns:
            return []
        try:
            if self.company_repo.get(ticker) is None:
                details = self.polygon.get_ticker_details(ticker)
                if details:
                    mapped = self._map_company(details, ticker)
                    if mapped is not None:
                        self.company_repo.upsert(mapped)
            for t in txns:
                try:
                    self.insiders_repo.append(t)
                except Exception:
                    # Per-row dedup failure is non-fatal.
                    pass
        except Exception as e:
            logger.warning(
                "insiders append failed ticker=%s err=%s", ticker, e,
            )
        # Return the most-recent 10 by transaction_date (descending).
        txns.sort(key=lambda t: t.transaction_date, reverse=True)
        return txns[:10]

    # ------------------------------------------------------------------
    # Mapping helpers — upstream dict → Pydantic model
    # ------------------------------------------------------------------

    def _map_company(
        self, raw: dict[str, Any], ticker: str,
    ) -> Optional[Company]:
        try:
            return Company(
                ticker=ticker.upper(),
                name=str(raw.get("name") or ticker.upper()),
                description=raw.get("description") or None,
                website=raw.get("homepage_url") or None,
                sector=raw.get("sector") or None,
            )
        except Exception as e:
            logger.warning(
                "map company failed ticker=%s err=%s", ticker, e,
            )
            return None

    def _map_fundamentals(
        self, raw: dict[str, Any], ticker: str,
    ) -> Optional[Fundamentals]:
        try:
            market_cap = raw.get("market_cap")
            try:
                market_cap_int = int(market_cap) if market_cap is not None else None
            except (ValueError, TypeError):
                market_cap_int = None
            return Fundamentals(
                ticker=ticker.upper(),
                market_cap=market_cap_int,
            )
        except Exception as e:
            logger.warning(
                "map fundamentals failed ticker=%s err=%s", ticker, e,
            )
            return None

    def _map_financials(
        self, raw: dict[str, Any], ticker: str,
    ) -> Optional[Financials]:
        try:
            fiscal_period = raw.get("fiscal_period")
            fiscal_year = raw.get("fiscal_year")
            period_end = _period_end_from(fiscal_period, fiscal_year)
            if period_end is None:
                return None
            try:
                fy_int = int(str(fiscal_year).strip())
            except (ValueError, TypeError):
                return None
            period_type = str(fiscal_period or "").upper().strip() or "Q4"
            revenue = raw.get("revenue")
            net_income = raw.get("net_income")
            eps = _to_decimal(raw.get("eps"))
            return Financials(
                ticker=ticker.upper(),
                period_end=period_end,
                period_type=period_type,
                fiscal_year=fy_int,
                revenue=int(revenue) if revenue is not None else None,
                net_income=int(net_income) if net_income is not None else None,
                eps_basic=eps,
                source="polygon",
            )
        except Exception as e:
            logger.warning(
                "map financials failed ticker=%s err=%s", ticker, e,
            )
            return None

    def _map_competitors(
        self, raw: list[dict[str, Any]], ticker: str,
    ) -> List[Competitor]:
        up = ticker.upper()
        out: List[Competitor] = []
        for idx, item in enumerate(raw or []):
            sym = (item.get("symbol") or "").strip().upper()
            if not sym or sym == up:
                continue
            try:
                # Polygon's related-companies returns ranked order; synthesize
                # a 1.0 → 0.1 descending similarity so top-N ordering is
                # preserved by the repo's ``similarity_score DESC`` query.
                score = Decimal(str(max(0.1, 1.0 - idx * 0.1))).quantize(
                    Decimal("0.0001")
                )
                out.append(Competitor(
                    ticker=up,
                    competitor_ticker=sym,
                    similarity_score=score,
                    source="polygon",
                ))
            except Exception:
                continue
        return out

    def _map_institutions(
        self, raw: list[dict[str, Any]], ticker: str,
    ) -> List[InstitutionalHolder]:
        up = ticker.upper()
        out: List[InstitutionalHolder] = []
        for item in raw or []:
            try:
                report_date_raw = item.get("report_date")
                if isinstance(report_date_raw, str):
                    # Parse ISO yyyy-mm-dd; accept prefix on longer strings.
                    report_date = date.fromisoformat(report_date_raw[:10])
                elif isinstance(report_date_raw, date):
                    report_date = report_date_raw
                else:
                    continue
                shares_held_raw = item.get("shares_held")
                value_raw = item.get("value")
                out.append(InstitutionalHolder(
                    ticker=up,
                    institution_name=item.get("institution_name") or None,
                    report_date=report_date,
                    shares_held=(
                        int(shares_held_raw)
                        if shares_held_raw is not None
                        else None
                    ),
                    market_value=(
                        int(value_raw) if value_raw is not None else None
                    ),
                ))
            except Exception:
                continue
        return out

    def _map_insiders(
        self, raw: list[dict[str, Any]], ticker: str,
    ) -> List[InsiderTransaction]:
        up = ticker.upper()
        out: List[InsiderTransaction] = []
        for item in raw or []:
            try:
                txn_date_raw = (
                    item.get("transaction_date")
                    or item.get("filing_date")
                )
                if isinstance(txn_date_raw, str):
                    txn_date = date.fromisoformat(txn_date_raw[:10])
                elif isinstance(txn_date_raw, date):
                    txn_date = txn_date_raw
                else:
                    continue
                filing_date_raw = item.get("filing_date")
                if isinstance(filing_date_raw, str) and filing_date_raw:
                    try:
                        filing_date: Optional[date] = date.fromisoformat(
                            filing_date_raw[:10]
                        )
                    except ValueError:
                        filing_date = None
                elif isinstance(filing_date_raw, date):
                    filing_date = filing_date_raw
                else:
                    filing_date = None
                shares_raw = item.get("shares")
                total_value_raw = item.get("total_value")
                out.append(InsiderTransaction(
                    ticker=up,
                    insider_name=item.get("insider_name") or None,
                    insider_title=item.get("title") or None,
                    transaction_date=txn_date,
                    transaction_type=item.get("transaction_type") or None,
                    shares=(
                        int(shares_raw)
                        if shares_raw is not None
                        else None
                    ),
                    price_per_share=_to_decimal(item.get("price_per_share")),
                    total_value=(
                        int(total_value_raw)
                        if total_value_raw is not None
                        else None
                    ),
                    shares_owned_after=(
                        int(item["shares_held_after"])
                        if item.get("shares_held_after") is not None
                        else None
                    ),
                    filing_date=filing_date,
                    form_type="4",
                ))
            except Exception:
                continue
        return out
