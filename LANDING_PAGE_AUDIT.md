# Landing Page Consistency Audit

**Date:** 2026-04-02
**Auditor:** Landing Page Consistency Agent

## Page-by-Page Audit Results

### 1. `static/landing.html`
- **Tier names:** Only "Free" and "Pro" appear. No Max/Plus references.
- **Pricing:** $0/mo (Free), $29.99/mo (Pro) -- correct.
- **Trial messaging:** "30-day free trial -- cancel anytime" displayed under Pro price. Pro CTA says "Start Free Trial" -- correct.
- **Feature comparison:** Matches tiers.py definitions. Deep History says "Up to 1 year" -- correct.
- **Nav CTA:** FIXED. Was "Subscribe Now", changed to "Start Free Trial".
- **Hero CTA:** "Start Free -- No Credit Card" for signup. Appropriate.
- **Footer links:** /terminal, /pricing, /docs, /privacy, /terms -- all have routes in static_pages.py.

### 2. `static/landing.css`
- No tier name references. Styling consistent.
- Pricing grid set to 2-column layout -- correct for Free + Pro.

### 3. `static/landing.js`
- `handleSubscribe('pro')` sends correct tier to billing API.
- Sentiment display falls back to "Pro" label when score unavailable (free tier) -- appropriate.
- No Max/Plus references.

### 4. `static/pricing.html`
- **Tier names:** Free and Pro only -- correct.
- **Pricing:** $0 and $29.99/mo -- correct.
- **Trial messaging:** "30-day free trial" badge on Pro card -- correct.
- **CTA buttons:** "Current Plan" for Free, "Start Free Trial" for Pro -- correct.
- **Footer:** FIXED. "Back to terminal" link was pointing to "/" (landing), changed to "/terminal".
- **Footer note:** "Pro includes 5-second refresh" -- matches `refresh_interval_min_ms: 5000` in tiers.py.

### 5. `static/index.html` (Terminal)
- **Tier badge:** Shows user tier in header. Dropdown shows "Free Plan" / "Pro Plan".
- **Auth gate:** Correct messaging. "No credit card required."
- **Status bar links:** /pricing, /privacy, /terms -- all valid routes.

### 6. `static/docs.html`
- **Tier comparison table:** Free vs Pro ($29.99/mo) -- correct.
- **Rate limits table:** Free (50 items, 10 req/min, 7 days) vs Pro (200 items, 60 req/min, 1 year) -- matches tiers.py.
- **Trial messaging:** "30-day free trial" mentioned. Upgrade link goes to /pricing.
- **API access claim:** FIXED. Previously said "No API key is required for free-tier access" which contradicted the feature comparison showing API access as Pro-only. Now clarified: "Free-tier users can browse the terminal without signing in. Authenticated API access requires a Pro subscription."

### 7. `static/style.css` (Terminal styles)
- **Tier badge CSS:** FIXED. `.tier-badge.plus` renamed to `.tier-badge.pro`. Removed `.tier-badge.max` (hidden tier).

### 8. `static/app.js` (Terminal logic)
- **Tier display:** FIXED. Backend "plus" alias now normalized to "pro" before applying CSS class and display text.
- **Dropdown labels:** `{ free: "Free Plan", pro: "Pro Plan", plus: "Pro Plan" }` -- backward-compat alias retained.

### 9. `static/auth.js`
- No tier references. Pure auth logic. No issues.

### 10. `static/base.css`
- No tier references. CSS reset only. No issues.

### 11. `static/privacy.html`
- No tier names mentioned. No issues.

### 12. `static/terms.html`
- **Tier names:** FIXED. Was "Free, Plus, and Max subscription tiers" -- changed to "Free and Pro".
- **Payment terms:** FIXED. Was "Paid plans (Plus, Max)" -- changed to "Paid plans (Pro)" with trial language added.

## Issues Found and Fix Status

| # | File | Issue | Status |
|---|------|-------|--------|
| 1 | `terms.html:30` | Referenced "Free, Plus, and Max" tiers | FIXED |
| 2 | `terms.html:37` | Referenced "Plus, Max" paid plans | FIXED |
| 3 | `style.css:1213` | CSS class `.tier-badge.plus` (old name) | FIXED to `.tier-badge.pro` |
| 4 | `style.css:1219` | CSS class `.tier-badge.max` (hidden tier) | FIXED (removed) |
| 5 | `landing.html:46` | Nav CTA said "Subscribe Now" instead of trial language | FIXED to "Start Free Trial" |
| 6 | `pricing.html:315` | "Back to terminal" linked to `/` (landing page) | FIXED to `/terminal` |
| 7 | `docs.html:193` | API access claim conflicted with feature gating | FIXED (clarified) |
| 8 | `app.js:806` | "plus" tier from backend not normalized to "pro" for CSS | FIXED |

## Link/CTA Verification

| Link | Target | Status |
|------|--------|--------|
| `/` | Landing page | OK (static_pages.py route exists) |
| `/terminal` | Terminal UI | OK |
| `/pricing` | Pricing page | OK |
| `/docs` | Documentation | OK |
| `/privacy` | Privacy policy | OK |
| `/terms` | Terms of service | OK |
| `#features` | Landing anchor | OK |
| `#demo` | Landing anchor | OK |
| `#api` | Landing anchor | OK |
| `#pricing` | Landing anchor | OK |
| Hero "Start Free" | Firebase sign-in popup | OK (via landing.js) |
| Hero "Try the Terminal" | `/terminal` | OK |
| Pro "Start Free Trial" | Stripe checkout via `/api/billing/checkout` | OK |
| Free "Open Terminal" | `/terminal` | OK |
| CTA "Get Started Free" | Firebase sign-in popup | OK |

## Pricing Consistency Check

| Location | Free Price | Pro Price | Trial | Consistent? |
|----------|-----------|-----------|-------|-------------|
| `tiers.py` | $0 | $29.99 | 30 days | Source of truth |
| `landing.html` pricing | $0/mo | $29.99/mo | 30-day free trial | YES |
| `pricing.html` | $0/mo | $29.99/mo | 30-day free trial | YES |
| `docs.html` tier table | -- | $29.99/mo | 30-day trial | YES |

No references to old $29.99 or $49.99 pricing found in any user-facing file.

## Trial Messaging Audit

| Page | Trial Visible? | CTA Text | Auto-convert Warning? |
|------|---------------|----------|----------------------|
| `landing.html` pricing | YES ("30-day free trial -- cancel anytime") | "Start Free Trial" | YES (cancel anytime) |
| `pricing.html` | YES ("30-day free trial" badge) | "Start Free Trial" | Implicit (cancel anytime via Stripe portal) |
| `docs.html` | YES ("30-day free trial") | Link to /pricing | YES ("cancel at any time") |
| `landing.html` nav | YES | "Start Free Trial" | N/A |

## Backend Compatibility Note

- `tiers.py` retains `TIERS["plus"]` as an alias for `TIERS["pro"]` -- backend-only, not user-visible.
- `tiers.py` retains `"max"` tier with `visible: False` -- backend-only, excluded from `get_all_tiers_summary()`.
- `app.js` normalizes "plus" -> "pro" for UI display.
