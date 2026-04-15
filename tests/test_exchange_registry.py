"""Tests for exchange registry — market hours and status detection."""

from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services.exchange_registry import EXCHANGES, ExchangeRegistry


class TestExchangeRegistryBasics:
    """Basic registry tests."""

    def test_supported_exchanges(self):
        reg = ExchangeRegistry()
        supported = reg.supported_exchanges
        assert "NYSE" in supported
        assert "NASDAQ" in supported
        assert "LSE" in supported
        assert "TSE" in supported
        assert "HKEX" in supported

    def test_get_exchange_info(self):
        reg = ExchangeRegistry()
        info = reg.get_exchange_info("NYSE")
        assert info is not None
        assert info["timezone"] == "America/New_York"
        assert len(info["sessions"]) == 1

    def test_unknown_exchange_returns_closed(self):
        reg = ExchangeRegistry()
        status = reg.get_status("FAKE")
        assert status["market_status"] == "closed"
        assert status["exchange"] == "FAKE"


class TestExchangeDetection:
    """Ticker suffix → exchange detection."""

    def test_no_suffix_defaults_to_nyse(self):
        reg = ExchangeRegistry()
        assert reg.detect_exchange("AAPL") == "NYSE"
        assert reg.detect_exchange("MSFT") == "NYSE"

    def test_london_suffix(self):
        reg = ExchangeRegistry()
        assert reg.detect_exchange("HSBA.L") == "LSE"

    def test_tokyo_suffix(self):
        reg = ExchangeRegistry()
        assert reg.detect_exchange("7203.T") == "TSE"

    def test_hong_kong_suffix(self):
        reg = ExchangeRegistry()
        assert reg.detect_exchange("0005.HK") == "HKEX"

    def test_case_insensitive(self):
        reg = ExchangeRegistry()
        assert reg.detect_exchange("hsba.l") == "LSE"


class TestMarketHoursNYSE:
    """NYSE market hours: 9:30-16:00 ET."""

    def test_open_during_trading(self):
        reg = ExchangeRegistry()
        et = ZoneInfo("America/New_York")
        # Wednesday 11:00 AM ET
        mock_now = datetime(2026, 4, 15, 11, 0, 0, tzinfo=et)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("NYSE")
        assert status["market_status"] == "open"
        assert status["exchange"] == "NYSE"
        assert status["next_close"] is not None

    def test_closed_after_hours(self):
        reg = ExchangeRegistry()
        et = ZoneInfo("America/New_York")
        # Wednesday 6:00 PM ET
        mock_now = datetime(2026, 4, 15, 18, 0, 0, tzinfo=et)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("NYSE")
        assert status["market_status"] == "closed"
        assert status["next_open"] is not None

    def test_closed_on_weekend(self):
        reg = ExchangeRegistry()
        et = ZoneInfo("America/New_York")
        # Saturday April 18, 2026
        mock_now = datetime(2026, 4, 18, 12, 0, 0, tzinfo=et)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("NYSE")
        assert status["market_status"] == "closed"


class TestMarketHoursTSE:
    """TSE market hours: 9:00-11:30 + 12:30-15:00 JST (lunch break)."""

    def test_open_morning_session(self):
        reg = ExchangeRegistry()
        jst = ZoneInfo("Asia/Tokyo")
        mock_now = datetime(2026, 4, 15, 10, 0, 0, tzinfo=jst)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("TSE")
        assert status["market_status"] == "open"

    def test_closed_during_lunch(self):
        reg = ExchangeRegistry()
        jst = ZoneInfo("Asia/Tokyo")
        mock_now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=jst)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("TSE")
        assert status["market_status"] == "closed"

    def test_open_afternoon_session(self):
        reg = ExchangeRegistry()
        jst = ZoneInfo("Asia/Tokyo")
        mock_now = datetime(2026, 4, 15, 14, 0, 0, tzinfo=jst)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("TSE")
        assert status["market_status"] == "open"


class TestMarketHoursHKEX:
    """HKEX: 9:30-12:00 + 13:00-16:00 HKT (lunch break)."""

    def test_closed_during_lunch(self):
        reg = ExchangeRegistry()
        hkt = ZoneInfo("Asia/Hong_Kong")
        mock_now = datetime(2026, 4, 15, 12, 30, 0, tzinfo=hkt)
        with patch("app.services.exchange_registry.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = reg.get_status("HKEX")
        assert status["market_status"] == "closed"


class TestExtensibility:
    """Registry supports adding new exchanges via config."""

    def test_custom_exchange(self):
        custom = {
            "SSE": {
                "name": "Shanghai Stock Exchange",
                "timezone": "Asia/Shanghai",
                "sessions": [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
            },
        }
        reg = ExchangeRegistry(exchanges=custom)
        assert "SSE" in reg.supported_exchanges
        info = reg.get_exchange_info("SSE")
        assert info is not None
        assert info["name"] == "Shanghai Stock Exchange"
