"""Repository for ``company_financials`` — quarterly/annual filings.

The table's composite PK ``(ticker, period_end, period_type)`` is the
dedup key; re-ingest of the same filing is a PK violation. ``append``
uses Postgres ``INSERT ... ON CONFLICT DO UPDATE`` so idempotent
re-ingest from multiple sources becomes a no-op row refresh instead of
an exception. On SQLite (test bootstrap) we fall back to a portable
"try INSERT, on IntegrityError do UPDATE" shim.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy.exc import IntegrityError

from app.cache.cache_keys import (
    TTL,
    company_financials_latest,
    company_financials_range,
)
from app.database import get_session
from app.models import CompanyFinancials as FinancialsORM
from app.models.financials import Financials
from app.repositories.base import BaseRepository


class FinancialsRepository(BaseRepository[Financials]):
    """CRUD + cache for ``company_financials``."""

    def __init__(self) -> None:
        super().__init__(Financials)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_latest(self, ticker: str) -> Financials | None:
        """Return the most recent filing row for ``ticker`` or ``None``.

        Cached for :data:`TTL["financials_latest"]` (1h).
        """
        up = ticker.upper()
        key = company_financials_latest(up)

        def loader() -> Financials | None:
            session = get_session()
            try:
                row = (
                    session.query(FinancialsORM)
                    .filter_by(ticker=up)
                    .order_by(FinancialsORM.period_end.desc())
                    .first()
                )
                return Financials.model_validate(row) if row else None
            finally:
                session.close()

        return self.cached_get(key, TTL["financials_latest"], loader)

    def get_range(
        self, ticker: str, from_date: date, to_date: date
    ) -> List[Financials]:
        """Return every filing row in ``[from_date, to_date]`` (inclusive)."""
        up = ticker.upper()
        key = company_financials_range(up, from_date.isoformat(), to_date.isoformat())

        def loader() -> List[Financials]:
            session = get_session()
            try:
                rows = (
                    session.query(FinancialsORM)
                    .filter(FinancialsORM.ticker == up)
                    .filter(FinancialsORM.period_end >= from_date)
                    .filter(FinancialsORM.period_end <= to_date)
                    .order_by(FinancialsORM.period_end.desc())
                    .all()
                )
                return [Financials.model_validate(r) for r in rows]
            finally:
                session.close()

        return self.cached_get_list(key, TTL["financials_latest"], loader)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def append(self, financials: Financials) -> Financials:
        """Insert a filing, updating in place if the PK already exists.

        Postgres: ``INSERT ... ON CONFLICT DO UPDATE``.
        SQLite / fallback: try INSERT, catch IntegrityError, UPDATE.

        Invalidates the ``financials:latest`` cache on success.
        """
        up = financials.ticker.upper()
        payload = financials.model_dump(exclude_none=True)
        payload["ticker"] = up

        session = get_session()
        try:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                # ``FinancialsORM`` itself is a valid insert target — using
                # the mapped class keeps the typing checker happy without
                # losing the Table behavior.
                stmt = pg_insert(FinancialsORM).values(**payload)
                # Don't overwrite PK columns or server-default ingested_at.
                update_cols = {
                    c: stmt.excluded[c]
                    for c in payload.keys()
                    if c not in ("ticker", "period_end", "period_type")
                }
                stmt = stmt.on_conflict_do_update(
                    constraint="pk_company_financials",
                    set_=update_cols,
                )
                session.execute(stmt)
                session.commit()
            else:
                # Portable fallback: add, commit; on IntegrityError roll back
                # and run a targeted UPDATE.
                try:
                    row = FinancialsORM(**payload)
                    session.add(row)
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    existing = (
                        session.query(FinancialsORM)
                        .filter_by(
                            ticker=up,
                            period_end=financials.period_end,
                            period_type=financials.period_type,
                        )
                        .first()
                    )
                    if existing is not None:
                        for f, v in payload.items():
                            if f in ("ticker", "period_end", "period_type"):
                                continue
                            setattr(existing, f, v)
                        session.commit()

            # Re-read the row we just wrote so the caller sees DB-side values
            # (server-default ``ingested_at`` in particular).
            reread: Optional[FinancialsORM] = (
                session.query(FinancialsORM)
                .filter_by(
                    ticker=up,
                    period_end=financials.period_end,
                    period_type=financials.period_type,
                )
                .first()
            )
            result: Financials = (
                Financials.model_validate(reread) if reread is not None else financials
            )
        finally:
            session.close()

        self.invalidate(company_financials_latest(up))
        return result
