# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SIGNAL (InstantNews) is a commercial SaaS financial news terminal. It aggregates 15+ RSS feeds, scores headline sentiment, detects cross-source duplicates via sentence embeddings, and serves a dark-themed terminal UI. Features are gated by subscription tier (Free/Plus/Max) with Firebase Auth (Google OAuth).

**Domain:** www.instnews.net (planned)
**Target deployment:** AWS ECS Fargate + RDS PostgreSQL

## Commands

```bash
# Development
python server.py                    # Starts on http://localhost:8000
pip install -r requirements-dev.txt # Install all deps including test

# Tests
python -m pytest tests/ -v                         # Run all tests
python -m pytest tests/ --cov=app --cov-report=term # With coverage

# Production
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 server:app

# Background worker (separate process for feed refresh)
python -m app.worker

# Docker (dev — SQLite, single container)
docker compose up -d

# Docker (prod — PostgreSQL + worker)
docker compose -f docker-compose.yml up -d

# Migrations
alembic upgrade head          # Apply all migrations
alembic revision --autogenerate -m "description"  # Generate new migration
```

## Architecture

**App factory pattern** (`app/__init__.py`): `create_app(config_class)` wires everything. Entry point is `server.py` (thin shim).

**Modular backend** under `app/`:
- `config.py` — env-based config, feed URLs, word lists
- `database.py` — SQLAlchemy engine/session (SQLite or PostgreSQL via `DATABASE_URL`)
- `models.py` — `News`, `Meta`, `User` ORM models
- `services/` — sentiment scoring, RSS parsing, feed refresh, dedup
- `routes/` — Flask blueprints for each API endpoint
- `auth/` — Firebase Admin SDK token verification, `before_request` middleware
- `billing/tiers.py` — tier definitions (feature flags + limits), single source of truth
- `middleware/tier_gate.py` — `@require_feature`, `@require_tier` decorators

**Frontend** (`static/`): Vanilla JS, no build step. `auth.js` handles Firebase Auth, `app.js` uses `SignalAuth.fetch()` for authenticated requests.

**Database**: SQLite for dev, PostgreSQL for prod. Three tables: `news`, `meta`, `users`. Migrations via Alembic.

## API Endpoints

- `GET /api/news` — news items (tier-gated: limit capped, sentiment/duplicate fields stripped for free)
- `GET /api/sources` — feed sources with counts
- `GET /api/stats` — aggregated statistics
- `POST /api/refresh` — force feed refresh
- `GET /api/docs` — API documentation JSON
- `GET /api/auth/me` — current user profile (requires auth)
- `GET /api/auth/tier` — user's tier, feature flags, limits
- `GET /api/pricing` — all tier definitions

## Configuration

All via environment variables (see `app/config.py` and `.env.example`):
`DATABASE_URL`, `PORT`, `STALE_SECONDS`, `FETCH_TIMEOUT`, `DEDUP_THRESHOLD`, `MAX_AGE_DAYS`, `WORKER_INTERVAL_SECONDS`, `WORKER_ENABLED`, `FIREBASE_CREDENTIALS` / `FIREBASE_CREDENTIALS_JSON`

## Tier System

Defined in `app/billing/tiers.py`. Free tier strips sentiment/duplicate data, caps at 50 items and 7 days history. Plus adds full analysis. Max adds AI features (not yet implemented). See `docs/future-features.md` for the feature roadmap.

## Key Implementation Details

- Embedding model loads lazily on first feed refresh (2-3s cold start, ~500MB memory)
- Feed fetching has 20-second total deadline across 15 parallel threads
- Auth middleware copies User fields into detached `CurrentUser` object to avoid SQLAlchemy `DetachedInstanceError`
- `StaticPool` used for in-memory SQLite so all connections share one database (tests + single-process mode)
- `docs/` contains phase-by-phase implementation documentation

## Documentation

- `docs/phase-1-backend-restructure.md` — monolith split, SQLAlchemy migration
- `docs/phase-2-authentication.md` — Firebase Auth, Google OAuth
- `docs/phase-3a-tier-gating.md` — feature gating by tier
- `docs/future-features.md` — unimplemented features roadmap with priorities
- `docs/architecture.md` — system architecture and file structure
