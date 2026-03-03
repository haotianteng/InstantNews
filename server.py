#!/usr/bin/env python3
"""
SIGNAL News Trading Terminal — Flask Server
Production-ready version for self-hosting.

Usage:
  Development:  python server.py
  Production:   gunicorn -w 4 -b 0.0.0.0:8000 server:app
  Docker:       docker compose up -d
"""

import json
import os
import re
import sqlite3
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock
import numpy as np
from flask import Flask, request, jsonify, send_from_directory

# ---------------------------------------------------------------------------
# Configuration (override with environment variables)
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("DB_PATH", "data/news_terminal.db")
STALE_SECONDS = int(os.environ.get("STALE_SECONDS", "30"))
FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "5"))
PORT = int(os.environ.get("PORT", "8000"))
MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", str(5 * 365)))  # 5 years
DEDUP_THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.85"))

FEEDS = {
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC_World": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
    "Reuters_Business": "https://www.reutersagency.com/feed/?best-topics=business-finance",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch_Markets": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "Investing_com": "https://www.investing.com/rss/news.rss",
    "Yahoo_Finance": "https://finance.yahoo.com/news/rssindex",
    "Nasdaq": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    "SeekingAlpha": "https://seekingalpha.com/market_currents.xml",
    "Benzinga": "https://www.benzinga.com/feeds/all",
    "AP_News": "https://rsshub.app/apnews/topics/business",
    "Bloomberg_Business": "https://rsshub.app/bloomberg/bbiz",
    "Bloomberg_Markets": "https://rsshub.app/bloomberg/markets",
    "BBC_Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "Google_News_Business": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB",
}

BULLISH_WORDS = [
    "surge", "soar", "rally", "gain", "jump", "rise", "bull", "record high",
    "upgrade", "beat", "exceed", "profit", "growth", "boom", "breakout",
    "outperform", "buy", "accelerate", "expand", "bullish", "uptick", "climb",
    "recover", "rebound", "strong", "positive", "upbeat", "optimis"
]

BEARISH_WORDS = [
    "crash", "plunge", "drop", "fall", "decline", "bear", "loss", "downgrade",
    "miss", "deficit", "recession", "layoff", "bankruptcy", "sell-off",
    "warning", "cut", "sink", "tumble", "slump", "bearish", "downturn",
    "weak", "negative", "pessimis", "fear", "risk", "volatil", "concern"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static", static_url_path="")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE,
            source TEXT,
            published TEXT,
            fetched_at TEXT,
            summary TEXT,
            sentiment_score REAL DEFAULT 0,
            sentiment_label TEXT DEFAULT 'neutral',
            tags TEXT DEFAULT ''
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_published ON news(published DESC)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetched ON news(fetched_at DESC)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_source ON news(source)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sentiment ON news(sentiment_label)")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup_title_source ON news(title, source)")
    # Migrate: add duplicate and embedding columns if missing
    try:
        db.execute("ALTER TABLE news ADD COLUMN duplicate INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE news ADD COLUMN embedding BLOB")
    except sqlite3.OperationalError:
        pass
    db.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Sentiment Scoring
# ---------------------------------------------------------------------------

def score_sentiment(text):
    if not text:
        return 0.0, "neutral"
    text_lower = text.lower()
    bullish = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bearish = sum(1 for w in BEARISH_WORDS if w in text_lower)
    total = bullish + bearish
    if total == 0:
        return 0.0, "neutral"
    raw = (bullish - bearish) / total
    score = max(-1.0, min(1.0, raw))
    if score > 0.1:
        label = "bullish"
    elif score < -0.1:
        label = "bearish"
    else:
        label = "neutral"
    return round(score, 3), label

# ---------------------------------------------------------------------------
# RSS Feed Fetching
# ---------------------------------------------------------------------------

def strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<(br|p|div|li|h[1-6]|tr|td|th)[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:500]

def utc_iso(dt):
    """Format a datetime as UTC ISO 8601 with T separator and +00:00."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

def parse_date(date_str):
    if not date_str:
        return utc_iso(datetime.now(timezone.utc))
    cleaned = date_str.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%d %b %Y %H:%M:%S %z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return utc_iso(dt)
        except ValueError:
            continue
    return utc_iso(datetime.now(timezone.utc))

def fetch_feed(source_name, url):
    items = []
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        # RSS 2.0
        for item in root.findall('.//item'):
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            pub_date = item.findtext('pubDate', '') or item.findtext('published', '')
            description = item.findtext('description', '')
            if not title or not link:
                continue
            summary = strip_html(description)
            combined = f"{title} {summary}"
            score, label = score_sentiment(combined)
            items.append({
                "title": title, "link": link, "source": source_name,
                "published": parse_date(pub_date), "summary": summary,
                "sentiment_score": score, "sentiment_label": label,
            })
        # Atom
        for entry in root.findall('atom:entry', ns):
            title = entry.findtext('atom:title', '', ns).strip()
            link_el = entry.find('atom:link', ns)
            link = link_el.get('href', '') if link_el is not None else ''
            pub_date = entry.findtext('atom:published', '', ns) or entry.findtext('atom:updated', '', ns)
            description = entry.findtext('atom:summary', '', ns) or entry.findtext('atom:content', '', ns)
            if not title or not link:
                continue
            summary = strip_html(description)
            combined = f"{title} {summary}"
            score, label = score_sentiment(combined)
            items.append({
                "title": title, "link": link, "source": source_name,
                "published": parse_date(pub_date), "summary": summary,
                "sentiment_score": score, "sentiment_label": label,
            })
    except Exception:
        pass
    return items

def fetch_single_feed_to_db(source_name, url, db_path):
    items = fetch_feed(source_name, url)
    if not items:
        return source_name, 0
    try:
        db = sqlite3.connect(db_path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        now_utc = utc_iso(datetime.now(timezone.utc))
        count = 0
        for item in items:
            try:
                db.execute("""
                    INSERT OR IGNORE INTO news (title, link, source, published, fetched_at, summary, sentiment_score, sentiment_label)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item["title"], item["link"], item["source"],
                    item["published"], now_utc, item["summary"],
                    item["sentiment_score"], item["sentiment_label"]
                ))
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    count += 1
            except Exception:
                pass
        db.commit()
        db.close()
        return source_name, count
    except Exception:
        return source_name, 0

def cleanup_old_entries(db):
    """Remove entries older than MAX_AGE_DAYS."""
    cutoff = utc_iso(datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS))
    db.execute("DELETE FROM news WHERE published < ?", (cutoff,))
    db.commit()

# ---------------------------------------------------------------------------
# Semantic Deduplication
# ---------------------------------------------------------------------------

_embedding_model = None
_embedding_lock = Lock()

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer
                _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def mark_new_duplicates(db):
    """Compute embeddings for new items and mark semantic duplicates."""
    new_rows = db.execute(
        "SELECT id, title FROM news WHERE embedding IS NULL"
    ).fetchall()
    if not new_rows:
        return

    model = get_embedding_model()
    new_titles = [r["title"] for r in new_rows]
    new_ids = [r["id"] for r in new_rows]
    new_embeddings = model.encode(new_titles, normalize_embeddings=True)

    # Load recent existing embeddings for comparison (last 48h)
    cutoff = utc_iso(datetime.now(timezone.utc) - timedelta(hours=48))
    existing_rows = db.execute(
        "SELECT id, embedding FROM news WHERE embedding IS NOT NULL AND fetched_at >= ?",
        (cutoff,)
    ).fetchall()

    existing_embeddings = None
    if existing_rows:
        existing_embeddings = np.array([
            np.frombuffer(r["embedding"], dtype=np.float32) for r in existing_rows
        ])

    for i in range(len(new_ids)):
        emb = new_embeddings[i]
        is_dup = False

        # Check against existing items with embeddings
        if existing_embeddings is not None and len(existing_embeddings) > 0:
            sims = existing_embeddings @ emb
            if float(np.max(sims)) >= DEDUP_THRESHOLD:
                is_dup = True

        # Check against earlier items in the same batch
        if not is_dup and i > 0:
            batch_sims = new_embeddings[:i] @ emb
            if float(np.max(batch_sims)) >= DEDUP_THRESHOLD:
                is_dup = True

        db.execute(
            "UPDATE news SET embedding = ?, duplicate = ? WHERE id = ?",
            (emb.tobytes(), 1 if is_dup else 0, new_ids[i])
        )

    db.commit()

def refresh_feeds_parallel(db):
    results = {}
    threads = []
    result_lock = Lock()

    def worker(name, url):
        src, count = fetch_single_feed_to_db(name, url, DB_PATH)
        with result_lock:
            results[src] = count

    for name, url in FEEDS.items():
        t = Thread(target=worker, args=(name, url))
        t.daemon = True
        threads.append(t)
        t.start()

    deadline = time.time() + 20
    for t in threads:
        remaining = max(0.1, deadline - time.time())
        t.join(timeout=remaining)

    total_new = sum(results.values())
    db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
               ("last_refresh", utc_iso(datetime.now(timezone.utc))))
    db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
               ("source_status", json.dumps(results)))
    db.commit()
    cleanup_old_entries(db)
    if total_new > 0:
        try:
            mark_new_duplicates(db)
        except Exception:
            pass
    return total_new, results

def maybe_refresh(db):
    row = db.execute("SELECT value FROM meta WHERE key='last_refresh'").fetchone()
    if row:
        try:
            last = datetime.fromisoformat(row[0])
            now = datetime.now(timezone.utc)
            if (now - last).total_seconds() < STALE_SECONDS:
                return False
        except Exception:
            pass
    refresh_feeds_parallel(db)
    return True

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/news")
def api_news():
    db = get_db()
    maybe_refresh(db)
    limit = request.args.get("limit", 200, type=int)
    source = request.args.get("source", "all")
    sentiment = request.args.get("sentiment", "all")
    query = request.args.get("q", "")
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    limit = max(1, min(limit, 500))

    sql = "SELECT id, title, link, source, published, fetched_at, summary, sentiment_score, sentiment_label, tags, duplicate FROM news WHERE 1=1"
    bind = []
    if source and source != "all":
        sql += " AND source = ?"
        bind.append(source)
    if sentiment and sentiment != "all":
        sql += " AND sentiment_label = ?"
        bind.append(sentiment)
    if query:
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        bind.extend([f"%{query}%", f"%{query}%"])
    if date_from:
        sql += " AND published >= ?"
        bind.append(date_from)
    if date_to:
        to_val = date_to + "T23:59:59+00:00" if len(date_to) == 10 else date_to
        sql += " AND published <= ?"
        bind.append(to_val)
    sql += " ORDER BY published DESC, id DESC LIMIT ?"
    bind.append(limit)

    rows = db.execute(sql, bind).fetchall()
    items = [dict(r) for r in rows]
    db.close()
    return jsonify({"count": len(items), "items": items})

@app.route("/api/sources")
def api_sources():
    db = get_db()
    maybe_refresh(db)
    row = db.execute("SELECT value FROM meta WHERE key='source_status'").fetchone()
    status = json.loads(row[0]) if row else {}
    sources = []
    for name, url in FEEDS.items():
        count = db.execute("SELECT COUNT(*) FROM news WHERE source=?", (name,)).fetchone()[0]
        sources.append({
            "name": name, "url": url,
            "last_fetch_items": status.get(name, 0),
            "total_items": count, "active": True
        })
    db.close()
    return jsonify({"sources": sources})

@app.route("/api/stats")
def api_stats():
    db = get_db()
    maybe_refresh(db)
    total = db.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    by_source = {}
    for row in db.execute("SELECT source, COUNT(*) as cnt FROM news GROUP BY source ORDER BY cnt DESC"):
        by_source[row[0]] = row[1]
    by_sentiment = {}
    for row in db.execute("SELECT sentiment_label, COUNT(*) as cnt FROM news GROUP BY sentiment_label"):
        by_sentiment[row[0]] = row[1]
    avg_score = db.execute("SELECT AVG(sentiment_score) FROM news").fetchone()[0] or 0
    last_refresh_row = db.execute("SELECT value FROM meta WHERE key='last_refresh'").fetchone()
    last_refresh = last_refresh_row[0] if last_refresh_row else None
    db.close()
    return jsonify({
        "total_items": total,
        "by_source": by_source,
        "by_sentiment": by_sentiment,
        "avg_sentiment_score": round(avg_score, 4),
        "last_refresh": last_refresh,
        "feed_count": len(FEEDS)
    })

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    db = get_db()
    new_count, status = refresh_feeds_parallel(db)
    db.close()
    return jsonify({
        "refreshed": True,
        "new_items": new_count,
        "source_status": status,
        "timestamp": utc_iso(datetime.now(timezone.utc))
    })

@app.route("/api/docs")
def api_docs():
    return jsonify({
        "api": "SIGNAL News Trading Terminal API",
        "version": "1.0",
        "endpoints": [
            {
                "method": "GET", "path": "/api/news",
                "description": "Get latest news items",
                "params": {
                    "limit": "Number of items (default 200, max 500)",
                    "source": "Filter by source name (default 'all')",
                    "sentiment": "Filter by sentiment: bullish, bearish, neutral (default 'all')",
                    "q": "Keyword search in title and summary",
                    "from": "Filter from date (ISO 8601, e.g. '2026-03-01')",
                    "to": "Filter to date (ISO 8601, e.g. '2026-03-02')"
                }
            },
            {"method": "GET", "path": "/api/sources", "description": "List all active feed sources with item counts"},
            {"method": "GET", "path": "/api/stats", "description": "Aggregated feed statistics"},
            {"method": "POST", "path": "/api/refresh", "description": "Force refresh all feeds immediately"},
            {"method": "GET", "path": "/api/docs", "description": "This API documentation"}
        ],
        "examples": [
            'curl "http://localhost:8000/api/news?limit=10&sentiment=bullish"',
            'curl "http://localhost:8000/api/sources"',
            'curl "http://localhost:8000/api/stats"',
            'curl -X POST "http://localhost:8000/api/refresh"'
        ]
    })

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Starting SIGNAL News Terminal on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
