"""Tests for authentication middleware and routes."""

from unittest.mock import patch

from app.models import User

MOCK_DECODED_TOKEN = {
    "uid": "firebase-test-uid-123",
    "email": "test@example.com",
    "name": "Test User",
    "picture": "https://example.com/photo.jpg",
}

# Patch target: where verify_id_token is defined (firebase module)
VERIFY_PATCH = "app.auth.firebase.verify_id_token"


class TestAuthMiddleware:
    def test_anonymous_access(self, client):
        """Requests without auth header should work (anonymous/free tier)."""
        resp = client.get("/api/docs")
        assert resp.status_code == 200

    @patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN)
    def test_authenticated_creates_user(self, mock_verify, client, session_factory):
        """First authenticated request should create a user record."""
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer fake-token"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["tier"] == "free"

        # Verify user was persisted
        session = session_factory()
        user = session.query(User).filter_by(firebase_uid="firebase-test-uid-123").first()
        assert user is not None
        assert user.display_name == "Test User"
        session.close()

    @patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN)
    def test_authenticated_updates_profile(self, mock_verify, client, session_factory):
        """Subsequent requests should update profile if changed."""
        # First request creates user
        client.get("/api/auth/me", headers={"Authorization": "Bearer fake-token"})

        # Second request with updated name
        updated = dict(MOCK_DECODED_TOKEN, name="Updated Name")
        mock_verify.return_value = updated
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer fake-token"})
        data = resp.get_json()
        assert data["user"]["display_name"] == "Updated Name"

    @patch(VERIFY_PATCH, side_effect=Exception("Invalid"))
    def test_invalid_token_treated_as_anonymous(self, mock_verify, client):
        """Invalid tokens should result in anonymous access, not errors."""
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-token"
        })
        assert resp.status_code == 401

    def test_missing_bearer_prefix(self, client):
        """Auth header without 'Bearer ' prefix should be ignored."""
        resp = client.get("/api/auth/me", headers={
            "Authorization": "not-a-bearer-token"
        })
        assert resp.status_code == 401


class TestAuthRoutes:
    def test_me_requires_auth(self, client):
        """GET /api/auth/me should return 401 for anonymous users."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Authentication required"

    def test_tier_anonymous(self, client):
        """GET /api/auth/tier should return free tier for anonymous users."""
        resp = client.get("/api/auth/tier")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tier"] == "free"
        assert data["features"]["news_feed"] is True
        assert data["features"]["deduplication"] is False
        assert data["features"]["ai_ticker_recommendations"] is False

    @patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN)
    def test_tier_authenticated_free(self, mock_verify, client):
        """Authenticated free user should get free tier features."""
        resp = client.get("/api/auth/tier", headers={
            "Authorization": "Bearer fake-token"
        })
        data = resp.get_json()
        assert data["tier"] == "free"

    @patch(VERIFY_PATCH, return_value=MOCK_DECODED_TOKEN)
    def test_tier_plus_user(self, mock_verify, client, session_factory):
        """Plus user should get plus tier features."""
        from datetime import datetime, timezone
        from app.services.feed_parser import utc_iso
        now = utc_iso(datetime.now(timezone.utc))
        session = session_factory()
        session.add(User(
            firebase_uid="firebase-test-uid-123",
            email="test@example.com",
            tier="plus",
            created_at=now,
            updated_at=now,
        ))
        session.commit()
        session.close()

        resp = client.get("/api/auth/tier", headers={
            "Authorization": "Bearer fake-token"
        })
        data = resp.get_json()
        assert data["tier"] == "plus"
        assert data["features"]["deduplication"] is True
        assert data["features"]["sentiment_filter"] is True
        assert data["features"]["ai_ticker_recommendations"] is False
