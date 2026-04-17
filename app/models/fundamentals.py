"""Pydantic schemas for ``company_fundamentals`` + its SCD-2 history.

Two models, one current-view + one append-only history row, matching the
tables created in ``migrations/versions/016_add_company_fundamentals.py``.

* ``Fundamentals`` — mirrors ``company_fundamentals``, PK = ``ticker``.
  Repositories hand this out on the hot read path.
* ``FundamentalsHistory`` — mirrors ``company_fundamentals_history``,
  PK = ``(ticker, valid_from)``. Used for point-in-time ``get_at(ticker,
  ts)`` queries; the Postgres trigger populates it automatically on each
  UPDATE to the current-view table.

Pydantic v2; ``from_attributes=True`` so callers can do
``Fundamentals.model_validate(orm_row)``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class Fundamentals(BaseModel):
    """Current-view fundamentals snapshot for a ticker.

    Mirrors ``company_fundamentals``. All non-PK fields are ``Optional``
    because upstream (Polygon) populates different subsets per ticker and
    per fetch — we do not synthesize defaults.
    """

    ticker: str
    market_cap: Optional[int] = None
    shares_outstanding: Optional[int] = None
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None
    ev_ebitda: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    beta: Optional[Decimal] = None
    next_earnings_date: Optional[date] = None
    next_earnings_time: Optional[str] = None  # BMO / AMC
    analyst_rating: Optional[Decimal] = None
    price_target_mean: Optional[Decimal] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FundamentalsHistory(BaseModel):
    """A single historical snapshot of fundamentals for a ticker.

    Mirrors ``company_fundamentals_history``. The SCD-2 validity interval
    is ``[valid_from, valid_to)`` — a row with ``valid_to = NOW()`` is the
    most recent snapshot written by the trigger.
    """

    ticker: str
    market_cap: Optional[int] = None
    shares_outstanding: Optional[int] = None
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None
    ev_ebitda: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    beta: Optional[Decimal] = None
    next_earnings_date: Optional[date] = None
    next_earnings_time: Optional[str] = None
    analyst_rating: Optional[Decimal] = None
    price_target_mean: Optional[Decimal] = None
    updated_at: Optional[datetime] = None
    valid_from: datetime
    valid_to: datetime

    model_config = {"from_attributes": True}
