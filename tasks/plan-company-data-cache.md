# Plan: Database Cache (L2) for Company Dimension Data

## Context

Company data (details, financials, competitors, SEC filings) is cached only in-memory (`_CacheEntry` dicts in `PolygonClient` and `EdgarClient`). This means data is lost on server restart, not shared across Gunicorn workers, and every cold start re-fetches from external APIs. We need a persistent L2 database cache sitting between the L1 in-memory cache and the external API calls.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Request Flow                            │
│                                                             │
│  Route handler                                              │
│       │                                                     │
│       ▼                                                     │
│  PolygonClient / EdgarClient                                │
│       │                                                     │
│       ▼                                                     │
│  L1: in-memory _CacheEntry ──hit──▶ return                  │
│       │ miss                                                │
│       ▼                                                     │
│  L2: CompanyCache.get() ──hit──▶ populate L1, return        │
│       │ miss                                                │
│       ▼                                                     │
│  External API (Polygon / EDGAR)                             │
│       │                                                     │
│       ▼                                                     │
│  CompanyCache.put() ──▶ write to DB                         │
│  populate L1 cache                                          │
│  return                                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Proactive Warm-Up (feed_refresh.py)            │
│                                                             │
│  _run_bedrock_analysis() completes                          │
│       │                                                     │
│       ▼                                                     │
│  Collect unique target_asset symbols from results           │
│       │                                                     │
│       ▼                                                     │
│  Spawn daemon thread ──▶ CompanyCache.warm(symbols,         │
│                           ["details", "financials"])         │
│       │                                                     │
│       ▼                                                     │
│  For each symbol: check DB, skip if fresh,                  │
│  else fetch from Polygon and store in DB                    │
└─────────────────────────────────────────────────────────────┘
```

## TTL Strategy

| data_type | DB (L2) TTL | L1 TTL (existing) | Rationale |
|---|---|---|---|
| `details` | 7 days | 1 hour | Near-static company info |
| `financials` | 6 hours | 1 hour | Quarterly data |
| `earnings` | 6 hours | 1 hour | Same source as financials |
| `competitors` | 12 hours | 1 hour | Relationships change slowly |
| `institutional` | 24 hours | 24 hours | Quarterly 13F filings |
| `positions` | 6 hours | 6 hours | Event-driven filings |
| `insiders` | 2 hours | 1 hour | Rolling 90-day window |
| snapshots | **not cached in DB** | 5 seconds | Too volatile |

## Key Design Decisions

**logo_url and API key**: `get_ticker_details` (line 175 of `market_data.py`) embeds the Polygon API key in `logo_url`. The DB cache must store the base URL without the API key suffix, and `PolygonClient` re-appends it when loading from L2. This avoids persisting secrets in the database.

**competitors composite data**: `get_related_companies` calls `get_ticker_details` + `get_ticker_snapshot` for each related ticker. The DB cache stores the final composite list (the snapshot prices within it will be stale-ish, but the 12h TTL is acceptable for competitor identification). The sub-calls to `get_ticker_details` will themselves hit/populate L2, so those are also covered.

**upsert strategy**: Use `session.query().filter_by(symbol, data_type).first()` then update-or-insert, with `IntegrityError` catch for concurrent writes (existing pattern in `feed_refresh.py:42`).

---

## Implementation Steps

### 1. Add `CompanyDataCache` model to `app/models.py`

Add after the `Meta` class at the end of the file:

```python
class CompanyDataCache(Base):
    __tablename__ = "company_data_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    data_type = Column(String(30), nullable=False)
    payload = Column(Text, nullable=False)             # JSON blob
    fetched_at = Column(String, nullable=False)         # ISO 8601
    ttl_seconds = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "data_type", name="uq_cache_symbol_dtype"),
        Index("idx_cache_symbol", "symbol"),
        Index("idx_cache_fetched", "fetched_at"),
    )
```

### 2. Create migration `migrations/versions/012_add_company_data_cache.py`

Follow existing pattern (see `011_own_auth_fields.py`). `revision = "012"`, `down_revision = "011"`. Create the table with all columns and constraints in `upgrade()`, drop it in `downgrade()`.

### 3. Update `migrations/env.py`

Add `CompanyDataCache` to the import on line 14:
```python
from app.models import News, Meta, CompanyDataCache  # noqa: F401
```

### 4. Create `app/services/cache_manager.py`

New file with `CompanyCache` class:

- **`DB_TTLS` dict**: maps data_type -> L2 TTL in seconds (from table above)
- **`get(symbol, data_type) -> Optional[dict | list]`**: Query DB by `(symbol, data_type)`, parse `fetched_at` + `ttl_seconds`, return deserialized JSON payload if still valid, else `None`. Uses `get_session()` from `app.database`, opens/closes session per call.
- **`put(symbol, data_type, data)`**: Upsert -- query existing row, update if exists, insert if not. Catch `IntegrityError` for races (retry with update). Serialize payload with `json.dumps`. Set `fetched_at` to current UTC ISO, `ttl_seconds` from `DB_TTLS`.
- **`invalidate(symbol, data_type=None)`**: Delete row(s). If `data_type` is None, delete all for symbol.
- **`warm(symbols, data_types)`**: For each symbol x data_type, call `get()` to check DB freshness. Return the set of `(symbol, data_type)` pairs that are stale/missing (caller is responsible for fetching those). This keeps the warm method independent of Polygon/Edgar clients.

### 5. Modify `app/services/market_data.py` -- add L2 to 4 methods

Add `db_cache: Optional["CompanyCache"] = None` parameter to `PolygonClient.__init__`, stored as `self._db_cache`.

For each of the 4 cacheable methods (`get_ticker_details`, `get_financials`, `get_earnings`, `get_related_companies`), add after the L1 miss check:

```python
# L2: database cache
if self._db_cache:
    db_hit = self._db_cache.get(symbol, "<data_type>")
    if db_hit is not None:
        # (for details: re-append API key to logo_url)
        self._<cache>[symbol] = _CacheEntry(db_hit, <TTL>)
        return db_hit
```

And after successful API fetch, before return:
```python
if self._db_cache:
    self._db_cache.put(symbol, "<data_type>", result)
```

**Special handling for `get_ticker_details`** (logo_url):
- Before `put()`: strip `?apiKey=...` from `logo_url` in the data being stored
- After `get()`: re-append `?apiKey={self._api_key}` to `logo_url`

**`get_ticker_snapshot`**: no changes -- remains L1 only.

### 6. Modify `app/services/edgar_client.py` -- add L2 to 3 methods

Add `db_cache: Optional["CompanyCache"] = None` parameter to `EdgarClient.__init__`, stored as `self._db_cache`.

Same L2 check/write pattern in:
- `get_institutional_holders` (data_type `"institutional"`)
- `get_major_position_changes` (data_type `"positions"`)
- `get_insider_transactions` (data_type `"insiders"`)

### 7. Modify `app/routes/market.py` -- wire up shared `CompanyCache`

```python
from app.services.cache_manager import CompanyCache

_cache = CompanyCache()
_polygon = PolygonClient(db_cache=_cache)
_edgar = EdgarClient(db_cache=_cache)
```

### 8. Modify `app/services/feed_refresh.py` -- proactive warm-up

After the `session.commit()` on line 206 (end of the AI results update loop), collect symbols and spawn warm-up:

```python
# Warm company data cache for newly tagged symbols
symbols_to_warm = {
    a["target_asset"] for a in results.values()
    if a and a.get("target_asset")
}
if symbols_to_warm:
    _warm_company_cache(symbols_to_warm)
```

Add helper at module level:
```python
def _warm_company_cache(symbols):
    """Background warm-up of company data cache for ticker symbols."""
    def _do_warm():
        try:
            from app.services.cache_manager import CompanyCache
            from app.services.market_data import PolygonClient
            cache = CompanyCache()
            client = PolygonClient(db_cache=cache)
            stale = cache.warm(symbols, ["details", "financials"])
            for symbol, data_type in stale:
                try:
                    if data_type == "details":
                        client.get_ticker_details(symbol)
                    elif data_type == "financials":
                        client.get_financials(symbol)
                except Exception:
                    pass  # best-effort
        except Exception as e:
            logger.warning("Cache warm-up error: %s", e)

    t = Thread(target=_do_warm, daemon=True)
    t.start()
```

---

## Files Changed Summary

| File | Action |
|---|---|
| `app/models.py` | Add `CompanyDataCache` model |
| `migrations/versions/012_add_company_data_cache.py` | **New** -- create table migration |
| `migrations/env.py` | Add `CompanyDataCache` import |
| `app/services/cache_manager.py` | **New** -- `CompanyCache` class |
| `app/services/market_data.py` | Add `db_cache` param, L2 check/write in 4 methods, logo_url handling |
| `app/services/edgar_client.py` | Add `db_cache` param, L2 check/write in 3 methods |
| `app/routes/market.py` | Instantiate `CompanyCache`, pass to both clients |
| `app/services/feed_refresh.py` | Add warm-up thread after AI analysis |

## Verification

1. Run migration: `alembic upgrade head` -- verify `company_data_cache` table exists
2. Start server, hit `GET /api/market/AAPL/details` -- should call Polygon, store row in DB
3. Restart server, hit same endpoint -- should return from DB (check logs: no Polygon call)
4. Query DB: `SELECT symbol, data_type, fetched_at FROM company_data_cache` -- verify row
5. Test all 7 data types via their respective endpoints (details, financials, competitors, institutions, insiders)
6. Trigger feed refresh -> verify warm-up creates DB rows for `details` + `financials` of tagged tickers
7. Run existing tests: `python -m pytest` -- ensure no regressions
