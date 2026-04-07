"""Tier definitions — single source of truth for feature gating AND display.

Every tier parameter lives here: backend gating (features, limits) and
frontend display (prices, descriptions, feature lists, CTA labels).
The /api/pricing endpoint exposes this data so the frontend never
hardcodes plan details.

Features marked STATUS:IMPLEMENTED are enforced today.
Features marked STATUS:FUTURE require new backend work before they can be gated.
See docs/future-features.md for implementation details.
"""

# Canonical display order — controls card layout left-to-right.
TIER_ORDER = ["free", "pro", "max"]

TIERS = {
    "free": {
        "name": "Free",
        "visible": True,
        "price_monthly_cents": 0,
        "trial_period_days": 0,
        "features": {
            # --- IMPLEMENTED: gated now ---
            "terminal_access": False,
            "news_feed": True,
            "keyword_search": True,
            "source_filter": True,
            "sentiment_filter": False,
            "deduplication": False,
            "date_range_filter": False,
            # --- FUTURE ---
            "extended_sources": False,
            "ai_ticker_recommendations": False,
            "price_analysis": False,
            "advanced_analytics": False,
            "api_access": False,
            "export_csv": False,
            "custom_alerts": False,
            "watchlist": False,
        },
        "limits": {
            "max_items_per_request": 50,
            "api_rate_per_minute": 30,
            "refresh_interval_min_ms": 30000,
            "max_saved_searches": 0,
            "history_days": 7,
        },
        "display": {
            "price": "$0",
            "price_period": "/mo",
            "description": "Get started with real-time news",
            "trial_text": None,
            "featured": False,
            "cta_label": "Open Terminal",
            "cta_style": "outline",
            "cta_action": "link",       # "link" = navigate, "checkout" = Stripe
            "cta_href": "/terminal",
            "feature_list": [
                {"included": True,  "text": "Real-time news feed"},
                {"included": True,  "text": "15+ sources"},
                {"included": True,  "text": "Keyword search"},
                {"included": True,  "text": "Source filtering"},
                {"included": False, "text": "Sentiment analysis"},
                {"included": False, "text": "Duplicate detection"},
                {"included": False, "text": "Date range filtering"},
                {"included": False, "text": "API access"},
            ],
            "limits_summary": "50 items/req \u00b7 7-day history",
        },
    },
    "pro": {
        "name": "Pro",
        "visible": True,
        "price_monthly_cents": 1499,
        "trial_period_days": 30,
        "features": {
            "terminal_access": True,
            "news_feed": True,
            "keyword_search": True,
            "source_filter": True,
            "sentiment_filter": True,
            "deduplication": True,
            "date_range_filter": True,
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
            "api_rate_per_minute": 300,
            "refresh_interval_min_ms": 5000,
            "max_saved_searches": 10,
            "history_days": 365,
        },
        "display": {
            "price": "$14.99",
            "price_period": "/mo",
            "description": "Full analysis for active traders",
            "trial_text": "30-day free trial \u2014 cancel anytime",
            "featured": True,
            "cta_label": "Start Free Trial",
            "cta_style": "primary",
            "cta_action": "checkout",
            "cta_href": None,
            "feature_list": [
                {"included": True, "text": "Everything in Free"},
                {"included": True, "text": "AI sentiment scoring"},
                {"included": True, "text": "Duplicate detection"},
                {"included": True, "text": "Date range filtering"},
                {"included": True, "text": "API access"},
                {"included": True, "text": "CSV export"},
                {"included": True, "text": "1-year history"},
                {"included": True, "text": "Watchlist"},
            ],
            "limits_summary": "200 items/req \u00b7 300 req/min",
        },
    },
    "max": {
        "name": "Max",
        "visible": True,
        "price_monthly_cents": 3999,
        "trial_period_days": 0,
        "features": {
            "terminal_access": True,
            "news_feed": True,
            "keyword_search": True,
            "source_filter": True,
            "sentiment_filter": True,
            "deduplication": True,
            "date_range_filter": True,
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
            "api_rate_per_minute": 1000,
            "refresh_interval_min_ms": 3000,
            "max_saved_searches": 50,
            "history_days": 1825,
        },
        "display": {
            "price": "$39.99",
            "price_period": "/mo",
            "description": "Maximum power for professional traders",
            "trial_text": None,
            "featured": False,
            "cta_label": "Subscribe",
            "cta_style": "outline",
            "cta_action": "checkout",
            "cta_href": None,
            "feature_list": [
                {"included": True, "text": "Everything in Pro"},
                {"included": True, "text": "AI ticker recommendations"},
                {"included": True, "text": "Price analysis"},
                {"included": True, "text": "Advanced analytics"},
                {"included": True, "text": "Custom alerts"},
                {"included": True, "text": "5-year history"},
                {"included": True, "text": "500 items/req"},
                {"included": True, "text": "1,000 req/min"},
            ],
            "limits_summary": "500 items/req \u00b7 1,000 req/min",
        },
    },
}

# Backward compatibility alias: "plus" -> "pro"
TIERS["plus"] = TIERS["pro"]


def get_tier(tier_name):
    """Get tier definition by name. Defaults to free."""
    return TIERS.get(tier_name, TIERS["free"])


def has_feature(tier_name, feature):
    """Check if a tier has a specific feature."""
    return get_tier(tier_name)["features"].get(feature, False)


def get_limit(tier_name, limit_key):
    """Get a numeric limit for a tier."""
    return get_tier(tier_name)["limits"].get(limit_key)


def get_features(tier_name):
    """Get all feature flags for a tier."""
    return dict(get_tier(tier_name)["features"])


def get_all_tiers_summary():
    """Return ordered list of visible tiers with display data for the frontend."""
    result = []
    for name in TIER_ORDER:
        t = TIERS[name]
        if not t.get("visible", True):
            continue
        result.append({
            "key": name,
            "name": t["name"],
            "price_monthly_cents": t["price_monthly_cents"],
            "trial_period_days": t.get("trial_period_days", 0),
            "features": t["features"],
            "limits": t["limits"],
            "display": t["display"],
        })
    return result
