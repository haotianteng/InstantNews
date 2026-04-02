"""Billing API routes — Stripe Checkout, Portal, and Webhooks."""

import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g, current_app

from app.auth.middleware import require_auth
from app.billing import stripe_client
from app.models import User, Subscription, StripeEvent
from app.services.feed_parser import utc_iso

billing_bp = Blueprint("billing", __name__)

WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Map Stripe Price IDs back to tier names
_PRICE_TO_TIER = {}


def _build_price_to_tier():
    """Build reverse lookup from price ID to tier name."""
    global _PRICE_TO_TIER
    for tier in ("plus", "max"):
        pid = stripe_client.get_price_id(tier)
        if pid:
            _PRICE_TO_TIER[pid] = tier


def _tier_from_price_id(price_id):
    """Look up tier name from a Stripe price ID."""
    if not _PRICE_TO_TIER:
        _build_price_to_tier()
    return _PRICE_TO_TIER.get(price_id, "free")


@billing_bp.route("/api/billing/checkout", methods=["POST"])
@require_auth
def create_checkout():
    """Create a Stripe Checkout session for upgrading.

    Body: {"tier": "plus" | "max"}
    Returns: {"url": "https://checkout.stripe.com/..."}
    """
    if not stripe_client.is_configured():
        return jsonify({
            "error": "Payment system is not yet configured. Coming soon!",
            "configured": False,
        }), 503

    data = request.get_json() or {}
    tier = data.get("tier")
    if tier not in ("plus", "max"):
        return jsonify({"error": "Invalid tier. Must be 'plus' or 'max'."}), 400

    price_id = stripe_client.get_price_id(tier)
    if not price_id:
        return jsonify({"error": f"Price not configured for {tier} tier."}), 500

    # Look up existing Stripe customer ID
    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        sub = db.query(Subscription).filter_by(user_id=g.current_user.id).first()
        customer_id = sub.stripe_customer_id if sub else None
    finally:
        db.close()

    base_url = request.host_url.rstrip("/")
    checkout_session = stripe_client.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=f"{base_url}/pricing?success=true",
        cancel_url=f"{base_url}/pricing?canceled=true",
        client_reference_id=str(g.current_user.id),
    )

    return jsonify({"url": checkout_session.url})


@billing_bp.route("/api/billing/portal", methods=["POST"])
@require_auth
def create_portal():
    """Create a Stripe Customer Portal session for managing subscription.

    Returns: {"url": "https://billing.stripe.com/..."}
    """
    if not stripe_client.is_configured():
        return jsonify({"error": "Payment system is not yet configured."}), 503

    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        sub = db.query(Subscription).filter_by(user_id=g.current_user.id).first()
        if not sub or not sub.stripe_customer_id:
            return jsonify({"error": "No active subscription found."}), 404
        customer_id = sub.stripe_customer_id
    finally:
        db.close()

    base_url = request.host_url.rstrip("/")
    portal_session = stripe_client.create_portal_session(
        customer_id=customer_id,
        return_url=f"{base_url}/pricing",
    )

    return jsonify({"url": portal_session.url})


@billing_bp.route("/api/billing/status")
@require_auth
def billing_status():
    """Return the current user's subscription status."""
    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        sub = db.query(Subscription).filter_by(user_id=g.current_user.id).first()
        if sub:
            result = sub.to_dict()
        else:
            result = {"status": "inactive", "tier": "free"}
    finally:
        db.close()

    return jsonify({"subscription": result})


@billing_bp.route("/api/billing/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events.

    This endpoint does NOT require auth — it uses Stripe signature verification.
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    if not WEBHOOK_SECRET:
        return jsonify({"error": "Webhook secret not configured"}), 500

    try:
        event = stripe_client.construct_webhook_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except Exception:
        return jsonify({"error": "Invalid signature"}), 400

    # Idempotency: skip already-processed events
    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        existing = db.query(StripeEvent).filter_by(id=event["id"]).first()
        if existing:
            return jsonify({"status": "already_processed"})

        # Process event
        event_type = event["type"]
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, event["data"]["object"])
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(db, event["data"]["object"])
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(db, event["data"]["object"])
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(db, event["data"]["object"])

        # Record event as processed
        db.add(StripeEvent(
            id=event["id"],
            type=event_type,
            processed_at=utc_iso(datetime.now(timezone.utc)),
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return jsonify({"status": "ok"})


def _handle_checkout_completed(db, session_obj):
    """Handle checkout.session.completed — create/update subscription."""
    user_id = int(session_obj.get("client_reference_id", 0))
    if not user_id:
        return

    customer_id = session_obj.get("customer")
    subscription_id = session_obj.get("subscription")

    # Fetch full subscription to get price/tier
    stripe_sub = stripe_client.get_subscription(subscription_id)
    price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    tier = _tier_from_price_id(price_id)
    now = utc_iso(datetime.now(timezone.utc))

    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if sub:
        sub.stripe_customer_id = customer_id
        sub.stripe_subscription_id = subscription_id
        sub.stripe_price_id = price_id
        sub.status = "active"
        sub.tier = tier
        sub.current_period_start = _ts_to_iso(stripe_sub.get("current_period_start"))
        sub.current_period_end = _ts_to_iso(stripe_sub.get("current_period_end"))
        sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
        sub.updated_at = now
    else:
        sub = Subscription(
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id,
            status="active",
            tier=tier,
            current_period_start=_ts_to_iso(stripe_sub.get("current_period_start")),
            current_period_end=_ts_to_iso(stripe_sub.get("current_period_end")),
            cancel_at_period_end=stripe_sub.get("cancel_at_period_end", False),
            created_at=now,
            updated_at=now,
        )
        db.add(sub)

    # Update user tier
    user = db.query(User).filter_by(id=user_id).first()
    if user:
        user.tier = tier
        user.updated_at = now

    db.commit()


def _handle_subscription_updated(db, stripe_sub):
    """Handle customer.subscription.updated — sync status and tier."""
    sub_id = stripe_sub.get("id")
    sub = db.query(Subscription).filter_by(stripe_subscription_id=sub_id).first()
    if not sub:
        return

    now = utc_iso(datetime.now(timezone.utc))
    status = stripe_sub.get("status", "active")
    price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    tier = _tier_from_price_id(price_id)

    sub.status = status
    sub.tier = tier
    sub.stripe_price_id = price_id
    sub.current_period_start = _ts_to_iso(stripe_sub.get("current_period_start"))
    sub.current_period_end = _ts_to_iso(stripe_sub.get("current_period_end"))
    sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
    sub.updated_at = now

    # Update user tier (downgrade if subscription is no longer active)
    user = db.query(User).filter_by(id=sub.user_id).first()
    if user:
        user.tier = tier if status == "active" else "free"
        user.updated_at = now

    db.commit()


def _handle_subscription_deleted(db, stripe_sub):
    """Handle customer.subscription.deleted — downgrade to free."""
    sub_id = stripe_sub.get("id")
    sub = db.query(Subscription).filter_by(stripe_subscription_id=sub_id).first()
    if not sub:
        return

    now = utc_iso(datetime.now(timezone.utc))
    sub.status = "canceled"
    sub.tier = "free"
    sub.updated_at = now

    user = db.query(User).filter_by(id=sub.user_id).first()
    if user:
        user.tier = "free"
        user.updated_at = now

    db.commit()


def _handle_payment_failed(db, invoice):
    """Handle invoice.payment_failed — mark subscription as past_due."""
    sub_id = invoice.get("subscription")
    if not sub_id:
        return

    sub = db.query(Subscription).filter_by(stripe_subscription_id=sub_id).first()
    if not sub:
        return

    now = utc_iso(datetime.now(timezone.utc))
    sub.status = "past_due"
    sub.updated_at = now
    db.commit()


def _ts_to_iso(timestamp):
    """Convert a Unix timestamp to ISO 8601 string."""
    if not timestamp:
        return None
    return utc_iso(datetime.fromtimestamp(timestamp, tz=timezone.utc))
