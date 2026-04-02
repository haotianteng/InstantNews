"""GET /api/stats — aggregated feed statistics."""

from flask import Blueprint, jsonify, current_app
from sqlalchemy import func

from app.models import News, Meta
from app.services.feed_refresh import maybe_refresh

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats")
def api_stats():
    config = current_app.config["APP_CONFIG"]
    session_factory = current_app.config["SESSION_FACTORY"]
    maybe_refresh(session_factory, config)

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

    return jsonify({
        "total_items": total,
        "by_source": by_source,
        "by_sentiment": by_sentiment,
        "avg_sentiment_score": round(avg_score, 4),
        "last_refresh": last_refresh,
        "feed_count": len(config.FEEDS),
    })
