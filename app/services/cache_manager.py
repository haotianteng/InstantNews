"""Two-tier company data cache manager.

.. deprecated:: US-013
   The normalized Postgres tables (``companies``, ``company_financials``,
   ``company_fundamentals``, ``company_competitors``,
   ``institutional_holders``, ``insider_transactions``) combined with the
   Redis-backed :mod:`app.repositories` layer supersede this JSON blob
   cache. ``CompanyCache`` is kept active during the 7-day dual-write
   soak (spec US-013) so legacy readers continue to see fresh data; it
   will be removed in US-018 once the backfill (US-014) is complete and
   the soak window has elapsed. New call sites must go through the
   repository layer instead.

L1: in-memory dicts inside PolygonClient / EdgarClient (per-process, fast)
L2: company_data_cache DB table (shared across workers, survives restarts)

This module provides the L2 layer. Service clients call get/put around
their existing L1 logic — no changes to route handlers required.
"""

import json
import logging
import warnings
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from app.database import get_session
from app.models import CompanyDataCache
from app.services.feed_parser import utc_iso

logger = logging.getLogger("signal.cache")

# L2 TTL per data_type (seconds)
DB_TTLS = {
    "details": 604800,       # 7 days
    "financials": 21600,     # 6 hours
    "earnings": 21600,       # 6 hours
    "competitors": 43200,    # 12 hours
    "institutional": 86400,  # 24 hours
    "positions": 21600,      # 6 hours
    "insiders": 7200,        # 2 hours
}


class CompanyCache:
    """L2 database cache for company dimension data.

    .. deprecated:: US-013
       Prefer ``app.repositories.*`` (backed by Redis + normalized
       tables). This class stays on the read+write path during the
       7-day dual-write soak so legacy consumers keep working; it will
       be removed alongside the ``company_data_cache`` table in US-018.
    """

    def __init__(self) -> None:
        warnings.warn(
            "CompanyCache is deprecated; use app.repositories.* "
            "(will be removed in US-018 after the dual-write soak).",
            DeprecationWarning,
            stacklevel=2,
        )

    def get(self, symbol: str, data_type: str) -> Optional[Any]:
        """Return cached data if still valid, else None."""
        session = get_session()
        try:
            row = (
                session.query(CompanyDataCache)
                .filter_by(symbol=symbol.upper(), data_type=data_type)
                .first()
            )
            if row is None:
                return None

            # Check TTL
            try:
                fetched = datetime.fromisoformat(row.fetched_at)
            except (ValueError, TypeError):
                return None

            now = datetime.now(timezone.utc)
            if now > fetched + timedelta(seconds=row.ttl_seconds):
                return None  # expired

            return json.loads(row.payload)
        except Exception as e:
            logger.debug("L2 cache get error: %s", e)
            return None
        finally:
            session.close()

    def put(self, symbol: str, data_type: str, data: Any) -> None:
        """Write data to DB cache (upsert)."""
        ttl = DB_TTLS.get(data_type)
        if ttl is None:
            return  # unknown data_type, skip

        sym = symbol.upper()
        now_iso = utc_iso(datetime.now(timezone.utc))
        payload = json.dumps(data, default=str)

        session = get_session()
        try:
            row = (
                session.query(CompanyDataCache)
                .filter_by(symbol=sym, data_type=data_type)
                .first()
            )
            if row:
                row.payload = payload
                row.fetched_at = now_iso
                row.ttl_seconds = ttl
            else:
                session.add(CompanyDataCache(
                    symbol=sym,
                    data_type=data_type,
                    payload=payload,
                    fetched_at=now_iso,
                    ttl_seconds=ttl,
                ))
            session.commit()
        except Exception:
            session.rollback()
            # Race condition on unique constraint — try update
            try:
                row = (
                    session.query(CompanyDataCache)
                    .filter_by(symbol=sym, data_type=data_type)
                    .first()
                )
                if row:
                    row.payload = payload
                    row.fetched_at = now_iso
                    row.ttl_seconds = ttl
                    session.commit()
            except Exception as e2:
                session.rollback()
                logger.debug("L2 cache put error: %s", e2)
        finally:
            session.close()

    def invalidate(self, symbol: str = None, data_type: str = None) -> None:
        """Delete cache entries. If symbol is None, clears all."""
        session = get_session()
        try:
            q = session.query(CompanyDataCache)
            if symbol:
                q = q.filter_by(symbol=symbol.upper())
            if data_type:
                q = q.filter_by(data_type=data_type)
            q.delete()
            session.commit()
        except Exception as e:
            session.rollback()
            logger.debug("L2 cache invalidate error: %s", e)
        finally:
            session.close()

    def warm(self, symbols, data_types):
        """Check which (symbol, data_type) pairs are stale or missing.

        Returns a set of (symbol, data_type) tuples that need fetching.
        Caller is responsible for actually fetching the data.
        """
        stale = set()
        for sym in symbols:
            for dt in data_types:
                if self.get(sym, dt) is None:
                    stale.add((sym.upper(), dt))
        return stale
