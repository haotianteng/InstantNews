"""Integration tests for API endpoints.

Note: Tests run as anonymous (free tier) by default.
Tier-specific behavior is tested in test_tiers.py.

Feed refresh no longer runs inline — it only runs in the worker process.
"""

from unittest.mock import patch


class TestNewsRoute:
    def test_get_news(self, client, sample_news):
        resp = client.get("/api/news")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "count" in data
        assert "items" in data
        assert data["count"] == 5

    def test_filter_by_source(self, client, sample_news):
        resp = client.get("/api/news?source=CNBC")
        data = resp.get_json()
        assert all(item["source"] == "CNBC" for item in data["items"])

    def test_filter_by_sentiment(self, client, sample_news):
        # Sentiment filter still works as a query param even for free tier
        # (the DB query filters, but the response strips the label field)
        resp = client.get("/api/news?sentiment=bearish")
        data = resp.get_json()
        assert data["count"] == 1

    def test_keyword_search(self, client, sample_news):
        resp = client.get("/api/news?q=Oil")
        data = resp.get_json()
        assert data["count"] >= 1
        assert any("Oil" in item["title"] for item in data["items"])

    def test_limit(self, client, sample_news):
        resp = client.get("/api/news?limit=2")
        data = resp.get_json()
        assert data["count"] == 2

    def test_free_tier_limit_capped_at_50(self, client, sample_news):
        """Free tier caps at 50 items (not 500)."""
        resp = client.get("/api/news?limit=999")
        data = resp.get_json()
        # We only have 5 items but limit is capped to 50, not 999
        assert data["count"] <= 50

    def test_items_have_base_fields(self, client, sample_news):
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
    def test_get_sources(self, client, sample_news):
        from app.routes.sources import _sources_cache
        _sources_cache.clear()

        resp = client.get("/api/sources")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sources" in data
        source_names = [s["name"] for s in data["sources"]]
        assert "CNBC" in source_names

    def test_source_fields(self, client, sample_news):
        from app.routes.sources import _sources_cache
        _sources_cache.clear()

        resp = client.get("/api/sources")
        source = resp.get_json()["sources"][0]
        assert "name" in source
        assert "url" in source
        assert "total_items" in source
        assert "active" in source


class TestStatsRoute:
    def test_get_stats(self, client, sample_news):
        # Clear stats cache to avoid stale data from other tests
        from app.routes.stats import _stats_cache
        _stats_cache.clear()

        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_items"] == 5
        assert "by_source" in data
        assert "feed_count" in data
        assert data["feed_count"] == 15
        # Free tier (anonymous) should NOT see sentiment aggregates
        assert "by_sentiment" not in data
        assert "avg_sentiment_score" not in data

    def test_stats_cache_returns_same_data(self, client, sample_news):
        """Second request within TTL should return cached data."""
        from app.routes.stats import _stats_cache
        _stats_cache.clear()

        resp1 = client.get("/api/stats")
        resp2 = client.get("/api/stats")
        assert resp1.get_json() == resp2.get_json()

    def test_sources_cache_returns_same_data(self, client, sample_news):
        """Second /api/sources request within TTL should return cached data."""
        from app.routes.sources import _sources_cache
        _sources_cache.clear()

        resp1 = client.get("/api/sources")
        resp2 = client.get("/api/sources")
        assert resp1.get_json() == resp2.get_json()


class TestRefreshRoute:
    @patch("app.routes.refresh.refresh_feeds_parallel")
    def test_refresh_unauthenticated(self, mock_refresh, client):
        """Unauthenticated users should get 401."""
        resp = client.post("/api/refresh")
        assert resp.status_code == 401

    @patch("app.routes.refresh.refresh_feeds_parallel")
    @patch("app.auth.firebase.verify_id_token")
    def test_refresh_authenticated(self, mock_verify, mock_refresh, client, db_session):
        """Authenticated users can trigger refresh."""
        from app.models import User
        from app.services.feed_parser import utc_iso
        from datetime import datetime, timezone

        mock_verify.return_value = {
            "uid": "refresh-test-uid",
            "email": "refresh@example.com",
            "name": "Refresh Test",
        }
        now = utc_iso(datetime.now(timezone.utc))
        user = User(
            firebase_uid="refresh-test-uid",
            email="refresh@example.com",
            display_name="Refresh Test",
            tier="pro",
            created_at=now,
            updated_at=now,
        )
        db_session.add(user)
        db_session.commit()

        mock_refresh.return_value = (3, {"CNBC": 2, "Reuters_Business": 1})
        resp = client.post("/api/refresh", headers={"Authorization": "Bearer fake-token"})
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
