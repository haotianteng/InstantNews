"""Tests for rate limiting middleware."""

from unittest.mock import patch

from app.billing.tiers import get_limit

VERIFY_PATCH = "app.auth.firebase.verify_id_token"

MOCK_TOKEN = {
    "uid": "ratelimit-test-uid",
    "email": "ratelimit@example.com",
    "name": "Rate Limit Test",
}


class TestRateLimitConfig:
    """Verify rate limits are defined in tier config."""

    def test_free_tier_rate_limit(self):
        rate = get_limit("free", "api_rate_per_minute")
        assert rate == 30

    def test_pro_tier_rate_limit(self):
        rate = get_limit("pro", "api_rate_per_minute")
        assert rate == 300

    def test_max_tier_rate_limit(self):
        rate = get_limit("max", "api_rate_per_minute")
        assert rate == 1000


class TestRateLimitHeaders:
    """Verify rate limit headers are present on API responses."""

    def test_api_response_includes_rate_limit_headers(self, client, sample_news):
        resp = client.get("/api/news")
        assert resp.status_code == 200
        # Flask-Limiter >=3.x uses IETF draft headers by default
        has_ietf = "RateLimit-Limit" in resp.headers or "RateLimit-Policy" in resp.headers
        has_legacy = "X-RateLimit-Limit" in resp.headers
        assert has_ietf or has_legacy, (
            f"No rate limit headers found. Headers: {dict(resp.headers)}"
        )


class TestRateLimitEnforcement:
    """Verify that exceeding rate limits returns 429."""

    def test_anonymous_rate_limit_exceeded(self, client, sample_news):
        """Anonymous users should be limited to free tier (10/min)."""
        free_limit = get_limit("free", "api_rate_per_minute")
        # Make requests up to the limit
        for i in range(free_limit):
            resp = client.get("/api/news")
            assert resp.status_code == 200, f"Request {i+1} should succeed"

        # Next request should be rate limited
        resp = client.get("/api/news")
        assert resp.status_code == 429
        data = resp.get_json()
        assert data["error"] == "Rate limit exceeded"
        assert "upgrade_url" in data

    def test_static_pages_not_rate_limited(self, client):
        """Non-API routes should not be rate limited."""
        # Make many requests to a static page
        for _ in range(20):
            resp = client.get("/")
            # Static page may return 200 or 404 depending on setup,
            # but should never return 429
            assert resp.status_code != 429


class TestRateLimitByTier:
    """Verify different tiers have different rate limits."""

    @patch(VERIFY_PATCH)
    def test_pro_user_higher_limit(self, mock_verify, client, db_session):
        """Pro users should have a higher rate limit than free."""
        mock_verify.return_value = MOCK_TOKEN

        # Create a pro-tier user
        from app.models import User
        from app.services.feed_parser import utc_iso
        from datetime import datetime, timezone

        now = utc_iso(datetime.now(timezone.utc))
        user = User(
            firebase_uid=MOCK_TOKEN["uid"],
            email=MOCK_TOKEN["email"],
            display_name=MOCK_TOKEN["name"],
            tier="pro",
            created_at=now,
            updated_at=now,
        )
        db_session.add(user)
        db_session.commit()

        headers = {"Authorization": "Bearer fake-token"}
        free_limit = get_limit("free", "api_rate_per_minute")

        # Make more requests than free tier allows — should all succeed for pro
        for i in range(free_limit + 1):
            resp = client.get("/api/news", headers=headers)
            assert resp.status_code == 200, (
                f"Pro user request {i+1} should succeed (limit is "
                f"{get_limit('pro', 'api_rate_per_minute')})"
            )
