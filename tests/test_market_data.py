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
            "results": [{
                "session": {
                    "price": 150.0,
                    "close": 150.0,
                    "previous_close": 148.0,
                    "change": 2.0,
                    "change_percent": round((2.0 / 148.0) * 100, 4),
                    "volume": 1000000,
                    "vwap": 149.5,
                },
            }],
        }
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.get_ticker_snapshot("AAPL")

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["price"] == 150.0
        assert result["change"] == 2.0
        assert result["change_percent"] == round((2.0 / 148.0) * 100, 4)  # from session directly
        assert result["volume"] == 1000000
        assert result["vwap"] == 149.5

    @patch("app.services.market_data.requests.Session.get")
    def test_snapshot_caching(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [{
                "session": {
                    "price": 150.0,
                    "close": 150.0,
                    "previous_close": 148.0,
                    "change": 2.0,
                    "change_percent": round((2.0 / 148.0) * 100, 4),
                    "volume": 1000000,
                    "vwap": 149.5,
                },
            }],
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
            "results": [{
                "session": {
                    "price": 100.0,
                    "close": 100.0,
                    "previous_close": 100.0,
                    "change": 0,
                    "change_percent": 0,
                    "volume": 500,
                    "vwap": 99.0,
                },
            }],
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

    @patch("app.services.market_data.requests.Session.get")
    def test_get_related_companies_competitor_success(self, mock_get: MagicMock):
        """get_related_companies returns top 5 competitors sorted by market cap."""
        call_count = 0

        def side_effect(url: str, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()

            if "/v1/related-companies/" in url:
                mock_resp.json.return_value = {
                    "results": [
                        {"ticker": "MSFT"},
                        {"ticker": "GOOG"},
                        {"ticker": "META"},
                    ],
                }
            elif "/v3/reference/tickers/" in url:
                ticker = url.split("/")[-1]
                caps = {"MSFT": 3000000000000, "GOOG": 2000000000000, "META": 1000000000000}
                mock_resp.json.return_value = {
                    "status": "OK",
                    "results": {
                        "name": f"{ticker} Inc.",
                        "sic_description": "Tech",
                        "market_cap": caps.get(ticker, 0),
                        "branding": {},
                        "description": "",
                        "homepage_url": "",
                    },
                }
            elif "/v3/snapshot" in url:
                mock_resp.json.return_value = {
                    "results": [{
                        "session": {
                            "price": 200.0,
                            "close": 200.0,
                            "previous_close": 195.0,
                            "change": 5.0,
                            "change_percent": round((5.0 / 195.0) * 100, 4),
                            "volume": 500000,
                            "vwap": 199.0,
                        },
                    }],
                }
            return mock_resp

        mock_get.side_effect = side_effect

        client = self._make_client()
        result = client.get_related_companies("AAPL")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3
        # Sorted by market cap descending
        assert result[0]["symbol"] == "MSFT"
        assert result[0]["market_cap"] == 3000000000000
        assert result[1]["symbol"] == "GOOG"
        assert result[2]["symbol"] == "META"
        # Each entry has required fields
        for comp in result:
            assert "symbol" in comp
            assert "name" in comp
            assert "market_cap" in comp
            assert "price" in comp
            assert "change_percent" in comp

    @patch("app.services.market_data.requests.Session.get")
    def test_get_related_companies_competitor_limit_5(self, mock_get: MagicMock):
        """get_related_companies limits to top 5 by market cap."""

        def side_effect(url: str, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()

            if "/v1/related-companies/" in url:
                mock_resp.json.return_value = {
                    "results": [{"ticker": f"T{i}"} for i in range(7)],
                }
            elif "/v3/reference/tickers/" in url:
                ticker = url.split("/")[-1]
                idx = int(ticker[1:]) if ticker[1:].isdigit() else 0
                mock_resp.json.return_value = {
                    "status": "OK",
                    "results": {
                        "name": f"{ticker} Inc.",
                        "sic_description": "Tech",
                        "market_cap": (7 - idx) * 1000000000,
                        "branding": {},
                        "description": "",
                        "homepage_url": "",
                    },
                }
            elif "/v2/snapshot/" in url:
                mock_resp.json.return_value = {
                    "status": "OK",
                    "ticker": {
                        "day": {"c": 100.0, "v": 100, "vw": 100.0},
                        "prevDay": {"c": 100.0},
                        "lastTrade": {"p": 100.0},
                    },
                }
            return mock_resp

        mock_get.side_effect = side_effect

        client = self._make_client()
        result = client.get_related_companies("AAPL")

        assert result is not None
        assert len(result) == 5

    @patch("app.services.market_data.requests.Session.get")
    def test_get_related_companies_competitor_caching(self, mock_get: MagicMock):
        """get_related_companies caches results."""

        def side_effect(url: str, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()

            if "/v1/related-companies/" in url:
                mock_resp.json.return_value = {"results": []}
            return mock_resp

        mock_get.side_effect = side_effect

        client = self._make_client()
        client.get_related_companies("AAPL")
        client.get_related_companies("AAPL")  # should hit cache

        # Only one call to the related-companies endpoint
        related_calls = [c for c in mock_get.call_args_list if "/v1/related-companies/" in str(c)]
        assert len(related_calls) == 1

    def test_get_related_companies_competitor_disabled(self):
        """get_related_companies returns None when disabled."""
        client = PolygonClient(api_key="")
        assert client.get_related_companies("AAPL") is None

    def test_clear_cache(self):
        client = self._make_client()
        # Manually populate caches
        from app.services.market_data import _CacheEntry
        client._snapshot_cache["TEST"] = _CacheEntry({"symbol": "TEST"}, 999)
        client._details_cache["TEST"] = _CacheEntry({"symbol": "TEST"}, 999)
        client._competitors_cache["TEST"] = _CacheEntry([], 999)

        client.clear_cache()
        assert len(client._snapshot_cache) == 0
        assert len(client._details_cache) == 0
        assert len(client._competitors_cache) == 0
