"""Polygon.io market data service — real-time prices and company details.

Provides PolygonClient with two main methods:
- get_ticker_snapshot(symbol): last price, change, change%, volume, VWAP, market_status
- get_ticker_details(symbol): company name, sector, market cap, logo URL, description

Caching: 5-second TTL for snapshots (real-time), 1-hour TTL for details (static).
Requires POLYGON_API_KEY env var. Service is disabled (returns None) if not set.
"""

import logging
import os
import time
from typing import Any, Optional

import requests

from app.services.exchange_registry import ExchangeRegistry

logger = logging.getLogger("signal.market_data")

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "")
POLYGON_BASE_URL = "https://api.polygon.io"

SNAPSHOT_TTL = 5  # seconds
DETAILS_TTL = 3600  # 1 hour
FINANCIALS_TTL = 3600  # 1 hour
COMPETITORS_TTL = 3600  # 1 hour


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


class PolygonClient:
    """Client for Polygon.io market data API with in-memory caching."""

    def __init__(self, api_key: Optional[str] = None, db_cache=None) -> None:
        self._api_key = api_key or POLYGON_API_KEY
        self._enabled = bool(self._api_key)
        self._db_cache = db_cache
        self._snapshot_cache: dict[str, _CacheEntry] = {}
        self._details_cache: dict[str, _CacheEntry] = {}
        self._financials_cache: dict[str, _CacheEntry] = {}
        self._earnings_cache: dict[str, _CacheEntry] = {}
        self._competitors_cache: dict[str, _CacheEntry] = {}
        self._exchange_registry = ExchangeRegistry()
        self._session = requests.Session()
        if not self._enabled:
            logger.warning("POLYGON_API_KEY not set — market data service disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_ticker_snapshot(
        self, symbol: str, asset_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Fetch real-time snapshot for a ticker.

        Returns dict with keys: symbol, price, change, change_percent, volume, vwap,
        market_status ('open'|'closed'|'24h'), exchange, next_open, next_close.
        Returns None if service is disabled, symbol not found, or API error.
        """
        if not self._enabled:
            return None

        symbol = symbol.upper().strip()

        # Build cache key that includes asset_type for futures distinction
        cache_key = symbol
        cached = self._snapshot_cache.get(cache_key)
        if cached and cached.is_valid():
            return cached.value

        try:
            # Strip suffix for Polygon API (uses US endpoint for all)
            api_symbol = symbol.split(".")[0] if "." in symbol else symbol
            url = f"{POLYGON_BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{api_symbol}"
            resp = self._session.get(url, params={"apiKey": self._api_key}, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "OK" or "ticker" not in data:
                logger.warning("polygon snapshot: unexpected response for %s: %s", symbol, data.get("status"))
                return None

            ticker = data["ticker"]
            day = ticker.get("day", {})
            prev_day = ticker.get("prevDay", {})
            last_trade = ticker.get("lastTrade", {})

            price = last_trade.get("p") or day.get("c", 0)
            prev_close = prev_day.get("c", 0)
            change = round(price - prev_close, 4) if price and prev_close else 0
            change_pct = round((change / prev_close) * 100, 4) if prev_close else 0

            # Detect exchange and market status
            if asset_type and asset_type.upper() == "FUTURE":
                market_info: dict[str, Any] = {
                    "market_status": "24h",
                    "exchange": "FUTURES",
                    "exchange_name": "Futures Market",
                    "next_open": None,
                    "next_close": None,
                }
            else:
                exchange = self._exchange_registry.detect_exchange(symbol)
                status = self._exchange_registry.get_status(exchange)
                market_info = {
                    "market_status": status["market_status"],
                    "exchange": exchange,
                    "exchange_name": status["name"],
                    "next_open": status["next_open"],
                    "next_close": status["next_close"],
                }

            result: dict[str, Any] = {
                "symbol": symbol,
                "price": price,
                "change": change,
                "change_percent": change_pct,
                "volume": day.get("v", 0),
                "vwap": day.get("vw", 0),
                **market_info,
            }

            self._snapshot_cache[cache_key] = _CacheEntry(result, SNAPSHOT_TTL)
            return result

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("polygon snapshot: ticker %s not found", symbol)
            else:
                logger.warning("polygon snapshot: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("polygon snapshot: error fetching %s: %s", symbol, e)
            return None

    def get_ticker_details(self, symbol: str) -> Optional[dict[str, Any]]:
        """Fetch company details for a ticker.

        Returns dict with keys: symbol, name, sector, market_cap, logo_url, description, homepage_url
        Returns None if service is disabled, symbol not found, or API error.
        """
        if not self._enabled:
            return None

        symbol = symbol.upper().strip()
        cached = self._details_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        # L2: database cache
        if self._db_cache:
            db_hit = self._db_cache.get(symbol, "details")
            if db_hit is not None:
                # Re-append API key to logo_url
                if db_hit.get("logo_url") and self._api_key:
                    db_hit["logo_url"] = f"{db_hit['logo_url']}?apiKey={self._api_key}"
                self._details_cache[symbol] = _CacheEntry(db_hit, DETAILS_TTL)
                return db_hit

        try:
            url = f"{POLYGON_BASE_URL}/v3/reference/tickers/{symbol}"
            resp = self._session.get(url, params={"apiKey": self._api_key}, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "OK" or "results" not in data:
                logger.warning("polygon details: unexpected response for %s: %s", symbol, data.get("status"))
                return None

            results = data["results"]
            branding = results.get("branding", {})
            logo_url = branding.get("icon_url") or branding.get("logo_url") or ""
            if logo_url and self._api_key:
                logo_url = f"{logo_url}?apiKey={self._api_key}"

            result: dict[str, Any] = {
                "symbol": symbol,
                "name": results.get("name", ""),
                "sector": results.get("sic_description", ""),
                "market_cap": results.get("market_cap"),
                "logo_url": logo_url,
                "description": results.get("description", ""),
                "homepage_url": results.get("homepage_url", ""),
            }

            # L2: write-through (strip API key from logo_url before storing)
            if self._db_cache:
                cache_data = dict(result)
                logo = cache_data.get("logo_url", "")
                if "?apiKey=" in logo:
                    cache_data["logo_url"] = logo.split("?apiKey=")[0]
                self._db_cache.put(symbol, "details", cache_data)

            self._details_cache[symbol] = _CacheEntry(result, DETAILS_TTL)
            return result

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("polygon details: ticker %s not found", symbol)
            else:
                logger.warning("polygon details: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("polygon details: error fetching %s: %s", symbol, e)
            return None

    def get_financials(self, symbol: str) -> Optional[dict[str, Any]]:
        """Fetch latest quarterly financials for a ticker.

        Returns dict with keys: symbol, fiscal_period, fiscal_year, revenue,
        net_income, eps, pe_ratio.
        Returns None if service is disabled, data unavailable, or API error.
        P/E ratio is computed from current price and trailing-twelve-month EPS.
        """
        if not self._enabled:
            return None

        symbol = symbol.upper().strip()
        cached = self._financials_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        # L2: database cache
        if self._db_cache:
            db_hit = self._db_cache.get(symbol, "financials")
            if db_hit is not None:
                self._financials_cache[symbol] = _CacheEntry(db_hit, FINANCIALS_TTL)
                return db_hit

        try:
            url = f"{POLYGON_BASE_URL}/vX/reference/financials"
            params: dict[str, Any] = {
                "apiKey": self._api_key,
                "ticker": symbol,
                "timeframe": "quarterly",
                "limit": 4,
                "sort": "period_of_report_date",
                "order": "desc",
            }
            resp = self._session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                result: dict[str, Any] = {
                    "symbol": symbol,
                    "fiscal_period": None,
                    "fiscal_year": None,
                    "revenue": None,
                    "net_income": None,
                    "eps": None,
                    "pe_ratio": None,
                }
                self._financials_cache[symbol] = _CacheEntry(result, FINANCIALS_TTL)
                return result

            latest = results[0]
            financials = latest.get("financials", {})
            income = financials.get("income_statement", {})

            revenue = income.get("revenues", {}).get("value")
            net_income = income.get("net_income_loss", {}).get("value")
            eps = income.get("basic_earnings_per_share", {}).get("value")

            # Compute trailing-twelve-month P/E ratio
            pe_ratio: Optional[float] = None
            ttm_eps = 0.0
            for quarter in results:
                q_income = quarter.get("financials", {}).get("income_statement", {})
                q_eps = q_income.get("basic_earnings_per_share", {}).get("value")
                if q_eps is not None:
                    ttm_eps += q_eps
            if ttm_eps > 0 and len(results) == 4:
                snapshot = self.get_ticker_snapshot(symbol)
                if snapshot and snapshot.get("price"):
                    pe_ratio = round(snapshot["price"] / ttm_eps, 2)

            result = {
                "symbol": symbol,
                "fiscal_period": latest.get("fiscal_period", ""),
                "fiscal_year": latest.get("fiscal_year", ""),
                "revenue": revenue,
                "net_income": net_income,
                "eps": eps,
                "pe_ratio": pe_ratio,
            }

            if self._db_cache:
                self._db_cache.put(symbol, "financials", result)
            self._financials_cache[symbol] = _CacheEntry(result, FINANCIALS_TTL)
            return result

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("polygon financials: ticker %s not found", symbol)
            else:
                logger.warning("polygon financials: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("polygon financials: error fetching %s: %s", symbol, e)
            return None

    def get_earnings(self, symbol: str) -> Optional[dict[str, Any]]:
        """Fetch last 4 quarters of EPS (actual vs estimate) for a ticker.

        Returns dict with keys: symbol, earnings (list of quarterly EPS data).
        Each entry has: fiscal_period, fiscal_year, actual_eps, estimated_eps.
        estimated_eps is None (Polygon.io does not provide consensus estimates).
        Returns None if service is disabled or API error.
        """
        if not self._enabled:
            return None

        symbol = symbol.upper().strip()
        cached = self._earnings_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        # L2: database cache
        if self._db_cache:
            db_hit = self._db_cache.get(symbol, "earnings")
            if db_hit is not None:
                self._earnings_cache[symbol] = _CacheEntry(db_hit, FINANCIALS_TTL)
                return db_hit

        try:
            url = f"{POLYGON_BASE_URL}/vX/reference/financials"
            params: dict[str, Any] = {
                "apiKey": self._api_key,
                "ticker": symbol,
                "timeframe": "quarterly",
                "limit": 4,
                "sort": "period_of_report_date",
                "order": "desc",
            }
            resp = self._session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            earnings: list[dict[str, Any]] = []
            for quarter in results:
                q_income = quarter.get("financials", {}).get("income_statement", {})
                actual_eps = q_income.get("basic_earnings_per_share", {}).get("value")
                earnings.append({
                    "fiscal_period": quarter.get("fiscal_period", ""),
                    "fiscal_year": quarter.get("fiscal_year", ""),
                    "actual_eps": actual_eps,
                    "estimated_eps": None,
                })

            result: dict[str, Any] = {
                "symbol": symbol,
                "earnings": earnings,
            }

            if self._db_cache:
                self._db_cache.put(symbol, "earnings", result)
            self._earnings_cache[symbol] = _CacheEntry(result, FINANCIALS_TTL)
            return result

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("polygon earnings: ticker %s not found", symbol)
            else:
                logger.warning("polygon earnings: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("polygon earnings: error fetching %s: %s", symbol, e)
            return None

    def get_related_companies(self, symbol: str) -> Optional[list[dict[str, Any]]]:
        """Fetch related companies/competitors for a ticker.

        Returns list of up to 5 competitors sorted by market cap (descending),
        each with keys: symbol, name, market_cap, price, change_percent, sector.
        Returns None if service is disabled or API error.
        """
        if not self._enabled:
            return None

        symbol = symbol.upper().strip()
        cached = self._competitors_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        # L2: database cache
        if self._db_cache:
            db_hit = self._db_cache.get(symbol, "competitors")
            if db_hit is not None:
                self._competitors_cache[symbol] = _CacheEntry(db_hit, COMPETITORS_TTL)
                return db_hit

        try:
            url = f"{POLYGON_BASE_URL}/v1/related-companies/{symbol}"
            resp = self._session.get(url, params={"apiKey": self._api_key}, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            related = data.get("results", [])
            if not related:
                result: list[dict[str, Any]] = []
                self._competitors_cache[symbol] = _CacheEntry(result, COMPETITORS_TTL)
                return result

            # Fetch details and snapshot for each related ticker
            candidates: list[dict[str, Any]] = []
            for item in related:
                ticker = item.get("ticker", "")
                if not ticker:
                    continue
                details = self.get_ticker_details(ticker)
                snapshot = self.get_ticker_snapshot(ticker)
                candidates.append({
                    "symbol": ticker,
                    "name": details.get("name", "") if details else "",
                    "market_cap": details.get("market_cap") if details else None,
                    "price": snapshot.get("price", 0) if snapshot else None,
                    "change_percent": snapshot.get("change_percent", 0) if snapshot else None,
                    "sector": details.get("sector", "") if details else "",
                })

            # Sort by market cap descending, limit to top 5
            candidates.sort(
                key=lambda c: c.get("market_cap") or 0,
                reverse=True,
            )
            result = candidates[:5]

            if self._db_cache:
                self._db_cache.put(symbol, "competitors", result)
            self._competitors_cache[symbol] = _CacheEntry(result, COMPETITORS_TTL)
            return result

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("polygon related: ticker %s not found", symbol)
            else:
                logger.warning("polygon related: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("polygon related: error fetching %s: %s", symbol, e)
            return None

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._snapshot_cache.clear()
        self._details_cache.clear()
        self._financials_cache.clear()
        self._earnings_cache.clear()
        self._competitors_cache.clear()
