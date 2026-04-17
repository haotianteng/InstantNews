"""Pydantic aggregate returned by :class:`CompanyService.get_full_profile`.

One flat container that holds the 6 company-info domains for a single
ticker plus two envelope fields:

* ``partial`` — ``True`` when at least one domain failed to load (cache
  miss + DB miss + upstream failure, or a Redis mutex timeout). Callers
  still get every domain that succeeded; the missing ones are ``None``
  (scalar fields) or an empty list (list fields).
* ``fetched_at`` — wall-clock timestamp when the aggregator started
  assembling the profile. Not a freshness per-field stamp (each domain
  carries its own ``updated_at`` / ``ingested_at`` where relevant).

All domain fields are optional so the model is cheap to construct even
when upstream data is incomplete. ``from_attributes`` is intentionally
omitted — this aggregate is constructed in Python rather than validated
from an ORM row.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.company import Company
from app.models.competitors import Competitor
from app.models.financials import Financials
from app.models.fundamentals import Fundamentals
from app.models.insiders import InsiderTransaction
from app.models.institutions import InstitutionalHolder


class CompanyProfile(BaseModel):
    """Full company profile aggregate for one ticker."""

    company: Optional[Company] = None
    fundamentals: Optional[Fundamentals] = None
    latest_financials: Optional[Financials] = None
    competitors: List[Competitor] = Field(default_factory=list)
    top_institutions: List[InstitutionalHolder] = Field(default_factory=list)
    recent_insiders: List[InsiderTransaction] = Field(default_factory=list)

    partial: bool = False
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
