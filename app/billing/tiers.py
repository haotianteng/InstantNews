"""Tier definitions — single source of truth for feature gating.

Each tier defines:
- features: dict of feature flags (True/False)
- limits: dict of numeric limits (max items, rate limits, etc.)
- price_monthly_cents: Stripe price in cents (0 for free)

Features marked STATUS:IMPLEMENTED are enforced today.
Features marked STATUS:FUTURE require new backend work before they can be gated.
See docs/future-features.md for implementation details.
"""

TIERS = {
    "free": {
        "name": "Free",
        "price_monthly_cents": 0,
        "features": {
            # --- IMPLEMENTED: gated now ---
            "news_feed": True,
            "keyword_search": True,
            "source_filter": True,
            "sentiment_filter": False,       # hides sentiment_score/label from response
            "deduplication": False,           # hides duplicate field, no DUP badge
            "date_range_filter": False,       # ignores from/to params

            # --- FUTURE: requires new backend/frontend work ---
            "extended_sources": False,        # additional premium RSS feeds
            "ai_ticker_recommendations": False,  # LLM-powered ticker analysis
            "price_analysis": False,          # stock price correlation
            "advanced_analytics": False,      # charts, heatmaps, trends
            "api_access": False,              # programmatic API key access
            "export_csv": False,              # export news to CSV
            "custom_alerts": False,           # email/webhook alerts on keywords
            "watchlist": False,               # personal ticker watchlist
        },
        "limits": {
            "max_items_per_request": 50,
            "api_rate_per_minute": 10,
            "refresh_interval_min_ms": 30000,
            "max_saved_searches": 0,
            "history_days": 7,               # only last 7 days of news
        },
    },
    "plus": {
        "name": "Plus",
        "price_monthly_cents": 1499,  # $14.99
        "features": {
            # --- IMPLEMENTED ---
            "news_feed": True,
            "keyword_search": True,
            "source_filter": True,
            "sentiment_filter": True,
            "deduplication": True,
            "date_range_filter": True,

            # --- FUTURE ---
            "extended_sources": True,
            "ai_ticker_recommendations": False,
            "price_analysis": False,
            "advanced_analytics": False,
            "api_access": True,
            "export_csv": True,
            "custom_alerts": False,
            "watchlist": True,
        },
        "limits": {
            "max_items_per_request": 200,
            "api_rate_per_minute": 60,
            "refresh_interval_min_ms": 5000,
            "max_saved_searches": 10,
            "history_days": 365,
        },
    },
    "max": {
        "name": "Max",
        "price_monthly_cents": 3999,  # $39.99
        "features": {
            # --- IMPLEMENTED ---
            "news_feed": True,
            "keyword_search": True,
            "source_filter": True,
            "sentiment_filter": True,
            "deduplication": True,
            "date_range_filter": True,

            # --- FUTURE ---
            "extended_sources": True,
            "ai_ticker_recommendations": True,
            "price_analysis": True,
            "advanced_analytics": True,
            "api_access": True,
            "export_csv": True,
            "custom_alerts": True,
            "watchlist": True,
        },
        "limits": {
            "max_items_per_request": 500,
            "api_rate_per_minute": 120,
            "refresh_interval_min_ms": 3000,
            "max_saved_searches": 50,
            "history_days": 1825,  # 5 years
        },
    },
}


def get_tier(tier_name):
    """Get tier definition by name. Defaults to free."""
    return TIERS.get(tier_name, TIERS["free"])


def has_feature(tier_name, feature):
    """Check if a tier has a specific feature."""
    tier = get_tier(tier_name)
    return tier["features"].get(feature, False)


def get_limit(tier_name, limit_key):
    """Get a numeric limit for a tier."""
    tier = get_tier(tier_name)
    return tier["limits"].get(limit_key)


def get_features(tier_name):
    """Get all feature flags for a tier."""
    return dict(get_tier(tier_name)["features"])


def get_all_tiers_summary():
    """Return tier comparison for pricing page."""
    return {
        name: {
            "name": t["name"],
            "price_monthly_cents": t["price_monthly_cents"],
            "features": t["features"],
            "limits": t["limits"],
        }
        for name, t in TIERS.items()
    }
