"""US-015 — EDGAR ingesters (10-Q/K, 13F, Form 4).

Three ticker-scoped functions called by the worker scheduler. Each one:

* fetches via the project-wide :class:`EdgarClient` singleton (its
  internal 10 req/sec throttle is respected),
* maps the upstream payload to Pydantic models,
* writes via the corresponding repository's idempotent ``append`` /
  ``upsert`` / ``append_batch`` helper (which handles Redis invalidation),
* returns a per-ticker ``{ticker: rows_written}`` dict.

These functions never mutate ``status`` directly; the scheduler wrapper
in :mod:`app.worker` records job-level success/failure into the audit
log.

10-Q / 10-K → ``company_financials``
------------------------------------
The current :class:`EdgarClient` does not yet expose a 10-Q/K parser. We
fall back to Polygon's ``vX/reference/financials`` endpoint via the
existing :class:`PolygonClient` (already used by the dual-write soak).
This keeps the contract of the spec — the scheduler wakes up, reads SEC
data, persists into ``company_financials`` — even though the upstream
API used is Polygon (which itself sources from SEC XBRL submissions).
A dedicated EDGAR XBRL fetcher can replace this without touching the
scheduler.

13F → ``institutional_holders`` (window-aware)
----------------------------------------------
:func:`ingest_13f` calls ``EdgarClient.get_institutional_holders`` per
ticker and batch-appends the result into ``institutional_holders``. The
scheduler decides whether to call this at the baseline (daily) or
intensive (hourly) cadence; the function itself is stateless.

Form 4 → ``insider_transactions``
---------------------------------
:func:`ingest_form4` calls ``EdgarClient.get_insider_transactions`` and
per-row appends each Form 4 row.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.models.company import Company
from app.models.financials import Financials
from app.models.insiders import InsiderTransaction
from app.models.institutions import InstitutionalHolder
from app.repositories.company_repo import CompanyRepository
from app.repositories.financials_repo import FinancialsRepository
from app.repositories.insiders_repo import InsidersRepository
from app.repositories.institutions_repo import InstitutionsRepository
from app.services.edgar_client import EdgarClient
from app.services.market_data import PolygonClient

logger = logging.getLogger("signal.ingest.edgar")


# Module-level singletons. The scheduler invokes these once per cron tick
# from inside the worker process; sharing them keeps the upstream
# clients' internal in-memory caches warm across ticks.
_company_repo: Optional[CompanyRepository] = None
_financials_repo: Optional[FinancialsRepository] = None
_institutions_repo: Optional[InstitutionsRepository] = None
_insiders_repo: Optional[InsidersRepository] = None
_edgar_client: Optional[EdgarClient] = None
_polygon_client: Optional[PolygonClient] = None


def _get_company_repo() -> CompanyRepository:
    global _company_repo
    if _company_repo is None:
        _company_repo = CompanyRepository()
    return _company_repo


def _get_financials_repo() -> FinancialsRepository:
    global _financials_repo
    if _financials_repo is None:
        _financials_repo = FinancialsRepository()
    return _financials_repo


def _get_institutions_repo() -> InstitutionsRepository:
    global _institutions_repo
    if _institutions_repo is None:
        _institutions_repo = InstitutionsRepository()
    return _institutions_repo


def _get_insiders_repo() -> InsidersRepository:
    global _insiders_repo
    if _insiders_repo is None:
        _insiders_repo = InsidersRepository()
    return _insiders_repo


def get_edgar_client() -> EdgarClient:
    global _edgar_client
    if _edgar_client is None:
        _edgar_client = EdgarClient()
    return _edgar_client


def get_polygon_client() -> PolygonClient:
    global _polygon_client
    if _polygon_client is None:
        _polygon_client = PolygonClient()
    return _polygon_client


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            return None
    return None


def _period_end_from(fp: Any, fy: Any) -> Optional[date]:
    try:
        year = int(str(fy).strip())
    except (ValueError, TypeError):
        return None
    period = str(fp or "").upper().strip()
    if period == "Q1":
        return date(year, 3, 31)
    if period == "Q2":
        return date(year, 6, 30)
    if period == "Q3":
        return date(year, 9, 30)
    if period in ("Q4", "FY", "ANNUAL"):
        return date(year, 12, 31)
    return None


def _ensure_master(ticker: str, *, name: Optional[str] = None) -> None:
    """Bootstrap the ``companies`` row so FK-RESTRICT children can land."""
    repo = _get_company_repo()
    if repo.get(ticker) is not None:
        return
    repo.upsert(Company(ticker=ticker, name=name or ticker))


# --------------------------------------------------------------------------- #
# Ingesters
# --------------------------------------------------------------------------- #


def ingest_10q_10k(tickers: list[str]) -> dict[str, int]:
    """Ingest the latest 10-Q / 10-K filings for ``tickers``.

    Currently sources data from Polygon's XBRL-derived
    ``vX/reference/financials`` endpoint (the same source used by the
    market routes). Each ``results[]`` row maps to one
    ``company_financials`` row; the ON CONFLICT DO UPDATE in the repo
    makes re-ingest a no-op refresh.

    Returns a per-ticker count of rows written. Tickers that yield zero
    rows are still present in the result with ``0``.
    """
    polygon = get_polygon_client()
    fin_repo = _get_financials_repo()
    out: dict[str, int] = {}

    if not polygon.enabled:
        logger.warning("ingest_10q_10k: polygon disabled (no API key); skipping all")
        for t in tickers:
            out[t.upper()] = 0
        return out

    for raw_ticker in tickers:
        ticker = raw_ticker.upper().strip()
        if not ticker:
            continue
        rows_written = 0
        try:
            payload = polygon.get_financials(ticker)
            if not payload or payload.get("fiscal_year") is None:
                out[ticker] = 0
                continue
            period_end = _period_end_from(
                payload.get("fiscal_period"), payload.get("fiscal_year")
            )
            if period_end is None:
                out[ticker] = 0
                continue
            try:
                fy_int = int(str(payload.get("fiscal_year")).strip())
            except (ValueError, TypeError):
                out[ticker] = 0
                continue
            period_type = (
                str(payload.get("fiscal_period") or "").upper().strip() or "Q4"
            )
            _ensure_master(ticker)
            fin_repo.append(
                Financials(
                    ticker=ticker,
                    period_end=period_end,
                    period_type=period_type,
                    fiscal_year=fy_int,
                    revenue=_to_int(payload.get("revenue")),
                    net_income=_to_int(payload.get("net_income")),
                    eps_basic=_to_decimal(payload.get("eps")),
                    source="ingest_10q_10k",
                )
            )
            rows_written += 1
        except Exception as e:
            logger.warning("ingest_10q_10k(%s) failed: %s", ticker, e)
        out[ticker] = rows_written
    return out


def ingest_13f(tickers: list[str]) -> dict[str, int]:
    """Ingest the latest 13F holdings for each ``ticker``.

    Calls ``EdgarClient.get_institutional_holders`` (which already runs
    its own 10 req/sec throttle + L2 cache) and batch-appends to
    ``institutional_holders`` (idempotent via UNIQUE).
    """
    edgar = get_edgar_client()
    inst_repo = _get_institutions_repo()
    out: dict[str, int] = {}

    for raw_ticker in tickers:
        ticker = raw_ticker.upper().strip()
        if not ticker:
            continue
        try:
            payload = edgar.get_institutional_holders(ticker)
            if not payload:
                out[ticker] = 0
                continue
            rows: list[InstitutionalHolder] = []
            for item in payload:
                rd = _parse_date(item.get("report_date"))
                if rd is None:
                    continue
                rows.append(
                    InstitutionalHolder(
                        ticker=ticker,
                        institution_name=item.get("institution_name") or None,
                        institution_cik=item.get("institution_cik") or item.get("cik"),
                        report_date=rd,
                        shares_held=_to_int(item.get("shares_held")),
                        market_value=_to_int(
                            item.get("value") or item.get("market_value")
                        ),
                    )
                )
            if not rows:
                out[ticker] = 0
                continue
            _ensure_master(ticker)
            written = inst_repo.append_batch(rows)
            out[ticker] = written
        except Exception as e:
            logger.warning("ingest_13f(%s) failed: %s", ticker, e)
            out[ticker] = 0
    return out


def ingest_form4(tickers: list[str]) -> dict[str, int]:
    """Ingest Form 4 insider transactions for each ``ticker``.

    Per-row append; ``InsidersRepository.append`` returns ``None`` on
    composite-UNIQUE dedup hits (already ingested), which keeps re-runs
    cheap.
    """
    edgar = get_edgar_client()
    ins_repo = _get_insiders_repo()
    out: dict[str, int] = {}

    for raw_ticker in tickers:
        ticker = raw_ticker.upper().strip()
        if not ticker:
            continue
        try:
            payload = edgar.get_insider_transactions(ticker)
            if not payload:
                out[ticker] = 0
                continue
            written = 0
            bootstrap_done = False
            for item in payload:
                td = _parse_date(
                    item.get("transaction_date") or item.get("filing_date")
                )
                if td is None:
                    continue
                fd = _parse_date(item.get("filing_date"))
                try:
                    txn = InsiderTransaction(
                        ticker=ticker,
                        insider_name=item.get("insider_name") or None,
                        insider_title=item.get("title")
                        or item.get("insider_title") or None,
                        transaction_date=td,
                        transaction_type=item.get("transaction_type") or None,
                        shares=_to_int(item.get("shares")),
                        price_per_share=_to_decimal(item.get("price_per_share")),
                        total_value=_to_int(item.get("total_value")),
                        shares_owned_after=_to_int(
                            item.get("shares_held_after")
                            or item.get("shares_owned_after")
                        ),
                        filing_date=fd,
                        form_type="4",
                    )
                except Exception:
                    continue
                if not bootstrap_done:
                    _ensure_master(ticker)
                    bootstrap_done = True
                try:
                    if ins_repo.append(txn) is not None:
                        written += 1
                except Exception:
                    continue
            out[ticker] = written
        except Exception as e:
            logger.warning("ingest_form4(%s) failed: %s", ticker, e)
            out[ticker] = 0
    return out
