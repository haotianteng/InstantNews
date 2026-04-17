"""Pydantic schema for the ``insider_transactions`` table (Form 4/5).

Each row is a single insider transaction (buy/sell/option exercise) as
reported to the SEC. Re-ingesting the same filing is a no-op via the
composite UNIQUE constraint
``(ticker, insider_name, transaction_date, transaction_type, shares,
form_type)`` (see the 019 migration for rationale).

Pydantic v2; ``from_attributes=True`` so repositories can return
``InsiderTransaction.model_validate(orm_row)``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class InsiderTransaction(BaseModel):
    """One insider transaction row (SEC Form 4 or Form 5)."""

    id: Optional[int] = None
    ticker: str
    insider_name: Optional[str] = None
    insider_title: Optional[str] = None
    transaction_date: date
    transaction_type: Optional[str] = None  # BUY / SELL / OPTION_EXERCISE
    shares: Optional[int] = None
    price_per_share: Optional[Decimal] = None
    total_value: Optional[int] = None
    shares_owned_after: Optional[int] = None
    filing_date: Optional[date] = None
    form_type: Optional[str] = None  # Form 4 / Form 5
    sec_url: Optional[str] = None

    model_config = {"from_attributes": True}
