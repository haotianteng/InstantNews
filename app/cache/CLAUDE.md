# app/cache/

Redis client + cache helpers for the company-info layer.

## Patterns

- `get_redis()` is a process-wide lazy singleton. **Do not** construct `redis.Redis` directly in repos — always go through this module so the connection pool is shared.
- `decode_responses=False`. Callers own serialization. Pass `bytes`/bytes-like in, expect `bytes` or `None` back. Downstream repo code should `json.dumps(...).encode()` on write and `json.loads(value)` on read.
- `reset_redis_client()` is a test-only helper. Production code must never call it.
- URL resolution order: `Config.REDIS_URL` → `os.environ["REDIS_URL"]` → `redis://localhost:6379/0`. The `Config` import is wrapped in try/except so tooling scripts that run before `create_app()` still work.

## Related

- `/health` endpoint (`app/routes/health.py`) pings the singleton — any changes here should preserve a `.ping()`-compatible surface.
- `BaseRepository` (`app/repositories/base.py`) uses `get_redis()` for cache-aside. All Redis calls there are wrapped in try/except + log + fallthrough to DB — Redis is non-critical.
- `cache_keys.py` is the single source of truth for key namespacing AND per-domain TTLs (`TTL` dict). Repo modules import from here; do not hard-code key strings or TTL seconds anywhere else.
- Ticker normalization: every key builder uppercases the ticker argument. Callers can pass any casing and get the canonical `company:{TICKER}:...` key.
