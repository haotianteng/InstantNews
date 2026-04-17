"""Repository for ``company_fundamentals`` (current view + SCD-2 history).

Writes go against the current-view table; the Postgres trigger
``fn_snapshot_fundamentals_before_update`` copies the OLD row into
``company_fundamentals_history`` on each UPDATE. We therefore never
write to the history table directly — reads of historical snapshots
use ``get_at(ticker, ts)`` against the history table.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy.exc import IntegrityError

from app.cache.cache_keys import TTL, company_fundamentals
from app.database import get_session
from app.models import (
    CompanyFundamentals as FundamentalsORM,
    CompanyFundamentalsHistory as FundamentalsHistoryORM,
)
from app.models.fundamentals import Fundamentals, FundamentalsHistory
from app.repositories.base import BaseRepository


class FundamentalsRepository(BaseRepository[Fundamentals]):
    """CRUD + cache for ``company_fundamentals``.

    ``get_at`` is a point-in-time read from the history table and is
    **not** cached — low-volume query, and the result varies per
    timestamp argument which makes a good cache key expensive.
    """

    def __init__(self) -> None:
        super().__init__(Fundamentals)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, ticker: str) -> Fundamentals | None:
        """Return the current-view fundamentals for ``ticker`` or ``None``.

        Cached for :data:`TTL["fundamentals"]` (5m).
        """
        up = ticker.upper()
        key = company_fundamentals(up)

        def loader() -> Fundamentals | None:
            session = get_session()
            try:
                row = (
                    session.query(FundamentalsORM).filter_by(ticker=up).first()
                )
                return Fundamentals.model_validate(row) if row else None
            finally:
                session.close()

        return self.cached_get(key, TTL["fundamentals"], loader)

    def get_at(self, ticker: str, ts: datetime) -> FundamentalsHistory | None:
        """Return the history row whose validity window covers ``ts``.

        Uses the half-open interval ``[valid_from, valid_to)`` matching
        the trigger's convention.
        """
        up = ticker.upper()
        session = get_session()
        try:
            row = (
                session.query(FundamentalsHistoryORM)
                .filter(FundamentalsHistoryORM.ticker == up)
                .filter(FundamentalsHistoryORM.valid_from <= ts)
                .filter(FundamentalsHistoryORM.valid_to > ts)
                .order_by(FundamentalsHistoryORM.valid_from.desc())
                .first()
            )
            return FundamentalsHistory.model_validate(row) if row else None
        finally:
            session.close()

    def list_history(self, ticker: str) -> List[FundamentalsHistory]:
        """Return every history row for a ticker ordered newest-first."""
        up = ticker.upper()
        session = get_session()
        try:
            rows = (
                session.query(FundamentalsHistoryORM)
                .filter(FundamentalsHistoryORM.ticker == up)
                .order_by(FundamentalsHistoryORM.valid_to.desc())
                .all()
            )
            return [FundamentalsHistory.model_validate(r) for r in rows]
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert(self, fundamentals: Fundamentals) -> Fundamentals:
        """Insert-or-update the current-view row; trigger handles history.

        On Postgres, the ``BEFORE UPDATE`` trigger is the atomic history
        writer — we don't touch the history table here. On SQLite (tests
        only) there is no trigger, so we manually append a history row
        on the UPDATE path to keep tests that assert SCD-2 behavior
        working dialect-agnostically.
        """
        up = fundamentals.ticker.upper()
        payload = fundamentals.model_dump(exclude_none=True)
        payload["ticker"] = up

        session = get_session()
        try:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            row = session.query(FundamentalsORM).filter_by(ticker=up).first()

            if row is None:
                # INSERT path — no history snapshot yet.
                row = FundamentalsORM(**payload)
                session.add(row)
                session.commit()
                session.refresh(row)
            else:
                # UPDATE path. On non-Postgres dialects the trigger does
                # not exist — emulate it so tests see a history row.
                if dialect != "postgresql":
                    old_valid_from = row.updated_at or datetime.utcnow()
                    now = datetime.utcnow()
                    snapshot = FundamentalsHistoryORM(
                        ticker=row.ticker,
                        market_cap=row.market_cap,
                        shares_outstanding=row.shares_outstanding,
                        pe_ratio=row.pe_ratio,
                        pb_ratio=row.pb_ratio,
                        ev_ebitda=row.ev_ebitda,
                        dividend_yield=row.dividend_yield,
                        beta=row.beta,
                        next_earnings_date=row.next_earnings_date,
                        next_earnings_time=row.next_earnings_time,
                        analyst_rating=row.analyst_rating,
                        price_target_mean=row.price_target_mean,
                        updated_at=row.updated_at,
                        valid_from=old_valid_from,
                        valid_to=now,
                    )
                    try:
                        session.add(snapshot)
                        session.flush()
                    except IntegrityError:
                        # Same ticker + valid_from already snapshotted — skip.
                        session.rollback()
                        # Re-fetch row because rollback invalidated it.
                        row = (
                            session.query(FundamentalsORM)
                            .filter_by(ticker=up)
                            .first()
                        )
                        if row is None:
                            # Extremely unlikely — the row existed pre-rollback
                            # but is gone now. Treat as an insert.
                            row = FundamentalsORM(**payload)
                            session.add(row)

                for f, v in payload.items():
                    setattr(row, f, v)
                if dialect != "postgresql":
                    # Mirror the Postgres trigger which also refreshes
                    # ``updated_at := NOW()`` on each UPDATE. setattr
                    # keeps mypy happy about legacy Column-typed ORM
                    # attributes.
                    setattr(row, "updated_at", datetime.utcnow())
                session.commit()
                session.refresh(row)

            result = Fundamentals.model_validate(row)
        finally:
            session.close()

        self.invalidate(company_fundamentals(up))
        return result
