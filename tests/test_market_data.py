"""Tests for Polygon.io market data service."""

from unittest.mock import MagicMock, patch

from app.services.market_data import PolygonClient


class TestPolygonClientDisabled:
    """Tests when POLYGON_API_KEY is not set."""

    def test_disabled_when_no_api_key(self):
        client = PolygonClient(api_key="")
        assert client.enabled is False

    def test_snapshot_returns_none_when_disabled(self):
        client = PolygonClient(api_key="")
        assert client.get_ticker_snapshot("AAPL") is None

    def test_details_returns_none_when_disabled(self):
        client = PolygonClient(api_key="")
        assert client.get_ticker_details("AAPL") is None


class TestPolygonClientEnabled:
    """Tests with a mocked API key."""

    def _make_client(self) -> PolygonClient:
        return PolygonClient(api_key="test-key")

    def test_enabled_with_api_key(self):
        client = self._make_client()
        assert client.enabled is True

    @patch("app.services.market_data.requests.Session.get")
    def test_snapshot_success(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "ticker": {
                "day": {"c": 150.0, "v": 1000000, "vw": 149.5},
                "prevDay": {"c": 148.0},
                "lastTrade": {"p": 150.0},
            },
        }
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_snapshot("AAPL")

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["price"] == 150.0
        assert result["change"] == 2.0
        assert result["change_percent"] == round((2.0 / 148.0) * 100, 4)
        assert result["volume"] == 1000000
        assert result["vwap"] == 149.5

    @patch("app.services.market_data.requests.Session.get")
    def test_snapshot_caching(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "ticker": {
                "day": {"c": 150.0, "v": 1000000, "vw": 149.5},
                "prevDay": {"c": 148.0},
                "lastTrade": {"p": 150.0},
            },
        }
        mock_get.return_value = mock_resp

        client = self._make_client()
        client.get_ticker_snapshot("AAPL")
        client.get_ticker_snapshot("AAPL")  # should hit cache

        assert mock_get.call_count == 1

    @patch("app.services.market_data.requests.Session.get")
    def test_snapshot_normalizes_symbol(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "ticker": {
                "day": {"c": 100.0, "v": 500, "vw": 99.0},
                "prevDay": {"c": 100.0},
                "lastTrade": {"p": 100.0},
            },
        }
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_snapshot("aapl")
        assert result is not None
        assert result["symbol"] == "AAPL"

    @patch("app.services.market_data.requests.Session.get")
    def test_snapshot_http_error(self, mock_get: MagicMock):
        import requests

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_snapshot("BAD")
        assert result is None

    @patch("app.services.market_data.requests.Session.get")
    def test_snapshot_404(self, mock_get: MagicMock):
        import requests

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_snapshot("ZZZZZ")
        assert result is None

    @patch("app.services.market_data.requests.Session.get")
    def test_details_success(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "results": {
                "name": "Apple Inc.",
                "sic_description": "Electronic Computers",
                "market_cap": 3000000000000,
                "branding": {
                    "icon_url": "https://api.polygon.io/icon.png",
                    "logo_url": "https://api.polygon.io/logo.png",
                },
                "description": "Apple designs consumer electronics.",
                "homepage_url": "https://apple.com",
            },
        }
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_details("AAPL")

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["sector"] == "Electronic Computers"
        assert result["market_cap"] == 3000000000000
        assert "icon.png" in result["logo_url"]
        assert "apiKey=test-key" in result["logo_url"]
        assert result["description"] == "Apple designs consumer electronics."
        assert result["homepage_url"] == "https://apple.com"

    @patch("app.services.market_data.requests.Session.get")
    def test_details_caching(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "results": {
                "name": "Apple",
                "sic_description": "",
                "branding": {},
                "description": "",
                "homepage_url": "",
            },
        }
        mock_get.return_value = mock_resp

        client = self._make_client()
        client.get_ticker_details("AAPL")
        client.get_ticker_details("AAPL")

        assert mock_get.call_count == 1

    @patch("app.services.market_data.requests.Session.get")
    def test_details_not_found(self, mock_get: MagicMock):
        import requests

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_details("ZZZZZ")
        assert result is None

    @patch("app.services.market_data.requests.Session.get")
    def test_details_network_error(self, mock_get: MagicMock):
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("network down")

        client = self._make_client()
        result = client.get_ticker_details("AAPL")
        assert result is None

    def test_clear_cache(self):
        client = self._make_client()
        # Manually populate caches
        from app.services.market_data import _CacheEntry
        client._snapshot_cache["TEST"] = _CacheEntry({"symbol": "TEST"}, 999)
        client._details_cache["TEST"] = _CacheEntry({"symbol": "TEST"}, 999)

        client.clear_cache()
        assert len(client._snapshot_cache) == 0
        assert len(client._details_cache) == 0
