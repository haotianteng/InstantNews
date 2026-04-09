# Future Features Roadmap

Features listed in `app/billing/tiers.py` that are flagged but **not yet implemented**. Each requires new backend and/or frontend work before the tier gate becomes meaningful.

## WeChat Login (Pending Approval)

**Status:** Code implemented, waiting for WeChat Open Platform approval (~1 week).

**What:** WeChat QR code scan login for Chinese users (Google OAuth is blocked in China).

**Registration steps:**
1. Register at https://open.weixin.qq.com/ (requires Chinese business license or individual ID)
2. Create a "Website Application" (website app)
3. Submit domain verification for www.instnews.net
4. Wait for approval (1-3 business days after submission)
5. Get `WECHAT_APP_ID` and `WECHAT_APP_SECRET`
6. Configure callback URL: `https://www.instnews.net/api/auth/wechat/callback`
7. Add secrets to AWS Secrets Manager (`instantnews/app`)
8. Generate `APP_JWT_SECRET` (32-byte random hex) and add to secrets

**Code already implemented:**
- `app/auth/wechat.py` — WeChat OAuth client (QR code flow)
- `app/auth/jwt_utils.py` — App JWT for WeChat session tokens
- `app/auth/routes.py` — `/api/auth/wechat/login`, `/callback`, `/refresh`
- `app/auth/middleware.py` — App JWT verification path
- `frontend/src/auth.js` — WeChat button + token handling (CN region)
- `migrations/versions/010_add_multi_auth_fields.py` — `wechat_openid`, `wechat_unionid` columns

**Deploy:** Once approved, add secrets and redeploy. No code changes needed.

---

## Phase 3B: Stripe Payment Integration (Next)

**What:** Connect Stripe Checkout for subscriptions so users can upgrade tiers.

| Component | Work Required |
|-----------|---------------|
| `app/billing/stripe_client.py` | Stripe SDK wrapper |
| `app/billing/routes.py` | `POST /api/billing/checkout`, `POST /api/billing/portal`, `POST /api/billing/webhook` |
| `static/pricing.html` | Two-column pricing page (Free/Pro) with Subscribe buttons |
| `migrations/003_add_subscriptions.py` | Subscriptions table (stripe_customer_id, stripe_subscription_id, status, etc.) |
| Stripe Dashboard | Create Products and Prices for Pro ($29.99/mo with 30-day trial). Max tier hidden for now. |

**Blocked by:** Company registration → Stripe account creation. Can develop in Stripe test mode.

---

## Pro Tier Features (Not Yet Implemented)

### 1. Extended Sources
**What:** Additional premium RSS feeds beyond the 15 free ones.
**Work:** Add premium feed URLs to config (behind a flag). Filter them out in `feed_refresh.py` when serving free users. Could include: WSJ, FT, Bloomberg full feeds via paid RSS.
**Tier gate:** `extended_sources`

### 2. API Key Access
**What:** Allow Plus/Max users to generate API keys for programmatic access (trading bots).
**Work:**
- New `api_keys` table (user_id, key_hash, created_at, last_used, name)
- `POST /api/keys` — generate API key
- `DELETE /api/keys/:id` — revoke key
- Auth middleware: support `X-API-Key` header in addition to Bearer tokens
- Rate limiting per API key
**Tier gate:** `api_access`

### 3. CSV Export
**What:** Export filtered news results to CSV file.
**Work:**
- `GET /api/news/export?format=csv` — returns CSV with same filters as `/api/news`
- Stream response for large datasets
**Tier gate:** `export_csv`

### 4. Watchlist
**What:** Personal ticker watchlist with filtered news view.
**Work:**
- New `watchlist` table (user_id, ticker, added_at)
- `GET/POST/DELETE /api/watchlist`
- `GET /api/news?watchlist=true` — filter news to only watchlist tickers
- Frontend: watchlist sidebar section
**Tier gate:** `watchlist`

---

## Max Tier Features (Not Yet Implemented)

### 5. AI Ticker Recommendations
**What:** LLM-powered analysis of mentioned tickers with sentiment aggregation and buy/sell signals.
**Work:**
- `app/services/ticker_extraction.py` — extract stock tickers from headlines using regex + NER
- `app/services/ai_analysis.py` — aggregate per-ticker sentiment, generate summaries via AWS Bedrock or OpenAI API
- `GET /api/analysis/tickers` — ranked list of tickers with sentiment, mention count, trend
- Frontend: ticker analysis panel
- External dependency: LLM API (cost per request)
**Tier gate:** `ai_ticker_recommendations`

### 6. Price Analysis
**What:** Correlate news sentiment with actual stock price movements.
**Work:**
- `app/services/price_data.py` — integrate financial data API (Alpha Vantage free tier, Polygon.io, or `yfinance`)
- Fetch price data for mentioned tickers
- Show price change alongside sentiment for each ticker
- Store price snapshots for historical correlation
**Tier gate:** `price_analysis`

### 7. Advanced Analytics Dashboard
**What:** Visual analytics: sentiment trends, volume heatmaps, source reliability, top tickers.
**Work:**
- `static/analytics.html` + `static/analytics.js` — new analytics page
- `GET /api/analytics/sentiment-trend` — sentiment by hour/day
- `GET /api/analytics/volume` — news volume heatmap
- `GET /api/analytics/top-tickers` — most mentioned tickers
- Add Chart.js for visualization
- Backend aggregation queries
**Tier gate:** `advanced_analytics`

### 8. Custom Alerts
**What:** Email or webhook notifications when keywords/tickers appear in news.
**Work:**
- New `alerts` table (user_id, type, keyword, channel, webhook_url)
- `GET/POST/DELETE /api/alerts`
- Alert evaluation in feed worker (check new items against user alerts)
- Email delivery via AWS SES
- Webhook delivery with retry logic
**Tier gate:** `custom_alerts`

---

## Implementation Priority

| Priority | Feature | Effort | Revenue Impact |
|----------|---------|--------|----------------|
| 1 | Stripe integration | Medium | Enables all paid tiers |
| 2 | Watchlist | Low | Core Pro differentiator |
| 3 | CSV Export | Low | Easy Pro value-add |
| 4 | API Key Access | Medium | Developer/bot audience |
| 5 | AI Ticker Recommendations | High | Core Max differentiator (hidden) |
| 6 | Price Analysis | Medium | High perceived value |
| 7 | Advanced Analytics | Medium | Visual appeal for Max (hidden) |
| 8 | Custom Alerts | High | Sticky retention feature |
| 9 | Extended Sources | Low | Depends on feed availability |

## Rate Limiting (Not Yet Implemented)

Rate limiting per tier is defined in `tiers.py` but not enforced yet. Implementation requires:
- Redis (ElastiCache) for sliding window counters
- `flask-limiter` with Redis backend, or custom middleware in `app/middleware/rate_limit.py`
- Different limits per tier: 10/min (free), 60/min (pro), 120/min (max)
- Return `429 Too Many Requests` with `Retry-After` header
