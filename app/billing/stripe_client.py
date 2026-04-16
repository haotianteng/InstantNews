"""Stripe SDK wrapper — isolates all Stripe API calls."""

import os

import stripe

# Configure Stripe from environment
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

# Price IDs (set these after creating products in Stripe Dashboard)
PRICE_IDS = {
    "pro": os.environ.get("STRIPE_PRICE_PRO", os.environ.get("STRIPE_PRICE_PLUS", "")),
    "max": os.environ.get("STRIPE_PRICE_MAX", ""),
}

# Trial configuration per tier (days)
TRIAL_DAYS = {
    "pro": 30,
    "max": 0,
}


def is_configured():
    """Check if Stripe keys are set."""
    return bool(stripe.api_key)


def create_checkout_session(customer_id, price_id, client_reference_id,
                            success_url=None, cancel_url=None,
                            trial_period_days=0, embedded=False,
                            return_url=None):
    """Create a Stripe Checkout Session for a subscription.

    Args:
        trial_period_days: Number of free trial days (0 to disable).
        embedded: If True, use embedded mode (returns client_secret).
        return_url: Required for embedded mode — URL with {CHECKOUT_SESSION_ID}.

    Returns the session object.
    """
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": client_reference_id,
    }

    if embedded:
        params["ui_mode"] = "elements"
        params["return_url"] = return_url
    else:
        params["success_url"] = success_url
        params["cancel_url"] = cancel_url

    if customer_id:
        params["customer"] = customer_id

    if trial_period_days > 0:
        params["subscription_data"] = {
            "trial_period_days": trial_period_days,
        }

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


def get_customer(customer_id):
    """Retrieve a customer from Stripe."""
    return stripe.Customer.retrieve(customer_id)


def get_payment_method(payment_method_id):
    """Retrieve a payment method from Stripe."""
    return stripe.PaymentMethod.retrieve(payment_method_id)


def list_payment_methods(customer_id, pm_type="card"):
    """List payment methods for a customer."""
    result = stripe.PaymentMethod.list(customer=customer_id, type=pm_type)
    return result.get("data", [])


def get_price_id(tier):
    """Get the Stripe Price ID for a tier."""
    return PRICE_IDS.get(tier, "")
