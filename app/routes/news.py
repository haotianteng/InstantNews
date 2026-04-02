"""GET /api/news — query news items with filtering."""

from flask import Blueprint, request, jsonify, current_app

from app.models import News
from app.services.feed_refresh import maybe_refresh
from app.middleware.tier_gate import tier_limit
from app.billing.tiers import has_feature

news_bp = Blueprint("news", __name__)


def _current_tier():
    from flask import g
    if g.get("current_user") and g.current_user is not None:
        return g.current_user.tier
    return "free"


@news_bp.route("/api/news")
def api_news():
    config = current_app.config["APP_CONFIG"]
    session_factory = current_app.config["SESSION_FACTORY"]
    maybe_refresh(session_factory, config)

    tier = _current_tier()
    max_limit = tier_limit("max_items_per_request") or 200

    session = session_factory()
    try:
        limit = request.args.get("limit", max_limit, type=int)
        source = request.args.get("source", "all")
        sentiment = request.args.get("sentiment", "all")
        query = request.args.get("q", "")
        date_from = request.args.get("from", "")
        date_to = request.args.get("to", "")

        # Cap limit to tier maximum
        limit = max(1, min(limit, max_limit))

        q = session.query(News)

        if source and source != "all":
            q = q.filter(News.source == source)
        if sentiment and sentiment != "all":
            q = q.filter(News.sentiment_label == sentiment)
        if query:
            like_pattern = f"%{query}%"
            q = q.filter(
                (News.title.like(like_pattern)) | (News.summary.like(like_pattern))
            )

        # Date range: only if tier has the feature
        if has_feature(tier, "date_range_filter"):
            if date_from:
                q = q.filter(News.published >= date_from)
            if date_to:
                to_val = date_to + "T23:59:59+00:00" if len(date_to) == 10 else date_to
                q = q.filter(News.published <= to_val)

        # History limit: restrict how far back free users can see
        history_days = tier_limit("history_days")
        if history_days and history_days < 1825:
            from datetime import datetime, timedelta, timezone
            from app.services.feed_parser import utc_iso
            cutoff = utc_iso(datetime.now(timezone.utc) - timedelta(days=history_days))
            q = q.filter(News.published >= cutoff)

        q = q.order_by(News.published.desc(), News.id.desc()).limit(limit)
        rows = q.all()
        items = [_shape_item(r.to_dict(), tier) for r in rows]
    finally:
        session.close()

    return jsonify({"count": len(items), "items": items})


def _shape_item(item, tier):
    """Strip fields that the user's tier doesn't have access to."""
    if not has_feature(tier, "sentiment_filter"):
        item.pop("sentiment_score", None)
        item.pop("sentiment_label", None)
    if not has_feature(tier, "deduplication"):
        item.pop("duplicate", None)
    return item
