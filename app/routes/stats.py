"""GET /api/stats — aggregated feed statistics."""

import time
from typing import Any

from flask import Blueprint, jsonify, current_app, g
from sqlalchemy import func

from app.models import News, Meta
from app.billing.tiers import has_feature

stats_bp = Blueprint("stats", __name__)

# Simple in-memory cache: {"data": ..., "ts": float}
_stats_cache: dict[str, Any] = {}
STATS_CACHE_TTL = 30  # seconds


def _current_tier():
    """Get the current user's tier, defaulting to free."""
    if g.get("current_user") and g.current_user is not None:
        return g.current_user.tier
    return "free"


def _fetch_stats_data(session_factory, config) -> dict[str, Any]:
    """Query aggregate stats from the database. Result is tier-agnostic."""
    now = time.monotonic()
    cached = _stats_cache.get("data")
    if cached and (now - _stats_cache.get("ts", 0)) < STATS_CACHE_TTL:
        return cached

    session = session_factory()
    try:
        total = session.query(func.count(News.id)).scalar()

        by_source = {}
        for source, cnt in session.query(News.source, func.count(News.id)).group_by(
            News.source
        ).order_by(func.count(News.id).desc()).all():
            by_source[source] = cnt

        by_sentiment = {}
        for label, cnt in session.query(
            News.sentiment_label, func.count(News.id)
        ).group_by(News.sentiment_label).all():
            by_sentiment[label] = cnt

        avg_score = session.query(func.avg(News.sentiment_score)).scalar() or 0

        last_refresh_row = session.query(Meta).filter_by(key="last_refresh").first()
        last_refresh = last_refresh_row.value if last_refresh_row else None
    finally:
        session.close()

    result = {
        "total_items": total,
        "by_source": by_source,
        "by_sentiment": by_sentiment,
        "avg_sentiment_score": round(avg_score, 4),
        "last_refresh": last_refresh,
        "feed_count": len(config.FEEDS),
    }

    _stats_cache["data"] = result
    _stats_cache["ts"] = now
    return result


@stats_bp.route("/api/stats")
def api_stats():
    config = current_app.config["APP_CONFIG"]
    session_factory = current_app.config["SESSION_FACTORY"]

    tier = _current_tier()
    data = _fetch_stats_data(session_factory, config)

    # Build tier-appropriate response (don't mutate cached dict)
    result = {
        "total_items": data["total_items"],
        "by_source": data["by_source"],
        "last_refresh": data["last_refresh"],
        "feed_count": data["feed_count"],
    }

    # Only include sentiment data for tiers with the sentiment_filter feature
    if has_feature(tier, "sentiment_filter"):
        result["by_sentiment"] = data["by_sentiment"]
        result["avg_sentiment_score"] = data["avg_sentiment_score"]

    return jsonify(result)
