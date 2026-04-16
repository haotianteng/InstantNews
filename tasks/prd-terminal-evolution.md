# PRD: Terminal Evolution — Ticker Recommendations, Dynamic Columns, Market Data & Company Intelligence

## 1. Introduction/Overview

InstantNews SIGNAL terminal currently displays news in a fixed 5-column layout (Time, Sentiment, Source, Headline, Summary) with no ticker recommendation visibility and no market data integration. This PRD covers four interconnected initiatives to transform the terminal into a competitive financial intelligence platform:

1. **Database Sync** — One-time push of locally backfilled AI ticker analysis to production RDS
2. **Ticker Recommendations** — Fix the production AI pipeline and surface ticker/reasoning data in a detail modal
3. **Dynamic Column Configuration** — Full drag-and-drop column reorder, toggle, and width customization
4. **Market Data & Company Intelligence** — Real-time Polygon.io (Developer plan) integration with comprehensive company profiles (fundamentals, competitors, SEC EDGAR institutional holdings + insider trading via Form 4, 13D/13G activity alerts)

**Target:** Max-tier users get the full Bloomberg-competitor experience; Pro users get sentiment + dedup; Free users see the upgrade gate.

**Decisions (resolved from open questions):**
- **Polygon.io plan:** Developer — all endpoints except insider trading and institutional data
- **Insider trading:** Restored — powered by **SEC EDGAR Form 4** filings (filed within 2 business days, free public data)
- **Institutional holdings:** SEC EDGAR 13F filings (quarterly base) + **13D/13G real-time alerts** (filed within 10 days when >5% ownership threshold crossed)
- **SEC EDGAR User-Agent:** `dev@instnews.net` (required by SEC policy)
- **Column defaults:** First-visit onboarding prompt lets Max users choose a layout preset
- **International tickers:** Supported for major markets (LSE, TSE, HKEX) where Polygon.io has coverage. Chinese markets (SSE/SZSE) planned for future.
- **Market hours:** Per-exchange detection via extensible exchange registry. US: 9:30 AM–4:00 PM ET. Futures: "24H" badge. International exchanges: native hours.
- **13F data staleness:** Prominent date banner + 13D/13G overlay for near-real-time large position changes

## 2. Goals

- Sync ~N locally backfilled AI analyses to production DB without data loss or downtime
- Ensure every new article in production gets AI ticker analysis via the worker pipeline
- Surface ticker recommendations and reasoning in an accessible detail modal (Max tier)
- Let users fully customize their terminal column layout (drag, reorder, toggle, resize) with persistence
- Display real-time market data (price, change, volume) alongside news via Polygon.io
- Show comprehensive company profiles: fundamentals, earnings, competitors, institutional holdings (SEC EDGAR 13F + 13D/13G), insider trading (SEC EDGAR Form 4)
- All features pass local testing before any production deployment

## 3. User Stories

---

### US-001: Export Local AI Backfill Data to SQL Dump

**Description:** As a developer, I want to export all AI-analyzed article data from my local database so that I can import it into production RDS.

**Acceptance Criteria:**
- [ ] Script `scripts/export_ai_backfill.py` exports AI fields (`sentiment_score`, `sentiment_label`, `target_asset`, `asset_type`, `confidence`, `risk_level`, `tradeable`, `reasoning`, `ai_analyzed`) for all locally analyzed articles
- [ ] Export format is a SQL file with `UPDATE` statements keyed on article `link` (unique identifier)
- [ ] Script reports count of exported records
- [ ] Handles NULL values correctly in generated SQL
- [ ] Typecheck passes (`mypy scripts/export_ai_backfill.py`)

**Test Strategy:** cli

**Test Assertions:**
- `python scripts/export_ai_backfill.py --dry-run` exits 0 and prints record count
- `python scripts/export_ai_backfill.py --output /tmp/ai_backfill.sql` exits 0
- Output file `/tmp/ai_backfill.sql` exists and contains `UPDATE` statements
- `grep -c "UPDATE news" /tmp/ai_backfill.sql` returns count > 0
- `mypy scripts/export_ai_backfill.py` exits 0

---

### US-002: Import AI Backfill Data into Production RDS

**Description:** As a developer, I want to safely import the AI backfill SQL dump into production PostgreSQL so that existing articles gain ticker recommendations.

**Acceptance Criteria:**
- [ ] Script `scripts/import_ai_backfill.py` reads the SQL dump and executes against target DATABASE_URL
- [ ] Runs in a single transaction with rollback on any error
- [ ] `--dry-run` flag parses and validates SQL without executing
- [ ] Reports: matched articles updated, unmatched articles skipped, errors encountered
- [ ] Does NOT overwrite articles that already have `ai_analyzed=True` in production (skip those)
- [ ] Typecheck passes

**Test Strategy:** cli

**Test Assertions:**
- `python scripts/import_ai_backfill.py --dry-run --input /tmp/ai_backfill.sql` exits 0 and prints summary
- Dry-run output includes "matched", "skipped", "errors" counts
- `mypy scripts/import_ai_backfill.py` exits 0

**Prod Test:**
- Run `--dry-run` against production DATABASE_URL and verify counts are reasonable
- Run actual import and verify via `psql` that `ai_analyzed=True` count increased

---

### US-003: Diagnose and Fix Production AI Worker Pipeline

**Description:** As a developer, I want to verify that the production worker correctly triggers AI analysis on new articles so that ticker recommendations are generated automatically going forward.

**Acceptance Criteria:**
- [ ] Audit `app/services/feed_refresh.py` `_run_bedrock_analysis()` — confirm it's called after feed fetch
- [ ] Audit `app/worker.py` — confirm BEDROCK_ENABLED is read from environment and passed correctly
- [ ] Verify production ECS task definition includes all required AI env vars: `BEDROCK_ENABLED`, `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, `MINIMAX_MODEL_ID`, `ANTHROPIC_API_KEY`
- [ ] Add structured logging to `_run_bedrock_analysis` for: batch size, success count, failure count, elapsed time
- [ ] After deploying, verify new articles in production have `ai_analyzed=True` with populated ticker fields
- [ ] Typecheck passes

**Test Strategy:** integration

**Test Assertions:**
- `python -c "from app.services.feed_refresh import refresh_feeds_parallel; print('import ok')"` exits 0
- `grep -n "_run_bedrock_analysis" app/services/feed_refresh.py` shows the function is called in `refresh_feeds_parallel`
- `grep -n "BEDROCK_ENABLED" app/worker.py app/config.py` shows the env var is referenced
- `python -m pytest tests/ -v -k "feed or worker"` exits 0
- `mypy app/services/feed_refresh.py app/worker.py` exits 0

**Prod Test:**
- Trigger manual refresh via `POST /api/refresh` on production
- Query production DB: `SELECT COUNT(*) FROM news WHERE ai_analyzed=True AND fetched_at > NOW() - INTERVAL '5 minutes'` returns > 0

---

### US-004: Add Ticker Recommendation Fields to Terminal API Response

**Description:** As a Max-tier user, I want the `/api/news` endpoint to include all ticker recommendation fields so the terminal can display them.

**Acceptance Criteria:**
- [ ] `/api/news` response includes `target_asset`, `asset_type`, `confidence`, `risk_level`, `tradeable`, `reasoning` for Max-tier users when `ai_analyzed=True`
- [ ] Fields are stripped (not present) for Pro and Free tier users
- [ ] Empty/null ticker fields are returned as empty strings or null (not omitted) for Max users so frontend can distinguish "no recommendation" from "not analyzed"
- [ ] `ai_analyzed` boolean is included in response for all tiers (so frontend knows if analysis ran)
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python -m pytest tests/ -v -k "news"` exits 0
- `python -c "from app.models import News; n = News(title='test', link='test', source='test'); d = n.to_dict(); print('target_asset' in d or not d.get('ai_analyzed', False))"` exits 0
- `mypy app/routes/news.py app/models.py` exits 0

**Local Test:**
- Start local server, authenticate as Max-tier user, call `GET /api/news` and verify ticker fields appear
- Authenticate as Pro-tier user, verify ticker fields are absent

---

### US-005: Ticker Recommendation Detail Modal — Frontend

**Description:** As a Max-tier user, I want to click on a news item to open a detail modal showing the full ticker recommendation, reasoning, and risk assessment so I can make informed trading decisions.

**Acceptance Criteria:**
- [ ] Clicking a news row (or a dedicated "details" icon) opens a side panel / modal
- [ ] Modal displays: `target_asset` (large, prominent), `asset_type`, `sentiment_label` with score, `confidence` (as percentage), `risk_level` (color-coded: green/yellow/red), `tradeable` (YES/NO badge), `reasoning` (full text, scrollable)
- [ ] Modal includes the article headline, source, and published time for context
- [ ] Modal has a close button and closes on Escape key or clicking outside
- [ ] If `ai_analyzed=False` or no ticker data, modal shows "Analysis pending" or "No recommendation"
- [ ] Modal styling matches dark terminal theme
- [ ] Non-Max users do not see the detail icon / clicking does nothing (or shows upgrade prompt)
- [ ] Typecheck passes (if applicable to JS tooling)
- [ ] **Verify in browser** — modal opens, displays data, closes correctly

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0 (no build errors)
- Open `http://localhost:5173/terminal` in browser as Max-tier user
- Click a news row → modal opens with ticker recommendation data
- Press Escape → modal closes
- Click outside modal → modal closes
- Verify reasoning text is scrollable for long content
- As Pro-tier user, verify modal shows upgrade prompt or detail icon is hidden

---

### US-006: Dynamic Column Toggle and Visibility

**Description:** As a terminal user, I want to toggle columns on/off so I can customize which information I see.

**Acceptance Criteria:**
- [ ] Column settings panel accessible via a gear/settings icon in the terminal header
- [ ] Each column has a toggle switch (on/off)
- [ ] Available columns: Time, Sentiment, Source, Headline, Summary, Ticker, Confidence, Risk Level, Tradeable
- [ ] Headline column cannot be toggled off (always visible)
- [ ] Toggling a column immediately shows/hides it in the table
- [ ] Tier-gated columns (Sentiment for Free, Ticker/Confidence/Risk/Tradeable for non-Max) show a lock icon and cannot be enabled
- [ ] Column visibility state persists in localStorage
- [ ] **Verify in browser** — toggling columns works, persists across page reload

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open terminal in browser, click settings icon → column panel appears
- Toggle "Summary" off → column disappears from table
- Toggle "Summary" on → column reappears
- Reload page → column state is preserved
- As Free-tier user, sentiment toggle shows lock icon and is disabled

---

### US-007: Dynamic Column Drag-and-Drop Reorder

**Description:** As a terminal user, I want to drag columns to reorder them so I can arrange my terminal layout.

**Acceptance Criteria:**
- [ ] Columns in the settings panel are draggable (drag handle icon)
- [ ] Dragging a column in the settings panel reorders it in the table
- [ ] Column order persists in localStorage
- [ ] Table header and body columns stay in sync after reorder
- [ ] Reorder works correctly when some columns are hidden
- [ ] **Verify in browser** — drag reorder works, table updates live, persists across reload

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open terminal, open settings, drag "Source" column above "Time" → table column order updates
- Reload page → custom order persists
- Hide a column, reorder remaining → no visual glitches

---

### US-008: Dynamic Column Width Customization

**Description:** As a terminal user, I want to resize column widths by dragging column borders so I can allocate space to the information I care about most.

**Acceptance Criteria:**
- [ ] Column borders in the table header are draggable to resize
- [ ] Minimum column width of 60px to prevent collapsing
- [ ] Double-click column border to auto-fit to content width
- [ ] Column widths persist in localStorage
- [ ] Resizing works correctly after column reorder or toggle
- [ ] **Verify in browser** — drag to resize, double-click to auto-fit, persists across reload

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open terminal, drag "Headline" column border to make it wider → column resizes
- Double-click "Source" column border → auto-fits
- Reload page → custom widths persist

---

### US-009: Polygon.io Integration — Backend Service

**Description:** As a developer, I want a backend service that fetches real-time market data from Polygon.io so the terminal can display live prices alongside news.

**Acceptance Criteria:**
- [ ] New module `app/services/market_data.py` with `PolygonClient` class
- [ ] Supports: `get_ticker_snapshot(symbol)` — returns last price, change, change%, volume, VWAP
- [ ] Supports: `get_ticker_details(symbol)` — returns company name, sector, market cap, logo URL, description
- [ ] Implements caching (5-second TTL for snapshots, 1-hour TTL for details) to respect rate limits
- [ ] Handles Polygon.io API errors gracefully (returns None, logs warning)
- [ ] `POLYGON_API_KEY` env var required; service disabled if not set
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python -c "from app.services.market_data import PolygonClient; print('import ok')"` exits 0
- `python -m pytest tests/ -v -k "polygon or market_data"` exits 0
- `mypy app/services/market_data.py` exits 0

**Local Test:**
- With `POLYGON_API_KEY` set, call `get_ticker_snapshot("AAPL")` and verify price data returned
- Call same ticker within 5s and verify cached response (no API call logged)

---

### US-010: Market Data API Endpoint

**Description:** As a frontend developer, I want an API endpoint to fetch real-time market data for a given ticker so the terminal can display it.

**Acceptance Criteria:**
- [ ] `GET /api/market/:symbol` returns: `{ symbol, price, change, change_percent, volume, vwap, updated_at }`
- [ ] `GET /api/market/:symbol/details` returns: `{ symbol, name, sector, market_cap, logo_url, description, homepage_url }`
- [ ] Both endpoints require authentication (any tier that has terminal access)
- [ ] Returns 404 for unknown tickers with descriptive message
- [ ] Returns 503 if Polygon.io is unavailable with retry-after header
- [ ] Rate limited: 60 req/min per user for market data endpoints
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python -m pytest tests/ -v -k "market"` exits 0
- `mypy app/routes/market.py` exits 0

**Local Test:**
- `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/market/AAPL` returns price data
- `curl http://localhost:8000/api/market/AAPL` returns 401

---

### US-011: Real-Time Market Data in Terminal — Ticker Column & Price Badge

**Description:** As a Max-tier user, I want to see the ticker symbol with live price data in the terminal so I can correlate news with market movements.

**Acceptance Criteria:**
- [ ] New "Ticker" column displays `target_asset` as a clickable badge
- [ ] Badge shows: ticker symbol + last price + change% (color-coded: green positive, red negative)
- [ ] Price data fetched from `/api/market/:symbol` when ticker is present
- [ ] Batch fetch: on news load, collect unique tickers and fetch prices in parallel (max 10 concurrent)
- [ ] Prices refresh every 10 seconds for visible tickers
- [ ] If no ticker or market data unavailable, show "—"
- [ ] Only visible to Max-tier users (column locked for others)
- [ ] **Verify in browser** — ticker badges show live prices, update periodically

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open terminal as Max user → "Ticker" column shows ticker badges with prices
- Wait 10s → prices update
- Verify green/red coloring matches positive/negative change

---

### US-012: Company Profile Modal — Fundamentals Tab

**Description:** As a Max-tier user, I want to click a ticker badge to see company fundamentals so I can quickly assess the company behind the news.

**Acceptance Criteria:**
- [ ] Clicking a ticker badge opens a company profile modal
- [ ] "Fundamentals" tab displays: company name, sector, market cap (formatted), description, logo, homepage link
- [ ] Data fetched from `/api/market/:symbol/details`
- [ ] Loading state shown while fetching
- [ ] Modal matches dark terminal theme
- [ ] **Verify in browser** — click ticker → modal opens with fundamentals data

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Click "AAPL" ticker badge → company profile modal opens
- Fundamentals tab shows: Apple Inc., Technology sector, market cap, logo
- Close modal → terminal is still functional

---

### US-013: Company Profile — Earnings & Financial Ratios via Polygon.io

**Description:** As a developer, I want to fetch company financials (earnings, P/E, EPS, revenue) from Polygon.io so the company profile modal can display them.

**Acceptance Criteria:**
- [ ] `PolygonClient` extended with `get_financials(symbol)` — returns latest quarterly: revenue, net_income, EPS, P/E ratio
- [ ] `PolygonClient` extended with `get_earnings(symbol)` — returns last 4 quarters of EPS (actual vs estimate)
- [ ] 1-hour cache TTL for financial data
- [ ] `GET /api/market/:symbol/financials` endpoint added
- [ ] Returns empty/null fields gracefully if data unavailable for a ticker
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python -c "from app.services.market_data import PolygonClient; c = PolygonClient(); print(type(c.get_financials('AAPL')))"` exits 0
- `python -m pytest tests/ -v -k "financials"` exits 0
- `mypy app/services/market_data.py` exits 0

---

### US-014: Company Profile Modal — Earnings & Ratios Tab (Frontend)

**Description:** As a Max-tier user, I want to see earnings history and key financial ratios in the company profile modal.

**Acceptance Criteria:**
- [ ] "Financials" tab in company profile modal
- [ ] Displays: revenue (formatted), net income, EPS, P/E ratio
- [ ] Earnings history: last 4 quarters as a mini bar chart (actual vs estimate, beat/miss color coding)
- [ ] Data fetched from `/api/market/:symbol/financials`
- [ ] "No data available" message for tickers without financials (e.g., ETFs)
- [ ] **Verify in browser** — financials tab shows data, chart renders

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open company profile for "AAPL" → "Financials" tab shows revenue, EPS, P/E
- Earnings chart shows 4 quarters with beat/miss colors
- Open company profile for "SPY" (ETF) → shows "No data available" gracefully

---

### US-015: Company Profile — Competitor Comparison via Polygon.io

**Description:** As a developer, I want to fetch related companies/competitors from Polygon.io so users can compare across peers.

**Acceptance Criteria:**
- [ ] `PolygonClient` extended with `get_related_companies(symbol)` — returns list of related tickers
- [ ] For each related ticker, fetch snapshot (price, change%) and details (name, market_cap)
- [ ] Limit to top 5 competitors by market cap
- [ ] `GET /api/market/:symbol/competitors` endpoint added
- [ ] 1-hour cache TTL
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python -c "from app.services.market_data import PolygonClient; c = PolygonClient(); print(type(c.get_related_companies('AAPL')))"` exits 0
- `python -m pytest tests/ -v -k "competitor"` exits 0
- `mypy app/services/market_data.py` exits 0

---

### US-016: Company Profile Modal — Competitors Tab (Frontend)

**Description:** As a Max-tier user, I want to see a competitor comparison table in the company profile modal.

**Acceptance Criteria:**
- [ ] "Competitors" tab in company profile modal
- [ ] Table columns: Ticker, Company Name, Market Cap, Price, Change%, Sector
- [ ] Rows sorted by market cap descending
- [ ] Each competitor ticker is clickable (opens that company's profile)
- [ ] Data fetched from `/api/market/:symbol/competitors`
- [ ] **Verify in browser** — competitors tab shows table with clickable tickers

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open company profile for "AAPL" → "Competitors" tab shows related companies
- Click a competitor ticker → opens that company's profile modal
- Verify market caps are formatted (e.g., "$2.8T")

---

### US-017: SEC EDGAR Client — 13F, 13D/13G, and Form 4 Parser

**Description:** As a developer, I want a unified SEC EDGAR client that fetches institutional holdings (13F), large position changes (13D/13G), and insider transactions (Form 4) so the company profile modal can display comprehensive ownership data.

**Acceptance Criteria:**
- [ ] New module `app/services/edgar_client.py` with `EdgarClient` class
- [ ] `User-Agent` header set to `InstantNews dev@instnews.net` per SEC EDGAR policy
- [ ] Respects SEC EDGAR rate limit (10 req/sec) via request throttling
- [ ] **13F institutional holdings:**
  - [ ] `get_institutional_holders(symbol, limit=20)` — fetches latest 13F filings from SEC EDGAR XBRL API
  - [ ] Each holder includes: institution_name, shares_held, value, report_date, change_type (increased/decreased/new/sold)
  - [ ] Parses CIK lookup for ticker → company CUSIP/CIK mapping
  - [ ] 24-hour cache TTL (13F filings update quarterly)
- [ ] **13D/13G large position alerts:**
  - [ ] `get_major_position_changes(symbol, limit=10)` — fetches recent 13D/13G filings
  - [ ] Each entry includes: filer_name, filing_date, filing_type (13D or 13G), percent_owned, shares_held, change_description
  - [ ] 6-hour cache TTL (more timely than 13F — filed within 10 days of crossing 5% threshold)
- [ ] **Form 4 insider transactions:**
  - [ ] `get_insider_transactions(symbol, limit=20)` — fetches recent Form 4 filings
  - [ ] Each transaction includes: filing_date, insider_name, title (CEO/CFO/Director/etc.), transaction_type (buy/sell/exercise), shares, price_per_share, total_value, shares_held_after
  - [ ] 1-hour cache TTL (Form 4 filed within 2 business days of transaction)
- [ ] `GET /api/market/:symbol/institutions` endpoint (13F + 13D/13G combined)
- [ ] `GET /api/market/:symbol/insiders` endpoint (Form 4)
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python -c "from app.services.edgar_client import EdgarClient; print('import ok')"` exits 0
- `python -c "from app.services.edgar_client import EdgarClient; c = EdgarClient(); print(type(c.get_institutional_holders('AAPL')))"` exits 0
- `python -c "from app.services.edgar_client import EdgarClient; c = EdgarClient(); print(type(c.get_insider_transactions('AAPL')))"` exits 0
- `python -c "from app.services.edgar_client import EdgarClient; c = EdgarClient(); print(type(c.get_major_position_changes('AAPL')))"` exits 0
- `python -m pytest tests/ -v -k "edgar"` exits 0
- `mypy app/services/edgar_client.py` exits 0

**Local Test:**
- Call `get_institutional_holders("AAPL")` and verify list of institutions returned with report_date
- Call `get_insider_transactions("AAPL")` and verify recent Form 4 data
- Call `get_major_position_changes("AAPL")` and verify 13D/13G data (may be empty for some tickers — that's OK)
- Call same ticker within cache TTL and verify cached response (no API call logged)

---

### US-018: Company Profile Modal — Institutional Holdings Tab (Frontend)

**Description:** As a Max-tier user, I want to see top institutional holders in the company profile modal, with a clear data freshness indicator and real-time 13D/13G alerts for major position changes.

**Acceptance Criteria:**
- [ ] "Institutions" tab in company profile modal
- [ ] **Date banner at top:** "Holdings as of {report_date} (filed {filing_date})" — prominent, not subtle
- [ ] **One-time info tooltip** on first view explaining: "13F filings are reported quarterly with a 45-day lag. 13D/13G alerts below show more recent large position changes."
- [ ] **13F holdings table:**
  - [ ] Columns: Institution Name, Shares Held (formatted), Value (formatted), Change (arrow up/down/new badge)
  - [ ] Top holders sorted by value descending
  - [ ] Summary at top: total institutional ownership %, number of institutions reporting
- [ ] **13D/13G "Recent Activity" section** below the 13F table:
  - [ ] Entries tagged with "NEW" badge if filed within last 30 days
  - [ ] Shows: filer name, % owned, filing date, filing type (13D/13G)
  - [ ] Color-coded: new/increased positions green, decreased/exited red
- [ ] Note at bottom: "Source: SEC EDGAR (13F quarterly + 13D/13G real-time filings)"
- [ ] **Verify in browser** — institutions tab shows both 13F table and 13D/13G section

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open company profile for "AAPL" → "Institutions" tab shows holders
- Date banner visible at top with report date
- First-time tooltip appears and can be dismissed
- Verify formatted numbers (e.g., "1.2B shares", "$180.5B")
- 13D/13G section visible below main table (may be empty for some tickers)
- Source attribution visible at bottom

---

### US-019: Company Profile Modal — Insider Trading Tab (Frontend, SEC EDGAR Form 4)

**Description:** As a Max-tier user, I want to see recent insider trading activity sourced from SEC EDGAR Form 4 filings in the company profile modal.

**Acceptance Criteria:**
- [ ] "Insiders" tab in company profile modal (restored — now powered by EDGAR Form 4, not Polygon.io)
- [ ] Table columns: Date, Insider Name, Title, Type (Buy/Sell/Exercise color-coded), Shares, Price, Total Value, Holdings After
- [ ] Buy transactions highlighted green, Sell highlighted red, Exercise neutral/yellow
- [ ] Most recent transactions first
- [ ] **Net insider sentiment indicator** at top: net buy vs sell volume over last 90 days (e.g., "Net Buying: +125K shares" in green, or "Net Selling: -80K shares" in red)
- [ ] Data fetched from `/api/market/:symbol/insiders`
- [ ] Note at bottom: "Source: SEC EDGAR Form 4 (filed within 2 business days of transaction)"
- [ ] **Verify in browser** — insiders tab shows transactions with color coding and net sentiment

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Open company profile for "AAPL" → "Insiders" tab shows recent Form 4 transactions
- Buy rows are green-tinted, Sell rows are red-tinted
- Net insider sentiment indicator visible at top
- Source attribution visible at bottom

---

### US-020: Market Hours Indicator & International Ticker Support

**Description:** As a terminal user, I want to see whether the market is open or closed for a ticker, with per-exchange detection and support for major international exchanges and futures.

**Acceptance Criteria:**
- [ ] New `app/services/exchange_registry.py` — extensible registry of exchange hours
- [ ] **Supported exchanges (launch):**
  - [ ] US: NYSE/NASDAQ — 9:30 AM–4:00 PM ET
  - [ ] UK: LSE — 8:00 AM–4:30 PM GMT
  - [ ] Japan: TSE — 9:00 AM–3:00 PM JST (with 11:30–12:30 lunch break)
  - [ ] Hong Kong: HKEX — 9:30 AM–4:00 PM HKT (with 12:00–1:00 lunch break)
- [ ] **Future-ready:** Registry supports adding new exchanges (SSE/SZSE for Chinese markets) via config without code changes
- [ ] **Futures:** Assets with `asset_type=FUTURE` show "24H" badge instead of open/closed (with note about brief settlement breaks)
- [ ] `PolygonClient` detects exchange from ticker suffix: `.L` → LSE, `.T` → TSE, `.HK` → HKEX, no suffix → US
- [ ] `/api/market/:symbol` response includes `market_status` ("open" | "closed" | "24h"), `exchange` name, `next_open` / `next_close` timestamps
- [ ] Terminal ticker badge shows: green dot = open, gray dot = closed, blue dot = 24H futures
- [ ] Outside market hours: show last close price with "Closed" label
- [ ] Typecheck passes
- [ ] **Verify in browser** — market status indicators per exchange

**Test Strategy:** function + browser

**Test Assertions:**
- `python -c "from app.services.exchange_registry import ExchangeRegistry; r = ExchangeRegistry(); print(r.get_status('NYSE'))"` exits 0
- `python -m pytest tests/ -v -k "market_hours or exchange"` exits 0
- `mypy app/services/exchange_registry.py app/services/market_data.py` exits 0
- Open terminal outside US market hours → US ticker badges show gray dot and "Closed"
- Verify international ticker (e.g., "HSBA.L") shows LSE market status
- Verify futures ticker shows blue "24H" badge

---

### US-021: Column Onboarding — First-Visit Layout Chooser

**Description:** As a new Max-tier user, I want to choose my preferred column layout on first visit so the terminal is immediately useful.

**Acceptance Criteria:**
- [ ] On first terminal visit (no localStorage column config), show an onboarding overlay
- [ ] Offer 3 preset layouts:
  - **News Focus:** Time, Source, Headline, Summary (default widths)
  - **Trading View:** Time, Sentiment, Ticker, Headline, Confidence, Risk Level
  - **Full Terminal:** All columns enabled
- [ ] User clicks a preset → columns configured accordingly, overlay dismissed
- [ ] "Customize later" link skips onboarding with "Full Terminal" as default
- [ ] Onboarding only shows once (flag in localStorage)
- [ ] Non-Max users skip onboarding (they have fewer columns available)
- [ ] **Verify in browser** — onboarding overlay appears on first visit, presets apply correctly

**Test Strategy:** browser

**Test Assertions:**
- `cd frontend && npx vite build` exits 0
- Clear localStorage, visit terminal as Max user → onboarding overlay appears
- Click "Trading View" → columns match preset, overlay dismissed
- Reload → onboarding does NOT appear again
- Clear localStorage, visit as Pro user → onboarding does NOT appear

---

### US-022: Polygon.io API Key in Production Secrets

**Description:** As a developer, I want the Polygon.io API key stored in AWS Secrets Manager and injected into the ECS task definition so the market data service works in production.

**Acceptance Criteria:**
- [ ] `POLYGON_API_KEY` added to `instantnews/app` secret in AWS Secrets Manager
- [ ] CDK stack (`infra/stack.py`) updated to inject `POLYGON_API_KEY` from Secrets Manager into both web and worker task definitions
- [ ] `cdk diff` shows only the new secret reference (no unintended changes)
- [ ] Typecheck passes (CDK synth succeeds)

**Test Strategy:** cli

**Test Assertions:**
- `cd infra && cdk synth` exits 0
- `cd infra && cdk diff 2>&1` shows POLYGON_API_KEY in task definition changes
- `grep -r "POLYGON_API_KEY" infra/stack.py` shows the secret reference

**Prod Test:**
- After `cdk deploy`, verify via AWS Console that task definition includes `POLYGON_API_KEY`
- Call `GET /api/market/AAPL` on production and verify price data returned

---

### US-023: End-to-End Production Deployment and Validation

**Description:** As a developer, I want to deploy all changes to production and validate the complete feature set works end-to-end.

**Acceptance Criteria:**
- [ ] Frontend built with `vite build` (no errors)
- [ ] Docker image built and pushed to ECR
- [ ] `cdk deploy` succeeds with new secret references
- [ ] ECS services restarted with new task definitions
- [ ] Production terminal shows ticker badges with live prices (Max user)
- [ ] Clicking ticker opens company profile with all 5 tabs populated (Fundamentals, Financials, Competitors, Institutions, Insiders)
- [ ] Column customization (toggle, reorder, resize) works and persists
- [ ] Recommendation detail modal opens with full reasoning
- [ ] AI worker is analyzing new articles (check DB)
- [ ] No regressions: existing terminal features (search, filter, sentiment, dedup) still work

**Test Strategy:** integration

**Test Assertions:**
- Visit `https://www.instnews.net/terminal` as Max user → terminal loads
- Ticker column shows live prices → prices update after 10s
- Click ticker → company profile modal with 5 tabs (Fundamentals, Financials, Competitors, Institutions, Insiders)
- Click news row → recommendation detail modal with reasoning
- Open column settings → toggle, reorder, resize all work
- Reload → customizations persist
- Filter by sentiment → still works
- Search by keyword → still works
- As Pro user → ticker/market columns locked, recommendation modal shows upgrade prompt

---

## 4. Functional Requirements

- **FR-1:** The system must export/import AI backfill data between local SQLite and production PostgreSQL without data loss
- **FR-2:** The production worker must trigger AI analysis (MiniMax → Claude → Bedrock chain) on every new article
- **FR-3:** The `/api/news` endpoint must include ticker recommendation fields for Max-tier users
- **FR-4:** The terminal must display a detail modal with full ticker recommendation and reasoning on news item click
- **FR-5:** The terminal must support column toggle (on/off), drag-and-drop reorder, and border-drag resize
- **FR-6:** Column configuration must persist in localStorage across sessions
- **FR-7:** The system must fetch real-time market data from Polygon.io with 5-second cache for prices and 1-hour cache for fundamentals
- **FR-8:** The terminal must display live ticker prices that refresh every 10 seconds
- **FR-9:** The company profile modal must show 5 tabs: Fundamentals, Financials, Competitors, Institutions (SEC EDGAR 13F + 13D/13G), Insiders (SEC EDGAR Form 4)
- **FR-10:** All market data features must be gated to Max tier; tier-locked columns show lock icons
- **FR-11:** The Polygon.io API key must be stored in AWS Secrets Manager and injected via CDK
- **FR-12:** Terminal must show per-exchange market status: green dot (open), gray dot (closed), blue dot (24H futures)
- **FR-13:** International tickers (LSE, TSE, HKEX) must resolve to correct Polygon.io format with native market hours
- **FR-14:** New Max-tier users must see a column layout onboarding prompt on first visit with 3 presets
- **FR-15:** SEC EDGAR requests must use `User-Agent: InstantNews dev@instnews.net` and respect 10 req/sec rate limit
- **FR-16:** Institutional holdings tab must show prominent data freshness banner ("Holdings as of {date}") with 13D/13G near-real-time overlay
- **FR-17:** Insider trading tab must show Form 4 transactions with net insider sentiment indicator (90-day net buy/sell)
- **FR-18:** Exchange registry must be extensible to support future Chinese markets (SSE/SZSE) without code changes

## 5. Non-Goals (Out of Scope)

- **No real-time WebSocket streaming** — polling at 10s intervals is sufficient for this phase
- **No custom watchlists** — watchlist feature exists in tier definition but is not part of this PRD
- **No charting/graphing** — no candlestick charts, time series plots, or TradingView-style visuals
- **No portfolio tracking** — no position management, P&L tracking, or trade execution
- **No options or derivatives data** — equity-focused only
- **No historical market data endpoints** — only current/latest data
- **No mobile-responsive terminal** — desktop-first terminal experience
- **No bidirectional database sync** — one-time local-to-prod push only
- **No pre/post-market prices** — show "Market Closed" with last close instead
- **No Chinese market support yet** — SSE/SZSE planned for future via exchange registry extension

## 6. Design Considerations

- **Dark theme consistency:** All new modals, panels, and UI elements must match the existing terminal dark theme (dark backgrounds, monospace fonts, green/red for sentiment/price)
- **Modal pattern:** Use a consistent modal component for both recommendation detail and company profile. Modal should support tabs, close on Escape/outside click, and be scrollable
- **Column settings panel:** Slide-in panel from the right side (similar to filter panel), not a modal, to avoid modal-over-modal
- **Ticker badge design:** Compact badge showing `AAPL $185.23 +1.2%` with color coding. Should fit within normal table row height
- **Existing components to reuse:** Sentiment badge styling, source tag styling, filter panel layout

## 7. Technical Considerations

- **Polygon.io rate limits:** Developer plan — unlimited API calls. Still implement caching to reduce latency and be a good API citizen
- **Polygon.io endpoints used:** `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}`, `/v3/reference/tickers/{symbol}`, `/vX/reference/financials`, `/v1/related-companies/{symbol}`, `/v1/marketstatus/now`
- **SEC EDGAR endpoints:**
  - `/submissions/CIK{cik}.json` — company lookup, CIK ↔ ticker mapping
  - `/api/xbrl/companyfacts/CIK{cik}.json` — financial facts (for cross-referencing)
  - EDGAR full-text search for 13F, 13D/13G, Form 4 filings
  - Must set `User-Agent: InstantNews dev@instnews.net` per SEC policy
  - Rate limit: 10 req/sec (implement throttling in `EdgarClient`)
  - Cache TTLs: 13F = 24h, 13D/13G = 6h, Form 4 = 1h
- **International ticker mapping:** LSE uses `.L` suffix (e.g., `HSBA.L`), TSE uses `.T`, HKEX uses `.HK`. Polygon.io uses exchange-prefixed format — build mapper in `market_data.py`
- **Exchange registry:** `exchange_registry.py` stores exchange hours as config dicts. Adding SSE/SZSE later is a data-only change (no logic changes). Futures detected via `asset_type=FUTURE` from AI analysis
- **localStorage schema:** Store column config as JSON: `{ columns: [{ id, visible, width, order }] }`. Version the schema for future migrations
- **Performance:** Batch market data requests for visible tickers. Don't fetch prices for off-screen rows. Use `IntersectionObserver` if list is long
- **Cache invalidation:** Market data cache should be time-based only (no complex invalidation). 5s for prices, 1h for fundamentals/financials/insiders/institutions
- **Database:** No new tables needed for market data (all fetched live). Existing `news` table already has all AI fields
- **CDK dependency:** `infra/stack.py` needs new secret reference but no new AWS resources

## 8. Success Metrics

- **AI coverage:** >95% of new production articles have `ai_analyzed=True` within 5 minutes of fetch
- **Backfill completeness:** 100% of locally analyzed articles successfully imported to production
- **Market data latency:** Ticker price displayed within 1 second of terminal load (cache hit) or 3 seconds (cache miss)
- **Column customization adoption:** Track localStorage usage — >50% of returning Max users customize columns within first week
- **Company profile engagement:** Average time spent in company profile modal >15 seconds (indicates users find it useful)
- **Error rate:** <1% of Polygon.io API calls fail (after retries)

## 9. Open Questions (Resolved)

All open questions have been resolved:

| # | Question | Decision |
|---|----------|----------|
| 1 | Polygon.io plan | **Developer** — all endpoints except insider trading & institutional data |
| 2 | Insider trading | **Restored** — SEC EDGAR Form 4 (filed within 2 business days, free) |
| 3 | Institutional holdings | **SEC EDGAR 13F** (quarterly base) + **13D/13G** real-time alerts for >5% changes |
| 4 | Column defaults | **Onboarding prompt** — 3 presets on first visit (US-021) |
| 5 | Non-US tickers | **Supported** — LSE, TSE, HKEX via suffix mapping (US-020) |
| 6 | Market hours | **Per-exchange detection** — native hours per exchange, futures show "24H" badge (US-020) |
| 7 | SEC EDGAR User-Agent | `InstantNews dev@instnews.net` |
| 8 | International market hours | **Per-exchange** — LSE, TSE, HKEX each have native hours. Extensible registry for future Chinese markets (SSE/SZSE) |
| 9 | 13F filing lag | **Prominent date banner** + 13D/13G overlay for near-real-time large position changes + first-time explainer tooltip |

No remaining open questions.
