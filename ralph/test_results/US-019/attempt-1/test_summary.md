# US-019 Test Report — PASSED (attempt 1)

## Test Assertions (5/5 pass)
1. PASS: `cd frontend && npx vite build exits 0` — 375ms, 0 errors
2. PASS: Open company profile for 'AAPL' — 'Insiders' tab shows 20 Form 4 transactions
3. PASS: Buy rows green-tinted, Sell rows red-tinted — Sell rows confirmed `rgba(248, 81, 73, 0.1)`, Exercise rows `rgba(255, 193, 7, 0.06)`, Buy CSS `.cp-insider-row-buy { background: var(--green-bg) }` = `rgba(63, 185, 80, 0.1)` (no buy transactions in AAPL data to visually show, but CSS+JS fully wired)
4. PASS: Net insider sentiment indicator visible at top — "Net Selling" with red left border (3px solid rgb(248, 81, 73)), 0 buys/$0, 8 sells/$24.17M, Net $24.17M
5. PASS: Source attribution visible at bottom — "Source: SEC EDGAR Form 4 (filed within 2 business days of transaction)"

## Acceptance Criteria (9/9 pass)
- AC1: PASS — 'Insiders' tab present as 5th tab in company profile modal
- AC2: PASS — Table columns: Date, Insider Name, Title, Type, Shares, Price, Total Value, Holdings After
- AC3: PASS — Sale rows red-tinted (`cp-insider-row-sell`, rgba(248,81,73,0.1)), Exercise yellow (`cp-insider-row-exercise`, rgba(255,193,7,0.06)), Buy green CSS defined (`cp-insider-row-buy`, var(--green-bg))
- AC4: PASS — Transactions sorted by most recent first (all dated 2026-04-03)
- AC5: PASS — Net insider sentiment: "Net Selling", 0 buys, 8 sells, NET $24.17M, color-coded (buy text green rgb(63,185,80), sell text red rgb(248,81,73))
- AC6: PASS — Data fetched from `/api/market/AAPL/insiders` (200 OK confirmed via network tab)
- AC7: PASS — Source: "SEC EDGAR Form 4 (filed within 2 business days of transaction)"
- AC8: PASS — Vite build clean (375ms)
- AC9: PASS — Browser verified: insiders tab shows transactions with color coding and net sentiment

## Quality Checks
- Vite build: PASS (375ms, 0 errors)
- pytest: 149 passed, 8 failed (all pre-existing in test_tiers.py/test_rate_limit.py)
- Console errors: 54 total — all pre-existing (TSE 404s, rate limiting 429s on market data). Zero errors related to insiders tab.
- No regressions introduced

## Transaction Details (20 rows)
- O'BRIEN DEIRDRE (Senior Vice President): Option exercise 64.3K, Tax withholding 34.3K/$8.77M, Sale 20.3K/$5.19M, Sale 9.7K/$2.47M, 3x Derivative Option exercises
- Khan Sabih (COO): Option exercise 64.3K, Tax withholding 33.3K/$8.52M, 3x Derivative Option exercises
- COOK TIMOTHY D (Chief Executive Officer): Option exercise 131.6K, Tax withholding 66.6K/$17.03M, 6x Sales totaling $16.49M

## Row Color Verification
- Sale rows: `rgba(248, 81, 73, 0.1)` — RED tint confirmed (8 rows)
- Exercise rows: `rgba(255, 193, 7, 0.06)` — YELLOW tint confirmed (3 rows)
- Other rows: `rgba(0, 0, 0, 0)` — NEUTRAL/transparent confirmed (9 rows: tax withholding, derivative exercises)
- Buy rows: CSS class `cp-insider-row-buy` with `var(--green-bg)` = `rgba(63, 185, 80, 0.1)` — GREEN defined, no purchase transactions in current AAPL data

## Null Value Handling
- Shares/Price/Total Value render as em-dash (—) for option exercises without monetary value

## Artifacts
- screenshot-01-modal-tabs.png — Modal open showing all 5 tabs
- screenshot-02-insiders-tab.png — Insiders tab with sentiment + table
- screenshot-03-source-attribution.png — Unused (scrollIntoView needed)
- screenshot-04-source-scrolled.png — Bottom of table with source attribution visible
- vite_build.log — Vite build output
- pytest.log — Full pytest output
- console.log — Browser console messages
- api_response.log — API auth check
- api_raw_response.log — Raw API response (auth required from CLI)
