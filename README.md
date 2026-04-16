# SIGNAL — Instant News Trading Terminal

A zero-cost, real-time news aggregation terminal for quantitative trading with REST API access. Aggregates 15+ financial news sources via free RSS feeds with keyword-based sentiment scoring and semantic duplicate detection.

## Features

- **5-second auto-refresh** — captures breaking news fast
- **15 free financial sources** — CNBC, Reuters, MarketWatch, Yahoo Finance, Nasdaq, SeekingAlpha, Benzinga, Investing.com, AP News, BBC Business, Google News, Bloomberg Business, Bloomberg Markets
- **Semantic deduplication** — detects cross-source duplicate stories using sentence embeddings (`all-MiniLM-L6-v2`), marks them with a `DUP` badge in the dashboard and `duplicate: true` in the API
- **Sentiment scoring** — keyword-based NLP (50+ bullish/bearish signal words) scores every headline
- **REST API** — JSON endpoints for programmatic access by trading bots
- **Date range filtering** — query historical data slices with `from`/`to` date parameters
- **Keyword search** — filter by ticker, company, or topic in real-time
- **Source filtering** — toggle any source on/off
- **Keyboard shortcuts** — `R` refresh, `F` search, `1-4` sentiment filter
- **Zero cost** — no API keys, no subscriptions, all free public RSS feeds
- **Docker ready** — one command to deploy anywhere
- **5-year retention** — stores up to 5 years of news history with automatic cleanup

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/haotianteng/InstantNews.git
cd InstantNews
docker compose up -d
```

Open http://localhost:8000 — done.

### Option 2: Run Directly

```bash
git clone https://github.com/haotianteng/InstantNews.git
cd InstantNews
pip install -r requirements.txt
python server.py
```

Open http://localhost:8000.

### Option 3: Production with Gunicorn

```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 server:app
```

---

## Deployment Guide

### Deploy to a VPS ($4-6/month)

This is the best option for a persistent, always-on news terminal. Works with any VPS provider: DigitalOcean, Vultr, Hetzner, Linode, etc.

**1. Get a VPS**

Any provider with Ubuntu 22.04+, 1 vCPU, 1GB RAM is sufficient:
- [Hetzner](https://www.hetzner.com/cloud/) — €3.79/mo (best value)
- [DigitalOcean](https://www.digitalocean.com/) — $6/mo
- [Vultr](https://www.vultr.com/) — $6/mo

**2. SSH in and install Docker**

```bash
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and run
git clone https://github.com/haotianteng/InstantNews.git
cd InstantNews
docker compose up -d
```

**3. Set up a domain (optional)**

```bash
# Install Caddy (auto-HTTPS reverse proxy)
apt install -y caddy

# Create Caddyfile
cat > /etc/caddy/Caddyfile << 'EOF'
news.yourdomain.com {
    reverse_proxy localhost:8000
}
EOF

# Restart Caddy (auto-provisions HTTPS certificate)
systemctl restart caddy
```

Now your terminal is live at `https://news.yourdomain.com` with automatic HTTPS.

---

### Deploy to Railway (Free Tier Available)

[Railway](https://railway.app/) offers a simple git-push deployment with a free trial.

**1. Install Railway CLI**
```bash
npm install -g @railway/cli
railway login
```

**2. Deploy**
```bash
cd InstantNews
railway init
railway up
```

Railway auto-detects the Dockerfile and deploys. You get a public URL immediately.

---

### Deploy to Render (Free Tier)

**1.** Go to [render.com](https://render.com) and create a new "Web Service"

**2.** Connect your GitHub repo `haotianteng/InstantNews`

**3.** Configure:
- **Runtime:** Docker
- **Instance Type:** Free (or Starter $7/mo for always-on)

Render will auto-deploy on every push to `main`.

---

### Deploy to Fly.io (~$3/mo)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh
fly auth login

# Deploy
cd InstantNews
fly launch          # Accept defaults, pick a region close to you
fly deploy
```

---

### Deploy to PythonAnywhere (Free)

[PythonAnywhere](https://www.pythonanywhere.com/) offers free Flask hosting — good for testing but has CPU limits.

**1.** Sign up at pythonanywhere.com

**2.** Open a Bash console and run:
```bash
git clone https://github.com/haotianteng/InstantNews.git
cd InstantNews
pip install --user -r requirements.txt
```

**3.** Go to **Web** tab → **Add a new web app** → **Flask** → Point to `/home/yourusername/InstantNews/server.py`

**4.** Set the source code directory and WSGI config to point to `server:app`

---

## Architecture

```
InstantNews/
├── server.py             # Flask backend (API + feed aggregation)
├── static/               # Frontend files (served by Flask)
│   ├── index.html        # Dashboard UI
│   ├── base.css          # CSS reset
│   ├── style.css         # Terminal theme
│   └── app.js            # Frontend logic
├── Dockerfile            # Container build
├── docker-compose.yml    # One-command deployment
├── requirements.txt      # Python dependencies
├── cgi-bin/              # Original CGI version (for reference)
│   └── api.py
└── README.md
```

### How It Works

1. **Backend** (`server.py`) — Flask app that fetches 13 RSS feeds in parallel using threads, parses XML, scores sentiment with keyword matching, and stores in SQLite. Auto-refreshes when data is >30 seconds stale.

2. **Frontend** (`static/`) — Dark-themed terminal UI with 5-second polling, real-time filters, and flash animations on new items.

3. **Database** — SQLite with WAL mode for concurrent reads. Deduplicates by URL (exact match) and by title semantics (embedding similarity). No external database needed.

---

## API Reference

### `GET /api/news`

Returns latest news items.

| Parameter   | Default | Description |
|-------------|---------|-------------|
| `limit`     | 200     | Number of items (max 500) |
| `source`    | all     | Filter by source name |
| `sentiment` | all     | Filter: `bullish`, `bearish`, `neutral` |
| `q`         |         | Keyword search in title & summary |
| `from`      |         | Filter from date (ISO 8601, e.g. `2026-03-01`) |
| `to`        |         | Filter to date (ISO 8601, e.g. `2026-03-02`) |

```bash
# Get 10 most recent bullish headlines
curl "http://localhost:8000/api/news?limit=10&sentiment=bullish"

# Search for NVIDIA news
curl "http://localhost:8000/api/news?q=nvidia"

# Get news from a specific date range
curl "http://localhost:8000/api/news?from=2026-03-01&to=2026-03-02"
```

### `GET /api/sources`
Returns all active feed sources with item counts.

### `GET /api/stats`
Returns aggregated statistics: total items, breakdown by source/sentiment, average sentiment score.

### `POST /api/refresh`
Force refresh all feeds immediately.

```bash
curl -X POST "http://localhost:8000/api/refresh"
```

### `GET /api/docs`
Returns API documentation as JSON.

### Response Format

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
      "fetched_at": "2026-03-01T14:31:12+00:00",
      "summary": "The S&P 500 index rallied to a new all-time high...",
      "sentiment_score": 1.0,
      "sentiment_label": "bullish",
      "tags": "",
      "duplicate": 0
    }
  ]
}
```

The `duplicate` field is `1` if the item was detected as a semantic duplicate of another item, `0` otherwise. See [Semantic Deduplication](#semantic-deduplication) below.

---

## Configuration

Environment variables (set in `docker-compose.yml` or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8000 | Server port |
| `DB_PATH` | data/news_terminal.db | SQLite database path |
| `STALE_SECONDS` | 30 | Seconds before data is considered stale |
| `FETCH_TIMEOUT` | 5 | Timeout per RSS feed fetch (seconds) |
| `DEDUP_THRESHOLD` | 0.85 | Cosine similarity threshold for semantic deduplication (0.0–1.0) |
| `MAX_AGE_DAYS` | 1825 | Maximum age of stored items in days (default 5 years) |

---

## Semantic Deduplication

The same news story often appears across multiple sources (e.g. CNBC, Reuters, Bloomberg) with slightly different titles. SIGNAL detects these cross-source duplicates using sentence embeddings.

**How it works:**

1. Each new headline is encoded into a 384-dimensional embedding using the [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) model (~22MB, runs on CPU)
2. The embedding is compared against all items from the last 48 hours using cosine similarity
3. If similarity >= threshold (default `0.85`), the item is marked as a duplicate
4. Embeddings are stored in the database for efficient re-comparison

**Dashboard:** Duplicate items display a yellow `DUP` badge next to the headline. Use the "Hide duplicates" checkbox in the sidebar to filter them out.

**API:** Each item in the `/api/news` response includes a `duplicate` field (`0` = original, `1` = duplicate). Clients can filter duplicates in post-processing.

**Performance:**
- Model loads lazily on first feed refresh (~2-3s one-time cost)
- Per-title embedding: ~5-10ms on CPU
- Batch of 15-20 titles: ~50ms total
- Cosine similarity over 200 recent items: <1ms

Adjust the threshold via the `DEDUP_THRESHOLD` environment variable. Lower values (e.g. `0.75`) catch more duplicates but risk false positives; higher values (e.g. `0.92`) are more conservative.

---

## Sentiment Scoring

Uses a keyword-based approach with 50+ financial signal words:

- **Bullish**: surge, soar, rally, gain, jump, rise, record high, upgrade, beat, exceed, profit, growth, boom, breakout, outperform, buy, accelerate, expand...
- **Bearish**: crash, plunge, drop, fall, decline, loss, downgrade, miss, deficit, recession, layoff, bankruptcy, sell-off, warning, sink, tumble, slump...

Score = `(bullish_count - bearish_count) / total_count`, normalized to [-1.0, 1.0].

## License

MIT
