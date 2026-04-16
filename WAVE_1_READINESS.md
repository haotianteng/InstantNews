# Wave 1 Pre-Launch Readiness Report

**Date:** 2026-04-02
**Project:** InstNews / SIGNAL (www.instnews.net)

---

## Executive Summary

Wave 1 addressed launch-blocking billing, feature gating, UI consistency, infrastructure, and market positioning. **5 agents completed all deliverables.** The billing restructure (Plus→Pro, Max hidden, 30-day trial) is implemented. Several critical issues were found and fixed.

**Wave 2 resolved all 3 launch blockers.** Terminal gating, API rate limiting, and DB connection pool fixes are implemented. **94 tests passing, 0 failures.** Verdict: **GO** (with warnings).

---

## Agent Deliverables — Go/No-Go

| # | Agent | Deliverable | Status | Verdict |
|---|-------|-------------|--------|---------|
| 1 | Billing & Stripe | BILLING.md, tier restructure, trial implementation | Complete | **GO** |
| 2 | Feature Gate QA | FEATURE_GATES.md, 7 code fixes | Complete | **GO** (criticals resolved in Wave 2) |
| 3 | Landing Page Consistency | LANDING_PAGE_AUDIT.md, 8 fixes across 6 files | Complete | **GO** |
| 4 | Load Test & Infrastructure | LOAD_TEST_REPORT.md, locust test suite | Complete | **GO** (P0s resolved in Wave 2) |
| 5 | Pain Point Discovery | PAIN_POINT_DISCOVERY.md | Complete | **GO** (research only) |

---

## Critical Issues — ALL RESOLVED (Wave 2)

### CRITICAL-1: Terminal not gated for Free users — FIXED
- Added `terminal_access` feature flag to `tiers.py` (Free=False, Pro=True)
- Server-side: `/terminal` redirects Free/anonymous to `/?upgrade=terminal`
- Client-side: full-screen upgrade overlay in `app.js`
- 6 new tests added and passing

### CRITICAL-2: No API rate limiting enforced — FIXED
- Added Flask-Limiter middleware (`app/middleware/rate_limit.py`)
- Tier-aware dynamic limits: Free=10/min, Pro=60/min, keyed by user ID or IP
- 429 response includes upgrade prompt and tier info
- Rate limit headers enabled; 5 new tests added and passing

### CRITICAL-3: Database connection pool + performance — FIXED
- Pool increased to `pool_size=10, max_overflow=20` (configurable via env vars)
- Removed `maybe_refresh()` from all read endpoints — refresh is now worker-only
- Added 30s in-memory caching for `/api/stats` and `/api/sources`
- CDK stack annotated with RDS upgrade recommendation (`db.t3.small`)

---

## Warnings — Should Fix But Don't Block Launch

### ~~HIGH: `maybe_refresh()` called on every read request~~ — RESOLVED in Wave 2
- Removed from all read endpoints. Refresh is now worker-only.

### HIGH: Web task memory too low (1 GB)
- Embedding model is ~500MB, leaving little room for request handling.
- **Remediation:** Increase ECS web task memory to 2GB, or ensure embedding model only loads in worker task.

### ~~MEDIUM: No response caching~~ — RESOLVED in Wave 2
- Added 30s in-memory caching for `/api/stats` and `/api/sources`.

### MEDIUM: `db.t3.micro` burstable CPU
- Will exhaust CPU credits under sustained load (30-60 min).
- **Remediation:** Upgrade to `db.t3.small` or `db.t3.medium` for launch.

### MEDIUM: Test coverage gaps
- Zero webhook handler tests, no subscription lifecycle tests, no history-days enforcement test.
- Tests still use "plus" terminology (functional via alias but should be "pro").

### LOW: Competitive research used training data
- Pain Point Discovery Agent's WebSearch was denied. Competitor data is from training knowledge, not live 2026 sources. Should re-run with web search enabled for freshest pricing and sentiment data.

---

## What Was Fixed (20 total fixes)

### Billing Agent (14 files modified, 1 created)
- Max tier hidden with `visible: False`, removed from all UI
- Plus→Pro rename across entire codebase with backward-compat alias
- 30-day free trial via Stripe `trial_period_days: 30`
- Webhook handlers for trial lifecycle events
- BILLING.md created

### Feature Gate QA Agent (6 code fixes)
- `/api/stats` stripped of sentiment data for Free users (was leaking)
- `/api/refresh` now requires authentication (was open to anonymous)
- Landing page "Deep History" corrected: "5 years" → "Up to 1 year"
- Landing page API claims corrected
- Pricing footer corrected: "5-second refresh" → Pro only
- Docs API limits corrected per tier

### Landing Page Agent (8 fixes across 6 files)
- `terms.html` — updated "Free, Plus, and Max" → "Free and Pro"
- `style.css` — renamed `.tier-badge.plus` → `.tier-badge.pro`, removed `.max`
- `landing.html` — nav CTA "Subscribe Now" → "Start Free Trial"
- `pricing.html` — "Back to terminal" link fixed to `/terminal`
- `docs.html` — API access claim clarified
- `app.js` — "plus" alias normalized to "pro" for CSS classes

### Load Test Agent (4 files created)
- `tests/load/locustfile.py` — full locust test suite
- `tests/load/config.py` — 100/500/1000 user profiles
- `tests/load/run_load_tests.py` — CLI runner
- `requirements-dev.txt` — added `locust>=2.20`

---

## Pain Point Discovery — Key Findings for Wave 2

**Recommended launch angle: Variant C — "Bloomberg-level intelligence at 1% of the cost"**

Rationale: Resonates across all 4 target personas, leverages price anchoring ($24K/yr Bloomberg vs $180/yr SIGNAL Pro), and aligns with high-intent SEO queries.

**4 personas validated:** Retail Day Trader (speed), Swing Trader (macro→sector connection), Finance Professional (time savings), Algo/Quant (structured signals)

**Top fake door test features:** Custom alerts, CSV export, AI summarization, watchlist — surface these as locked Pro teasers to Free users to measure upgrade intent.

Full details in PAIN_POINT_DISCOVERY.md.

---

## Remaining Recommendations

1. ~~Fix 3 launch blockers~~ — **DONE** (Wave 2)
2. **Run load tests** against staging with the locust suite after deploying
3. **Re-run competitive research** with web search enabled
4. **Add webhook tests** and subscription lifecycle test coverage
5. ~~Implement response caching~~ — **DONE** (Wave 2)
6. **A/B test landing page** with the 3 proposed variants
7. **Upgrade RDS** to at least `db.t3.small` (requires AWS cost approval)
8. ~~Move `maybe_refresh()`~~ — **DONE** (Wave 2)
9. **Increase ECS web task memory** to 2GB

---

## Wave 2 Fixes Applied

### Terminal Gate Agent
- `app/billing/tiers.py` — added `terminal_access` feature flag
- `app/routes/static_pages.py` — server-side auth + tier check on `/terminal`
- `static/app.js` — client-side upgrade overlay for Free/anonymous users
- `tests/test_tiers.py` — 6 new terminal gating tests

### Rate Limiter Agent
- `app/middleware/rate_limit.py` — new Flask-Limiter middleware with tier-aware limits
- `app/__init__.py` — wired rate limiter into app factory
- `requirements.txt` — added `Flask-Limiter>=3.5`
- `tests/test_rate_limit.py` — 5 new rate limiting tests

### DB Pool & Performance Agent
- `app/database.py` — pool_size=10, max_overflow=20, configurable via env vars
- `app/routes/news.py`, `stats.py`, `sources.py` — removed `maybe_refresh()` calls
- `app/routes/stats.py`, `sources.py` — added 30s in-memory caching
- `infra/stack.py` — added RDS upgrade recommendation comment
- `tests/test_routes.py` — updated refresh tests for `@require_auth`, removed stale mocks

### Test Fixes (integration)
- `tests/test_rate_limit.py` — removed stale `maybe_refresh` mocks
- `tests/test_routes.py` — updated refresh route tests for auth requirement
- **Final result: 94 tests passing, 0 failures**

---

## Files Created (Both Waves)

| File | Description |
|------|-------------|
| `BILLING.md` | Stripe configuration, product IDs, webhook docs |
| `FEATURE_GATES.md` | Feature × tier matrix, audit results |
| `LANDING_PAGE_AUDIT.md` | Page-by-page consistency audit |
| `LOAD_TEST_REPORT.md` | Infrastructure review, load test setup |
| `PAIN_POINT_DISCOVERY.md` | Personas, competitors, A/B variants, interview script |
| `WAVE_1_READINESS.md` | This file |
| `tests/load/locustfile.py` | Locust load test suite |
| `tests/load/config.py` | Load test profiles |
| `tests/load/run_load_tests.py` | Load test CLI runner |
| `app/middleware/rate_limit.py` | Tier-aware API rate limiting |
| `tests/test_rate_limit.py` | Rate limiting tests |
