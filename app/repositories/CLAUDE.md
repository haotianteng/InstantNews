# app/repositories/

Repository layer for the company-info domain. Each concrete repo
inherits from `BaseRepository[T]` and wraps one Postgres table
(plus its Redis cache entries). Pydantic models cross the package
boundary; SQLAlchemy sessions and ORM rows stay inside.

## Patterns

- **Cache-aside is the default.** All reads go through
  `BaseRepository.cached_get` / `cached_get_list`. They return cached
  data on hit, run the caller-supplied `db_loader` on miss, and
  populate Redis on successful load. Every Redis call is wrapped in
  `try/except` that logs a warning and falls through — Redis is an
  accelerator, not a source of truth.
- **Invalidate on write.** Every write path (`upsert`, `append`,
  `append_batch`, `upsert_batch`) ends with either `self.invalidate(key)`
  for a precise single-key drop or `self.invalidate_pattern(pattern)`
  for SCAN-based scoped eviction when the exact suffix (top-N, N-days)
  isn't known. Never leave stale caches after a write.
- **Ticker normalization.** Uppercase the ticker on entry to every
  public method and reuse the upper variant for both the SQL `WHERE`
  and the cache key. Callers pass any casing; internal state is
  always canonical.
- **Sticky-negative avoidance.** `cached_get` does not cache a `None`
  return from the DB loader — an absent row shouldn't poison the cache
  for 24h. List caches DO store an empty list: "no competitors for
  AAPL" is a legitimate cacheable result.
- **Dialect-gated UPSERT.** On Postgres use
  `from sqlalchemy.dialects.postgresql import insert as pg_insert`
  with `stmt.on_conflict_do_update(constraint=..., set_=...)`. Pass
  the mapped class (e.g. `pg_insert(FinancialsORM)`) — passing
  `__table__` trips typing. For SQLite (test bootstrap), wrap
  `session.add(row)` + `session.commit()` in `try/except IntegrityError`
  and run a targeted UPDATE on rollback.
- **SCD-2 trigger vs emulation.** `fundamentals_repo.upsert` relies on
  the Postgres `fn_snapshot_fundamentals_before_update` trigger to
  write history rows on every UPDATE. Under SQLite (tests only) the
  trigger doesn't exist, so the repo manually appends a history row
  before the UPDATE — guarded by `session.bind.dialect.name !=
  "postgresql"`. Production path never executes the emulation branch.
- **Idempotent append.** `insiders_repo.append` catches `IntegrityError`
  on the dedup UNIQUE and returns `None` rather than raising — callers
  treat `None` as "already ingested". `financials_repo.append` and
  `institutions_repo.append_batch` go further: they ON CONFLICT DO
  UPDATE so re-ingest refreshes the row instead of being a no-op.

## Testing conventions

- Unit tests patch `get_redis` at `app.repositories.base.get_redis` and
  `get_session` at `app.repositories.<module>.get_session`. A
  MagicMock session is sufficient for 90% of the surface; real ORM
  row objects are simulated with MagicMocks that carry all Pydantic
  fields (Pydantic v2 with `from_attributes=True` uses `getattr`, not
  dict access).
- Tests that require the Postgres SCD-2 trigger are marked
  `@pytest.mark.integration` and `pytest.skipif(not os.environ.get(
  "INTEGRATION_TEST"), ...)`. Tester runs the full suite with
  `INTEGRATION_TEST=1 DATABASE_URL=postgresql://signal:signal@localhost:5433/signal_news REDIS_URL=redis://127.0.0.1:6379/0`.
- The `integration` marker is registered in `pyproject.toml`.

## Related

- `app/cache/` — Redis singleton + cache_keys + TTL table.
- `app/models/<domain>.py` — Pydantic schemas this repo returns.
- `app/models/__init__.py` — SQLAlchemy ORM classes this repo reads/writes.
- Future `app/services/company_service.py` (US-011) will compose these
  repos via ThreadPoolExecutor + per-(ticker, domain) Redis mutex
  (`company_lock(ticker, domain)`).
