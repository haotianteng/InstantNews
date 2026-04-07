# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

InstNews is a commercial SaaS financial news integrating platform. It collects news from trusted sources and includes a SIGNAL terminal. It aggregates 15+ RSS feeds, scores headline sentiment via AI (MiniMax M2.7 with Claude Sonnet fallback), detects cross-source duplicates via sentence embeddings, and serves a dark-themed terminal UI. Features are gated by subscription tier (Free/Pro/Max) with Firebase Auth (Google OAuth + email/password). Pro tier includes a 30-day free trial.

**Domain:** www.instnews.net
**Target deployment:** AWS ECS Fargate + RDS PostgreSQL

## Commands

```bash
# Development (frontend + backend)
cd frontend && npx vite dev           # Vite dev server on :5173 (HMR, proxies /api to :8000)
python server.py                      # Flask backend on :8000
pip install -r requirements-dev.txt   # Install all deps including test

# Frontend build (required before deploying or testing on :8000)
cd frontend && npx vite build         # Outputs to static/

# Tests
python -m pytest tests/ -v
python -m pytest tests/ --cov=app --cov-report=term

# AI backfill (sentiment analysis for existing articles)
python scripts/backfill_ai.py                     # all unanalyzed
python scripts/backfill_ai.py --limit 100         # first 100
python scripts/backfill_ai.py --all               # re-analyze everything
python scripts/backfill_ai.py --dry-run           # preview only

# Production
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 server:app

# Background worker (separate process for feed refresh + AI analysis)
python -m app.worker

# Docker (prod — Nginx + Gunicorn)
docker build -f Dockerfile.prod -t instantnews:latest .

# Deploy to ECS
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 596080539716.dkr.ecr.us-east-1.amazonaws.com
docker tag instantnews:latest 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
docker push 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
aws ecs update-service --cluster instantnews --service InstantNewsStack-WebService... --force-new-deployment

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Architecture

**App factory pattern** (`app/__init__.py`): `create_app(config_class)` wires everything. Entry point is `server.py` (loads `.env` via python-dotenv).

**Modular backend** under `app/`:
- `config.py` — env-based config, feed URLs, word lists
- `database.py` — SQLAlchemy engine/session (SQLite or PostgreSQL via `DATABASE_URL`)
- `logging_config.py` — structured JSON logging for CloudWatch
- `models.py` — `News`, `Meta`, `User`, `Subscription`, `StripeEvent`, `ApiKey`, `ApiUsage` ORM models
- `services/sentiment.py` — keyword-based fallback sentiment (fast, inline during fetch)
- `services/bedrock_config.py` — **centralized AI config** (model IDs, prompts, token limits)
- `services/bedrock_analysis.py` — AI sentiment + ticker recommendations (MiniMax → Claude → Bedrock fallback chain)
- `services/feed_parser.py` — RSS parsing, calls keyword sentiment inline
- `services/feed_refresh.py` — parallel feed fetch, storage, dedup, then AI analysis on new articles
- `services/dedup.py` — sentence embedding deduplication
- `routes/` — Flask blueprints for each API endpoint
- `routes/keys.py` — API key CRUD (create, list, revoke)
- `routes/usage.py` — per-user API usage stats
- `auth/` — Firebase Auth + API key verification, `before_request` middleware
- `billing/tiers.py` — **single source of truth** for all tier data: features, limits, prices, display metadata
- `billing/routes.py` — Stripe Checkout (embedded + redirect), Portal, webhooks, payment method
- `middleware/tier_gate.py` — `@require_feature`, `@require_tier` decorators
- `middleware/rate_limit.py` — per-tier rate limiting (Flask-Limiter)
- `middleware/request_logger.py` — per-request logging + API usage counting

**Frontend** (`frontend/` source, `static/` built):
- **Vite** build tool with HMR dev server (port 5173, proxies `/api` → 8000)
- `src/auth.js` — Firebase Auth (Google OAuth redirect/popup + email/password)
- `src/landing.js` — landing page interactivity
- `src/pricing-renderer.js` — **shared** pricing card renderer (fetches from `/api/pricing`)
- `src/checkout.js` — Stripe Embedded Checkout sidebar
- `src/account.js` — account dashboard (Overview, Usage, Plans, Billing, API Keys tabs)
- `src/terminal-app.js` — SIGNAL terminal
- `src/styles/` — `base.css`, `landing.css`, `terminal.css`

**Database**: SQLite for dev, PostgreSQL for prod. Tables: `news`, `meta`, `users`, `subscriptions`, `stripe_events`, `api_keys`, `api_usage`. Migrations via Alembic.

## API Endpoints

- `GET /api/news` — news items (tier-gated: sentiment/duplicate/ticker fields stripped for free)
- `GET /api/sources` — feed sources with counts
- `GET /api/stats` — aggregated statistics
- `POST /api/refresh` — force feed refresh
- `GET /api/docs` — API documentation JSON
- `GET /api/auth/me` — current user profile (requires auth)
- `GET /api/auth/tier` — user's tier, feature flags, limits
- `GET /api/pricing` — all tier definitions with display metadata (ordered list)
- `GET /api/keys` — list user's API keys
- `POST /api/keys` — create new API key (returns key once)
- `DELETE /api/keys/:id` — revoke API key
- `GET /api/usage` — user's API request counts (today, 7-day, month, all-time)
- `GET /api/billing/config` — Stripe publishable key
- `POST /api/billing/checkout` — create Stripe Checkout session (supports `embedded: true`)
- `POST /api/billing/portal` — create Stripe Customer Portal session
- `GET /api/billing/status` — subscription status
- `GET /api/billing/payment-method` — default payment method (card brand, last4, expiry)

## Configuration

All via environment variables (see `.env.example`):

**Core:** `DATABASE_URL`, `PORT`, `STALE_SECONDS`, `FETCH_TIMEOUT`, `DEDUP_THRESHOLD`, `MAX_AGE_DAYS`, `WORKER_INTERVAL_SECONDS`, `WORKER_ENABLED`

**Auth:** `FIREBASE_CREDENTIALS` (file path, dev) / `FIREBASE_CREDENTIALS_JSON` (inline, prod)

**Stripe:** `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PLUS`, `STRIPE_PRICE_MAX`

**AI Analysis:** `BEDROCK_ENABLED`, `BEDROCK_REGION`, `BEDROCK_MODEL_ID`, `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, `MINIMAX_MODEL_ID`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_ID`, `MINIMAX_MAX_TOKENS`, `ANTHROPIC_MAX_TOKENS`, `BEDROCK_MAX_TOKENS`, `BEDROCK_MAX_CONCURRENT`

## Tier System

Defined in `app/billing/tiers.py` — **single source of truth** for ALL tier data (backend gating + frontend display). Three visible tiers:

- **Free** ($0): news feed, keyword search, source filtering. 50 items/req, 30 req/min, 7-day history.
- **Pro** ($14.99/mo, 30-day trial): sentiment analysis, dedup, date filtering, API access, CSV export, watchlist. 200 items/req, 300 req/min, 1-year history.
- **Max** ($39.99/mo): everything in Pro + AI ticker recommendations, price analysis, advanced analytics, custom alerts. 500 items/req, 1000 req/min, 5-year history.

The `plus` key is a backward-compatibility alias for `pro`. Frontend fetches tier display data from `/api/pricing` — never hardcoded.

## AI Sentiment & Ticker Analysis

**Pipeline:** Feed refresh → store with keyword sentiment → run AI analysis on new articles → update DB.

**Model fallback chain:** MiniMax M2.7 → Claude Sonnet 4 → AWS Bedrock (configurable in `bedrock_config.py`).

**Output per article:** `sentiment_score`, `sentiment_label`, `target_asset` (ticker), `asset_type`, `confidence`, `risk_level`, `tradeable`, `reasoning`.

**Backfill:** `python scripts/backfill_ai.py` — concurrent batch processing (50 articles/batch, 500 RPM MiniMax limit).

## Key Implementation Details

- Embedding model loads lazily on first feed refresh (2-3s cold start, ~500MB memory)
- Feed fetching has 20-second total deadline across 15 parallel threads
- Auth middleware supports both Firebase tokens (`Authorization: Bearer`) and API keys (`X-API-Key`)
- `StaticPool` used for in-memory SQLite so all connections share one database
- Server-side route guards removed for `/terminal` and `/account` — auth checked client-side (Firebase tokens aren't sent on page navigation)
- `server.py` loads `.env` via python-dotenv for local dev
- Stripe Embedded Checkout via sidebar overlay (no page redirect)

## Deployment

**Infrastructure:** AWS CDK stack (`infra/stack.py`) — ECS Fargate (2-10 tasks, 0.5 vCPU), RDS PostgreSQL, ALB with HTTPS, ECR, Secrets Manager, Route 53, auto-scaling.

**Docker:** `Dockerfile.prod` — Nginx (static files + proxy) + Gunicorn via Supervisor.

**Secrets:** `instantnews/app` in AWS Secrets Manager stores: Stripe keys, Firebase service account JSON, MiniMax API key, Anthropic API key.

**Deploy flow:** `vite build` → `docker build` → `docker push` to ECR → `aws ecs update-service --force-new-deployment`.

## Observability

**Structured JSON logging** — all logs are single-line JSON for CloudWatch. Logger hierarchy: `signal`, `signal.requests`, `signal.auth`, `signal.billing`, `signal.rate_limit`, `signal.worker`, `signal.ai`.

**API usage tracking** — `request_logger.py` increments daily per-user counters in `api_usage` table on every `/api/*` request.

## Documentation

- `docs/phase-1-backend-restructure.md` — monolith split, SQLAlchemy migration
- `docs/phase-2-authentication.md` — Firebase Auth, Google OAuth
- `docs/phase-3a-tier-gating.md` — feature gating by tier
- `docs/future-features.md` — unimplemented features roadmap with priorities
- `docs/architecture.md` — system architecture and file structure
