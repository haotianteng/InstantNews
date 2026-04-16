"""Exchange registry — data-driven market hours for global exchanges.

Provides ExchangeRegistry with methods:
- get_status(exchange): current market status ('open'|'closed') with next_open/next_close
- detect_exchange(symbol): infer exchange from ticker suffix (.L→LSE, .T→TSE, .HK→HKEX)

Extensible: add new exchanges (e.g., SSE/SZSE) by appending to EXCHANGES config.
"""

import logging
from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("signal.exchange_registry")

# Each exchange defines: timezone, trading sessions (list of (open, close) time tuples).
# Multiple sessions model lunch breaks (TSE, HKEX).
# To add a new exchange (e.g., SSE for Shanghai): append an entry — no code changes needed.
EXCHANGES: dict[str, dict[str, Any]] = {
    "NYSE": {
        "name": "New York Stock Exchange",
        "timezone": "America/New_York",
        "sessions": [(time(9, 30), time(16, 0))],
    },
    "NASDAQ": {
        "name": "NASDAQ",
        "timezone": "America/New_York",
        "sessions": [(time(9, 30), time(16, 0))],
    },
    "LSE": {
        "name": "London Stock Exchange",
        "timezone": "Europe/London",
        "sessions": [(time(8, 0), time(16, 30))],
    },
    "TSE": {
        "name": "Tokyo Stock Exchange",
        "timezone": "Asia/Tokyo",
        "sessions": [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
    },
    "HKEX": {
        "name": "Hong Kong Stock Exchange",
        "timezone": "Asia/Hong_Kong",
        "sessions": [(time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))],
    },
}

# Ticker suffix → exchange mapping for detect_exchange()
SUFFIX_MAP: dict[str, str] = {
    ".L": "LSE",
    ".T": "TSE",
    ".HK": "HKEX",
}


class ExchangeRegistry:
    """Data-driven registry of global exchange trading hours."""

    def __init__(self, exchanges: Optional[dict[str, dict[str, Any]]] = None) -> None:
        self._exchanges = exchanges or EXCHANGES

    @property
    def supported_exchanges(self) -> list[str]:
        return list(self._exchanges.keys())

    def get_exchange_info(self, exchange: str) -> Optional[dict[str, Any]]:
        return self._exchanges.get(exchange.upper())

    def get_status(self, exchange: str) -> dict[str, Any]:
        """Get current market status for an exchange.

        Returns dict with: exchange, name, market_status ('open'|'closed'),
        next_open (ISO), next_close (ISO).
        """
        exchange = exchange.upper()
        info = self._exchanges.get(exchange)
        if info is None:
            return {
                "exchange": exchange,
                "name": exchange,
                "market_status": "closed",
                "next_open": None,
                "next_close": None,
            }

        tz = ZoneInfo(info["timezone"])
        now = datetime.now(tz)
        sessions: list[tuple[time, time]] = info["sessions"]

        is_open, current_close = self._check_open(now, sessions)

        if is_open and current_close is not None:
            close_dt = now.replace(
                hour=current_close.hour, minute=current_close.minute, second=0, microsecond=0,
            )
            open_dt = self._find_next_open(now, sessions, tz, after_current=True)
            return {
                "exchange": exchange,
                "name": info["name"],
                "market_status": "open",
                "next_open": open_dt.isoformat() if open_dt else None,
                "next_close": close_dt.isoformat(),
            }

        next_open_dt = self._find_next_open(now, sessions, tz, after_current=False)
        next_close_dt: Optional[datetime] = None
        if next_open_dt:
            # next_close is the close of the session that starts at next_open
            open_time = next_open_dt.timetz().replace(tzinfo=None)
            for sess_open, sess_close in sessions:
                if sess_open == open_time:
                    next_close_dt = next_open_dt.replace(
                        hour=sess_close.hour, minute=sess_close.minute, second=0, microsecond=0,
                    )
                    break

        return {
            "exchange": exchange,
            "name": info["name"],
            "market_status": "closed",
            "next_open": next_open_dt.isoformat() if next_open_dt else None,
            "next_close": next_close_dt.isoformat() if next_close_dt else None,
        }

    def detect_exchange(self, symbol: str) -> str:
        """Detect exchange from ticker suffix. No suffix → NYSE (US default)."""
        symbol = symbol.upper().strip()
        for suffix, exchange in SUFFIX_MAP.items():
            if symbol.endswith(suffix.upper()):
                return exchange
        return "NYSE"

    def _check_open(
        self, now: datetime, sessions: list[tuple[time, time]],
    ) -> tuple[bool, Optional[time]]:
        """Check if current time falls within any trading session.

        Returns (is_open, close_time_of_current_session).
        """
        if now.weekday() >= 5:  # Saturday/Sunday
            return False, None

        current_time = now.time()
        for sess_open, sess_close in sessions:
            if sess_open <= current_time < sess_close:
                return True, sess_close
        return False, None

    def _find_next_open(
        self,
        now: datetime,
        sessions: list[tuple[time, time]],
        tz: ZoneInfo,
        after_current: bool,
    ) -> Optional[datetime]:
        """Find next session open time. Skips weekends.

        If after_current=True, skip the current session and find the next one.
        """
        current_time = now.time()

        # Check remaining sessions today (or next session if after_current)
        if now.weekday() < 5:
            found_current = False
            for sess_open, sess_close in sessions:
                if after_current:
                    if sess_open <= current_time < sess_close:
                        found_current = True
                        continue
                    if found_current and sess_open > current_time:
                        return now.replace(
                            hour=sess_open.hour, minute=sess_open.minute, second=0, microsecond=0,
                        )
                else:
                    if sess_open > current_time:
                        return now.replace(
                            hour=sess_open.hour, minute=sess_open.minute, second=0, microsecond=0,
                        )

        # Check next 7 days for the first weekday
        for days_ahead in range(1, 8):
            next_day = now + timedelta(days=days_ahead)
            if next_day.weekday() < 5:  # weekday
                first_open = sessions[0][0]
                return next_day.replace(
                    hour=first_open.hour, minute=first_open.minute, second=0, microsecond=0,
                )

        return None
