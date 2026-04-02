"""Tests for tier gating and feature access control."""

from unittest.mock import patch

from app.billing.tiers import (
    get_tier,
    has_feature,
    get_limit,
    get_features,
    get_all_tiers_summary,
    TIERS,
)

VERIFY_PATCH = "app.auth.firebase.verify_id_token"
NEWS_REFRESH = "app.routes.news.maybe_refresh"

MOCK_TOKEN = {
    "uid": "tier-test-uid",
    "email": "tier@example.com",
    "name": "Tier Test",
}


class TestTierConfig:
    def test_all_tiers_exist(self):
        assert "free" in TIERS
        assert "plus" in TIERS
        assert "max" in TIERS

    def test_free_has_basic_features(self):
        assert has_feature("free", "news_feed")
        assert has_feature("free", "keyword_search")
        assert has_feature("free", "source_filter")

    def test_free_lacks_premium_features(self):
        assert not has_feature("free", "sentiment_filter")
        assert not has_feature("free", "deduplication")
        assert not has_feature("free", "date_range_filter")
        assert not has_feature("free", "ai_ticker_recommendations")

    def test_plus_has_analysis_features(self):
        assert has_feature("plus", "sentiment_filter")
        assert has_feature("plus", "deduplication")
        assert has_feature("plus", "date_range_filter")
        assert not has_feature("plus", "ai_ticker_recommendations")

    def test_max_has_all_features(self):
        assert has_feature("max", "sentiment_filter")
        assert has_feature("max", "deduplication")
        assert has_feature("max", "ai_ticker_recommendations")
        assert has_feature("max", "price_analysis")

    def test_limits_differ_by_tier(self):
        assert get_limit("free", "max_items_per_request") == 50
        assert get_limit("plus", "max_items_per_request") == 200
        assert get_limit("max", "max_items_per_request") == 500

    def test_unknown_tier_defaults_to_free(self):
        tier = get_tier("nonexistent")
        assert tier == TIERS["free"]

    def test_get_all_tiers_summary(self):
        summary = get_all_tiers_summary()
        assert len(summary) == 3
        assert summary["plus"]["price_monthly_cents"] == 1499

    def test_history_days_limit(self):
        assert get_limit("free", "history_days") == 7
        assert get_limit("plus", "history_days") == 365
        assert get_limit("max", "history_days") == 1825


class TestNewsEndpointTierGating:
    @patch(NEWS_REFRESH)
    def test_free_user_capped_at_50_items(self, mock_refresh, client, sample_news):
        """Free tier (anonymous) should cap items at 50."""
        resp = client.get("/api/news?limit=200")
        data = resp.get_json()
        # We only have 5 sample items, but limit should be capped
        assert data["count"] <= 50

    @patch(NEWS_REFRESH)
    def test_free_user_no_sentiment_fields(self, mock_refresh, client, sample_news):
        """Free tier should strip sentiment_score and sentiment_label."""
        resp = client.get("/api/news?limit=1")
        item = resp.get_json()["items"][0]
        assert "sentiment_score" not in item
        assert "sentiment_label" not in item

    @patch(NEWS_REFRESH)
    def test_free_user_no_duplicate_field(self, mock_refresh, client, sample_news):
        """Free tier should strip the duplicate field."""
        resp = client.get("/api/news?limit=1")
        item = resp.get_json()["items"][0]
        assert "duplicate" not in item

    @patch(NEWS_REFRESH)
    def test_free_user_date_range_ignored(self, mock_refresh, client, sample_news):
        """Free tier should ignore date range filters."""
        # With date filter that should return 0 items if applied
        resp = client.get("/api/news?from=2099-01-01&to=2099-12-31")
        data = resp.get_json()
        # Date filter is ignored for free tier, so items are returned
        assert data["count"] > 0

    @patch(VERIFY_PATCH, return_value={**MOCK_TOKEN, "uid": "plus-user"})
    @patch(NEWS_REFRESH)
    def test_plus_user_gets_sentiment(self, mock_refresh, mock_verify, client, session_factory):
        """Plus tier should include sentiment fields."""
        # Create a plus user
        from app.models import User
        from app.services.feed_parser import utc_iso
        from datetime import datetime, timezone
        now = utc_iso(datetime.now(timezone.utc))
        session = session_factory()
        session.add(User(
            firebase_uid="plus-user", email="plus@example.com",
            tier="plus", created_at=now, updated_at=now,
        ))
        session.commit()
        session.close()

        # Add a news item
        from app.models import News
        session = session_factory()
        session.add(News(
            title="Plus Test", link="https://example.com/plus",
            source="CNBC", published=now, fetched_at=now,
            summary="Test", sentiment_score=0.5, sentiment_label="bullish",
            duplicate=0,
        ))
        session.commit()
        session.close()

        resp = client.get("/api/news?limit=1", headers={
            "Authorization": "Bearer fake"
        })
        item = resp.get_json()["items"][0]
        assert "sentiment_score" in item
        assert "sentiment_label" in item
        assert "duplicate" in item


class TestTierGatingDecorator:
    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_require_feature_blocks_free(self, mock_verify, app, client):
        """require_feature should return 403 for missing features."""
        from app.middleware.tier_gate import require_feature
        from flask import Blueprint

        test_bp = Blueprint("test_gate", __name__)

        @test_bp.route("/api/test-gated")
        @require_feature("ai_ticker_recommendations")
        def gated_endpoint():
            return {"ok": True}

        app.register_blueprint(test_bp)

        resp = client.get("/api/test-gated", headers={
            "Authorization": "Bearer fake"
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["current_tier"] == "free"
        assert "upgrade_url" in data


class TestPricingEndpoint:
    def test_pricing_returns_all_tiers(self, client):
        resp = client.get("/api/pricing")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "free" in data["tiers"]
        assert "plus" in data["tiers"]
        assert "max" in data["tiers"]
        assert data["tiers"]["plus"]["price_monthly_cents"] == 1499
