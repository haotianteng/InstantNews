"""Repository for the ``companies`` master-reference table.

Hands out Pydantic :class:`app.models.company.Company` instances — ORM
rows and sessions stay inside this module. Read path is cache-aside
(24h TTL per spec §2); writes ``upsert`` and invalidate the cache so a
subsequent ``get`` sees the new value.
"""

from __future__ import annotations

from typing import List

from app.cache.cache_keys import TTL, company_master
from app.database import get_session
from app.models import Company as CompanyORM
from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    """CRUD + cache-aside helpers for the ``companies`` table."""

    def __init__(self) -> None:
        super().__init__(Company)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, ticker: str) -> Company | None:
        """Return the master row for ``ticker`` or ``None``.

        Cached for :data:`TTL["master"]` seconds (24h). Ticker is
        uppercased for the DB lookup so the cache key and query stay
        consistent with the spec's ``company:{TICKER}:master``
        namespacing.
        """
        up = ticker.upper()
        key = company_master(up)

        def loader() -> Company | None:
            session = get_session()
            try:
                row = (
                    session.query(CompanyORM).filter_by(ticker=up).first()
                )
                return Company.model_validate(row) if row else None
            finally:
                session.close()

        return self.cached_get(key, TTL["master"], loader)

    def list_by_sector(self, sector: str) -> List[Company]:
        """Return every active company in a sector (DB only, uncached)."""
        session = get_session()
        try:
            rows = (
                session.query(CompanyORM).filter_by(sector=sector).all()
            )
            return [Company.model_validate(r) for r in rows]
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert(self, company: Company) -> Company:
        """Insert-or-update the master row and invalidate the cache.

        Pydantic → dict via ``model_dump(exclude_none=True)`` so we
        don't clobber DB-populated fields (``created_at``, server
        defaults) with ``None`` on update. Returns the refreshed
        Pydantic model.
        """
        session = get_session()
        try:
            row = (
                session.query(CompanyORM)
                .filter_by(ticker=company.ticker.upper())
                .first()
            )
            payload = company.model_dump(exclude_none=True)
            # Normalize ticker to upper in the write path too
            payload["ticker"] = company.ticker.upper()

            if row is not None:
                for field, value in payload.items():
                    setattr(row, field, value)
            else:
                row = CompanyORM(**payload)
                session.add(row)
            session.commit()
            session.refresh(row)
            result = Company.model_validate(row)
        finally:
            session.close()

        self.invalidate(company_master(company.ticker))
        return result
