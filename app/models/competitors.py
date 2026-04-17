"""Pydantic schema for the ``company_competitors`` similarity graph.

Each row is a directional edge: ``ticker`` → ``competitor_ticker`` with a
0-1 ``similarity_score``. Sources include ``polygon`` (Polygon's
``get_related_companies``), ``sec_peer`` (peers listed in 10-K filings),
``embedding`` (future vector-based builder), or ``manual``.

Pydantic v2; ``from_attributes=True`` so repositories can return
``Competitor.model_validate(orm_row)``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class Competitor(BaseModel):
    """One directional similarity edge between two tickers.

    The CHECK constraint ``ticker != competitor_ticker`` is enforced by
    the database — callers that construct this model from upstream data
    should filter self-references before insertion (otherwise the commit
    raises an IntegrityError).
    """

    ticker: str
    competitor_ticker: str
    similarity_score: Optional[Decimal] = None  # 0.0 - 1.0
    source: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
