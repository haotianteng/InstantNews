"""Application configuration loaded from environment variables.

Falls back to AWS Secrets Manager for secrets not in env vars (production).
"""

import json
import os


def _load_secret(key, secret_id="instantnews/app"):
    """Load a single key from Secrets Manager if not in env vars."""
    val = os.environ.get(key, "")
    if val:
        return val
    try:
        import boto3
        client = boto3.client("secretsmanager", region_name="us-east-1")
        resp = client.get_secret_value(SecretId=secret_id)
        secrets = json.loads(resp["SecretString"])
        return secrets.get(key, "")
    except Exception:
        return ""


def _build_database_url():
    """Construct DATABASE_URL from individual DB_* env vars, or use DATABASE_URL directly."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    # Construct from components (set by ECS task definition)
    host = os.environ.get("DB_HOST")
    if host:
        port = os.environ.get("DB_PORT", "5432")
        name = os.environ.get("DB_NAME", "signal_news")
        user = os.environ.get("DB_USER", "signal")
        password = os.environ.get("DB_PASSWORD", "")
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///data/news_terminal.db"


class Config:
    DATABASE_URL = _build_database_url()
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    PORT = int(os.environ.get("PORT", "8000"))
    STALE_SECONDS = int(os.environ.get("STALE_SECONDS", "30"))
    FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "5"))
    MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", str(5 * 365)))
    DEDUP_THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.85"))
    WORKER_INTERVAL_SECONDS = int(os.environ.get("WORKER_INTERVAL_SECONDS", "15"))
    WORKER_ENABLED = os.environ.get("WORKER_ENABLED", "true").lower() == "true"
    BEDROCK_ENABLED = os.environ.get("BEDROCK_ENABLED", "true").lower() == "true"

    # WeChat OAuth (CN social login, pending approval)
    WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
    WECHAT_REDIRECT_URI = os.environ.get(
        "WECHAT_REDIRECT_URI", "https://www.instnews.net/api/auth/wechat/callback"
    )

    # App JWT (for email/password + WeChat session tokens)
    APP_JWT_SECRET = _load_secret("APP_JWT_SECRET")
    APP_JWT_EXPIRY_DAYS = int(os.environ.get("APP_JWT_EXPIRY_DAYS", "7"))

    # Email service (Gmail API via service account delegation)
    GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "noreply@instnews.net")
    BASE_URL = os.environ.get("BASE_URL", "https://www.instnews.net")

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    FEEDS = {
        "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "CNBC_World": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
        "Reuters_Business": "https://news.google.com/rss/search?q=when:24h+site:reuters.com+business&hl=en-US&gl=US&ceid=US:en",
        "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "MarketWatch_Markets": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
        "Investing_com": "https://www.investing.com/rss/news.rss",
        "Yahoo_Finance": "https://finance.yahoo.com/news/rssindex",
        "Nasdaq": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
        "SeekingAlpha": "https://seekingalpha.com/market_currents.xml",
        "Benzinga": "https://www.benzinga.com/feed",
        "AP_News": "https://news.google.com/rss/search?q=when:24h+site:apnews.com+business&hl=en-US&gl=US&ceid=US:en",
        "Bloomberg_Business": "https://feeds.bloomberg.com/economics/news.rss",
        "Bloomberg_Markets": "https://feeds.bloomberg.com/markets/news.rss",
        "BBC_Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "Google_News_Business": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB",
    }

    # Diplomatic social sources (Twitter + Truth Social)
    # Env var name is X_API_BEARER_TOKEN to match .env + AWS Secrets Manager key.
    X_API_BEARER_TOKEN = _load_secret("X_API_BEARER_TOKEN")
    SOCIAL_SOURCES_ENABLED = os.environ.get("SOCIAL_SOURCES_ENABLED", "true").lower() == "true"
    TWITTER_MAX_RESULTS_PER_RUN = int(os.environ.get("TWITTER_MAX_RESULTS_PER_RUN", "100"))
    # Per-source poll intervals (seconds). 5s for Twitter — rate-limited at 450/15m
    # per-app, we use 180/15m = 40% of cap with since_id keeping costs flat.
    TWITTER_POLL_INTERVAL_SECONDS = int(os.environ.get("TWITTER_POLL_INTERVAL_SECONDS", "5"))
    TRUTH_SOCIAL_POLL_INTERVAL_SECONDS = int(os.environ.get("TRUTH_SOCIAL_POLL_INTERVAL_SECONDS", "60"))


class TestConfig(Config):
    DATABASE_URL = "sqlite://"  # in-memory
    TESTING = True
    WORKER_ENABLED = False
    STALE_SECONDS = 0
    FETCH_TIMEOUT = 1
