"""Stripe SDK wrapper — isolates all Stripe API calls."""

import os

import stripe

# Configure Stripe from environment
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

# Price IDs (set these after creating products in Stripe Dashboard)
PRICE_IDS = {
    "plus": os.environ.get("STRIPE_PRICE_PLUS", ""),
    "max": os.environ.get("STRIPE_PRICE_MAX", ""),
}


def is_configured():
    """Check if Stripe keys are set."""
    return bool(stripe.api_key)


def create_checkout_session(customer_id, price_id, success_url, cancel_url, client_reference_id):
    """Create a Stripe Checkout Session for a subscription.

    Returns the session object with a .url for redirect.
    """
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": client_reference_id,
    }
    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_creation"] = "always"

    return stripe.checkout.Session.create(**params)


def create_portal_session(customer_id, return_url):
    """Create a Stripe Customer Portal session for subscription management."""
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


def construct_webhook_event(payload, sig_header, webhook_secret):
    """Verify and construct a Stripe webhook event."""
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)


def get_subscription(subscription_id):
    """Retrieve a subscription from Stripe."""
    return stripe.Subscription.retrieve(subscription_id)


def get_price_id(tier):
    """Get the Stripe Price ID for a tier."""
    return PRICE_IDS.get(tier, "")
