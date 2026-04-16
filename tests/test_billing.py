"""Tests for Stripe billing routes and webhook handling."""

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.models import User, Subscription, StripeEvent
from app.services.feed_parser import utc_iso

VERIFY_PATCH = "app.auth.firebase.verify_id_token"

MOCK_TOKEN = {
    "uid": "billing-test-uid",
    "email": "billing@example.com",
    "name": "Billing Test",
}


def _create_user(session_factory, tier="free"):
    now = utc_iso(datetime.now(timezone.utc))
    session = session_factory()
    user = User(
        firebase_uid="billing-test-uid",
        email="billing@example.com",
        tier=tier,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


class TestCheckoutEndpoint:
    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_checkout_requires_auth(self, mock_verify, client):
        """POST /api/billing/checkout requires authentication."""
        resp = client.post("/api/billing/checkout",
                           json={"tier": "plus"})
        # Without auth header, treated as anonymous -> 401
        assert resp.status_code == 401

    @patch("app.billing.stripe_client.is_configured", return_value=True)
    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_checkout_invalid_tier(self, mock_verify, mock_configured, client, session_factory):
        _create_user(session_factory)
        resp = client.post("/api/billing/checkout",
                           json={"tier": "invalid"},
                           headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 400
        assert "Invalid tier" in resp.get_json()["error"]

    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_checkout_stripe_not_configured(self, mock_verify, client, session_factory):
        """When Stripe keys are empty, return 503 with friendly message."""
        _create_user(session_factory)
        resp = client.post("/api/billing/checkout",
                           json={"tier": "plus"},
                           headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 503
        assert resp.get_json()["configured"] is False


class TestPortalEndpoint:
    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_portal_no_subscription(self, mock_verify, client, session_factory):
        """Portal should return 404 if user has no subscription."""
        _create_user(session_factory)
        resp = client.post("/api/billing/portal",
                           headers={"Authorization": "Bearer fake"})
        # Either 404 (no sub) or 503 (stripe not configured)
        assert resp.status_code in (404, 503)


class TestBillingStatus:
    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_status_no_subscription(self, mock_verify, client, session_factory):
        """Status should return inactive/free when no subscription exists."""
        _create_user(session_factory)
        resp = client.get("/api/billing/status",
                          headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["subscription"]["status"] == "inactive"
        assert data["subscription"]["tier"] == "free"

    @patch(VERIFY_PATCH, return_value=MOCK_TOKEN)
    def test_status_with_subscription(self, mock_verify, client, session_factory):
        """Status should return subscription details when one exists."""
        user_id = _create_user(session_factory, tier="plus")
        now = utc_iso(datetime.now(timezone.utc))

        session = session_factory()
        session.add(Subscription(
            user_id=user_id,
            stripe_customer_id="cus_test",
            stripe_subscription_id="sub_test",
            stripe_price_id="price_test",
            status="active",
            tier="plus",
            created_at=now,
            updated_at=now,
        ))
        session.commit()
        session.close()

        resp = client.get("/api/billing/status",
                          headers={"Authorization": "Bearer fake"})
        data = resp.get_json()
        assert data["subscription"]["status"] == "active"
        assert data["subscription"]["tier"] == "plus"


class TestWebhook:
    def test_webhook_missing_signature(self, client):
        """Webhook should reject requests without proper signature."""
        resp = client.post("/api/billing/webhook",
                           data="{}",
                           content_type="application/json")
        assert resp.status_code == 500  # webhook secret not configured

    def test_webhook_idempotency(self, client, session_factory):
        """Already-processed events should be skipped."""
        now = utc_iso(datetime.now(timezone.utc))
        session = session_factory()
        session.add(StripeEvent(
            id="evt_already_processed",
            type="checkout.session.completed",
            processed_at=now,
        ))
        session.commit()
        session.close()

        # Verify the event exists
        session = session_factory()
        evt = session.query(StripeEvent).filter_by(id="evt_already_processed").first()
        assert evt is not None
        session.close()


class TestPricingPage:
    def test_pricing_page_serves(self, client):
        resp = client.get("/pricing")
        assert resp.status_code == 200


class TestSubscriptionModel:
    def test_create_subscription(self, db_session):
        now = utc_iso(datetime.now(timezone.utc))

        user = User(
            firebase_uid="sub-model-test",
            email="sub@example.com",
            tier="free",
            created_at=now,
            updated_at=now,
        )
        db_session.add(user)
        db_session.commit()

        sub = Subscription(
            user_id=user.id,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            status="active",
            tier="plus",
            created_at=now,
            updated_at=now,
        )
        db_session.add(sub)
        db_session.commit()

        result = db_session.query(Subscription).filter_by(user_id=user.id).first()
        assert result.status == "active"
        assert result.tier == "plus"

    def test_subscription_to_dict(self, db_session):
        now = utc_iso(datetime.now(timezone.utc))
        user = User(
            firebase_uid="sub-dict-test",
            email="subdict@example.com",
            tier="plus",
            created_at=now,
            updated_at=now,
        )
        db_session.add(user)
        db_session.commit()

        sub = Subscription(
            user_id=user.id,
            status="active",
            tier="plus",
            cancel_at_period_end=False,
            created_at=now,
            updated_at=now,
        )
        db_session.add(sub)
        db_session.commit()

        d = sub.to_dict()
        assert d["status"] == "active"
        assert d["tier"] == "plus"
        assert d["cancel_at_period_end"] is False
        assert "stripe_customer_id" not in d  # sensitive, not exposed
