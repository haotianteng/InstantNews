# Architecture Overview

## Current State (Post Phase 3A)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vanilla JS)                     │
│  static/index.html  ─  static/app.js  ─  static/auth.js         │
│  Firebase JS SDK (CDN) for Google OAuth                          │
│  SignalAuth.fetch() attaches Bearer token to all API calls       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP + Authorization: Bearer <token>
┌──────────────────────────────▼──────────────────────────────────┐
│                     Flask Application (server.py)                │
│                                                                  │
│  before_request: load_current_user()                             │
│    └─ Verify Firebase token → Create/update User → g.current_user│
│                                                                  │
│  Routes:                                                         │
│    /api/news     ← tier-gated (limit, field stripping, history)  │
│    /api/sources  ← open                                          │
│    /api/stats    ← open                                          │
│    /api/refresh  ← open                                          │
│    /api/docs     ← open                                          │
│    /api/auth/me  ← requires auth                                 │
│    /api/auth/tier ← open (returns free for anon)                 │
│    /api/pricing  ← open                                          │
│                                                                  │
│  Tier Gating:                                                    │
│    app/billing/tiers.py  ← feature flags + limits per tier       │
│    app/middleware/tier_gate.py  ← @require_feature, @require_tier│
└──────────────────────────────┬──────────────────────────────────┘
                               │ SQLAlchemy
┌──────────────────────────────▼──────────────────────────────────┐
│                         Database                                 │
│  SQLite (dev) or PostgreSQL (prod)                               │
│                                                                  │
│  Tables:                                                         │
│    news  ─ id, title, link, source, published, fetched_at,       │
│            summary, sentiment_score, sentiment_label, tags,      │
│            duplicate, embedding                                  │
│    meta  ─ key, value (last_refresh, source_status)              │
│    users ─ id, firebase_uid, email, display_name, photo_url,     │
│            tier, created_at, updated_at                          │
└─────────────────────────────────────────────────────────────────┘
```

## Production Target (ECS Fargate)

```
        Route 53 (instnews.net)
                │
        Application Load Balancer
           /              \
   ECS Fargate           ECS Fargate
   (web: gunicorn)       (feed-worker)
        │                     │
   RDS PostgreSQL ────────────┘
        │
   ElastiCache Redis (future: rate limiting, sessions)
```

## File Structure

```
InstantNews/
├── server.py                  # Entry point (thin shim)
├── app/
│   ├── __init__.py            # create_app() factory
│   ├── config.py              # Environment-based config
│   ├── database.py            # SQLAlchemy engine/session
│   ├── models.py              # News, Meta, User
│   ├── worker.py              # Standalone feed worker
│   ├── auth/
│   │   ├── firebase.py        # Firebase Admin SDK
│   │   ├── middleware.py       # Token verification, user loading
│   │   └── routes.py          # /api/auth/* endpoints
│   ├── billing/
│   │   └── tiers.py           # Tier definitions (features + limits)
│   ├── middleware/
│   │   └── tier_gate.py       # @require_feature, @require_tier
│   ├── routes/
│   │   ├── news.py            # /api/news (tier-gated)
│   │   ├── sources.py         # /api/sources
│   │   ├── stats.py           # /api/stats
│   │   ├── refresh.py         # /api/refresh
│   │   ├── docs.py            # /api/docs
│   │   └── static_pages.py    # /
│   └── services/
│       ├── sentiment.py       # Keyword-based scoring
│       ├── feed_parser.py     # RSS/Atom parsing
│       ├── feed_refresh.py    # Parallel feed fetching
│       └── dedup.py           # Sentence embedding dedup
├── static/                    # Frontend (vanilla JS, no build step)
│   ├── index.html
│   ├── app.js
│   ├── auth.js                # Firebase Auth module
│   ├── style.css
│   └── base.css
├── migrations/
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_add_users_table.py
├── tests/
│   ├── conftest.py
│   ├── test_sentiment.py
│   ├── test_feed_parser.py
│   ├── test_models.py
│   ├── test_routes.py
│   ├── test_auth.py
│   └── test_tiers.py
├── docs/                      # Phase documentation
├── Dockerfile
├── docker-compose.yml         # Prod (PostgreSQL + worker)
├── docker-compose.override.yml # Dev (SQLite, in-process worker)
├── requirements.txt
├── requirements-dev.txt
├── alembic.ini
└── pyproject.toml
```

## Key Patterns

- **App factory:** `create_app(config_class)` enables testing with different configs
- **Session-per-request:** Each route handler creates and closes its own session. No shared state.
- **Detached user objects:** Auth middleware copies User fields into a plain `CurrentUser` object to avoid SQLAlchemy `DetachedInstanceError` after session close.
- **Feed refresh decoupled from API:** Background worker or APScheduler refreshes feeds. API only reads. Staleness check via `meta.last_refresh` timestamp.
- **Tier gating at route level:** `_shape_item()` strips fields from response based on tier. `tier_limit()` caps numeric parameters. `@require_feature` blocks entire endpoints.
