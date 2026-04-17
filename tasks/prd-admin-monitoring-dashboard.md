# PRD — Admin Monitoring Dashboard (Fintech)

**Status:** Draft
**Owner:** Implementor + Tester (Ralph v2 / JOJO v2 adversarial)
**Branch suggestion:** `jojo/admin-monitoring-dashboard`
**Created:** 2026-04-17

---

## 1. Introduction / Overview

InstantNews has 18 RSS + social sources, a 3-tier LLM analysis pipeline, three upstream market-data/filings/payments APIs, and ElastiCache + RDS + ECS running the stack. We can currently only observe any of this by grepping CloudWatch Logs Insights after-the-fact.

Today's latency debugging session (the ~20-min SeekingAlpha delay that turned out to be synchronous AI analysis starving the worker loop) required manual log-mining for 90 minutes to diagnose. That evidence would have been a single glance on a real dashboard.

This PRD builds an **admin-only, VPN-gated monitoring dashboard** at `https://admin.instnews.net/monitoring` that surfaces:

- **Per-source ingestion latency** (`published → fetched_at`), live and 24h rollup
- **AI pipeline health** (queue depth, batch duration, MiniMax→Claude→Bedrock fallback chain)
- **Upstream API health** (X rate-limit headroom, Polygon/EDGAR throttle, Stripe webhook latency)
- **Cost tracking** (AWS Cost Explorer + X API usage endpoint, authoritative numbers)

The dashboard is the ops control room for the system we just debugged by hand.

Metrics are emitted from the app using **CloudWatch Embedded Metrics Format (EMF)** — a structured JSON log line CloudWatch auto-extracts into metrics, no separate emit call or SDK. The dashboard reads them back via `cloudwatch:GetMetricData` and `ce:GetCostAndUsage`.

**Refresh model:**
- Live panels auto-refresh every 10 s (1-hour window).
- 24 h view: minute-resolution, 1,440 points per series.
- 7 d view: hour-resolution, 168 points per series.

**Out of scope (explicit non-goals):** alerting/paging, user-visible SLO reporting, historical beyond 7 d (CloudWatch retention decides that separately), mobile layout.

---

## 2. Goals

- **G1 — Diagnose faster.** Every incident we investigated today (AI blocking the scheduler, duplicate gunicorn schedulers, X API `since_id` regression) should be visible on the dashboard within 30 s of occurring.
- **G2 — Fintech-grade UI.** Dark theme, dense layout, monospace numerics, green/yellow/red status badges, sparklines next to every metric. Match the existing `/terminal` aesthetic.
- **G3 — No new infra.** Reuse existing CloudWatch Logs pipeline (via EMF), existing admin ECS task, existing internal ALB. Don't introduce Prometheus/Grafana/Datadog.
- **G4 — Authoritative cost numbers.** Pull AWS Cost Explorer + X API usage endpoint directly. No estimation in the dashboard.
- **G5 — Admin-only access.** Behind VPN (already present) + admin role check. No public surface.
- **G6 — Cheap to operate.** Cost Explorer is $0.01/request — aggressively cache. GetMetricData is cheaper but still metered — batch requests. Budget: < $5/mo additional AWS spend for the dashboard itself.

---

## 3. User Stories

Stories are ordered by dependency: metric emission → IAM → admin API → UI panels. Each story fits one Implementor iteration.

---

### US-001: EMF metrics helper (`app/services/metrics.py`)

**Description:** As a backend engineer, I want a single Python helper that emits a CloudWatch EMF log line so producers across the app can publish metrics without duplicating the EMF JSON schema.

**Acceptance Criteria:**
- [ ] `app/services/metrics.py` defines `emit_metric(namespace: str, metric_name: str, value: float, unit: str = "Count", dimensions: dict | None = None, **extra_fields)` that prints one valid EMF JSON line to stdout.
- [ ] EMF payload conforms to the spec: top-level `_aws.Timestamp` (ms), `_aws.CloudWatchMetrics` with `Namespace`, `Dimensions`, `Metrics[{Name, Unit}]`; dimension values at top level; extra_fields merged at top level.
- [ ] Also supports a multi-metric variant `emit_metrics(namespace, metrics=[{name, value, unit}], dimensions, **extra)` so one log line emits ≥ 1 metric — keeps log volume low.
- [ ] A context manager `timed(namespace, metric_name, dimensions=…)` measures wall time and emits on exit.
- [ ] `tests/services/test_metrics.py` validates JSON shape, dimension handling, and the context manager.
- [ ] `mypy app/services/metrics.py` exits 0.

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.metrics import emit_metric; emit_metric('SIG', 'FeedLatency', 1.5, 'Seconds', {'Source':'SeekingAlpha'})"` exits 0 and prints valid JSON.
- `python3 -c "import json,sys; from io import StringIO; import contextlib; from app.services.metrics import emit_metric; buf=StringIO(); import contextlib;\n\nwith contextlib.redirect_stdout(buf): emit_metric('X','Y',1.0,'Count',{'A':'b'});\n\nd=json.loads(buf.getvalue().strip()); assert '_aws' in d and d['A']=='b' and d['Y']==1.0"` exits 0.
- `pytest tests/services/test_metrics.py -v` exits 0.
- `mypy app/services/metrics.py` exits 0.

---

### US-002: IAM + CDK — CloudWatch/CostExplorer read for admin task

**Description:** As an SRE, I want the admin ECS task to have IAM permission to read CloudWatch metrics and Cost Explorer data, so the dashboard can call `GetMetricData` and `GetCostAndUsage` from the container.

**Acceptance Criteria:**
- [ ] `infra/stack.py` adds an IAM policy to the admin task's execution role grant: `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`, `ce:GetCostAndUsage`, `ce:GetDimensionValues`. Scope to `Resource: *` (these APIs don't support resource-level ARNs).
- [ ] Confirmed `cdk diff` shows only the IAM policy diff — no other resource churn.
- [ ] Deploy applied via `cdk deploy`.
- [ ] `aws sts assume-role` as the admin task role and calling `aws cloudwatch list-metrics --max-items 1` exits 0.
- [ ] Typecheck passes (`python3 infra/app.py` — CDK synthesis smoke).

**Test Strategy:** integration

**Test Assertions:**
- `cd infra && npx cdk diff 2>&1 | grep -E 'IAM|PolicyDocument'` matches expected additions.
- Post-deploy: a one-shot script run inside an admin ECS task does `boto3.client('cloudwatch').list_metrics(MaxResults=1)` without AccessDenied.
- `boto3.client('ce').get_cost_and_usage(TimePeriod={'Start':'2026-04-10','End':'2026-04-17'}, Granularity='DAILY', Metrics=['UnblendedCost'])` returns data without AccessDenied.
- `cd infra && npx cdk synth > /dev/null` exits 0.

---

### US-003: Instrument per-source pollers with EMF metrics

**Description:** As a backend engineer, I want every `source_poller.py` tick to emit EMF metrics (latency, item count, fetch status) so the dashboard can render per-source health.

**Acceptance Criteria:**
- [ ] `app/services/source_poller.py` `_run_once`: on each tick, after `_store_items`, emits one EMF line with metrics `NewItems`, `IngestLatencySeconds` (median of `fetched_at - published` for new rows), `FetchDurationMs` (the HTTP call time), all dimensioned by `{Source: <name>, SourceType: rss|social}`.
- [ ] On fetch exception, emits `FetchErrors=1` with dimension `ErrorType: <exception class>`.
- [ ] Metrics landed in namespace `InstantNews/Ingestion`.
- [ ] No added CloudWatch cost beyond the existing log ingestion (EMF is log-driven).
- [ ] Per-source intervals unchanged from US-017 (not this PRD's concern).
- [ ] Typecheck passes.
- [ ] After deploy, `aws cloudwatch list-metrics --namespace "InstantNews/Ingestion"` shows ≥ 3 metric names across ≥ 3 source dimensions.

**Test Strategy:** integration

**Test Assertions:**
- Unit test: mock `fetch_feed` to return 2 items with known `published` timestamps; run `_run_once`; capture stdout; assert exactly one EMF line with `NewItems=2` and `IngestLatencySeconds` within expected range.
- Post-deploy query: `aws cloudwatch get-metric-statistics --namespace InstantNews/Ingestion --metric-name NewItems --dimensions Name=Source,Value=SeekingAlpha --start-time $(date -u -d '-10 min' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 60 --statistics Sum` returns ≥ 1 datapoint.
- `mypy app/services/source_poller.py` exits 0.

---

### US-004: Instrument AI pipeline with EMF metrics

**Description:** As a backend engineer, I want the AI pipeline to emit queue depth, batch duration, and backend-choice counters so the dashboard shows when MiniMax is rate-limited and falling back to Claude.

**Acceptance Criteria:**
- [ ] `app/services/ai_pipeline.py` emits `QueueDepth` gauge once per dispatcher loop iteration.
- [ ] `app/services/bedrock_analysis.py` emits per-article `BackendChosen` counter with dimension `{Backend: minimax|claude|bedrock}` after each `_call_model` call.
- [ ] Emits `BatchSize` and `BatchDurationMs` metrics on each `analyze_articles_batch` completion.
- [ ] Namespace `InstantNews/AIPipeline`.
- [ ] Typecheck passes.

**Test Strategy:** function

**Test Assertions:**
- Unit test: mock Bedrock clients to simulate MiniMax failure → Claude success; capture stdout; assert the EMF line has `BackendChosen` with `Backend=claude`.
- `pytest tests/services/test_ai_pipeline_metrics.py -v` exits 0.
- Post-deploy: `aws cloudwatch get-metric-statistics --namespace InstantNews/AIPipeline --metric-name QueueDepth --start-time ... --statistics Maximum` returns datapoints.
- `mypy app/services/ai_pipeline.py app/services/bedrock_analysis.py` exits 0.

---

### US-005: Instrument X API calls with rate-limit + cost metrics

**Description:** As a backend engineer, I want every `/2/tweets/search/recent` response to emit rate-limit headroom + tweet/user counts so the dashboard shows X API health and live-estimated monthly spend.

**Acceptance Criteria:**
- [ ] `app/services/twitter_source.py` `TwitterClient._get` on a 200 response emits EMF metrics: `RateLimitRemaining` (from `x-rate-limit-remaining` header), `RateLimitLimit` (cap), `TweetsBilled` (len of response `data`), `UsersBilled` (len of expansion users). Dimension `{Endpoint: search_recent}`.
- [ ] On 429 emits `RateLimited=1` with same dimension.
- [ ] Namespace `InstantNews/Twitter`.
- [ ] Typecheck passes.

**Test Strategy:** function

**Test Assertions:**
- Unit test: mock requests.Session.get to return a 200 with the right headers and body; call `_get`; assert the EMF line shape.
- Unit test: mock 429; assert `RateLimited=1`.
- `pytest tests/services/test_twitter_metrics.py -v` exits 0.
- Post-deploy: `aws cloudwatch get-metric-statistics --namespace InstantNews/Twitter --metric-name TweetsBilled --statistics Sum --start-time $(date -u -d '-1h' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 300` returns datapoints matching observed call volume.
- `mypy app/services/twitter_source.py` exits 0.

---

### US-006: Admin API `GET /admin/api/metrics/cloudwatch`

**Description:** As a frontend engineer, I want one admin endpoint that proxies `cloudwatch:GetMetricData` so the dashboard can fetch multi-metric time series in one call.

**Acceptance Criteria:**
- [ ] New blueprint `app/admin/metrics.py` exposes `POST /admin/api/metrics/cloudwatch` (POST because the query payload is large).
- [ ] Request JSON: `{range: "1h"|"24h"|"7d", queries: [{id, namespace, metric, dimensions, stat}]}`.
- [ ] Resolves `range` to `start_time, end_time, period` (1h→60s, 24h→60s, 7d→3600s).
- [ ] Calls `cloudwatch:GetMetricData` with up to 500 queries per request (AWS API limit).
- [ ] Response JSON: `{series: {[id]: {timestamps, values}}}`.
- [ ] Gated by admin role check (matches existing `/admin/*` pattern).
- [ ] Server-side in-memory cache (60 s TTL) keyed by query hash to reduce AWS API cost.
- [ ] Typecheck passes.

**Test Strategy:** cli

**Test Assertions:**
- `curl -X POST "http://localhost:8000/admin/api/metrics/cloudwatch" -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" -d '{"range":"1h","queries":[{"id":"q1","namespace":"InstantNews/Ingestion","metric":"NewItems","dimensions":{"Source":"SeekingAlpha"},"stat":"Sum"}]}'` returns 200 with `series.q1.timestamps` array.
- Unauthenticated request → 401.
- Admin-flag=false user → 403.
- `mypy app/admin/metrics.py` exits 0.

---

### US-007: Admin API `GET /admin/api/metrics/cost`

**Description:** As a frontend engineer, I want the dashboard to fetch authoritative cost figures (AWS Cost Explorer daily totals + X API usage) without the frontend holding IAM credentials.

**Acceptance Criteria:**
- [ ] `GET /admin/api/metrics/cost?range=7d` returns `{aws: {by_service: [...], daily_totals: [...]}, x_api: {used_this_month: N, quota: M, reset_at: ...}}`.
- [ ] AWS piece: `ce.get_cost_and_usage(Granularity='DAILY', GroupBy=[{Type:'DIMENSION',Key:'SERVICE'}], Metrics=['UnblendedCost'])`.
- [ ] X API piece: `GET https://api.x.com/2/usage/tweets` with the app's bearer token (confirm endpoint exists on Basic — else fall back to cumulative counters from our own `InstantNews/Twitter` metrics summed over the month).
- [ ] Aggressive cache: 1h TTL on Cost Explorer (CE is $0.01/request); 5 min on X usage.
- [ ] Admin role check + VPN (inherits from internal ALB).
- [ ] Typecheck passes.

**Test Strategy:** cli

**Test Assertions:**
- `curl -H "Authorization: Bearer $ADMIN_JWT" "http://localhost:8000/admin/api/metrics/cost?range=7d"` returns 200 with keys `aws` and `x_api`.
- Second call within 1 h returns identical `aws.daily_totals` with response header `X-Cache: HIT`.
- Non-admin → 403.
- `mypy app/admin/metrics.py` exits 0.

---

### US-008: Dashboard page scaffold + shared components

**Description:** As a frontend engineer, I want the base `/admin/monitoring` page with navigation, dark theme CSS, time-range selector, and auto-refresh plumbing wired to the admin API, so each panel story can drop in without re-building the shell.

**Acceptance Criteria:**
- [ ] New route `GET /admin/monitoring` (admin-only) serves an HTML page built with Vite under `frontend/src/admin-monitoring.js`.
- [ ] Dark theme matching `/terminal` — reuses existing `styles/` tokens (`--bg-primary`, `--green`, `--red`, `--text-secondary`, etc.).
- [ ] Time-range selector: `1h (Live)`, `24h`, `7d` as a segmented control. Live mode auto-refreshes every 10 s; 24h/7d every 60 s.
- [ ] Shared `fetchMetrics(queries, range)` function that POSTs to `/admin/api/metrics/cloudwatch`.
- [ ] uPlot integrated as the charting library (~40 KB, fastest for dense time-series).
- [ ] Empty panel placeholders with section headers: `Ingestion`, `AI Pipeline`, `Upstream APIs`, `Cost`.
- [ ] No JS console errors on load.
- [ ] Typecheck passes; `npm run build` exits 0.
- [ ] **Browser verification**: navigate to `https://admin.instnews.net/monitoring` over VPN, see the shell + working time-range toggle.

**Test Strategy:** browser

**Test Assertions:**
- Playwright: navigate to `/admin/monitoring` as admin user, assert presence of selectors `.panel--ingestion`, `.panel--ai`, `.panel--upstream`, `.panel--cost`, `.timerange-selector`.
- Playwright: click 24h chip, assert the fetch polling interval is 60 s (via intercepting `window.fetch`).
- `curl -I http://localhost:8000/admin/monitoring -H "Authorization: Bearer $ADMIN_JWT"` returns 200.
- `mypy app/routes/admin_monitoring.py` exits 0.

---

### US-009: Ingestion panel — per-source latency tiles + sparklines

**Description:** As an admin, I want to see per-source ingestion latency p50/p95 + new-item rate as small tiles with sparklines so I can spot a slow source at a glance.

**Acceptance Criteria:**
- [ ] `panel--ingestion` renders one tile per source (17 tiles: 15 RSS + Twitter + TruthSocial).
- [ ] Each tile shows: source name + `rss|social` badge, p50 latency (seconds) with green/yellow/red badge (thresholds: <30 s green, <120 s yellow, ≥120 s red), p95 latency in small text, items/min sparkline (last 60 points).
- [ ] Tiles sort by p95 latency desc (worst first) so issues bubble to the top.
- [ ] Live mode: tiles recompute every 10 s; smooth value transitions (CSS).
- [ ] Click a tile to pin it → right-side detail drawer shows 24 h latency series for that source with uPlot line chart.
- [ ] No JS console errors.
- [ ] Typecheck passes; `npm run build` exits 0.

**Test Strategy:** browser

**Test Assertions:**
- Playwright: navigate to `/admin/monitoring`, wait for ingestion panel to populate, assert tile count ≥ 15.
- Playwright: assert at least one tile has `data-source-type="social"` and at least 10 have `data-source-type="rss"`.
- Playwright: click the first tile, assert the detail drawer opens with an SVG or canvas chart element.
- Playwright: intercept `/admin/api/metrics/cloudwatch` response, verify request includes metric `IngestLatencySeconds` with `Source` dimension.
- `mypy` on any new Python not applicable (JS-only story); `npm run build` exits 0.

---

### US-010: AI pipeline panel — queue depth + batch duration + fallback chain

**Description:** As an admin, I want to see live AI queue depth, batch duration over time, and the minimax/claude/bedrock fallback ratio so I can catch backend degradation before it causes user-visible delay.

**Acceptance Criteria:**
- [ ] `panel--ai` shows three widgets:
  - Queue depth gauge (live): current value + 1h trend sparkline.
  - Batch duration line chart (uPlot): p50 + p95 batch duration over selected range.
  - Fallback-chain donut: % of requests that hit MiniMax / Claude / Bedrock in the range.
- [ ] Each widget updates on the dashboard's active refresh interval.
- [ ] If MiniMax share drops below 80% → show a yellow warning banner: "MiniMax fallback active — check credits".
- [ ] Typecheck passes; `npm run build` exits 0.

**Test Strategy:** browser

**Test Assertions:**
- Playwright: navigate, assert panel has `.widget--queue-depth`, `.widget--batch-duration`, `.widget--fallback-chain`.
- Playwright: mock `/admin/api/metrics/cloudwatch` to return a response with 50% Bedrock share; assert the yellow warning banner appears.
- Playwright: assert the donut renders three arcs with data-backend attributes `minimax`, `claude`, `bedrock`.
- `npm run build` exits 0.

---

### US-011: Upstream APIs panel — X rate-limit meter + Polygon/EDGAR tiles

**Description:** As an admin, I want to see live X API rate-limit headroom (450 cap) plus Polygon/EDGAR request-rate tiles so I know we're not about to be throttled.

**Acceptance Criteria:**
- [ ] `panel--upstream` shows:
  - X rate-limit meter: horizontal bar filled to `(used / 450) × 100%`, green <50%, yellow 50-80%, red >80%. Tooltip shows reset-at time.
  - Polygon tile: requests/min (from CloudWatch) + status (green if HTTP 200 rate >99%).
  - EDGAR tile: same shape.
  - Stripe webhook tile: p95 webhook latency + error count.
- [ ] Each tile links to the relevant CloudWatch Logs Insights saved query (open in new tab).
- [ ] Typecheck passes; `npm run build` exits 0.

**Test Strategy:** browser

**Test Assertions:**
- Playwright: assert presence of `.meter--x-api`, `.tile--polygon`, `.tile--edgar`, `.tile--stripe`.
- Playwright: mock `RateLimitRemaining=50` in the metric response; assert meter bar width is `(400/450) × 100%` ≈ 88% and has class `meter--danger`.
- Playwright: click EDGAR tile, assert it opens a new tab pointing to `console.aws.amazon.com/cloudwatch/home?.../edgar-insights`.
- `npm run build` exits 0.

---

### US-012: Cost panel — AWS daily + X API usage

**Description:** As an admin, I want authoritative daily AWS spend + X API monthly usage so I can confirm the cost-saving work actually saved money.

**Acceptance Criteria:**
- [ ] `panel--cost` shows:
  - AWS daily spend stacked bar chart (by service: ECS, RDS, ElastiCache, CloudWatch, other) for the selected range.
  - X API monthly usage progress bar: `{used}/{quota}` with days-remaining countdown.
  - Top-line summary: `MTD spend: $X | projected month-end: $Y`.
- [ ] Pulls from `/admin/api/metrics/cost` with 1h cache.
- [ ] If X API usage endpoint is unavailable on Basic tier, show estimated usage from our own `TweetsBilled` metric sum × $0.005 with an "estimated" footnote.
- [ ] Typecheck passes; `npm run build` exits 0.

**Test Strategy:** browser

**Test Assertions:**
- Playwright: assert presence of `.chart--aws-daily`, `.meter--x-api-monthly`, `.summary--mtd`.
- Playwright: assert the stacked bar chart has ≥ 7 bars when range=7d and is non-empty.
- Playwright: if endpoint returned `x_api.estimated=true`, assert footnote text "estimated" appears.
- `mypy app/admin/metrics.py` exits 0 (for any cost helper funcs).
- `npm run build` exits 0.

---

### US-013: Anomaly highlights — red/yellow row badges

**Description:** As an admin, I want badges on source tiles / pipeline widgets that turn yellow/red when a metric crosses a threshold so I can see problems at a glance without alert fatigue (no paging, just visual highlighting).

**Acceptance Criteria:**
- [ ] Shared helper `classifyStatus(value, warn, crit)` returns `"ok"|"warn"|"crit"`.
- [ ] Thresholds defined centrally in `frontend/src/admin-monitoring.js` `THRESHOLDS = {ingestion_p95_s: {warn:60, crit:180}, ai_queue_depth: {warn:100, crit:500}, x_rate_limit_pct: {warn:50, crit:80}, minimax_fallback_pct: {warn:20, crit:50}}`.
- [ ] Badge classes `badge--ok | badge--warn | badge--crit` with CSS tokens matching the terminal palette (`--green`, `--yellow`, `--red`).
- [ ] At the top of the page, a summary counter "X criticals / Y warnings" links to filter the panels.
- [ ] Typecheck passes; `npm run build` exits 0.

**Test Strategy:** browser

**Test Assertions:**
- Playwright: inject a mock metric response where `Source=SeekingAlpha` p95=200 s; assert the SeekingAlpha tile has class `badge--crit`.
- Playwright: click the "X criticals" counter, assert only critical tiles remain visible.
- `npm run build` exits 0.

---

## 4. Functional Requirements

- **FR-1** — Metrics are emitted via CloudWatch EMF from application code; no direct CloudWatch SDK `put_metric_data` calls.
- **FR-2** — Namespaces: `InstantNews/Ingestion`, `InstantNews/AIPipeline`, `InstantNews/Twitter`, `InstantNews/Polygon`, `InstantNews/EDGAR`, `InstantNews/Stripe`.
- **FR-3** — The dashboard is gated by admin role AND runs behind the internal ALB (inherits VPN requirement).
- **FR-4** — `cloudwatch:GetMetricData` requests are batched to ≤500 queries per HTTP request; server-side cached for 60 s.
- **FR-5** — `ce:GetCostAndUsage` is called at most once per hour per unique query; cached in Redis.
- **FR-6** — Time-range semantics: `1h` = 60s period (60 points), `24h` = 60s period (1440 points), `7d` = 3600s period (168 points).
- **FR-7** — Live mode refreshes every 10 s; 24h/7d modes refresh every 60 s. Refresh interval is user-overridable via a dropdown.
- **FR-8** — Dashboard uses uPlot for all time-series charts (no Chart.js, D3, or ECharts).
- **FR-9** — All panels degrade gracefully: if a metric query returns no data, the widget shows "no data" rather than throwing.
- **FR-10** — No PII or customer data appears in the dashboard. This is infrastructure telemetry only.

---

## 5. Non-Goals (Out of Scope)

- **No alerting / paging.** Visual badges only. PagerDuty / Slack integration is a separate PRD.
- **No SLO reports for external stakeholders.** This is ops-internal.
- **No mobile layout.** Assumes 1440×900+ desktop.
- **No user-level telemetry.** Individual user sessions, request traces, and Apdex-style metrics are out.
- **No custom dashboard builder.** Panel layout is hardcoded in the frontend.
- **No historical beyond CloudWatch Metrics retention** (15 mo default for detailed, 3h–455d depending on period). We don't back-fill to Timescale or S3.
- **No Prometheus / Grafana / Datadog.** EMF + CloudWatch-only stack.
- **Not a replacement for `/api/sources` public status.** That page is for customers; this dashboard is for ops.

---

## 6. Design Considerations

- **Theme:** match `/terminal` dark theme. Typography: Inter for labels, JetBrains Mono for numbers. Color tokens from existing CSS: `--green` (#10b981), `--yellow` (#f59e0b), `--red` (#ef4444), `--bg-primary`, `--bg-secondary`, `--text-primary`, `--text-secondary`.
- **Layout:** 4-row grid. Row 1: header + time-range selector + summary counter. Row 2: Ingestion panel (full width, 17 tiles). Row 3: AI Pipeline + Upstream APIs side-by-side. Row 4: Cost panel full width.
- **Dense numerics:** all values right-aligned, fixed-width font, always show 1-2 sig figs + unit. Example: `p95: 42.3s`, not `42.3 seconds ago`.
- **Sparklines:** 60 points, no axes, thin line in `--text-secondary`, filled area at 10% opacity.
- **Status badges:** 8px square dot + monospace label, tight layout. Not pills.
- **uPlot** because it's 40 KB gzipped and handles 100k+ points at 60fps — built for financial terminals.
- **Existing CSS vars** in `frontend/src/styles/` — reuse, don't introduce new tokens.

---

## 7. Technical Considerations

- **EMF JSON schema**: one log line = one timestamp = up to 100 metric values (AWS limit). Prefer single-line multi-metric emission from `source_poller` to keep log volume low.
- **CloudWatch Metrics retention** is automatic: 1-min resolution for 15 days, 5-min for 63 days, 1-hr for 455 days. Our 7-day view at 1-hr resolution fits comfortably; 24-h view at 1-min resolution fits in the 15-day window.
- **Cost Explorer pricing**: $0.01 per API request. With 1h cache and 4 panels / 3 ranges, worst case ~288 calls/day/user × $0.01 = $3/day/user. Cache aggressively. Estimated after caching: <$5/mo.
- **X API `/2/usage/tweets` endpoint** — confirm availability on Basic tier before relying on it. Implementor must WebFetch the current X doc, not trust memory. If unavailable, fall back to `InstantNews/Twitter.TweetsBilled` sum-of-month × $0.005.
- **Admin auth**: admin blueprint already has a role-check decorator; reuse.
- **Backward compatibility**: all changes are additive. Zero public-route changes.
- **Deploy ordering**: US-002 (IAM) before US-006/US-007 (admin APIs that use the IAM) before UI stories. US-001 (metrics helper) before US-003/004/005 (producers). Producers can deploy independently; UI fills in once producers have emitted enough data to render.
- **Soak before demo**: wait ≥ 2 hours after US-003/004/005 deploy so metrics have enough datapoints to look meaningful in the 24h view.

---

## 8. Success Metrics

- **M1 (coverage):** dashboard surfaces ≥ 90% of the signals that were grep-mined in today's incident (per-source latency, AI batch duration, fallback rate, rate-limit headroom, duplicate-scheduler detection).
- **M2 (latency):** live panel updates in < 2 s after a metric event (CloudWatch EMF typically 30-60 s end-to-end; accept that, display "data age" indicator).
- **M3 (cost):** dashboard itself adds < $5/mo AWS spend after caching.
- **M4 (correctness):** AWS Cost Explorer daily totals match AWS Billing Console to the cent for the last 3 days.
- **M5 (usability):** a first-time admin user identifies the slowest source in under 10 s without reading docs.
- **M6 (reliability):** 0 JS console errors across all 4 panels over a 30-min soak.

---

## 9. Open Questions

- **OQ-1:** Does X API Basic tier expose `/2/usage/tweets`? If not, we fall back to our own `TweetsBilled` sum. Implementor must WebFetch the current X docs during US-007. **Resolution policy:** if unavailable, implement the fallback + add "(estimated)" footnote in the UI.
- **OQ-2:** Should the Cost panel include a projected month-end cost based on the current run rate? Deferred — add in a follow-up if users ask for it.
- **OQ-3:** uPlot vs Chart.js — locked to uPlot in FR-8 based on performance. If Implementor hits a showstopper (e.g., stacked bar not supported), fall back to a lightweight custom SVG for just the cost stacked bar, not swap libraries.
- **OQ-4:** Should we also instrument the Flask request logger with EMF metrics (request latency per route)? Deferred to a follow-up; this PRD is ingestion + AI + upstream-APIs + cost only.

---

## File Locations Referenced

| Concern | Path |
|---|---|
| Per-source pollers | `app/services/source_poller.py` |
| AI pipeline | `app/services/ai_pipeline.py`, `app/services/bedrock_analysis.py` |
| X API client | `app/services/twitter_source.py` |
| Admin blueprint | `app/admin/routes.py`, `app/admin/middleware.py` |
| Admin frontend | `frontend/src/admin.js`, `frontend/admin.html` |
| CDK stack | `infra/stack.py` |
| Metrics helper (new) | `app/services/metrics.py` |
| Admin metrics API (new) | `app/admin/metrics.py` |
| Dashboard entry (new) | `frontend/src/admin-monitoring.js`, `frontend/admin-monitoring.html` |
| Dashboard route (new) | `app/routes/admin_monitoring.py` |
