"""Pydantic schema for the ``company_financials`` append-only table.

One row per quarterly or annual filing for a ticker. The composite PK
``(ticker, period_end, period_type)`` is the dedup key — re-ingesting the
same filing raises an integrity error at the DB layer, so callers never
need app-side dedup logic.

Pydantic v2; ``from_attributes=True`` lets repositories return
``Financials.model_validate(orm_row)``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class Financials(BaseModel):
    """Single filing snapshot for a ticker. Mirrors
    ``migrations/versions/015_add_company_financials.py``.

    All metric fields are ``Optional`` because upstream sources
    (EDGAR XBRL, Polygon) may not populate every line item for every
    filing (e.g. banks don't report gross_profit, small-caps may omit
    diluted EPS).
    """

    # Composite primary key — required
    ticker: str
    period_end: date
    period_type: str  # Q1/Q2/Q3/Q4/FY
    fiscal_year: int

    # Income statement
    revenue: Optional[int] = None
    gross_profit: Optional[int] = None
    operating_income: Optional[int] = None
    net_income: Optional[int] = None
    eps_basic: Optional[Decimal] = None
    eps_diluted: Optional[Decimal] = None

    # Balance sheet
    total_assets: Optional[int] = None
    total_liabilities: Optional[int] = None
    total_equity: Optional[int] = None
    cash_equivalents: Optional[int] = None
    long_term_debt: Optional[int] = None

    # Cash flow
    operating_cf: Optional[int] = None
    investing_cf: Optional[int] = None
    financing_cf: Optional[int] = None
    free_cash_flow: Optional[int] = None

    # Metadata
    filing_date: Optional[date] = None
    source: Optional[str] = None
    ingested_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
