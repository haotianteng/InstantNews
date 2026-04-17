"""Centralized Redis cache key builders for the company-info layer.

All keys follow the ``company:{TICKER}:{domain}`` namespacing convention
from the PRD §2. Builders uppercase the ticker so callers can pass either
``"aapl"`` or ``"AAPL"`` — the resulting key is always deterministic.

The :data:`TTL` mapping is the single source of truth for per-domain
cache lifetime (in seconds). Repositories import these keys and TTLs
rather than hard-coding strings so a change here propagates everywhere.
"""

from __future__ import annotations


def company_master(ticker: str) -> str:
    """Master reference row for a ticker (``companies`` table)."""
    return f"company:{ticker.upper()}:master"


def company_fundamentals(ticker: str) -> str:
    """Current-view fundamentals snapshot (``company_fundamentals``)."""
    return f"company:{ticker.upper()}:fundamentals"


def company_financials_latest(ticker: str) -> str:
    """Latest filing row in ``company_financials`` for a ticker."""
    return f"company:{ticker.upper()}:financials:latest"


def company_financials_range(ticker: str, start: str, end: str) -> str:
    """Range query for ``company_financials`` — keyed by ISO date bounds."""
    return f"company:{ticker.upper()}:financials:range:{start}:{end}"


def company_competitors_top(ticker: str, n: int) -> str:
    """Top-N competitors by similarity score for a ticker."""
    return f"company:{ticker.upper()}:competitors:top{n}"


def company_institutions_top(ticker: str, n: int) -> str:
    """Top-N institutional holders by market value for a ticker."""
    return f"company:{ticker.upper()}:institutions:top{n}"


def company_insiders_recent(ticker: str, days: int) -> str:
    """Recent insider transactions for a ticker in the last N days."""
    return f"company:{ticker.upper()}:insiders:{days}d"


def company_lock(ticker: str, domain: str) -> str:
    """Per-(ticker, domain) Redis mutex key for on-demand backfill.

    Used by the future ``CompanyService`` (US-011) to serialize concurrent
    backfill requests. Domain is a free-form short string such as
    ``"fundamentals"`` or ``"competitors"``.
    """
    return f"lock:company:{ticker.upper()}:{domain}"


# Per-domain TTL in seconds. Matches spec §2 "TTL table".
TTL: dict[str, int] = {
    "master": 86400,            # 24h — master row rarely changes
    "fundamentals": 300,        # 5m — Polygon snapshot cadence
    "financials_latest": 3600,  # 1h — latest filing refresh
    "competitors": 86400,       # 24h — similarity graph is stable
    "institutions": 21600,      # 6h — 13F quarterly, but window-aware
    "insiders": 900,            # 15m — Form 4 arrives continuously
}
