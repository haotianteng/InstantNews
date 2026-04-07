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

MOCK_TOKEN = {
    "uid": "tier-test-uid",
    "email": "tier@example.com",
    "name": "Tier Test",
}


class TestTierConfig:
    def test_all_tiers_exist(self):
        assert "free" in TIERS
        assert "pro" in TIERS
        assert "max" in TIERS
        # Backward compat alias
        assert "plus" in TIERS
        assert TIERS["plus"] is TIERS["pro"]

    def test_free_has_basic_features(self):
        assert has_feature("free", "news_feed")
        assert has_feature("free", "keyword_search")
        assert has_feature("free", "source_filter")

    def test_free_lacks_premium_features(self):
        assert not has_feature("free", "sentiment_filter")
        assert not has_feature("free", "deduplication")
        assert not has_feature("free", "date_range_filter")
        assert not has_feature("free", "ai_ticker_recommendations")

    def test_pro_has_analysis_features(self):
        assert has_feature("pro", "sentiment_filter")
        assert has_feature("pro", "deduplication")
        assert has_feature("pro", "date_range_filter")
        assert not has_feature("pro", "ai_ticker_recommendations")

    def test_plus_alias_works(self):
        """plus is an alias for pro — backward compatibility."""
        assert has_feature("plus", "sentiment_filter")
        assert get_limit("plus", "max_items_per_request") == 200

    def test_max_has_all_features(self):
        assert has_feature("max", "sentiment_filter")
        assert has_feature("max", "deduplication")
        assert has_feature("max", "ai_ticker_recommendations")
        assert has_feature("max", "price_analysis")

    def test_max_is_hidden(self):
        assert TIERS["max"]["visible"] is False

    def test_pro_is_visible(self):
        assert TIERS["pro"]["visible"] is True

    def test_limits_differ_by_tier(self):
        assert get_limit("free", "max_items_per_request") == 50
        assert get_limit("pro", "max_items_per_request") == 200
        assert get_limit("max", "max_items_per_request") == 500

    def test_unknown_tier_defaults_to_free(self):
        tier = get_tier("nonexistent")
        assert tier == TIERS["free"]

    def test_get_all_tiers_summary_excludes_hidden(self):
        summary = get_all_tiers_summary()
        assert "free" in summary
        assert "pro" in summary
        assert "max" not in summary
        assert "plus" not in summary
        assert summary["pro"]["price_monthly_cents"] == 1499

    def test_pro_has_trial(self):
        assert TIERS["pro"]["trial_period_days"] == 30

    def test_history_days_limit(self):
        assert get_limit("free", "history_days") == 7
        assert get_limit("pro", "history_days") == 365
        assert get_limit("max", "history_days") == 1825


class TestNewsEndpointTierGating:
    def test_free_user_capped_at_50_items(self, client, sample_news):
        """Free tier (anonymous) should cap items at 50."""
        resp = client.get("/api/news?limit=200")
        data = resp.get_json()
        # We only have 5 sample items, but limit should be capped
        assert data["count"] <= 50

    def test_free_user_no_sentiment_fields(self, client, sample_news):
        """Free tier should strip sentiment_score and sentiment_label."""
        resp = client.get("/api/news?limit=1")
        item = resp.get_json()["items"][0]
        assert "sentiment_score" not in item
        assert "sentiment_label" not in item

    def test_free_user_no_duplicate_field(self, client, sample_news):
        """Free tier should strip the duplicate field."""
        resp = client.get("/api/news?limit=1")
        item = resp.get_json()["items"][0]
        assert "duplicate" not in item

    def test_free_user_date_range_ignored(self, client, sample_news):
        """Free tier should ignore date range filters."""
        # With date filter that should return 0 items if applied
        resp = client.get("/api/news?from=2099-01-01&to=2099-12-31")
        data = resp.get_json()
        # Date filter is ignored for free tier, so items are returned
        assert data["count"] > 0

    @patch(VERIFY_PATCH, return_value={**MOCK_TOKEN, "uid": "pro-user"})
    def test_pro_user_gets_sentiment(self, mock_verify, client, session_factory):
        """Pro tier should include sentiment fields."""
        # Create a pro user
        from app.models import User
        from app.services.feed_parser import utc_iso
        from datetime import datetime, timezone
        now = utc_iso(datetime.now(timezone.utc))
        session = session_factory()
        session.add(User(
            firebase_uid="pro-user", email="pro@example.com",
            tier="pro", created_at=now, updated_at=now,
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


class TestTerminalAccessGating:
    """Terminal route must redirect Free/unauthenticated users."""

    def test_anonymous_user_redirected_from_terminal(self, client):
        """Unauthenticated visitor should be redirected to landing page."""
        resp = client.get("/terminal")
        assert resp.status_code == 302
        assert "/?upgrade=terminal" in resp.headers["Location"]

    @patch(VERIFY_PATCH, return_value={**MOCK_TOKEN, "uid": "free-terminal-user"})
    def test_free_user_redirected_from_terminal(self, mock_verify, client, session_factory):
        """Free-tier authenticated user should be redirected."""
        from app.models import User
        from app.services.feed_parser import utc_iso
        from datetime import datetime, timezone
        now = utc_iso(datetime.now(timezone.utc))
        session = session_factory()
        session.add(User(
            firebase_uid="free-terminal-user", email="free@example.com",
            tier="free", created_at=now, updated_at=now,
        ))
        session.commit()
        session.close()

        resp = client.get("/terminal", headers={
            "Authorization": "Bearer fake"
        })
        assert resp.status_code == 302
        assert "/?upgrade=terminal" in resp.headers["Location"]

    @patch(VERIFY_PATCH, return_value={**MOCK_TOKEN, "uid": "pro-terminal-user"})
    def test_pro_user_can_access_terminal(self, mock_verify, client, session_factory):
        """Pro-tier user should access terminal (200 OK)."""
        from app.models import User
        from app.services.feed_parser import utc_iso
        from datetime import datetime, timezone
        now = utc_iso(datetime.now(timezone.utc))
        session = session_factory()
        session.add(User(
            firebase_uid="pro-terminal-user", email="pro@example.com",
            tier="pro", created_at=now, updated_at=now,
        ))
        session.commit()
        session.close()

        resp = client.get("/terminal", headers={
            "Authorization": "Bearer fake"
        })
        assert resp.status_code == 200

    def test_free_tier_lacks_terminal_access_feature(self):
        """Free tier should not have terminal_access feature."""
        assert not has_feature("free", "terminal_access")

    def test_pro_tier_has_terminal_access_feature(self):
        """Pro tier should have terminal_access feature."""
        assert has_feature("pro", "terminal_access")

    def test_tier_endpoint_includes_terminal_access(self, client):
        """The /api/auth/tier endpoint should return terminal_access flag."""
        resp = client.get("/api/auth/tier")
        data = resp.get_json()
        assert "terminal_access" in data["features"]
        # Anonymous user = free tier = no terminal access
        assert data["features"]["terminal_access"] is False


class TestPricingEndpoint:
    def test_pricing_returns_visible_tiers_only(self, client):
        resp = client.get("/api/pricing")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "free" in data["tiers"]
        assert "pro" in data["tiers"]
        assert "max" not in data["tiers"]
        assert "plus" not in data["tiers"]
        assert data["tiers"]["pro"]["price_monthly_cents"] == 1499
        assert data["tiers"]["pro"]["trial_period_days"] == 30
