# TODO: Yearly Subscription Pricing

## Context
Currently only monthly billing is supported ($29.99/mo Pro, $89.99/mo Max). We want to add yearly billing with a discount, and a toggle on the pricing page/checkout to switch between monthly and yearly.

## Requirements

### Pricing Page
- Add a **Monthly / Yearly toggle** above the pricing cards
- When "Yearly" is selected:
  - Show the yearly price (e.g., $299.99/yr for Pro, $899.99/yr for Max)
  - Show the **monthly equivalent** (e.g., "$25.00/mo")
  - **Cross out the original monthly price** with strikethrough (e.g., ~~$29.99~~ → $25.00/mo)
  - Show a "Save X%" badge on each card
- Default to Monthly view

### Checkout Sidebar
- Pass the billing period (monthly/yearly) to `/api/billing/checkout`
- The plan summary in the checkout sidebar should show:
  - For monthly: "$29.99 /month"
  - For yearly: "$299.99 /year ($25.00/mo)" with the savings shown
- The Subscribe button text should reflect the period

### Backend
- Create yearly Stripe Price IDs in Stripe Dashboard (or via API)
- Add `STRIPE_PRICE_PRO_YEARLY` and `STRIPE_PRICE_MAX_YEARLY` env vars
- Update `/api/billing/checkout` to accept `period: "monthly" | "yearly"` and select the correct price_id
- Update `_tier_from_price_id()` to map yearly price IDs to the correct tier

### Landing Page
- Same monthly/yearly toggle on the landing page pricing section

### Account Page
- Show current billing period in the subscription status
- Switching from monthly to yearly (or vice versa) should be treated as a plan change

## Design Reference
- Toggle should be a pill/switch with "Monthly" and "Yearly" labels
- The cross-out effect: `<span style="text-decoration:line-through;color:#8b949e">$29.99</span>` next to the new price
- Save badge: small green pill like "Save 17%"

## Files to Modify
- `app/billing/stripe_client.py` — add yearly price IDs
- `app/billing/routes.py` — accept period param in checkout
- `app/billing/tiers.py` — add yearly pricing info to tier data
- `frontend/src/pricing-renderer.js` — toggle + cross-out UI
- `frontend/src/checkout.js` — plan summary with period
- `frontend/src/pricing.js` — toggle state
- `frontend/src/landing.js` — toggle on landing page
- `frontend/src/styles/landing.css` — toggle styles
