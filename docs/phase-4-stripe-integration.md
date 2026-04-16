# Phase 4: Stripe Payment Integration

**Status:** Complete (frontend-ready, backend-ready, awaiting Stripe account)
**Goal:** Enable paid subscriptions via Stripe Checkout. Users can upgrade from Free to Plus ($29.99/mo) or Max ($89.99/mo). Webhook keeps subscription state in sync.

## What Was Built

### Backend
- **`app/billing/stripe_client.py`** — Stripe SDK wrapper. Functions:
  - `is_configured()` — checks if `STRIPE_SECRET_KEY` is set
  - `create_checkout_session()` — creates Stripe Checkout for subscription
  - `create_portal_session()` — creates Stripe Customer Portal for self-service management
  - `construct_webhook_event()` — verifies webhook signature
  - `get_subscription()` — retrieves subscription details
  - `get_price_id(tier)` — maps tier name to Stripe Price ID

- **`app/billing/routes.py`** — Billing endpoints:
  - `POST /api/billing/checkout` — requires auth, body `{"tier": "plus"|"max"}`, returns `{"url": "https://checkout.stripe.com/..."}`. Returns 503 with friendly message when Stripe isn't configured.
  - `POST /api/billing/portal` — requires auth, returns portal URL for managing subscription
  - `GET /api/billing/status` — requires auth, returns current subscription state
  - `POST /api/billing/webhook` — NO auth (uses Stripe signature), handles:
    - `checkout.session.completed` → creates subscription, upgrades user tier
    - `customer.subscription.updated` → syncs status/tier changes
    - `customer.subscription.deleted` → downgrades to free
    - `invoice.payment_failed` → marks subscription past_due

### Database
- **`Subscription` model** — user_id, stripe_customer_id, stripe_subscription_id, stripe_price_id, status, tier, period dates, cancel_at_period_end
- **`StripeEvent` model** — stores processed event IDs for webhook idempotency
- **Migration `003_add_subscriptions.py`**

### Frontend
- **`static/pricing.html`** — Three-column pricing page:
  - Feature comparison grid with checkmarks/crosses
  - "MOST POPULAR" badge on Plus tier
  - Subscribe buttons that trigger Google sign-in if needed, then redirect to Stripe Checkout
  - Success/cancel alerts on return from Checkout
  - Graceful handling when Stripe isn't configured (shows "coming soon" message)
  - Mobile responsive (stacks to single column)
  - `/pricing` route added to `static_pages.py`

## Checkout Flow
```
User clicks "Subscribe to Plus" on /pricing
  → If not signed in: Google sign-in popup
  → POST /api/billing/checkout {tier: "plus"}
  → Backend creates Stripe Checkout Session
  → Returns checkout URL
  → Frontend redirects to Stripe Checkout
  → User enters payment info on Stripe-hosted page
  → Stripe redirects to /pricing?success=true
  → Meanwhile: Stripe sends checkout.session.completed webhook
  → Backend creates Subscription record, upgrades User.tier to "plus"
  → User now has Plus features on next page load
```

## Webhook Idempotency
Each Stripe event ID is stored in `stripe_events` table after processing. If the same event arrives again, it's skipped. This handles Stripe's at-least-once delivery guarantee.

## Setup Required (When Stripe Account Is Ready)

1. **Create Stripe account** at https://dashboard.stripe.com
2. **Create Products and Prices:**
   - Product "SIGNAL Plus" → Price $29.99/month (recurring)
   - Product "SIGNAL Max" → Price $89.99/month (recurring)
3. **Set environment variables:**
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_PRICE_PLUS=price_...     (Plus monthly price ID)
   STRIPE_PRICE_MAX=price_...      (Max monthly price ID)
   ```
4. **Configure webhook in Stripe Dashboard:**
   - URL: `https://www.instnews.net/api/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
5. **Configure Customer Portal** in Stripe Dashboard → Settings → Customer portal:
   - Enable subscription cancellation
   - Enable plan switching
   - Enable payment method updates

## Test Mode
Everything works in Stripe test mode (`sk_test_...` keys). Test card: `4242 4242 4242 4242`, any future exp date, any CVC.

## Test Coverage
11 billing tests covering: auth requirements, invalid tier, Stripe not configured, portal with no subscription, billing status, webhook signature, idempotency, pricing page, subscription model.

## Total Tests: 74 (all passing)
