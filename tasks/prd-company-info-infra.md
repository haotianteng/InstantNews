# PRD — Company Information Infrastructure Upgrade

**Status:** Draft
**Owner:** Implementor + Tester (Ralph v2)
**Branch:** `ralph/company-info-infra`
**Created:** 2026-04-17

---

## 1. Introduction / Overview

InstantNews currently stores all company-related data (details, financials, competitors, institutional holders, insider transactions, earnings) as opaque JSON blobs in a single `company_data_cache` table (`migrations/versions/012_add_company_data_cache.py`). The terminal's Company panel hits six on-demand routes (`app/routes/market.py:24-186`) that fan out to Polygon.io and SEC EDGAR per request, with two cache tiers (in-process dicts + Postgres JSON cache).

This PRD upgrades the storage layer to a **normalized, query-able, history-preserving** company data warehouse:

- Six normalized Postgres tables matching the reference schema in `tasks/todo_company_table.md`
- Type-2 SCD versioning for fundamentals (current row + history table) so users can retrieve point-in-time snapshots
- Append-only seasonal data (financials, 13F, Form 4) keyed by `period_end` / `transaction_date` for historical queries
- Redis (ElastiCache) as the hot-read cache, with cache-aside pattern in repositories
- Repository + Service layer separation, with a unified `GET /api/company/<ticker>/profile` endpoint that fans out 6 cache lookups in parallel via `ThreadPoolExecutor`
- Scheduled ingestion jobs for EDGAR (10-Q/10-K/13F/Form 4) and Polygon (fundamentals refresh)
- One-time backfill from existing `company_data_cache` JSON blobs into normalized tables, then deprecate

**Out of explicit scope:** full async migration of the Flask app — see Tech Considerations §7.

---

## 2. Goals

- **G1**: Normalize company data into 6 purpose-built tables; eliminate JSON-blob storage for company domain data.
- **G2**: Preserve full history for fundamentals (SCD-2) and seasonal data (append-only) so the terminal can show point-in-time views.
- **G3**: Add Redis cache layer (ElastiCache in prod, container in dev) with TTLs aligned to data volatility — full company profile served in <50ms p99 on cache hit.
- **G4**: Scheduled ingestion (EDGAR + Polygon) replaces on-demand fetches as the primary data path. On-demand fetch becomes the fallback.
- **G5**: New `GET /api/company/<ticker>/profile` aggregates all 6 domains in one response via parallel fan-out.
- **G6**: Backfill existing cache, then deprecate `company_data_cache` table in a follow-up migration (after 7 days of dual-write soak).
- **G7**: Repository interfaces designed so a future sync→async migration is mechanical (~3-5 days), not architectural.

---

## 3. User Stories

Stories are ordered by dependency. Each fits one Implementor iteration.

---

### US-001: Add Redis to dev + prod infrastructure

**Description:** As a backend engineer, I want a Redis instance available in both local Docker and AWS production so the new repository layer has a hot cache to read/write to.

**Acceptance Criteria:**
- [ ] `docker-compose.yml` adds a `redis:7-alpine` service named `redis` exposed on port 6379, with a named volume `redis-data` for persistence
- [ ] `docker-compose.override.yml` exposes Redis to the host on `localhost:6379` for dev tooling
- [ ] CDK stack in `infra/` provisions an `aws_elasticache.CfnCacheCluster` (Redis 7, `cache.t4g.micro`) in the same VPC/subnet as ECS, with security group allowing inbound 6379 from the ECS task security group only
- [ ] `REDIS_URL` env var added to `app/config.py` (default `redis://localhost:6379/0`); injected into ECS task definition from CDK output
- [ ] `requirements.txt` adds `redis>=5.0.0` (sync client; async client is same package)
- [ ] `app/cache/redis_client.py` exports a singleton `get_redis()` returning a `redis.Redis` client built from `REDIS_URL`, with connection pooling (`max_connections=50`)
- [ ] Health endpoint `/health` (or existing equivalent) reports Redis ping status
- [ ] Typecheck passes (`mypy app/cache/`)

**Test Strategy:** integration

**Test Assertions:**
- `docker compose up -d redis && docker compose exec redis redis-cli PING` returns `PONG`
- `python3 -c "from app.cache.redis_client import get_redis; r = get_redis(); r.set('test', '1'); assert r.get('test') == b'1'"` exits 0
- `grep -E '^redis>=' requirements.txt` exits 0
- `mypy app/cache/` exits 0
- CDK synth: `cd infra && cdk synth | grep -q 'AWS::ElastiCache::CacheCluster'` exits 0
- `/health` endpoint response JSON contains `redis: "ok"` after Redis is up

---

### US-002: Migration — companies (master reference table)

**Description:** As a backend engineer, I want a `companies` master table so stable per-ticker reference data (name, exchange, sector, CIK, etc.) is normalized. Includes a nullable `delisted_at` column to gracefully handle delistings without losing historical rows (OQ-5 resolution).

**Acceptance Criteria:**
- [ ] New Alembic revision `014_add_companies_table.py` creates the `companies` table per `tasks/todo_company_table.md` §1 Layer 1, **plus one extra column**: `delisted_at TIMESTAMP NULL` (NULL = currently listed; non-NULL = delisted at that timestamp)
- [ ] Indexes created on `sector`, `industry`, and partial index `idx_companies_active ON companies(ticker) WHERE delisted_at IS NULL` for fast active-ticker scans
- [ ] `app/models.py` adds `Company` SQLAlchemy model matching the schema (including `delisted_at`)
- [ ] `app/models/company.py` adds Pydantic `Company` schema (separate from ORM model — used by repositories as return type)
- [ ] `alembic upgrade head` runs cleanly against an empty Postgres
- [ ] `alembic downgrade -1` rolls back cleanly
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `alembic upgrade head` exits 0; `psql -c "\d companies"` shows all 14 spec columns + `delisted_at`
- `psql -c "SELECT indexname FROM pg_indexes WHERE tablename='companies'"` includes `idx_companies_sector`, `idx_companies_industry`, and `idx_companies_active`
- `python3 -c "from app.models import Company; c = Company(ticker='AAPL', name='Apple Inc'); print(c.ticker)"` exits 0 with output `AAPL`
- `python3 -c "from app.models.company import Company as PydCompany; PydCompany(ticker='AAPL', name='Apple Inc.', delisted_at=None)"` exits 0
- `alembic downgrade -1` exits 0; `\d companies` then errors
- `mypy app/models/company.py` exits 0

---

### US-003: Migration — company_financials (append-only seasonal)

**Description:** As a backend engineer, I want a `company_financials` table that is append-only and keyed by `(ticker, period_end, period_type)` so historical filings are preserved for backtests.

**Acceptance Criteria:**
- [ ] New Alembic revision `015_add_company_financials.py` creates `company_financials` per spec §1 Layer 2
- [ ] Composite primary key `(ticker, period_end, period_type)` enforced
- [ ] Foreign key `ticker → companies(ticker)` with `ON DELETE RESTRICT`
- [ ] Index `idx_financials_period` on `(ticker, period_end DESC)`
- [ ] `app/models/financials.py` adds Pydantic `Financials` model
- [ ] `app/models.py` adds SQLAlchemy `CompanyFinancials` model
- [ ] Migration is reversible
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `alembic upgrade head` exits 0; `\d company_financials` shows all expected columns
- Insert smoke test: `psql -c "INSERT INTO companies(ticker, name) VALUES ('AAPL','Apple'); INSERT INTO company_financials(ticker, period_end, period_type, fiscal_year, revenue) VALUES ('AAPL','2025-12-31','Q4',2025,90000000000)"` exits 0
- Duplicate PK rejection: second identical insert returns SQL error
- `python3 -c "from app.models.financials import Financials; Financials(ticker='AAPL', period_end='2025-12-31', period_type='Q4', fiscal_year=2025)"` exits 0
- `mypy app/models/financials.py` exits 0

---

### US-004: Migration — company_fundamentals + company_fundamentals_history (SCD-2)

**Description:** As a backend engineer, I want a current-view `company_fundamentals` table plus an immutable `company_fundamentals_history` table so callers can fetch the latest fundamentals fast and also retrieve point-in-time snapshots.

**Acceptance Criteria:**
- [ ] New Alembic revision `016_add_company_fundamentals.py` creates:
  - `company_fundamentals` (PK = `ticker`) per spec §1 Layer 2 with all forward-looking metrics
  - `company_fundamentals_history` with columns from the spec PLUS `valid_from TIMESTAMP NOT NULL`, `valid_to TIMESTAMP NOT NULL`, PK `(ticker, valid_from)`, index `(ticker, valid_to DESC)`
- [ ] Postgres trigger `fn_snapshot_fundamentals_before_update`: BEFORE UPDATE on `company_fundamentals`, copy OLD row to `company_fundamentals_history` with `valid_from = OLD.updated_at`, `valid_to = NOW()`
- [ ] Foreign key `ticker → companies(ticker)` on both tables
- [ ] `app/models/fundamentals.py` adds Pydantic `Fundamentals` and `FundamentalsHistory` models
- [ ] Migration reversible (drops trigger first)
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `alembic upgrade head` exits 0; both tables and trigger exist (`\d company_fundamentals`, `\d company_fundamentals_history`, `psql -c "SELECT tgname FROM pg_trigger WHERE tgname='fn_snapshot_fundamentals_before_update'"` returns 1 row)
- SCD test script: insert AAPL row with `pe_ratio=30`, then UPDATE to `pe_ratio=32` — `SELECT count(*) FROM company_fundamentals_history WHERE ticker='AAPL'` returns 1, and the historical row has `pe_ratio=30`
- `python3 -c "from app.models.fundamentals import Fundamentals; Fundamentals(ticker='AAPL', market_cap=3000000000000)"` exits 0
- `mypy app/models/fundamentals.py` exits 0

---

### US-005: Migration — company_competitors

**Description:** As a backend engineer, I want a `company_competitors` table to store the directional similarity graph between tickers.

**Acceptance Criteria:**
- [ ] New Alembic revision `017_add_company_competitors.py` creates the table per spec §1 Layer 3
- [ ] Composite PK `(ticker, competitor_ticker)`, CHECK constraint `ticker != competitor_ticker`
- [ ] Index `idx_competitors_score` on `(ticker, similarity_score DESC)`
- [ ] `app/models/competitors.py` adds Pydantic `Competitor` model
- [ ] Migration reversible
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `alembic upgrade head` exits 0; `\d company_competitors` matches spec
- Self-reference rejection: `INSERT INTO company_competitors VALUES ('AAPL','AAPL',0.5,'manual',NOW())` returns CHECK violation
- `python3 -c "from app.models.competitors import Competitor; Competitor(ticker='AAPL', competitor_ticker='MSFT', similarity_score=0.85)"` exits 0
- `mypy app/models/competitors.py` exits 0

---

### US-006: Migration — institutional_holders

**Description:** As a backend engineer, I want an `institutional_holders` table to store quarterly 13F snapshots, append-only by `(ticker, institution_cik, report_date)`.

**Acceptance Criteria:**
- [ ] New Alembic revision `018_add_institutional_holders.py` creates the table per spec §1 Layer 3
- [ ] BIGSERIAL `id` PK, UNIQUE constraint on `(ticker, institution_cik, report_date)`
- [ ] Indexes `idx_inst_ticker_date` and `idx_inst_by_value` from spec
- [ ] `app/models/institutions.py` adds Pydantic `InstitutionalHolder` model
- [ ] Migration reversible
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `alembic upgrade head` exits 0; `\d institutional_holders` matches spec
- Duplicate `(ticker, institution_cik, report_date)` insert returns UNIQUE violation
- `psql -c "SELECT indexname FROM pg_indexes WHERE tablename='institutional_holders'"` includes both expected indexes
- `python3 -c "from app.models.institutions import InstitutionalHolder; InstitutionalHolder(ticker='AAPL', institution_cik='0001067983', institution_name='Berkshire', report_date='2025-12-31', shares_held=100, market_value=10000)"` exits 0
- `mypy app/models/institutions.py` exits 0

---

### US-007: Migration — insider_transactions

**Description:** As a backend engineer, I want an `insider_transactions` table to store Form 4/5 events.

**Acceptance Criteria:**
- [ ] New Alembic revision `019_add_insider_transactions.py` creates the table per spec §1 Layer 3
- [ ] BIGSERIAL `id` PK; index `idx_insider_ticker_date` on `(ticker, transaction_date DESC)`
- [ ] **Dedup constraint** added beyond the spec: UNIQUE on `(ticker, insider_name, transaction_date, transaction_type, shares, form_type)` so re-ingesting the same Form 4 is idempotent (resolves Q6 ambiguity for events)
- [ ] `app/models/insiders.py` adds Pydantic `InsiderTransaction` model
- [ ] Migration reversible
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `alembic upgrade head` exits 0; `\d insider_transactions` matches spec + unique constraint
- Duplicate insert (same insider, date, type, shares, form_type) returns UNIQUE violation
- `python3 -c "from app.models.insiders import InsiderTransaction; InsiderTransaction(ticker='AAPL', insider_name='Tim Cook', insider_title='CEO', transaction_date='2025-12-31', transaction_type='SELL', shares=100, price_per_share=200.0, total_value=20000, form_type='Form 4')"` exits 0
- `mypy app/models/insiders.py` exits 0

---

### US-008: BaseRepository with cache-aside pattern

**Description:** As a backend engineer, I want a `BaseRepository` class that encapsulates the cache-aside pattern (Redis read → DB read → Redis populate) so all six repos share consistent behavior.

**Acceptance Criteria:**
- [ ] `app/repositories/base.py` defines `BaseRepository[T]` (generic over Pydantic model type)
- [ ] Methods: `cached_get(key: str, ttl: int, db_loader: Callable[[], T | None]) -> T | None` — checks Redis, falls back to DB loader, populates Redis on miss
- [ ] `cached_get_list(key: str, ttl: int, db_loader: Callable[[], list[T]]) -> list[T]` — same pattern for lists
- [ ] `invalidate(key: str)` — removes a cache key
- [ ] Cache-miss exceptions on Redis are caught and logged; DB loader still runs (Redis is a non-critical cache)
- [ ] `app/cache/cache_keys.py` exports key builders: `company_master(ticker)`, `company_fundamentals(ticker)`, `company_financials_latest(ticker)`, `company_competitors_top(ticker, n)`, `company_institutions_top(ticker, n)`, `company_insiders_recent(ticker, days)`
- [ ] All keys follow `company:{ticker}:{domain}` namespacing per spec §2
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.cache.cache_keys import company_master; assert company_master('AAPL') == 'company:AAPL:master'"` exits 0
- Unit test in `tests/repositories/test_base.py`: `pytest tests/repositories/test_base.py -v` exits 0 with all tests passing, covering: (a) cache hit returns cached value without calling db_loader, (b) cache miss calls db_loader and populates Redis, (c) Redis exception falls through to db_loader
- `mypy app/repositories/base.py app/cache/cache_keys.py` exits 0

---

### US-009: CompanyRepository

**Description:** As a backend engineer, I want a `CompanyRepository` that reads/writes the `companies` master table with cache-aside.

**Acceptance Criteria:**
- [ ] `app/repositories/company_repo.py` defines `CompanyRepository` with:
  - `get(ticker: str) -> Company | None` — cache-aside via `BaseRepository.cached_get`, 24h TTL per spec §2
  - `upsert(company: Company) -> Company` — INSERT ... ON CONFLICT (ticker) DO UPDATE; invalidates cache key on success
  - `list_by_sector(sector: str) -> list[Company]` — DB-only (low value to cache)
- [ ] Returns Pydantic models, not SQLAlchemy rows
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `pytest tests/repositories/test_company_repo.py -v` exits 0 covering: (a) `upsert` then `get` returns same data, (b) second `get` is a cache hit (verify via Redis MONITOR or by clearing DB and re-getting), (c) `upsert` invalidates cache so subsequent `get` reflects update
- `python3 -c "from app.repositories.company_repo import CompanyRepository; r = CompanyRepository(); print(type(r).__name__)"` exits 0
- `mypy app/repositories/company_repo.py` exits 0

---

### US-010: Remaining 5 repositories (financials, fundamentals, competitors, institutions, insiders)

**Description:** As a backend engineer, I want repositories for the remaining 5 domains, each following the BaseRepository pattern with TTLs from spec §2.

**Acceptance Criteria:**
- [ ] `app/repositories/financials_repo.py`: `get_latest(ticker)`, `get_range(ticker, from, to)`, `append(financials)` — 1h TTL on latest
- [ ] `app/repositories/fundamentals_repo.py`: `get(ticker)`, `get_at(ticker, ts)` (queries history table for SCD-2), `upsert(fundamentals)` — 5min TTL on current; trigger handles history snapshot on UPDATE
- [ ] `app/repositories/competitors_repo.py`: `get_top(ticker, n)`, `upsert_batch(ticker, competitors)` — 24h TTL
- [ ] `app/repositories/institutions_repo.py`: `get_top(ticker, n, as_of=None)`, `append_batch(holders)` — 6h TTL on top-N
- [ ] `app/repositories/insiders_repo.py`: `get_recent(ticker, days)`, `append(txn)` (idempotent via UNIQUE) — 15min TTL
- [ ] All return Pydantic models
- [ ] Each repo has a unit test file under `tests/repositories/`
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `pytest tests/repositories/ -v` exits 0; each repo's tests cover get/upsert(or append)/cache invalidation
- Fundamentals SCD test: insert v1, update to v2, call `get_at(ticker, v1_timestamp)` returns v1 data
- `python3 -c "from app.repositories import financials_repo, fundamentals_repo, competitors_repo, institutions_repo, insiders_repo; print('ok')"` exits 0
- `mypy app/repositories/` exits 0

---

### US-011: CompanyService.get_full_profile() with parallel fan-out + on-demand backfill (OQ-3)

**Description:** As a backend engineer, I want a service-layer aggregator that fetches all 6 domains in parallel via `ThreadPoolExecutor`, returns a single `CompanyProfile`, and **synchronously backfills missing domains from upstream (Polygon/EDGAR) on cache+DB miss**, guarded by a per-(ticker, domain) Redis mutex to prevent thundering herd (OQ-3 Option B).

**Acceptance Criteria:**
- [ ] `app/services/company_service.py` defines `CompanyService.get_full_profile(ticker: str) -> CompanyProfile`
- [ ] Uses `concurrent.futures.ThreadPoolExecutor(max_workers=6)` to parallelize the 6 repo calls
- [ ] Each repo call wrapped in try/except — failure of one domain does not fail the whole profile (returns `None` for that field, sets `partial=True` flag in response)
- [ ] **On-demand backfill**: when a repo call returns `None` (cache + DB miss), the service attempts a synchronous fetch from the corresponding upstream client (Polygon for fundamentals/competitors/financials, EDGAR for institutions/insiders), persists via `upsert`/`append`, and returns the freshly-fetched data
- [ ] **Per-(ticker, domain) mutex** via Redis SETNX with 30s TTL: key format `lock:company:{ticker}:{domain}`. If lock is held, wait up to 5s polling for the lock holder's result in Redis; if still empty, return `None` for that domain and set `partial=True`. Prevents N concurrent users from triggering N upstream fetches for the same cold ticker.
- [ ] Mutex always released in a `finally` block (even on exception) to prevent deadlocks
- [ ] `app/models/company_profile.py` defines Pydantic `CompanyProfile` aggregate (company, fundamentals, latest_financials, competitors, top_institutions, recent_insiders, partial: bool, fetched_at: datetime)
- [ ] On total cache hit (all 6 keys present), latency <50ms p99 measured locally
- [ ] On cold ticker (full backfill needed), latency <5s p99 (bounded by upstream API + mutex wait)
- [ ] **Repository interfaces written so future async migration is mechanical** (return Pydantic models, no Session leakage, methods could be `async def` with same signature) — see Tech Considerations §7
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `pytest tests/services/test_company_service.py -v` exits 0 covering:
  (a) all 6 fields populated when data exists in cache
  (b) graceful degradation when one repo raises and upstream also fails (`partial=True`)
  (c) parallel execution: mock each repo with 100ms sleep — total time <200ms (proves not serial)
  (d) on-demand backfill: with empty DB, mock upstream to return AAPL competitors → service returns competitors AND `psql -c "SELECT count(*) FROM company_competitors WHERE ticker='AAPL'"` returns ≥1 after the call
  (e) mutex behavior: spawn 5 concurrent threads calling `get_full_profile('XYZ')` against an empty cache+DB, mock upstream with a 1s sleep — assert upstream was called exactly once (not 5 times), and at least one caller saw the populated result
- `python3 -c "from app.services.company_service import CompanyService; from app.models.company_profile import CompanyProfile; print(CompanyProfile.model_fields.keys())"` exits 0 and includes all 6 domain fields plus `partial` and `fetched_at`
- `mypy app/services/company_service.py app/models/company_profile.py` exits 0

---

### US-012: GET /api/company/<ticker>/profile route

**Description:** As a frontend engineer, I want a single endpoint that returns the full company profile so the Company panel doesn't need to compose 6 separate calls.

**Acceptance Criteria:**
- [ ] New blueprint `app/routes/company.py` exposes `GET /api/company/<ticker>/profile`
- [ ] Calls `CompanyService.get_full_profile(ticker)` and returns its JSON
- [ ] Returns 404 if `companies` table has no row for ticker AND no on-demand fetch succeeds
- [ ] Same auth/tier-gating decorators as existing `/api/market/<symbol>/details` route
- [ ] Blueprint registered in `app/__init__.py`
- [ ] Response includes `Cache-Control: private, max-age=60` header
- [ ] Typecheck passes
- [ ] **Browser verification**: open Company panel for AAPL on `/terminal`, confirm panel renders with data from new endpoint (use DevTools Network tab to verify `/api/company/AAPL/profile` is called)

**Test Strategy:** browser

**Test Assertions:**
- `curl -s http://localhost:8000/api/company/AAPL/profile -H "Authorization: Bearer $TOKEN" | jq '.company.ticker'` outputs `"AAPL"`
- Response JSON has top-level keys: `company`, `fundamentals`, `latest_financials`, `competitors`, `top_institutions`, `recent_insiders`, `partial`, `fetched_at`
- 404 path: `curl -sw "%{http_code}" http://localhost:8000/api/company/ZZZZZ/profile` outputs `404`
- Playwright: navigate to `/terminal` as a Max user, click an AAPL ticker badge, verify Company panel mounts and `Network` shows `/api/company/AAPL/profile` 200
- `mypy app/routes/company.py` exits 0

---

### US-013: Refactor existing /api/market/<symbol>/* routes to use new repositories

**Description:** As a backend engineer, I want the 6 existing `/api/market/<symbol>/*` routes to read from the new normalized tables (via repositories) instead of `company_data_cache` JSON, so we have a single source of truth.

**Acceptance Criteria:**
- [ ] `app/routes/market.py` routes (`/details`, `/financials`, `/competitors`, `/institutions`, `/insiders`) refactored to call the corresponding repository
- [ ] On cache + DB miss, route triggers an on-demand Polygon/EDGAR fetch, persists result via repo's `upsert`/`append`, then returns
- [ ] `app/services/cache_manager.py` (`CompanyCache` class) marked `@deprecated`; existing `company_data_cache` table is **dual-written** (old class continues to fire) for the soak period
- [ ] Response shape backward compatible — existing terminal panels keep working without frontend changes
- [ ] Typecheck passes
- [ ] **Browser verification**: existing Company panel still works (Fundamentals, Financials, Competitors, Institutions, Insiders tabs all render)

**Test Strategy:** browser

**Test Assertions:**
- `curl -s http://localhost:8000/api/market/AAPL/details -H "Authorization: Bearer $TOKEN" | jq '.ticker'` outputs `"AAPL"` and shape matches pre-refactor response (snapshot diff)
- All 5 routes return 200 with non-empty payloads for AAPL
- Playwright: navigate to `/terminal`, click AAPL ticker badge, click through all 5 tabs (Fundamentals, Financials, Competitors, Institutions, Insiders), verify each renders without errors
- DB verification: after a route hit for a previously-unknown ticker, `psql -c "SELECT count(*) FROM companies WHERE ticker='<new_ticker>'"` returns 1
- `mypy app/routes/market.py` exits 0

---

### US-014: Backfill script — migrate company_data_cache JSON → normalized tables

**Description:** As a backend engineer, I want a one-shot CLI script that reads existing `company_data_cache` rows and writes them into the new normalized tables, so we don't lose the cache we've already paid to populate.

**Acceptance Criteria:**
- [ ] `scripts/backfill_company_data.py` — reads all `company_data_cache` rows, parses the JSON `data` column by `data_type`, writes to the appropriate normalized table via the new repositories
- [ ] Idempotent — re-running on the same data is a no-op (UPSERT semantics)
- [ ] `--dry-run` flag prints planned writes without committing
- [ ] `--data-type` flag scopes to one type (details, financials, etc.) for incremental backfill
- [ ] Logs progress every 100 rows; reports final counts (succeeded, failed, skipped) per data_type
- [ ] Failed parses do not abort the run — logged to `ralph/test_results/US-014/attempt-N/failures.log`
- [ ] Typecheck passes

**Test Strategy:** cli

**Test Assertions:**
- `python3 scripts/backfill_company_data.py --dry-run` exits 0 and prints planned write counts
- After actual run on a populated `company_data_cache`: `psql -c "SELECT count(*) FROM companies"` ≥ count of unique symbols in cache with `data_type='details'`
- Idempotency: running twice in a row → second run reports 0 new inserts
- `python3 scripts/backfill_company_data.py --data-type=financials` only touches `company_financials` table
- `mypy scripts/backfill_company_data.py` exits 0

---

### US-015: Scheduled ingestion — EDGAR pollers (10-Q/10-K, 13F, Form 4) (OQ-2)

**Description:** As a backend engineer, I want APScheduler jobs that periodically poll SEC EDGAR for new filings and write them to the normalized tables, so company data refreshes without depending on user requests. 13F polling uses **hardcoded filing windows** (Feb/May/Aug/Nov, the months following each quarter's 45-day filing deadline), with a **monthly SEC calendar probe** at the start of each filing month to discover the actual deadline and adjust if it shifted (OQ-2 resolution).

**Acceptance Criteria:**
- [ ] `app/ingestion/edgar_ingester.py` defines:
  - `ingest_10q_10k(tickers: list[str])` — fetches latest 10-Q/10-K, writes rows to `company_financials` (idempotent via PK)
  - `ingest_13f(tickers: list[str])` — fetches latest 13F snapshots, writes to `institutional_holders` (idempotent via UNIQUE)
  - `ingest_form4(tickers: list[str])` — fetches recent Form 4s, writes to `insider_transactions` (idempotent via UNIQUE)
- [ ] APScheduler jobs registered in `app/worker.py`:
  - `edgar_10q_10k`: daily at 02:00 UTC
  - `edgar_form4`: every 30 minutes
  - `edgar_13f_baseline`: daily at 03:00 UTC (always-on baseline)
  - `edgar_13f_intensive`: hourly, **but the job body is a no-op outside the active filing window**. The filing window is computed each run from `app/ingestion/edgar_calendar.py` (see below).
  - `edgar_13f_calendar_probe`: runs at 00:05 UTC on the **1st of Feb/May/Aug/Nov**. Calls SEC's filing calendar/EDGAR full-text search to discover the official 13F deadline for the just-ended quarter. If found, persists `(quarter, deadline_date)` to a small `ingestion_calendar` config table (or Redis key `edgar:13f:deadline:{YYYY-Q}`). If the call fails, falls back to the hardcoded default (45 days after quarter end).
- [ ] `app/ingestion/edgar_calendar.py` — pure function `get_active_13f_window(now: datetime) -> tuple[date, date] | None`. Reads the persisted deadline if present, otherwise computes from hardcoded rule. Returns the 14-day window `[deadline - 14d, deadline + 1d]` or `None` if outside any window. Used by `edgar_13f_intensive` to gate work.
- [ ] Job scope: tickers present in `companies` table where `delisted_at IS NULL` (no full-universe scan, no delisted tickers)
- [ ] Each job invalidates corresponding Redis cache keys after writing
- [ ] EDGAR rate limit (10 req/sec) respected — uses existing throttle in `app/services/edgar_client.py:35-36`
- [ ] Job failures logged to `app/services/audit.py` (existing audit log) with `event_type='ingestion_failure'`
- [ ] Calendar probe failures logged but do not crash the scheduler — fallback to hardcoded windows
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `python3 -c "from app.ingestion.edgar_ingester import ingest_10q_10k; ingest_10q_10k(['AAPL'])"` exits 0; `psql -c "SELECT count(*) FROM company_financials WHERE ticker='AAPL'"` ≥ 1
- Idempotency: run twice; row count unchanged after second run
- `python3 -c "from app.worker import scheduler; print([j.id for j in scheduler.get_jobs()])"` includes `edgar_10q_10k`, `edgar_13f_baseline`, `edgar_13f_intensive`, `edgar_13f_calendar_probe`, `edgar_form4`
- Calendar window logic: `python3 -c "from app.ingestion.edgar_calendar import get_active_13f_window; from datetime import datetime; print(get_active_13f_window(datetime(2026,2,10)))"` returns a date tuple; `get_active_13f_window(datetime(2026,3,10))` returns `None`
- Calendar probe override: pre-populate Redis `edgar:13f:deadline:2026-Q1` with a date 7 days from "now", call `get_active_13f_window(now)` → returns the override-derived window, not the hardcoded one
- Form 4 ingest: `python3 -c "from app.ingestion.edgar_ingester import ingest_form4; ingest_form4(['AAPL'])"` exits 0 and at least one row in `insider_transactions` for AAPL
- After ingest, Redis keys `company:AAPL:financials:latest` and `company:AAPL:insiders:30d` are absent or refreshed (proven by setting them to a sentinel before, then asserting they were deleted/replaced)
- `mypy app/ingestion/edgar_ingester.py app/ingestion/edgar_calendar.py` exits 0

---

### US-016: Scheduled ingestion — Polygon fundamentals refresh

**Description:** As a backend engineer, I want a scheduled job that refreshes `company_fundamentals` (market_cap, PE, beta, etc.) from Polygon for all tracked tickers.

**Acceptance Criteria:**
- [ ] `app/ingestion/market_data_ingester.py` defines `refresh_fundamentals(tickers: list[str])`
- [ ] Calls `PolygonClient.get_ticker_details()` per ticker, maps fields to `company_fundamentals` row, calls `fundamentals_repo.upsert()` (which fires the SCD-2 trigger)
- [ ] APScheduler job `polygon_fundamentals` runs every 15 minutes during US market hours (9:30–16:00 ET, weekdays), hourly outside
- [ ] Job scope: tickers in `companies` table where `is_active=TRUE`
- [ ] Redis key `company:{ticker}:fundamentals` invalidated after each upsert
- [ ] Polygon rate limit respected (5 req/sec on free tier — use existing throttle if present, else add)
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `python3 -c "from app.ingestion.market_data_ingester import refresh_fundamentals; refresh_fundamentals(['AAPL'])"` exits 0; `psql -c "SELECT market_cap FROM company_fundamentals WHERE ticker='AAPL'"` returns a non-null bigint
- Second run updates `updated_at` AND creates a new row in `company_fundamentals_history` (proves SCD-2 trigger fires)
- Scheduler registration: `python3 -c "from app.worker import scheduler; assert 'polygon_fundamentals' in [j.id for j in scheduler.get_jobs()]"` exits 0
- `mypy app/ingestion/market_data_ingester.py` exits 0

---

### US-017: S&P 500 initial seed + scheduled refresh for core tickers (OQ-1)

**Description:** As a backend engineer, I want to seed the `companies` table with the S&P 500 constituents up front (rate-gated so we don't blow EDGAR's 10 req/sec limit), and add a scheduled job that keeps these "core tickers" fresh on a tighter cadence than organic-growth tickers — so the most-viewed companies always have warm data, while long-tail tickers grow organically via the on-demand backfill in US-011.

**Acceptance Criteria:**
- [ ] `scripts/seed_sp500.py` — one-shot CLI script that:
  - Reads S&P 500 tickers from a checked-in static list at `data/sp500_tickers.txt` (one ticker per line, sourced from a public SEC list — checked in for reproducibility, not fetched at runtime)
  - For each ticker, runs the full ingest sequence: `companies` row UPSERT (basic details from Polygon), `ingest_10q_10k`, `refresh_fundamentals`, `ingest_13f`, `ingest_form4`, plus competitors fetch via Polygon `get_related_companies`
  - **Rate-gated** to ≤8 req/sec to EDGAR (under the 10 req/sec ceiling) and ≤4 req/sec to Polygon (under the 5 req/sec free tier ceiling). Uses a token-bucket rate limiter, not naive `sleep()`
  - **Resumable** — tracks progress in a `seed_progress` table (or `data/seed_progress.json`) so re-running after a crash skips already-completed tickers. `--reset` flag wipes progress and starts fresh
  - `--dry-run` flag lists tickers that would be processed without making API calls
  - Logs per-ticker outcome (ok / partial / failed) and a final summary
  - Estimated runtime: ~500 tickers × 6 fetches × ~150ms = ~7-10 minutes (acceptable for a one-shot)
- [ ] `data/sp500_tickers.txt` — checked into the repo with current S&P 500 constituents
- [ ] APScheduler job `core_ticker_refresh` in `app/worker.py`:
  - Runs every 4 hours
  - Iterates the same S&P 500 list, calling `refresh_fundamentals` (cheap) every run
  - Calls `ingest_form4` every run (Form 4s are event-driven and frequent for big names)
  - 10-Q/13F refresh continues to run via the existing US-015 scheduled jobs (no need to duplicate)
- [ ] Organic growth path (US-011 on-demand backfill) is unchanged and serves any ticker NOT in the S&P 500 list — no special-casing in `CompanyService`
- [ ] Audit log entry written when seed completes: `event_type='sp500_seed_complete'` with row counts
- [ ] Typecheck passes

**Test Strategy:** cli

**Test Assertions:**
- `python3 scripts/seed_sp500.py --dry-run` exits 0 and prints ≥500 ticker symbols
- After actual run on a fresh DB: `psql -c "SELECT count(*) FROM companies"` ≥ 500; `psql -c "SELECT count(DISTINCT ticker) FROM company_fundamentals"` ≥ 400 (some tickers may legitimately have no Polygon coverage)
- Resumability: kill the script mid-run (after ~50 tickers), re-run without `--reset` → output reports "skipping N already-processed tickers" and resumes
- `--reset`: re-run with `--reset` → starts from ticker #1 again
- Rate limit: instrument the script with a counter — observed EDGAR request rate stays ≤8 req/sec across the full run (assert via log analysis in `ralph/test_results/US-017/attempt-N/rate.log`)
- Scheduler registration: `python3 -c "from app.worker import scheduler; assert 'core_ticker_refresh' in [j.id for j in scheduler.get_jobs()]"` exits 0
- `wc -l data/sp500_tickers.txt` outputs a count between 500 and 510 (S&P 500 occasionally has 503-505 due to dual-class shares)
- `mypy scripts/seed_sp500.py` exits 0

---

### US-018: Drop deprecated company_data_cache (after 7-day soak)

**Description:** As a backend engineer, I want to remove the deprecated `company_data_cache` table and `CompanyCache` class once we've verified the new system is stable for 7 days, so we don't carry dead weight.

**Acceptance Criteria:**
- [ ] **Pre-condition gate**: a manual check in `implementation_notes` confirms (a) US-013 deployed ≥ 7 days ago, (b) zero `company_data_cache` reads in the last 7 days (verified via audit log or grep on production logs), (c) all 5 market routes serving from new tables
- [ ] New Alembic revision `020_drop_company_data_cache.py` drops the table
- [ ] `app/services/cache_manager.py` `CompanyCache` class deleted
- [ ] All call sites of `CompanyCache` removed (should be zero by this point)
- [ ] Migration reversible (re-creates empty table on downgrade)
- [ ] Typecheck passes
- [ ] **Browser verification**: terminal Company panel still works after deploy

**Test Strategy:** browser

**Test Assertions:**
- `alembic upgrade head` exits 0; `psql -c "\d company_data_cache"` errors with "did not find any relation"
- `grep -r "CompanyCache" app/ scripts/ --include="*.py"` returns zero results (excluding the migration itself)
- Playwright: open Company panel for AAPL on `/terminal`, verify all 5 tabs render
- All existing `tests/` pass: `pytest tests/ -v` exits 0
- `mypy app/` exits 0

---

## 4. Functional Requirements

- **FR-1**: System must store company master data (ticker, name, sector, etc.) in a normalized `companies` table with `ticker` as primary key.
- **FR-2**: System must store quarterly/annual financial statements append-only in `company_financials`, keyed by `(ticker, period_end, period_type)`, so historical filings are preserved indefinitely for backtesting.
- **FR-3**: System must store frequently-changing fundamentals (market_cap, PE, beta) in `company_fundamentals` (current view) AND snapshot the prior value to `company_fundamentals_history` on every UPDATE via a Postgres trigger, so point-in-time queries are supported.
- **FR-4**: System must store competitor relationships in `company_competitors` with similarity scores, supporting top-N reads sorted by score.
- **FR-5**: System must store 13F institutional holdings as quarterly snapshots in `institutional_holders`, deduplicated by `(ticker, institution_cik, report_date)`.
- **FR-6**: System must store Form 4 insider transactions in `insider_transactions`, deduplicated by `(ticker, insider_name, transaction_date, transaction_type, shares, form_type)`.
- **FR-7**: System must cache all six domains in Redis with TTLs from spec §2, with cache-aside pattern in repositories.
- **FR-8**: System must expose `GET /api/company/<ticker>/profile` returning all six domains in a single response, with parallel fan-out (≤50ms p99 on cache hit).
- **FR-9**: System must refresh fundamentals from Polygon every 15 minutes during US market hours via a scheduled job.
- **FR-10**: System must poll EDGAR for new 10-Q/10-K (daily), 13F (hourly in season), and Form 4 (every 30 min) filings via scheduled jobs.
- **FR-11**: System must remain backward compatible — existing `/api/market/<symbol>/*` routes continue to serve the terminal Company panel without frontend changes.
- **FR-12**: System must backfill the existing `company_data_cache` JSON blobs into the new normalized tables before the old table is dropped.
- **FR-13**: Repository interfaces must be designed so a future sync→async migration is mechanical (return Pydantic models, no SQLAlchemy Session leakage to callers, methods convertible to `async def` without signature changes).
- **FR-14**: `companies` table must include a nullable `delisted_at` timestamp so delisted tickers are retained for historical queries but excluded from active scheduled jobs.
- **FR-15**: `CompanyService.get_full_profile()` must perform synchronous on-demand backfill of any missing domain from upstream (Polygon/EDGAR), guarded by a per-(ticker, domain) Redis mutex (SETNX, 30s TTL) to prevent thundering-herd duplicate fetches.
- **FR-16**: System must support both seeded ingestion (S&P 500 baseline via `scripts/seed_sp500.py` and `core_ticker_refresh` scheduled job) AND organic-growth ingestion (on-demand backfill in FR-15) — no special-case branches in the read-path service code.
- **FR-17**: 13F polling must be window-aware: hardcoded windows derived from the SEC 45-day deadline (Feb/May/Aug/Nov), with a monthly calendar-probe job that overrides the hardcoded date if SEC publishes a different deadline.

---

## 5. Non-Goals (Out of Scope)

- **Full async migration of the Flask app** — see Tech Considerations §7. New repositories are written sync but with clean interfaces for future conversion.
- **New ML models** for competitor similarity. The `company_competitors` table is provisioned, but the embedding-based competitor builder (`competitor_builder.py` in spec §3) is deferred. Competitors will be sourced from Polygon's `get_related_companies` endpoint initially.
- **Frontend redesign** — Company panel UI does not change. The new `/api/company/<ticker>/profile` endpoint is available but the terminal continues using the existing 6 routes (US-013 just rewires their backend).
- **Multi-currency / FX normalization** — financials are stored in their reported currency; conversion is left to the read layer if/when needed.
- **Historical price data** (OHLCV) — out of scope; that's a separate concern handled by Polygon snapshot endpoints.
- **News integration** — `news` table is unrelated and untouched.
- **Removing in-process L1 cache** in `PolygonClient` and `EdgarClient` — leave as-is; they protect against burst traffic to upstream APIs and are independent of the new Redis layer.

---

## 6. Design Considerations

- **Type-2 SCD for fundamentals (Q6 resolution)**: Current row in `company_fundamentals` (PK = ticker, fast lookup). Postgres BEFORE UPDATE trigger snapshots the OLD row to `company_fundamentals_history` with `valid_from = OLD.updated_at`, `valid_to = NOW()`. History queries hit the history table; the linked timestamps form a complete chain. No application code needs to remember to snapshot.
- **Append-only seasonal data**: financials, institutional holders, insider transactions all use composite/unique keys that include a date column. Re-ingestion is idempotent via UNIQUE constraints, eliminating ingestion-side dedup logic.
- **Cache key convention**: `company:{ticker}:{domain}` — flat, predictable, easy to invalidate by domain. Centralized in `app/cache/cache_keys.py` so future renames don't require grep-and-pray.
- **Graceful partial profile**: `CompanyProfile.partial: bool` flag lets the frontend render what it has even if 1-2 domains fail upstream, instead of showing a blank panel.
- **Repository interface design for future async**: All repo methods take primitives (str, int, datetime) and return Pydantic models. No SQLAlchemy Session, Query, or Result objects leak to callers. Internal queries use SQLAlchemy 2.0's `select()` API which is identical between sync and async sessions. Future migration is `def → async def` + `await` insertion at I/O calls.

---

## 7. Technical Considerations

- **Sync vs. Async (resolved as Option A)**: Full async migration of Flask is 2-4 weeks of high-risk surgery on auth, billing, and Stripe webhook paths. We stay sync now, use `ThreadPoolExecutor(max_workers=6)` for parallel fan-out in `CompanyService.get_full_profile()`. Functionally equivalent to `asyncio.gather()` for I/O-bound work. **Future migration burden**: ~3-5 days for the company stack alone, *if* we follow FR-13 (clean repo interfaces). Repos use SQLAlchemy 2.0's `select()` API which is identical between sync and async sessions; `redis-py` ships matched sync/async clients.
- **Redis client**: `redis-py` (sync) for now. The async client is the same package — `redis.asyncio.Redis` — so a future swap is one import change.
- **Connection pooling**: Redis `max_connections=50`, Postgres pool reused from existing `app/database.py` config.
- **CDK changes**: ElastiCache `cache.t4g.micro` is ~$11/mo; deploy to same VPC as ECS; security group restricts to ECS task SG. Rotate `REDIS_URL` via existing AWS Secrets Manager pattern (project memory: stripe_setup.md).
- **Migration ordering**: US-002→US-003→US-004→US-005→US-006→US-007 (foreign keys depend on `companies`).
- **Backfill safety**: US-014 must run AFTER US-009-US-010 so repos exist; runs as a one-shot script, not a recurring job. Keep `--dry-run` outputs in `ralph/test_results/US-014/attempt-N/` for review.
- **Trigger management**: SCD-2 trigger is created in US-004 migration; if dropped accidentally, run `alembic downgrade -1 && alembic upgrade head` to recreate.
- **No breaking API changes**: US-013 keeps response shapes identical to existing `/api/market/<symbol>/*` routes. Frontend doesn't move.

---

## 8. Success Metrics

- **M1 (correctness)**: `pytest tests/repositories/ tests/services/ -v` passes 100%; `mypy app/` clean.
- **M2 (latency)**: `GET /api/company/AAPL/profile` returns in <50ms p99 on Redis cache hit, <500ms p99 on cold (DB only).
- **M3 (cache hit rate)**: After 24h of production traffic, Redis cache hit rate ≥80% on `company:*:*` keys.
- **M4 (data freshness)**: Newly-filed Form 4s appear in `insider_transactions` within 60 minutes; new 13Fs within 24h; new 10-Qs within 24h.
- **M5 (storage)**: After backfill, `companies` table has ≥1 row per unique ticker in `company_data_cache` with `data_type='details'`. Zero data loss.
- **M6 (regression)**: All routes in `mandatory Playwright tests` (CLAUDE.md §Mandatory Playwright Tests) still pass — Company panel for stock/futures/currency renders correctly.
- **M7 (deprecation)**: `company_data_cache` table dropped 7 days after US-013 ships, with zero application errors.

---

## 9. Resolutions (formerly Open Questions)

All five open questions resolved 2026-04-17. Captured here for traceability.

- **OQ-1 — Seeding strategy → Hybrid**: S&P 500 tickers seeded up front via `scripts/seed_sp500.py` with token-bucket rate limiting (≤8 req/sec EDGAR, ≤4 req/sec Polygon). These "core tickers" get a tighter scheduled-refresh cadence (`core_ticker_refresh` every 4h). All other tickers grow organically via on-demand backfill (OQ-3). Implemented in **US-017**.
- **OQ-2 — 13F polling → Hardcoded windows + monthly SEC calendar probe**: Default to hardcoded 14-day filing windows (Feb/May/Aug/Nov, derived from the SEC 45-day deadline). At 00:05 UTC on the 1st of each filing month, `edgar_13f_calendar_probe` queries SEC for the actual deadline and overrides the hardcoded date if found. Calendar probe failure falls back to hardcoded. Implemented in **US-015** (FR-17).
- **OQ-3 — On-demand backfill → Option B with mutex**: `CompanyService.get_full_profile()` synchronously fetches missing domains from upstream on cache+DB miss. A per-(ticker, domain) Redis mutex (`lock:company:{ticker}:{domain}`, SETNX, 30s TTL) prevents thundering-herd duplicate fetches when multiple users hit the same cold ticker concurrently. Cold-read latency budget: <5s p99. Implemented in **US-011** (FR-15).
- **OQ-4 — Competitor source → Polygon `get_related_companies`**: Embedding-based competitor builder explicitly deferred to a follow-up PRD. Initial similarity scores come from Polygon's related-companies endpoint, with `source='polygon'` recorded in `company_competitors`.
- **OQ-5 — Delisting → Add `delisted_at` now**: `companies` table includes nullable `delisted_at TIMESTAMP` plus a partial index for fast active-ticker scans. All scheduled jobs filter `WHERE delisted_at IS NULL`. Implemented in **US-002** (FR-14).

---

## File Locations Referenced

| Concern | Path |
|---|---|
| Existing JSON-blob cache table | `migrations/versions/012_add_company_data_cache.py` |
| Existing market routes | `app/routes/market.py` (lines 24-186) |
| Polygon client | `app/services/market_data.py` (lines 42-521) |
| EDGAR client | `app/services/edgar_client.py` |
| Existing L2 cache wrapper | `app/services/cache_manager.py` (lines 33-143) |
| App factory + scheduler registration | `app/__init__.py` (lines 121-142) |
| Worker | `app/worker.py` |
| DB config | `app/config.py` (lines 25-38) |
| ORM base | `app/database.py` |
| ORM models | `app/models.py` |
| CDK | `infra/` |
| Compose | `docker-compose.yml`, `docker-compose.override.yml` |
