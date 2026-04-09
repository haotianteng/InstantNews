"""Application configuration loaded from environment variables."""

import os


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
    PORT = int(os.environ.get("PORT", "8000"))
    STALE_SECONDS = int(os.environ.get("STALE_SECONDS", "30"))
    FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "5"))
    MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", str(5 * 365)))
    DEDUP_THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.85"))
    WORKER_INTERVAL_SECONDS = int(os.environ.get("WORKER_INTERVAL_SECONDS", "30"))
    WORKER_ENABLED = os.environ.get("WORKER_ENABLED", "true").lower() == "true"

    # WeChat OAuth (CN social login, pending approval)
    WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
    WECHAT_REDIRECT_URI = os.environ.get(
        "WECHAT_REDIRECT_URI", "https://www.instnews.net/api/auth/wechat/callback"
    )

    # App JWT (for email/password + WeChat session tokens)
    APP_JWT_SECRET = os.environ.get("APP_JWT_SECRET", "")
    APP_JWT_EXPIRY_DAYS = int(os.environ.get("APP_JWT_EXPIRY_DAYS", "7"))

    # Email service (Gmail API via service account delegation)
    GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "noreply@instnews.net")
    BASE_URL = os.environ.get("BASE_URL", "https://www.instnews.net")

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

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


class TestConfig(Config):
    DATABASE_URL = "sqlite://"  # in-memory
    TESTING = True
    WORKER_ENABLED = False
    STALE_SECONDS = 0
    FETCH_TIMEOUT = 1
