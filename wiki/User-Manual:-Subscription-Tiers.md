# Subscription Tiers

## Tier Comparison

```mermaid
graph TB
    subgraph Free [Free — $0/month]
        direction TB
        F1[fa:fa-check News feed — 15 sources]
        F2[fa:fa-check Keyword search]
        F3[fa:fa-check Source filtering]
        F4[fa:fa-check 50 items per request]
        F5[fa:fa-check 7-day history]
        F6[fa:fa-times No sentiment data]
        F7[fa:fa-times No duplicate detection]
        F8[fa:fa-times No date range filter]
        F9[fa:fa-times No AI features]
    end

    subgraph Plus [Plus — $14.99/month]
        direction TB
        P1[fa:fa-check Everything in Free]
        P2[fa:fa-check Sentiment analysis]
        P3[fa:fa-check Duplicate detection]
        P4[fa:fa-check Date range filtering]
        P5[fa:fa-check 200 items per request]
        P6[fa:fa-check 1-year history]
        P7[fa:fa-check CSV export]
        P8[fa:fa-times No AI features]
    end

    subgraph Max [Max — $39.99/month]
        direction TB
        M1[fa:fa-check Everything in Plus]
        M2[fa:fa-check AI ticker recommendations]
        M3[fa:fa-check Price analysis]
        M4[fa:fa-check Advanced analytics]
        M5[fa:fa-check Custom alerts]
        M6[fa:fa-check 500 items per request]
        M7[fa:fa-check 5-year history]
    end

    style Free fill:#21262d,color:#c9d1d9
    style Plus fill:#0d47a1,color:#fff
    style Max fill:#e65100,color:#fff
```

## Detailed Feature Matrix

| Feature | Free | Plus | Max |
|---------|:----:|:----:|:---:|
| **Core** | | | |
| Real-time news feed | Yes | Yes | Yes |
| Keyword search | Yes | Yes | Yes |
| Source filtering | Yes | Yes | Yes |
| **Analysis** | | | |
| Sentiment scoring | — | Yes | Yes |
| Sentiment labels (bullish/bearish/neutral) | — | Yes | Yes |
| Duplicate detection (DUP badge) | — | Yes | Yes |
| Date range filtering | — | Yes | Yes |
| **AI (Coming Soon)** | | | |
| AI ticker recommendations | — | — | Yes |
| Price analysis & correlation | — | — | Yes |
| Advanced analytics dashboard | — | — | Yes |
| Custom keyword/ticker alerts | — | — | Yes |
| **Limits** | | | |
| Items per API request | 50 | 200 | 500 |
| History depth | 7 days | 1 year | 5 years |
| API rate limit | 10/min | 60/min | 120/min |
| Refresh interval (minimum) | 30s | 5s | 3s |

## How Tier Gating Works

### API Response Differences

The `/api/news` endpoint returns different fields based on your tier:

**Free tier response** — sentiment and duplicate fields are omitted:

```json
{
  "id": 1234,
  "title": "S&P 500 Hits Record High",
  "link": "https://...",
  "source": "CNBC",
  "published": "2026-03-20T14:30:00+00:00",
  "fetched_at": "2026-03-20T14:31:12+00:00",
  "summary": "Markets rallied on strong earnings...",
  "tags": ""
}
```

**Plus/Max tier response** — includes sentiment analysis and deduplication:

```json
{
  "id": 1234,
  "title": "S&P 500 Hits Record High",
  "link": "https://...",
  "source": "CNBC",
  "published": "2026-03-20T14:30:00+00:00",
  "fetched_at": "2026-03-20T14:31:12+00:00",
  "summary": "Markets rallied on strong earnings...",
  "tags": "",
  "sentiment_score": 0.75,
  "sentiment_label": "bullish",
  "duplicate": 0
}
```

### Check Your Tier Programmatically

```bash
# Without auth (anonymous = free)
curl -s "https://www.instnews.net/api/auth/tier" | jq .

# With auth
curl -s -H "Authorization: Bearer YOUR_TOKEN" \
  "https://www.instnews.net/api/auth/tier" | jq .
```

Response:

```json
{
  "tier": "plus",
  "features": {
    "sentiment_filter": true,
    "deduplication": true,
    "date_range_filter": true,
    "ai_ticker_recommendations": false
  },
  "limits": {
    "max_items_per_request": 200,
    "api_rate_per_minute": 60,
    "history_days": 365
  }
}
```

## Subscribing

1. Visit [www.instnews.net/pricing](https://www.instnews.net/pricing)
2. Click **Subscribe to Plus** or **Subscribe to Max**
3. Sign in with Google (if not already signed in)
4. Complete payment on Stripe Checkout
5. Your tier is upgraded immediately

## Managing Your Subscription

Signed-in users can:
- **View current plan** — User menu → dropdown shows current tier
- **Change plan** — Via Stripe Customer Portal (Manage Subscription)
- **Cancel** — Via Stripe Customer Portal

Cancellation takes effect at the end of the current billing period. You keep access until then.

## Sentiment Scoring Details

Sentiment is calculated using keyword matching against 50+ financial signal words:

| Bullish words | Bearish words |
|---------------|---------------|
| surge, soar, rally, gain, jump, rise, bull, record high, upgrade, beat, exceed, profit, growth, boom, breakout, outperform, buy, accelerate, expand, bullish, uptick, climb, recover, rebound, strong, positive, upbeat, optimis | crash, plunge, drop, fall, decline, bear, loss, downgrade, miss, deficit, recession, layoff, bankruptcy, sell-off, warning, cut, sink, tumble, slump, bearish, downturn, weak, negative, pessimis, fear, risk, volatil, concern |

**Formula:** `score = (bullish_count - bearish_count) / total_count`

| Score Range | Label |
|-------------|-------|
| > 0.1 | Bullish |
| < -0.1 | Bearish |
| -0.1 to 0.1 | Neutral |

## Deduplication Details

The same story often appears across multiple sources. SIGNAL detects duplicates using sentence embeddings:

1. Each headline is encoded into a 384-dimensional vector using the `all-MiniLM-L6-v2` model
2. New items are compared against the last 48 hours of embeddings via cosine similarity
3. If similarity >= 0.85, the newer item is marked as a duplicate
4. The dashboard shows a yellow `DUP` badge on duplicate items
5. Use "Hide duplicates" in the sidebar to filter them out
