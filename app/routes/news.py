"""GET /api/news — query news items with filtering."""

from flask import Blueprint, request, jsonify, current_app

from app.models import News
from app.middleware.tier_gate import tier_limit
from app.billing.tiers import has_feature

news_bp = Blueprint("news", __name__)


def _current_tier():
    from flask import g
    if g.get("current_user") and g.current_user is not None:
        return g.current_user.tier
    return "free"


# Absolute safety cap on a single /api/news response regardless of tier
# or date-range override. Keeps accidental runaway queries (e.g. a user
# dragging a year-wide range) from blowing up the response payload.
HARD_LIMIT_ITEMS = 2000


@news_bp.route("/api/news")
def api_news():
    session_factory = current_app.config["SESSION_FACTORY"]

    tier = _current_tier()
    max_limit = tier_limit("max_items_per_request") or 200

    session = session_factory()
    try:
        limit = request.args.get("limit", max_limit, type=int)
        source = request.args.get("source", "all")
        source_type = request.args.get("source_type", "all")
        sentiment = request.args.get("sentiment", "all")
        query = request.args.get("q", "")
        date_from = request.args.get("from", "")
        date_to = request.args.get("to", "")
        before = request.args.get("before", "", type=str)  # cursor: News.id < before

        # Cap limit to tier maximum, but when an explicit date range is set,
        # allow up to 5x the tier limit (still hard-capped at HARD_LIMIT_ITEMS).
        # This is what unblocks "look at news from last Tuesday" — the default
        # 200-row cap otherwise truncates the query before the date window
        # even reaches the client.
        if (date_from or date_to) and has_feature(tier, "date_range_filter"):
            effective_cap = min(max_limit * 5, HARD_LIMIT_ITEMS)
        else:
            effective_cap = max_limit
        limit = max(1, min(limit, effective_cap))

        q = session.query(News)

        if source and source != "all":
            q = q.filter(News.source == source)
        if source_type == "social":
            q = q.filter(
                (News.source.like("Twitter/%")) | (News.source.like("TruthSocial/%"))
            )
        elif source_type == "rss":
            q = q.filter(
                ~(News.source.like("Twitter/%")) & ~(News.source.like("TruthSocial/%"))
            )
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

        # Cursor pagination: ?before=<news_id> returns items strictly older than
        # that id. Combined with ORDER BY published DESC, id DESC, this lets
        # the frontend load older pages on scroll-down without duplicates.
        if before:
            try:
                before_id = int(before)
                q = q.filter(News.id < before_id)
            except (TypeError, ValueError):
                pass

        q = q.order_by(News.published.desc(), News.id.desc()).limit(limit)
        rows = q.all()
        items = [_shape_item(r.to_dict(), tier) for r in rows]
    finally:
        session.close()

    # Cursor for the next older page: id of the last item in this response.
    next_before = items[-1]["id"] if items else None
    return jsonify({"count": len(items), "items": items, "next_before": next_before})


def _shape_item(item, tier):
    """Strip or mask fields that the user's tier doesn't have access to."""
    if not has_feature(tier, "sentiment_filter"):
        item.pop("sentiment_score", None)
        item.pop("sentiment_label", None)
    if not has_feature(tier, "deduplication"):
        item.pop("duplicate", None)
    # Ticker recommendations require ai_ticker_recommendations feature
    if not has_feature(tier, "ai_ticker_recommendations"):
        item.pop("target_asset", None)
        item.pop("asset_type", None)
        item.pop("confidence", None)
        item.pop("risk_level", None)
        item.pop("tradeable", None)
        item.pop("reasoning", None)
    return item
