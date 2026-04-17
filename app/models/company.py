"""Pydantic schema for the ``companies`` master-reference table.

This is the API / repository return type — separate from the SQLAlchemy
ORM model (``app.models.Company``). Repositories constructed via
``BaseRepository[Company]`` hand these out so callers never see SQLAlchemy
row objects or sessions (see US-008, US-009).

Pydantic v2 only. ``model_config = {"from_attributes": True}`` lets callers
do ``Company.model_validate(orm_row)`` to convert from the ORM model.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class Company(BaseModel):
    """Master reference data for a ticker. Mirrors the ``companies`` table
    defined in ``migrations/versions/014_add_companies_table.py``.

    All columns except ``ticker`` and ``name`` are nullable — upstream data
    sources (Polygon, EDGAR) fill in different subsets per ticker. Keep this
    permissive so ingestion code doesn't need to synthesize defaults.
    """

    ticker: str
    cik: Optional[str] = None
    name: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    employee_count: Optional[int] = None
    founded_year: Optional[int] = None
    ipo_date: Optional[date] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # OQ-5 resolution: delisted tickers keep their rows (for historical
    # queries / backtests) but scheduled jobs filter WHERE delisted_at IS NULL.
    delisted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
