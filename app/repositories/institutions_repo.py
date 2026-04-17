"""Repository for ``institutional_holders`` (13F snapshots)."""

from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy.exc import IntegrityError

from app.cache.cache_keys import TTL, company_institutions_top
from app.database import get_session
from app.models import InstitutionalHolder as HolderORM
from app.models.institutions import InstitutionalHolder
from app.repositories.base import BaseRepository


class InstitutionsRepository(BaseRepository[InstitutionalHolder]):
    """Read top-N institutional holders by market value; bulk-append 13F rows."""

    def __init__(self) -> None:
        super().__init__(InstitutionalHolder)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_top(
        self, ticker: str, n: int = 20, as_of: date | None = None
    ) -> List[InstitutionalHolder]:
        """Return the top-N holders for ``ticker`` ordered by market value.

        Without ``as_of`` we resolve the latest ``report_date`` for the
        ticker and return that quarter's top-N. With ``as_of`` we return
        the top-N reported on exactly that date. Only the ``as_of=None``
        variant is cached (6h TTL) — pinning to a historical date is a
        cold-path analyst query that doesn't benefit from caching.
        """
        up = ticker.upper()

        def loader() -> List[InstitutionalHolder]:
            session = get_session()
            try:
                effective = as_of
                if effective is None:
                    # Find the latest report_date for this ticker.
                    latest = (
                        session.query(HolderORM.report_date)
                        .filter_by(ticker=up)
                        .order_by(HolderORM.report_date.desc())
                        .first()
                    )
                    if latest is None:
                        return []
                    effective = latest[0]
                rows = (
                    session.query(HolderORM)
                    .filter(HolderORM.ticker == up)
                    .filter(HolderORM.report_date == effective)
                    .order_by(HolderORM.market_value.desc())
                    .limit(n)
                    .all()
                )
                return [InstitutionalHolder.model_validate(r) for r in rows]
            finally:
                session.close()

        if as_of is None:
            key = company_institutions_top(up, n)
            return self.cached_get_list(key, TTL["institutions"], loader)
        return loader()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def append_batch(self, holders: List[InstitutionalHolder]) -> int:
        """Bulk append 13F rows with UPSERT semantics on the dedup key.

        The UNIQUE ``(ticker, institution_cik, report_date)`` constraint
        is the idempotent-ingest gate — re-running the same 13F just
        refreshes ``market_value`` / ``shares_held`` / ``change_shares``.

        Returns the number of rows upserted. Invalidates every cached
        ``institutions:top*`` variant for every ticker seen in the batch.
        """
        if not holders:
            return 0

        session = get_session()
        affected_tickers = set()
        count = 0
        try:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                for h in holders:
                    payload = h.model_dump(exclude_none=True)
                    payload.pop("id", None)
                    payload["ticker"] = h.ticker.upper()
                    affected_tickers.add(payload["ticker"])

                    stmt = pg_insert(HolderORM).values(**payload)
                    update_cols = {
                        c: stmt.excluded[c]
                        for c in payload.keys()
                        if c not in ("ticker", "institution_cik", "report_date")
                    }
                    if update_cols:
                        stmt = stmt.on_conflict_do_update(
                            constraint="uq_inst_ticker_cik_date",
                            set_=update_cols,
                        )
                    else:
                        stmt = stmt.on_conflict_do_nothing(
                            constraint="uq_inst_ticker_cik_date"
                        )
                    session.execute(stmt)
                    count += 1
                session.commit()
            else:
                # Portable fallback — try insert, on conflict update via
                # the UNIQUE tuple.
                for h in holders:
                    payload = h.model_dump(exclude_none=True)
                    payload.pop("id", None)
                    payload["ticker"] = h.ticker.upper()
                    affected_tickers.add(payload["ticker"])
                    try:
                        session.add(HolderORM(**payload))
                        session.commit()
                        count += 1
                    except IntegrityError:
                        session.rollback()
                        row = (
                            session.query(HolderORM)
                            .filter_by(
                                ticker=payload["ticker"],
                                institution_cik=payload.get("institution_cik"),
                                report_date=payload["report_date"],
                            )
                            .first()
                        )
                        if row is not None:
                            for f, v in payload.items():
                                if f in (
                                    "ticker",
                                    "institution_cik",
                                    "report_date",
                                ):
                                    continue
                                setattr(row, f, v)
                            session.commit()
                            count += 1
        finally:
            session.close()

        for t in affected_tickers:
            self.invalidate_pattern(f"company:{t}:institutions:top*")
        return count
