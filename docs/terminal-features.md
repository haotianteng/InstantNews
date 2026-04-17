# Terminal Features (April 2026)

Living reference for the feature set currently shipping on the SIGNAL terminal. Update this doc whenever a new column, panel, or endpoint lands.

## 1. Ticker Column & Asset Type Icons

**Where:** `frontend/src/terminal-app.js` — `renderCell('ticker', ...)`

Each news article row shows its AI-tagged ticker with:
- **Asset class icon** (SVG from `frontend/public/assets/icons/`) indicating the instrument type
- **Ticker symbol**
- **Live price + % change** when available

### Icons

Configurable SVGs in `assets/icons/` — replace these files to rebrand:

| Asset type | File | Unicode fallback |
|---|---|---|
| `STOCK` | `stock.svg` | △ |
| `ETF` | `etf.svg` | ◇ |
| `FUTURE` | `future.svg` | ◎ |
| `CURRENCY` | `currency.svg` | ¤ |
| `CRYPTO` | `crypto.svg` | ₿ |
| `BOND` | `bond.svg` | ▬ |
| `OPTION` | `option.svg` | ⊕ |

If the SVG fails to load (e.g., 404), the Unicode glyph renders as fallback.

See `tasks/todo-instrument-icons.md` for the design backlog.

## 2. Live Prices — Polygon v3 Universal Snapshot

**Where:** `app/services/market_data.py` — `PolygonClient.get_ticker_snapshot()`

Uses Polygon's `/v3/snapshot` endpoint (Basil release) instead of the legacy `/v2/snapshot/locale/us/markets/stocks`. Benefits:
- **Extended-hours prices** for US equities (pre-market + after-hours)
- **24h futures** pricing (CL, ES, NQ, GC, etc.) during overnight sessions
- **Unified response shape** — single `results[0].session` object across all asset types
- Falls back to `previous_close` when the market is closed

Price display rule: a ticker shows the price only when `price > 0`. Invalid tickers (e.g., AI-generated "MGolf") return `None` and render a dash.

## 3. Company Profile Slide-Out Panel

**Where:** `frontend/src/terminal-app.js` — `openCompanyProfile(symbol, assetType)` + `frontend/terminal.html` `<aside class="cp-panel">`

Clicking a ticker badge opens a slide-out panel (560px, right side) — not a modal. The news table stays visible on the left; panel persists across ticker clicks so users can compare.

Tabs shown depend on `asset_type`:

| Asset type | Tabs |
|---|---|
| `STOCK` / `ETF` / `""` | Fundamentals, Financials, Competitors, Institutions, Insiders |
| `FUTURE` | Overview (contract specs from `FUTURES_CONTRACTS` table + live price) |
| `CURRENCY` | Overview (forex rate — requires Polygon forex plan, otherwise graceful error) |

The futures contract registry (`FUTURES_CONTRACTS` in `terminal-app.js`) covers ~10 common contracts (CL, NG, GC, SI, ES, NQ, YM, ZB, ZC, ZW, HG). Unknown futures symbols degrade to a generic "Futures Contract" layout.

## 4. Two-Tier Company Data Cache

**Where:** `app/services/cache_manager.py`, `app/models.py::CompanyDataCache`, migration `012`

Company dimension data (details, financials, earnings, competitors, 13F, 13D/G, Form 4) is cached in:

1. **L1 (in-memory)** — per-process `_CacheEntry` dicts in `PolygonClient`/`EdgarClient`. Fast path, lost on restart.
2. **L2 (PostgreSQL)** — `company_data_cache` table. Shared across workers, persists across restarts.

TTL per `data_type`:

| data_type | DB TTL | L1 TTL |
|---|---|---|
| `details` | 7d | 1h |
| `financials` | 6h | 1h |
| `earnings` | 6h | 1h |
| `competitors` | 12h | 1h |
| `institutional` | 24h | 24h |
| `positions` (13D/G) | 6h | 6h |
| `insiders` (Form 4) | 2h | 1h |
| snapshots (live price) | not cached in DB | 5s |

### Proactive warm-up

After the AI analysis pipeline in `app/services/feed_refresh.py` tags new articles with `target_asset`, a daemon thread pre-fetches `details` + `financials` for those symbols. By the time a user clicks the ticker, the cache is warm.

## 5. Pro-Tier Column Locks

**Where:** `frontend/src/terminal-app.js` — `COLUMN_DEFS`, `isColumnLocked()`, `showMaxUpgradePrompt()`

Columns have a `requiredFeature` (from the tier config). If the user's tier lacks the feature:
- Column toggle in the settings panel shows a lock icon + **MAX** badge
- Clicking the locked row opens the "Upgrade to Max" modal with a `/pricing` CTA

Free tier can't access the terminal at all (redirected to the Upgrade gate). Pro users see all columns except `ticker`, `confidence`, `risk_level` — those are Max-only.

## 6. Stripe Custom Checkout Sidebar

**Where:** `frontend/src/checkout.js`, `app/billing/stripe_client.py`

Uses Stripe's Custom Checkout (`ui_mode: "elements"`) with Payment Element mounted in a sidebar:
- JS SDK: `https://js.stripe.com/basil/stripe.js` (Basil release required for `initCheckoutElementsSdk`)
- Calls `stripe.initCheckoutElementsSdk({ fetchClientSecret })` — **not** the legacy `initEmbeddedCheckout`
- Plan summary (name, price, trial) shown above the Payment Element
- Cancel button + ESC + backdrop click all close the panel

Test accounts (`is_test_account=True`) bypass Stripe entirely: the sidebar shows "Upgraded to MAX — Test account, no billing required" and updates the user's tier directly.

## 7. Downgrade Flow with `pending_tier`

**Where:** `app/billing/routes.py::downgrade()`, migration `013`

`Subscription.pending_tier` tracks a scheduled plan change. The flow:

1. User clicks downgrade → frontend calls `POST /api/billing/downgrade` with the target tier.
2. Backend calls `stripe.Subscription.modify()` with `proration_behavior="none"` and `billing_cycle_anchor="unchanged"`. For `free`, uses `cancel_at_period_end=True`.
3. `subscription.pending_tier` is set; **user tier is not changed yet** — they keep current features until the billing period ends.
4. Account page shows a yellow "Pending plan change" banner via `subscription.to_dict()` → `pending_downgrade` + `downgrade_date`.
5. Any attempt to checkout/downgrade again is blocked with `409` while `pending_tier` is set.
6. Stripe webhook `customer.subscription.updated` clears `pending_tier` when the actual tier change takes effect.

Admin/superadmin accounts without a Stripe subscription bypass Stripe and downgrade immediately (same as test accounts).

## 8. Admin Cache Inspection API

**Where:** `app/admin/routes.py`

Read-only endpoints for production DB inspection (requires admin role, admin ALB via VPN):

```
GET /admin/api/cache/stats
  → total_rows, unique_symbols, by_data_type breakdown, recent entries

GET /admin/api/cache/<symbol>
  → all cached data_types for one symbol (includes full payloads)

GET /admin/api/cache/<symbol>/<data_type>
  → single cached entry with full JSON payload
```

Uses the read replica (`_get_read_db()`). No write paths, no destructive operations.

## 9. Rate Limit

Market endpoints: **600 per minute per user** (raised from 60 to handle price polling for 35+ tickers at 10s intervals). All other endpoints use per-tier limits from `app/billing/tiers.py`.

## 10. Auth Race Fix

**Where:** `frontend/src/terminal-app.js::fetchTier()`

On page load, `fetchNews()` fires immediately (before Firebase auth resolves) and gets anonymous data — no sentiment, no tickers. After auth completes, `fetchTier()` re-fetches news with the auth token so tier-gated fields (sentiment, ticker, reasoning) appear without waiting for the next 5s auto-refresh.

## 11. Mandatory Playwright Regression Tests

**Where:** `CLAUDE.md` — "Mandatory Playwright Tests" section

Before marking any UI/billing feature complete, implementors must run the checklist: auth flows, checkout sidebar (test + real accounts), terminal core features (company panel for stock/futures/currency), and non-regression checks (page loads, no JS errors).
