"""Integration tests for API endpoints.

Note: Tests run as anonymous (free tier) by default.
Tier-specific behavior is tested in test_tiers.py.
"""

from unittest.mock import patch

NEWS_REFRESH = "app.routes.news.maybe_refresh"
SOURCES_REFRESH = "app.routes.sources.maybe_refresh"
STATS_REFRESH = "app.routes.stats.maybe_refresh"


class TestNewsRoute:
    @patch(NEWS_REFRESH)
    def test_get_news(self, mock_refresh, client, sample_news):
        resp = client.get("/api/news")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "count" in data
        assert "items" in data
        assert data["count"] == 5

    @patch(NEWS_REFRESH)
    def test_filter_by_source(self, mock_refresh, client, sample_news):
        resp = client.get("/api/news?source=CNBC")
        data = resp.get_json()
        assert all(item["source"] == "CNBC" for item in data["items"])

    @patch(NEWS_REFRESH)
    def test_filter_by_sentiment(self, mock_refresh, client, sample_news):
        # Sentiment filter still works as a query param even for free tier
        # (the DB query filters, but the response strips the label field)
        resp = client.get("/api/news?sentiment=bearish")
        data = resp.get_json()
        assert data["count"] == 1

    @patch(NEWS_REFRESH)
    def test_keyword_search(self, mock_refresh, client, sample_news):
        resp = client.get("/api/news?q=Oil")
        data = resp.get_json()
        assert data["count"] >= 1
        assert any("Oil" in item["title"] for item in data["items"])

    @patch(NEWS_REFRESH)
    def test_limit(self, mock_refresh, client, sample_news):
        resp = client.get("/api/news?limit=2")
        data = resp.get_json()
        assert data["count"] == 2

    @patch(NEWS_REFRESH)
    def test_free_tier_limit_capped_at_50(self, mock_refresh, client, sample_news):
        """Free tier caps at 50 items (not 500)."""
        resp = client.get("/api/news?limit=999")
        data = resp.get_json()
        # We only have 5 items but limit is capped to 50, not 999
        assert data["count"] <= 50

    @patch(NEWS_REFRESH)
    def test_items_have_base_fields(self, mock_refresh, client, sample_news):
        """Free tier items should have base fields but NOT premium fields."""
        resp = client.get("/api/news?limit=1")
        item = resp.get_json()["items"][0]
        # Base fields always present
        for field in ["id", "title", "link", "source", "published", "fetched_at", "summary", "tags"]:
            assert field in item, f"Missing field: {field}"
        # Premium fields stripped for free tier
        assert "sentiment_score" not in item
        assert "sentiment_label" not in item
        assert "duplicate" not in item


class TestSourcesRoute:
    @patch(SOURCES_REFRESH)
    def test_get_sources(self, mock_refresh, client, sample_news):
        resp = client.get("/api/sources")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sources" in data
        source_names = [s["name"] for s in data["sources"]]
        assert "CNBC" in source_names

    @patch(SOURCES_REFRESH)
    def test_source_fields(self, mock_refresh, client, sample_news):
        resp = client.get("/api/sources")
        source = resp.get_json()["sources"][0]
        assert "name" in source
        assert "url" in source
        assert "total_items" in source
        assert "active" in source


class TestStatsRoute:
    @patch(STATS_REFRESH)
    def test_get_stats(self, mock_refresh, client, sample_news):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_items"] == 5
        assert "by_source" in data
        assert "by_sentiment" in data
        assert "avg_sentiment_score" in data
        assert "feed_count" in data
        assert data["feed_count"] == 15


class TestRefreshRoute:
    @patch("app.routes.refresh.refresh_feeds_parallel")
    def test_refresh(self, mock_refresh, client):
        mock_refresh.return_value = (3, {"CNBC": 2, "Reuters_Business": 1})
        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["refreshed"] is True
        assert data["new_items"] == 3
        assert "timestamp" in data


class TestDocsRoute:
    def test_get_docs(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["api"] == "SIGNAL News Trading Terminal API"
        assert len(data["endpoints"]) == 5


class TestStaticRoute:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
