# SIGNAL — Instant News Trading Terminal

A zero-cost, real-time news aggregation terminal for quantitative trading with REST API access. Aggregates 13+ financial news sources via free RSS feeds with keyword-based sentiment scoring.

![Terminal Screenshot](https://img.shields.io/badge/status-live-brightgreen) ![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **5-second auto-refresh** — captures breaking news fast
- **13 free financial sources** — CNBC, Reuters, MarketWatch, Yahoo Finance, Nasdaq, SeekingAlpha, Benzinga, Investing.com, AP News, BBC Business, Google News
- **Sentiment scoring** — keyword-based NLP (50+ bullish/bearish signal words) scores every headline
- **REST API** — JSON endpoints for programmatic access by trading bots
- **Keyword search** — filter by ticker, company, or topic in real-time
- **Source filtering** — toggle any source on/off
- **Keyboard shortcuts** — `R` refresh, `F` search, `1-4` sentiment filter
- **Zero cost** — no API keys, no subscriptions, all free public RSS feeds

## Architecture

```
news-terminal/
├── index.html          # Dashboard UI
├── base.css            # CSS reset & base styles
├── style.css           # Terminal theme & components
├── app.js              # Frontend logic (auto-refresh, filters, API calls)
├── cgi-bin/
│   └── api.py          # Backend API (RSS aggregation, sentiment, SQLite)
└── README.md
```

### Backend (`cgi-bin/api.py`)

A single Python CGI script that:
- Fetches 13 RSS feeds in parallel using threads (~1-2s total)
- Parses RSS/Atom XML with `xml.etree.ElementTree`
- Scores sentiment using keyword matching (no external dependencies)
- Stores items in SQLite with deduplication by URL
- Auto-refreshes when data is >30 seconds stale

### Frontend

Dark-themed financial terminal UI with:
- Dense table layout optimized for scanning
- Monospace timestamps and tabular numbers
- "NEW" badges on items <60 seconds old
- Flash animations on incoming items
- Mobile-responsive with hamburger sidebar

## API Reference

### `GET /cgi-bin/api.py/news`

Returns latest news items.

| Parameter   | Default | Description |
|-------------|---------|-------------|
| `limit`     | 200     | Number of items (max 500) |
| `source`    | all     | Filter by source name |
| `sentiment` | all     | Filter: `bullish`, `bearish`, `neutral` |
| `q`         |         | Keyword search in title & summary |

```bash
# Get 10 most recent bullish headlines
curl "https://your-url/cgi-bin/api.py/news?limit=10&sentiment=bullish"

# Search for NVIDIA news
curl "https://your-url/cgi-bin/api.py/news?q=nvidia"
```

### `GET /cgi-bin/api.py/sources`

Returns all active feed sources with item counts.

### `GET /cgi-bin/api.py/stats`

Returns aggregated statistics: total items, breakdown by source/sentiment, average sentiment score.

### `POST /cgi-bin/api.py/refresh`

Force refresh all feeds immediately.

```bash
curl -X POST "https://your-url/cgi-bin/api.py/refresh"
```

### `GET /cgi-bin/api.py/docs`

Returns API documentation as JSON.

## Response Format

```json
{
  "count": 10,
  "items": [
    {
      "id": 1,
      "title": "S&P 500 Surges to Record High on Strong Earnings",
      "link": "https://...",
      "source": "CNBC",
      "published": "2026-03-01T14:30:00+00:00",
      "fetched_at": "2026-03-01 14:31:12",
      "summary": "The S&P 500 index rallied to a new all-time high...",
      "sentiment_score": 1.0,
      "sentiment_label": "bullish",
      "tags": ""
    }
  ]
}
```

## Sentiment Scoring

Uses a keyword-based approach with 50+ financial signal words:

- **Bullish**: surge, soar, rally, gain, jump, rise, record high, upgrade, beat, exceed, profit, growth, boom, breakout, outperform, buy, accelerate, expand...
- **Bearish**: crash, plunge, drop, fall, decline, loss, downgrade, miss, deficit, recession, layoff, bankruptcy, sell-off, warning, sink, tumble, slump...

Score = `(bullish_count - bearish_count) / total_count`, normalized to [-1.0, 1.0].

| Score       | Label    |
|-------------|----------|
| > 0.1       | bullish  |
| < -0.1      | bearish  |
| -0.1 to 0.1 | neutral  |

## Deployment

This app is designed as a static site + CGI backend. Deploy to any platform that supports Python CGI scripts, or adapt the backend to Flask/FastAPI for other hosting options.

### Requirements

- Python 3.8+
- No external dependencies (uses only stdlib: `urllib`, `xml.etree`, `sqlite3`, `threading`, `json`, `re`)

## License

MIT
