"""US-016 — Polygon fundamentals refresh.

One scheduled job (registered in :mod:`app.worker`) calls
:func:`refresh_fundamentals` periodically with the active universe of
tickers. The function pulls Polygon's ``ticker_details`` payload, maps
the relevant fields to ``company_fundamentals``, and lets the
repository's ``upsert`` fire the SCD-2 trigger for the history table.
Redis invalidation is also handled by the repo.

Rate limiting
-------------
Polygon's free tier is 5 req/sec. The internal :class:`PolygonClient`
does not throttle today, so we add a tiny per-iteration sleep here to
stay safely below the limit (4 req/sec).

Errors
------
Per-ticker failures are swallowed and counted; the function never
raises. Job-level error handling is in :mod:`app.worker`'s wrapper.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.models.company import Company
from app.models.fundamentals import Fundamentals
from app.repositories.company_repo import CompanyRepository
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.services.market_data import PolygonClient

logger = logging.getLogger("signal.ingest.market_data")


# Polygon free tier ceiling = 5 req/sec → 0.25s spacing keeps us at 4 rps.
POLYGON_MIN_INTERVAL_SECONDS = 0.25


_company_repo: Optional[CompanyRepository] = None
_fundamentals_repo: Optional[FundamentalsRepository] = None
_polygon: Optional[PolygonClient] = None


def _get_company_repo() -> CompanyRepository:
    global _company_repo
    if _company_repo is None:
        _company_repo = CompanyRepository()
    return _company_repo


def _get_fundamentals_repo() -> FundamentalsRepository:
    global _fundamentals_repo
    if _fundamentals_repo is None:
        _fundamentals_repo = FundamentalsRepository()
    return _fundamentals_repo


def get_polygon_client() -> PolygonClient:
    global _polygon
    if _polygon is None:
        _polygon = PolygonClient()
    return _polygon


def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def refresh_fundamentals(tickers: list[str]) -> dict[str, int]:
    """Refresh ``company_fundamentals`` for each ``ticker``.

    Returns a per-ticker dict where the value is ``1`` on a successful
    upsert (trigger fires once on update; insert + 0 history rows on
    first write) and ``0`` on no-op / failure. The aggregate ``sum`` is
    a useful job-level "rows written" gauge for the audit log.
    """
    polygon = get_polygon_client()
    fund_repo = _get_fundamentals_repo()
    comp_repo = _get_company_repo()
    out: dict[str, int] = {}

    if not polygon.enabled:
        logger.warning("refresh_fundamentals: polygon disabled (no API key); skipping")
        for t in tickers:
            out[t.upper()] = 0
        return out

    last_request_ts = 0.0
    for raw_ticker in tickers:
        ticker = raw_ticker.upper().strip()
        if not ticker:
            continue
        # Token-bucket-equivalent: enforce a minimum interval between
        # Polygon calls. Cheap and dependency-free.
        elapsed = time.monotonic() - last_request_ts
        if elapsed < POLYGON_MIN_INTERVAL_SECONDS:
            time.sleep(POLYGON_MIN_INTERVAL_SECONDS - elapsed)

        try:
            details = polygon.get_ticker_details(ticker)
            last_request_ts = time.monotonic()
            if not details:
                out[ticker] = 0
                continue

            market_cap = _to_int(details.get("market_cap"))
            shares = _to_int(
                details.get("share_class_shares_outstanding")
                or details.get("weighted_shares_outstanding")
            )
            if market_cap is None and shares is None:
                out[ticker] = 0
                continue

            # Bootstrap master row to satisfy FK.
            if comp_repo.get(ticker) is None:
                comp_repo.upsert(
                    Company(
                        ticker=ticker,
                        name=str(details.get("name") or ticker),
                        description=details.get("description") or None,
                        website=details.get("homepage_url") or None,
                        sector=details.get("sector") or details.get("sic_description") or None,
                    )
                )
            fund_repo.upsert(
                Fundamentals(
                    ticker=ticker,
                    market_cap=market_cap,
                    shares_outstanding=shares,
                )
            )
            out[ticker] = 1
        except Exception as e:
            logger.warning("refresh_fundamentals(%s) failed: %s", ticker, e)
            out[ticker] = 0

    return out
