"""Pydantic schema for the ``institutional_holders`` 13F snapshot table.

Each row is one institution's reported holdings of one ticker on one
report date. Re-ingestion of the same 13F is a no-op via the UNIQUE
constraint on ``(ticker, institution_cik, report_date)`` — callers do
not need app-side dedup.

Pydantic v2; ``from_attributes=True`` so repositories can return
``InstitutionalHolder.model_validate(orm_row)``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class InstitutionalHolder(BaseModel):
    """One institution's holdings of one ticker on one 13F report date."""

    id: Optional[int] = None
    ticker: str
    institution_cik: Optional[str] = None
    institution_name: Optional[str] = None
    report_date: date
    shares_held: Optional[int] = None
    market_value: Optional[int] = None
    pct_of_portfolio: Optional[Decimal] = None
    pct_of_company: Optional[Decimal] = None
    change_shares: Optional[int] = None
    filing_date: Optional[date] = None

    model_config = {"from_attributes": True}
