# Phase 4: Frontend Overhaul + AI Sentiment Analysis

**Date:** 2026-04-05
**Status:** Deployed

## Summary

Major frontend redesign, AI-powered sentiment analysis, account dashboard, API key management, and centralized tier configuration.

## Changes

### Frontend (Vite Build System)
- Migrated from static files to **Vite** build toolchain (`frontend/` → `static/`)
- Dev server on port 5173 with HMR, proxies `/api` to Flask on 8000
- All tier/pricing data now fetched from `/api/pricing` — zero hardcoded plan details in frontend
- Shared `pricing-renderer.js` renders pricing cards on landing, pricing, and account pages
- Stripe Embedded Checkout via sidebar overlay (no page redirect)

### Account Dashboard
- 5-tab layout: Overview, Usage, Plans, Billing & Payment, API Keys
- **Usage tab**: real API request tracking (per-user daily counts in `api_usage` table)
- **API Keys tab**: users create/revoke `instnews_<hex>` API keys (max 5, Pro/Max only)
- **Billing tab**: credit card visualization from Stripe, billing overview
- **Plans tab**: inline plan comparison with downgrade confirmation (red notice with effective date)

### AI Sentiment & Ticker Analysis
- **Model chain**: MiniMax M2.7 (primary) → Claude Sonnet 4 (fallback) → AWS Bedrock (last resort)
- Replaces keyword-based sentiment with LLM analysis
- Each article gets: sentiment_score, sentiment_label, target_asset, asset_type, confidence, risk_level, tradeable, reasoning
- Backfill script: `scripts/backfill_ai.py` (concurrent batch processing, 50/batch)
- All AI config centralized in `app/services/bedrock_config.py`

### Centralized Tier Configuration
- `app/billing/tiers.py` is the **single source of truth** for all tier data
- Added `display` dict to each tier (prices, descriptions, feature lists, CTA labels)
- Added `TIER_ORDER` list for canonical display ordering
- `/api/pricing` returns ordered list with display metadata + max-tier limits
- Three visible tiers: Free ($0), Pro ($14.99/mo), Max ($39.99/mo)

### Auth & API Keys
- Auth middleware now accepts `X-API-Key` header alongside Firebase Bearer tokens
- API keys stored as SHA-256 hashes, prefix shown for identification
- `last_used_at` tracked on each API key use
- `api_access` feature gate required (Pro/Max)

### Rate Limits (updated)
- Free: 30 req/min (was 10)
- Pro: 300 req/min (was 60)
- Max: 1,000 req/min (was 120)

## Infrastructure Changes

### Secrets Manager (`instantnews/app`)
New fields added:
- `STRIPE_PUBLISHABLE_KEY` — for Stripe Embedded Checkout
- `MINIMAX_API_KEY` — MiniMax AI model access
- `MINIMAX_BASE_URL` — MiniMax API endpoint
- `ANTHROPIC_API_KEY` — Claude fallback model access

### CDK Stack (`infra/stack.py`)
- Web container: added `BEDROCK_ENABLED`, `BEDROCK_REGION` env vars + new secrets
- Worker container: added AI-related secrets (MiniMax, Anthropic) for feed refresh analysis
- Firebase credentials already added in earlier phase

### Nginx Config (`deploy/nginx.conf`)
- Added `/assets/` location block with 1-year cache for Vite hashed assets
- Separate from other static files (images etc.) which get 1-hour cache

### Database Schema
New tables:
- `api_keys` — user-generated API keys (id, user_id, name, key_prefix, key_hash, created_at, last_used_at)
- `api_usage` — daily per-user API request counts (user_id, date, request_count)

New columns on `news`:
- `target_asset` (TEXT) — recommended ticker symbol
- `asset_type` (TEXT) — STOCK, FUTURE, ETF, CURRENCY
- `confidence` (REAL) — 0.0 to 1.0
- `risk_level` (TEXT) — LOW, MEDIUM, HIGH
- `tradeable` (BOOLEAN) — AI recommendation
- `reasoning` (TEXT) — full analysis reasoning chain
- `ai_analyzed` (BOOLEAN) — whether AI analysis completed

### Docker Image
- Updated `requirements.txt`: added `python-dotenv`, `boto3`, `anthropic`
- `server.py` now loads `.env` via python-dotenv
- Static files built by Vite with content-hashed filenames

## Deploy Checklist
1. `cd frontend && npx vite build`
2. `docker build -f Dockerfile.prod -t instantnews:latest .`
3. `docker tag` + `docker push` to ECR
4. Update Secrets Manager with new keys (MINIMAX, ANTHROPIC, STRIPE_PUBLISHABLE_KEY)
5. `cdk deploy` if stack changes needed
6. `aws ecs update-service --force-new-deployment`
7. Run Alembic migration for new columns/tables (or `create_tables()` handles it on startup for new tables)
