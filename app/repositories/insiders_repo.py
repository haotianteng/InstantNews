"""Repository for ``insider_transactions`` (SEC Form 4/5)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

from sqlalchemy.exc import IntegrityError

from app.cache.cache_keys import TTL, company_insiders_recent
from app.database import get_session
from app.models import InsiderTransaction as InsiderORM
from app.models.insiders import InsiderTransaction
from app.repositories.base import BaseRepository


class InsidersRepository(BaseRepository[InsiderTransaction]):
    """Read recent insider transactions; idempotent-append new ones."""

    def __init__(self) -> None:
        super().__init__(InsiderTransaction)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_recent(
        self, ticker: str, days: int = 90
    ) -> List[InsiderTransaction]:
        """Return every transaction in the last ``days`` for ``ticker``.

        Cached for :data:`TTL["insiders"]` (15m). The ``days`` value is
        part of the cache key.
        """
        up = ticker.upper()
        key = company_insiders_recent(up, days)

        def loader() -> List[InsiderTransaction]:
            session = get_session()
            try:
                cutoff = date.today() - timedelta(days=days)
                rows = (
                    session.query(InsiderORM)
                    .filter(InsiderORM.ticker == up)
                    .filter(InsiderORM.transaction_date >= cutoff)
                    .order_by(InsiderORM.transaction_date.desc())
                    .all()
                )
                return [InsiderTransaction.model_validate(r) for r in rows]
            finally:
                session.close()

        return self.cached_get_list(key, TTL["insiders"], loader)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def append(self, txn: InsiderTransaction) -> InsiderTransaction | None:
        """Insert one transaction; returns the row or ``None`` on dedup hit.

        The composite UNIQUE (excluding ``price_per_share`` — see spec
        §US-007) makes re-ingest idempotent: a repeat filing from a
        different source returns ``None`` without raising.

        On success, invalidates every cached ``insiders:*d`` variant.
        """
        up = txn.ticker.upper()
        payload = txn.model_dump(exclude_none=True)
        payload.pop("id", None)
        payload["ticker"] = up

        session = get_session()
        try:
            session.add(InsiderORM(**payload))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                result = None
            else:
                row = (
                    session.query(InsiderORM)
                    .filter_by(
                        ticker=up,
                        insider_name=payload.get("insider_name"),
                        transaction_date=payload["transaction_date"],
                        transaction_type=payload.get("transaction_type"),
                        shares=payload.get("shares"),
                        form_type=payload.get("form_type"),
                    )
                    .first()
                )
                result = (
                    InsiderTransaction.model_validate(row) if row else None
                )
        finally:
            session.close()

        if result is not None:
            self.invalidate_pattern(f"company:{up}:insiders:*d")
        return result
