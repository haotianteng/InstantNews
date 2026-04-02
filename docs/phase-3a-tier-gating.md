# Phase 3A: Tier Gating

**Status:** Complete
**Goal:** Gate features by subscription tier (Free/Plus/Max). Server-side enforcement with client-side UI adaptation.

## Tier Definitions

Centralized in `app/billing/tiers.py`. Single source of truth for both backend enforcement and frontend display.

| Feature | Free | Plus ($14.99/mo) | Max ($39.99/mo) |
|---------|------|-------------------|-----------------|
| News feed | Yes | Yes | Yes |
| Keyword search | Yes | Yes | Yes |
| Source filtering | Yes | Yes | Yes |
| Sentiment data | **No** | Yes | Yes |
| Deduplication | **No** | Yes | Yes |
| Date range filter | **No** | Yes | Yes |
| History depth | 7 days | 1 year | 5 years |
| Items per request | 50 | 200 | 500 |
| API rate limit | 10/min | 60/min | 120/min |

## What Was Built

### Backend
- **`app/billing/tiers.py`** — Tier configuration with feature flags and limits. Functions: `get_tier()`, `has_feature()`, `get_limit()`, `get_features()`, `get_all_tiers_summary()`.
- **`app/middleware/tier_gate.py`** — Decorators:
  - `@require_feature("feature_name")` — returns 403 if user's tier lacks the feature
  - `@require_tier("plus")` — requires at least the specified tier
  - `tier_limit("limit_key")` — returns the numeric limit for the current user's tier
- **`app/routes/news.py`** — Updated with tier gating:
  - Item limit capped by `max_items_per_request` per tier
  - `sentiment_score`, `sentiment_label` stripped from response for free tier
  - `duplicate` field stripped from response for free tier
  - `from`/`to` date range params ignored for free tier
  - `history_days` limit restricts how far back free users can see
- **`app/auth/routes.py`** — Updated:
  - `GET /api/auth/tier` now returns full feature flags + limits from tiers.py
  - `GET /api/pricing` — new endpoint returning all tier definitions for pricing page

### 403 Response Format
When a gated feature is accessed:
```json
{
  "error": "Feature not available on your current plan",
  "feature": "ai_ticker_recommendations",
  "current_tier": "free",
  "upgrade_url": "/pricing"
}
```

## Test Coverage
15 tier-gating tests covering: tier config validation, field stripping per tier, limit capping, date range gating, decorator behavior, pricing endpoint.

## Total Tests: 63 (all passing)
