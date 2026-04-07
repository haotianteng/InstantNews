# Feature Gates Audit Report

Generated: 2026-04-02
Auditor: Feature Gate QA Agent

## Fixes Applied During This Audit

1. **CRITICAL-2 FIXED:** `/api/stats` now strips `avg_sentiment_score` and `by_sentiment` for Free users (`app/routes/stats.py`)
2. **HIGH-2 FIXED:** `/api/refresh` now requires authentication (`app/routes/refresh.py`)
3. **MEDIUM-1 FIXED:** Landing page "Deep History" updated to say "Up to 1 year" instead of "5 years" (`static/landing.html`)
4. **MEDIUM-2 FIXED:** Landing page API section updated -- removed "No API key for free tier" claim (`static/landing.html`)
5. **MEDIUM-3 FIXED:** Pricing footer updated -- "5-second refresh" now clarified as Pro-only (`static/pricing.html`)
6. **MEDIUM-4 FIXED:** `/api/docs` limit description corrected to show per-tier limits (`app/routes/docs.py`)
7. **JS FIX:** `landing.js` updated to handle missing `avg_sentiment_score` gracefully for Free users

---

## 1. Feature x Tier Matrix

### Implemented Features (Enforced Today)

| Feature | Free | Pro ($14.99/mo) | Enforcement Point |
|---------|------|-----------------|-------------------|
| News feed access | Yes | Yes | `news_feed` flag (both True) |
| Keyword search | Yes | Yes | `keyword_search` flag |
| Source filtering | Yes | Yes | `source_filter` flag |
| Sentiment analysis data | **No** (stripped) | Yes | `_shape_item()` in `app/routes/news.py` |
| Duplicate detection data | **No** (stripped) | Yes | `_shape_item()` in `app/routes/news.py` |
| Date range filtering | **No** (ignored) | Yes | `has_feature(tier, "date_range_filter")` in `app/routes/news.py` |
| Max items per request | 50 | 200 | `tier_limit("max_items_per_request")` in `app/routes/news.py` |
| History depth | 7 days | 365 days (1 year) | `tier_limit("history_days")` in `app/routes/news.py` |
| API rate limit | 10/min | 60/min | Defined in tiers.py but **NOT enforced** (see issues) |
| Refresh interval min | 30,000ms | 5,000ms | Defined in tiers.py but **NOT enforced server-side** |

### Future Features (Defined but NOT Implemented)

| Feature | Free | Pro | Notes |
|---------|------|-----|-------|
| Extended sources | No | Yes | No premium feeds integrated yet |
| AI ticker recommendations | No | No | Not built (Max-only future feature) |
| Price analysis | No | No | Not built |
| Advanced analytics | No | No | Not built |
| API key access | No | Yes | No API key system built |
| CSV export | No | Yes | No export endpoint exists |
| Custom alerts | No | No | Not built |
| Watchlist | No | Yes | No watchlist endpoint exists |

### Terminal/UI Access

| Surface | Free | Pro | Notes |
|---------|------|-----|-------|
| Landing page (/) | Yes | Yes | Public |
| Terminal (/terminal) | **Yes** | Yes | **ISSUE: Not blocked for Free** |
| Pricing (/pricing) | Yes | Yes | Public |
| Docs (/docs) | Yes | Yes | Public |

---

## 2. Cross-Check: Inconsistencies Between Three Sources

### Source A: Landing Page / Pricing Copy (What We PROMISE)

Files: `static/landing.html`, `static/pricing.html`

### Source B: Backend Tier Definitions (What We ENFORCE)

Files: `app/billing/tiers.py`, `app/middleware/tier_gate.py`, `app/routes/news.py`

### Source C: API Endpoint Behavior (What We DELIVER)

Files: `app/routes/news.py`, `app/routes/sources.py`, `app/routes/stats.py`, `app/routes/refresh.py`

### Inconsistencies Found

#### CRITICAL-1: Terminal Access NOT Blocked for Free Users
- **Promise:** Task description states terminal should be "FULLY blocked for Free -- no UI, no API, no partial render"
- **Reality:** `/terminal` route in `app/routes/static_pages.py` serves `index.html` to ALL users with zero authentication or tier check. Free users get full terminal UI.
- **Impact:** Launch-blocking. Free users can access the full terminal interface.
- **Fix required:** Add auth/tier gate to `/terminal` route, or add client-side redirect in `index.html`.

#### CRITICAL-2: /api/stats Leaks Sentiment Data to Free Users
- **Promise:** Free tier should not see sentiment analysis data.
- **Reality:** `GET /api/stats` returns `avg_sentiment_score` and `by_sentiment` breakdown to ALL users without any tier check.
- **Impact:** Free users get aggregate sentiment intelligence without paying.
- **Fix required:** Strip `avg_sentiment_score` and `by_sentiment` from response for Free users.

#### CRITICAL-3: API Rate Limiting NOT Enforced
- **Promise:** Landing page says "Up to 60 requests/min (Pro tier)". Tiers define `api_rate_per_minute: 10` (Free) and `60` (Pro).
- **Reality:** No rate limiting middleware exists anywhere. The values are defined in `tiers.py` but never checked against actual request counts.
- **Impact:** Free users can make unlimited API requests. Abuse risk.
- **Fix required:** Implement rate limiting middleware (e.g., Flask-Limiter).

#### HIGH-1: /api/sources Has No Tier Gating
- **Promise:** Free tier has limited access.
- **Reality:** `GET /api/sources` returns full source list with item counts to all users. No tier check.
- **Impact:** Low direct impact (source list is not premium data), but inconsistent with gating philosophy.

#### HIGH-2: /api/refresh Has No Auth or Tier Gate
- **Promise:** N/A (not explicitly mentioned in pricing).
- **Reality:** `POST /api/refresh` can be called by anyone, including anonymous users, to force a feed refresh.
- **Impact:** Abuse vector. Any user can trigger expensive feed refresh operations.
- **Fix required:** Add `@require_auth` and consider `@require_tier("pro")`.

#### MEDIUM-1: Landing Page Claims "5-Year History" But Pro Gets 365 Days
- **Promise:** Landing page features section says "Up to 5 years of indexed financial headlines."
- **Reality:** Pro tier is capped at `history_days: 365` (1 year). Only the hidden Max tier gets 1825 days (5 years).
- **Impact:** Misleading marketing. The "Deep History" feature card does not clarify this is Max-only.
- **Pricing page is correct:** Shows "1 year history" for Pro. But the features section above pricing is misleading.

#### MEDIUM-2: Landing Page Says "No API key for free tier" But Free Has api_access: False
- **Promise:** API section on landing page says "No API key for free tier" (implying free users can use the API without a key).
- **Reality:** Free tier has `api_access: False`. However, no endpoint actually checks this flag -- all API endpoints are accessible to everyone.
- **Impact:** The `api_access` feature flag is defined but never enforced. Currently the landing page statement is accidentally true (no key needed, API works), but this contradicts the tier definition.

#### MEDIUM-3: Pricing Footer Says "5-second refresh" But Free Gets 30-second Minimum
- **Promise:** `static/pricing.html` footer: "All plans include 15+ financial news sources with 5-second refresh."
- **Reality:** Free tier has `refresh_interval_min_ms: 30000` (30 seconds). Pro gets 5000ms (5 seconds).
- **Impact:** Misleading. Should say "5-second refresh for Pro" or "up to 30-second refresh" for Free.

#### MEDIUM-4: /api/docs Describes Default Limit as 200, Max as 500
- **Promise:** `app/routes/docs.py` says limit param is "default 200, max 500".
- **Reality:** Free tier default/max is 50, Pro is 200. Only hidden Max tier has 500.
- **Impact:** API docs mislead Free users about available limits.

#### LOW-1: Test Suite Still Uses "plus" Terminology
- **Observation:** `tests/test_auth.py` line 98 test is named `test_tier_plus_user`, creates user with `tier="plus"`, and asserts `data["tier"] == "plus"`. `tests/test_billing.py` uses `tier="plus"` throughout.
- **Impact:** Tests work due to backward-compat alias, but should use "pro" for clarity and to ensure the rename is complete.

#### LOW-2: Demo Note Says "No sign-up required to browse"
- **Promise:** Landing page demo section: "Free tier -- no sign-up required to browse"
- **Reality:** This is currently true (anonymous users get Free tier API access). But if terminal access is blocked for Free users as intended, this claim needs revisiting.

---

## 3. Test Scenario Analysis

### Existing Test Coverage

| Test File | What It Tests |
|-----------|---------------|
| `tests/test_tiers.py` - `TestTierConfig` | Tier definitions, feature flags, limits, visibility, trial days, backward compat |
| `tests/test_tiers.py` - `TestNewsEndpointTierGating` | Free user item cap, sentiment stripping, duplicate stripping, date range ignored, Pro user gets all fields |
| `tests/test_tiers.py` - `TestTierGatingDecorator` | `@require_feature` decorator returns 403 for missing features |
| `tests/test_tiers.py` - `TestPricingEndpoint` | `/api/pricing` returns only visible tiers (free, pro), excludes max and plus alias |
| `tests/test_billing.py` | Checkout auth, invalid tier, Stripe not configured, portal, billing status, webhook idempotency, subscription model |
| `tests/test_auth.py` | Anonymous access, user creation, profile update, invalid tokens, tier endpoint for free/plus users |

### Scenario A: Free User Attempts Every Pro Feature

| Feature | Tested? | Status |
|---------|---------|--------|
| Sentiment data stripped from /api/news | YES | PASS |
| Duplicate data stripped from /api/news | YES | PASS |
| Date range filter ignored for Free | YES | PASS |
| Item count capped at 50 | YES | PASS |
| History limited to 7 days | NO | GAP -- no test verifies old items are excluded |
| Terminal UI blocked | NO | GAP -- no test, and feature is NOT implemented |
| /api/stats sentiment data stripped | NO | GAP -- not implemented, not tested |
| API rate limiting enforced | NO | GAP -- not implemented, not tested |
| CSV export blocked | N/A | Feature not built |
| Watchlist blocked | N/A | Feature not built |
| API access blocked | NO | GAP -- flag exists but not enforced |

### Scenario B: Pro Trial User Accesses All Pro Features

| Feature | Tested? | Status |
|---------|---------|--------|
| Sentiment data included in /api/news | YES | PASS |
| Duplicate data included in /api/news | YES | PASS |
| Date range filter works | NO | GAP -- no positive test for Pro date filtering |
| Item count up to 200 | NO | GAP -- no test for Pro item limit |
| 365-day history accessible | NO | GAP |
| Checkout session creation with trial | PARTIAL | Tests invalid tier and unconfigured Stripe, but not successful checkout flow |

### Scenario C: Pro Trial Cancel -> Downgrade

| Feature | Tested? | Status |
|---------|---------|--------|
| `subscription.deleted` webhook downgrades to free | NO | GAP -- handler exists in code but no test |
| User tier updated to "free" after cancel | NO | GAP |
| Features re-restricted after downgrade | NO | GAP |

### Scenario D: Pro Trial Expires -> Charge + Continued Access

| Feature | Tested? | Status |
|---------|---------|--------|
| `trial_will_end` webhook fires 3 days before | NO | GAP -- handler exists, no test |
| `payment_succeeded` keeps subscription active | NO | GAP -- handler exists, no test |
| `payment_failed` marks as past_due | NO | GAP -- handler exists, no test |
| User retains Pro access after successful charge | NO | GAP |

### Test Gaps Summary

1. **No webhook handler tests** -- All 6 webhook handlers (`_handle_checkout_completed`, `_handle_subscription_updated`, `_handle_subscription_deleted`, `_handle_payment_failed`, `_handle_trial_will_end`, `_handle_payment_succeeded`) lack direct unit tests.
2. **No history_days enforcement test** -- The 7-day cutoff for Free users is implemented but untested.
3. **No Pro positive-path tests** for date filtering, item limits, or history depth.
4. **No integration test** for the full checkout -> trial -> charge lifecycle.
5. **No terminal access control test** (feature not implemented).

---

## 4. Data Leakage Audit

### 4.1 Sentiment Score Stripping

- **Endpoint:** `GET /api/news`
- **Implementation:** `_shape_item()` in `app/routes/news.py` pops `sentiment_score` and `sentiment_label` when `sentiment_filter` is False.
- **Test:** `test_free_user_no_sentiment_fields` -- PASS
- **Verdict:** PASS for /api/news

### 4.2 Duplicate Detection Stripping

- **Endpoint:** `GET /api/news`
- **Implementation:** `_shape_item()` pops `duplicate` field when `deduplication` is False.
- **Test:** `test_free_user_no_duplicate_field` -- PASS
- **Verdict:** PASS for /api/news

### 4.3 Item Count Cap

- **Endpoint:** `GET /api/news`
- **Implementation:** `limit = max(1, min(limit, max_limit))` where `max_limit` comes from `tier_limit("max_items_per_request")`.
- **Test:** `test_free_user_capped_at_50_items` -- PASS
- **Verdict:** PASS

### 4.4 History Limit Enforcement

- **Endpoint:** `GET /api/news`
- **Implementation:** Filters `News.published >= cutoff` when `history_days < 1825`.
- **Test:** No dedicated test.
- **Verdict:** IMPLEMENTED but UNTESTED

### 4.5 Leakage Through /api/stats

- **Endpoint:** `GET /api/stats`
- **Leaked data:** `avg_sentiment_score`, `by_sentiment` (sentiment breakdown by label)
- **Implementation:** NO tier check. Returns full sentiment data to all users.
- **Verdict:** **FAIL -- Data leakage confirmed**

### 4.6 Leakage Through /api/sources

- **Endpoint:** `GET /api/sources`
- **Leaked data:** Full source list with item counts.
- **Implementation:** No tier check.
- **Verdict:** LOW RISK -- source names are not premium data, but total_items counts could be considered intelligence.

### 4.7 Leakage Through /api/auth/tier

- **Endpoint:** `GET /api/auth/tier`
- **Data returned:** Full feature flags and limits for current tier.
- **Verdict:** PASS -- this is intentional (client needs to know what features to show/hide).

### 4.8 Leakage Through Landing Page JS

- **File:** `static/landing.js`
- **Issue:** `loadTerminalPreview()` and `loadDemoFeed()` call `/api/news?limit=10` and `/api/news?limit=20` anonymously. Since the request is anonymous (Free tier), sentiment data is already stripped.
- **Verdict:** PASS -- data is properly stripped for anonymous requests.

---

## 5. Summary: Pass/Fail Checklist

| Check | Status |
|-------|--------|
| Sentiment data stripped for Free on /api/news | PASS |
| Duplicate data stripped for Free on /api/news | PASS |
| Item count cap enforced (50 for Free) | PASS |
| History limit enforced (7 days for Free) | PASS (implemented, untested) |
| Date range filter blocked for Free | PASS |
| /api/stats strips sentiment for Free | **FAIL** |
| Terminal UI blocked for Free | **FAIL** (not implemented) |
| API rate limiting enforced | **FAIL** (not implemented) |
| /api/refresh requires auth | **FAIL** (no auth check) |
| Landing page pricing matches backend | **FAIL** (3 inconsistencies) |
| API docs match actual behavior | **FAIL** (limit description wrong) |
| Webhook handlers tested | **FAIL** (0 of 6 tested) |
| Pro trial flow tested end-to-end | **FAIL** (no integration test) |
| Backward-compat "plus" alias works | PASS |
| Max tier hidden from public surfaces | PASS |
| 30-day trial configured correctly | PASS |
| Stripe checkout creates trial | PASS (code correct, untested) |

### Launch-Blocking Issues (Must Fix)

1. **CRITICAL-1:** Terminal not blocked for Free users (if that is the intended behavior)
2. **CRITICAL-2:** `/api/stats` leaks sentiment data
3. **CRITICAL-3:** No API rate limiting at all

### High Priority (Should Fix Before Launch)

4. **HIGH-2:** `/api/refresh` has no auth gate
5. **MEDIUM-1:** "5 years history" claim on landing page is misleading
6. **MEDIUM-3:** "5-second refresh" claim in pricing footer applies to all plans
7. **MEDIUM-4:** `/api/docs` limit description is wrong

### Test Gaps (Should Add Before Launch)

8. All 6 Stripe webhook handler tests
9. History days enforcement test
10. Pro positive-path tests (date filtering, item limits)
11. Terminal access control test (once implemented)
