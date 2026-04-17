"""Repository for ``company_competitors`` — directional similarity edges."""

from __future__ import annotations

from typing import List

from app.cache.cache_keys import TTL, company_competitors_top
from app.database import get_session
from app.models import CompanyCompetitor as CompetitorORM
from app.models.competitors import Competitor
from app.repositories.base import BaseRepository


class CompetitorsRepository(BaseRepository[Competitor]):
    """Read top-N competitors by similarity; batch-upsert the full graph
    for a ticker and invalidate every cached top-N variant."""

    def __init__(self) -> None:
        super().__init__(Competitor)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_top(self, ticker: str, n: int = 10) -> List[Competitor]:
        """Return the top-N competitors for ``ticker`` by similarity score.

        Cached for :data:`TTL["competitors"]` (24h). The ``n`` value is
        part of the cache key, so ``get_top(t, 10)`` and
        ``get_top(t, 20)`` have independent entries.
        """
        up = ticker.upper()
        key = company_competitors_top(up, n)

        def loader() -> List[Competitor]:
            session = get_session()
            try:
                rows = (
                    session.query(CompetitorORM)
                    .filter_by(ticker=up)
                    .order_by(CompetitorORM.similarity_score.desc())
                    .limit(n)
                    .all()
                )
                return [Competitor.model_validate(r) for r in rows]
            finally:
                session.close()

        return self.cached_get_list(key, TTL["competitors"], loader)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert_batch(
        self, ticker: str, competitors: List[Competitor]
    ) -> List[Competitor]:
        """Replace the competitor edges for ``ticker`` with ``competitors``.

        Strategy: delete existing rows for the source ticker, then
        insert the new ones in a single transaction. Invalidates every
        ``top*`` cached variant for the ticker via ``SCAN``.
        """
        up = ticker.upper()
        session = get_session()
        try:
            session.query(CompetitorORM).filter_by(ticker=up).delete(
                synchronize_session=False
            )
            for c in competitors:
                payload = c.model_dump(exclude_none=True)
                payload["ticker"] = up
                payload["competitor_ticker"] = c.competitor_ticker.upper()
                session.add(CompetitorORM(**payload))
            session.commit()

            rows = (
                session.query(CompetitorORM)
                .filter_by(ticker=up)
                .order_by(CompetitorORM.similarity_score.desc())
                .all()
            )
            result = [Competitor.model_validate(r) for r in rows]
        finally:
            session.close()

        # Unknown which top-N variants were cached — nuke the whole prefix.
        self.invalidate_pattern(f"company:{up}:competitors:top*")
        return result
