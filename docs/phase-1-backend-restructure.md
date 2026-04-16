# Phase 1: Backend Restructure + Database Migration

**Status:** Complete
**Goal:** Split the 523-line `server.py` monolith into a modular Flask application, replace raw SQLite with SQLAlchemy (supporting both SQLite and PostgreSQL), and add Alembic migrations.

## What Changed

### Before
- Single file `server.py` with all logic: config, DB, sentiment, RSS fetching, dedup, routes
- Raw `sqlite3` calls with inline DDL
- Feed refresh happened inside API request handlers (blocking)
- No tests, no migrations

### After

```
app/
  __init__.py              # Flask app factory (create_app)
  config.py                # Centralized config from env vars
  database.py              # SQLAlchemy engine/session management
  models.py                # ORM models: News, Meta
  services/
    sentiment.py           # score_sentiment() + word lists
    feed_parser.py         # RSS parsing, date handling, HTML stripping
    feed_refresh.py        # Parallel feed fetching, staleness check
    dedup.py               # Sentence embedding deduplication
  routes/
    news.py                # GET /api/news
    sources.py             # GET /api/sources
    stats.py               # GET /api/stats
    refresh.py             # POST /api/refresh
    docs.py                # GET /api/docs
    static_pages.py        # GET / (serves index.html)
  worker.py                # Standalone background feed worker
migrations/
  versions/
    001_initial_schema.py  # News + Meta tables
tests/
  conftest.py              # Fixtures: app, client, db_session, sample_news
  test_sentiment.py
  test_feed_parser.py
  test_models.py
  test_routes.py
server.py                  # Thin shim: from app import create_app; app = create_app()
```

### Key Decisions
- **SQLAlchemy with dual backend:** `sqlite://` for local dev, `postgresql://` for production. Configured via `DATABASE_URL` env var.
- **StaticPool for in-memory SQLite:** Required so all connections share the same database (critical for tests and single-process mode).
- **Background worker as separate process:** `python -m app.worker` runs independently from the web server. In Docker, this is a separate container. For single-process dev, APScheduler runs in-process.
- **server.py kept as shim:** `gunicorn server:app` and `python server.py` still work unchanged.
- **ISO 8601 strings for dates:** Kept as strings (not datetime columns) for backward compatibility with existing API consumers.

### Docker Changes
- `docker-compose.yml` now includes PostgreSQL service + separate `feed-worker` container
- `docker-compose.override.yml` for dev mode (SQLite, no PostgreSQL, in-process worker)
- `Dockerfile` runs `alembic upgrade head` before starting gunicorn

### Dependencies Added
- `sqlalchemy>=2.0` — ORM
- `alembic>=1.13` — schema migrations
- `psycopg2-binary>=2.9` — PostgreSQL driver
- `apscheduler>=3.10` — background scheduling
- `numpy>=1.26` — (was implicit, now explicit)

### Test Coverage
39 tests covering sentiment scoring, feed parsing, ORM models, and all API endpoints.
