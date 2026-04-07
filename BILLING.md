# Billing Configuration

Stripe integration for InstNews (SIGNAL) subscription billing.

## Tier Structure

| Tier | Internal Key | Price | Visible | Trial |
|------|-------------|-------|---------|-------|
| Free | `free` | $0/mo | Yes | N/A |
| Pro | `pro` | $14.99/mo | Yes | 30 days |
| Max | `max` | $39.99/mo | **No** (hidden, future) | None |

The `plus` key is a backward-compatibility alias for `pro` in `app/billing/tiers.py`.

## Stripe Products & Prices

Products and Prices must be created in the [Stripe Dashboard](https://dashboard.stripe.com/products).

| Product | Stripe Price ID Env Var | Monthly Price |
|---------|------------------------|---------------|
| SIGNAL Pro | `STRIPE_PRICE_PRO` | $14.99 |
| SIGNAL Max | `STRIPE_PRICE_MAX` | (not active) |

Legacy env var `STRIPE_PRICE_PLUS` is still accepted as a fallback for `STRIPE_PRICE_PRO`.

## Environment Variables

```bash
STRIPE_SECRET_KEY=sk_live_...          # Stripe secret key
STRIPE_WEBHOOK_SECRET=whsec_...        # Webhook endpoint signing secret
STRIPE_PRICE_PRO=price_...             # Pro tier Stripe Price ID
# STRIPE_PRICE_MAX=price_...           # Max tier (hidden, not needed yet)
```

These are stored in AWS Secrets Manager and injected into the ECS task definition.

## Free Trial

The Pro tier includes a **30-day free trial** configured via Stripe's `subscription_data.trial_period_days` on checkout session creation.

- Trial starts immediately upon checkout completion.
- No charge is made during the 30-day trial period.
- Users can cancel at any time during the trial via the Stripe Customer Portal (`POST /api/billing/portal`).
- If the user does not cancel, Stripe automatically charges after the trial ends.
- Trial configuration is defined in `app/billing/stripe_client.py` (`TRIAL_DAYS`) and `app/billing/tiers.py` (`trial_period_days`).

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/billing/checkout` | Required | Create Stripe Checkout session. Body: `{"tier": "pro"}` |
| `POST` | `/api/billing/portal` | Required | Create Stripe Customer Portal session for subscription management |
| `GET` | `/api/billing/status` | Required | Get current user's subscription status |
| `POST` | `/api/billing/webhook` | Stripe signature | Handle Stripe webhook events |

## Webhook Configuration

**Endpoint URL:** `https://www.instnews.net/api/billing/webhook`

### Required Webhook Events

Configure these events in the Stripe Dashboard under Developers > Webhooks:

| Event | Handler | Purpose |
|-------|---------|---------|
| `checkout.session.completed` | `_handle_checkout_completed` | Create/update subscription after successful checkout |
| `customer.subscription.updated` | `_handle_subscription_updated` | Sync tier/status when subscription changes |
| `customer.subscription.deleted` | `_handle_subscription_deleted` | Downgrade user to free tier on cancellation |
| `customer.subscription.trial_will_end` | `_handle_trial_will_end` | Fires 3 days before trial ends (for future email notification) |
| `invoice.payment_succeeded` | `_handle_payment_succeeded` | Confirm subscription remains active after payment (including post-trial first charge) |
| `invoice.payment_failed` | `_handle_payment_failed` | Mark subscription as past_due |

### Webhook Idempotency

All webhook events are tracked in the `stripe_events` table. Duplicate events (same Stripe event ID) are skipped automatically.

## Database Tables

### `subscriptions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment |
| `user_id` | Integer (FK -> users.id) | Owner |
| `stripe_customer_id` | String | Stripe Customer ID (`cus_...`) |
| `stripe_subscription_id` | String (unique) | Stripe Subscription ID (`sub_...`) |
| `stripe_price_id` | String | Stripe Price ID (`price_...`) |
| `status` | String | `active`, `trialing`, `past_due`, `canceled`, `inactive` |
| `tier` | String | `pro`, `max`, or `free` |
| `current_period_start` | String (ISO 8601) | Current billing period start |
| `current_period_end` | String (ISO 8601) | Current billing period end |
| `cancel_at_period_end` | Boolean | Whether subscription cancels at period end |
| `created_at` | String (ISO 8601) | Record creation time |
| `updated_at` | String (ISO 8601) | Last update time |

### `stripe_events`

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | Stripe event ID (`evt_...`) |
| `type` | String | Event type |
| `processed_at` | String (ISO 8601) | When the event was processed |

## Subscription Lifecycle

1. **Checkout:** User clicks "Start Free Trial" on pricing page
2. **Stripe Checkout:** Redirected to Stripe with 30-day trial configured
3. **Trial Active:** `checkout.session.completed` webhook fires, user upgraded to Pro
4. **Trial Warning:** `customer.subscription.trial_will_end` fires 3 days before trial ends
5. **First Charge:** Trial ends, Stripe charges the card
   - Success: `invoice.payment_succeeded` keeps subscription active
   - Failure: `invoice.payment_failed` marks as `past_due`
6. **Cancellation:** User cancels via Customer Portal
   - `customer.subscription.deleted` downgrades to free
7. **Management:** User accesses Customer Portal via `POST /api/billing/portal`
