"""API usage tracking routes."""

from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, g, current_app
from sqlalchemy import func

from app.auth.middleware import require_auth
from app.models import ApiUsage

usage_bp = Blueprint("usage", __name__)


@usage_bp.route("/api/usage")
@require_auth
def get_usage():
    """Return the current user's API usage stats.

    Returns daily counts for the last 30 days, plus totals.
    """
    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        period_start = now.replace(day=1).strftime("%Y-%m-%d")  # 1st of month

        # Daily breakdown (last 30 days)
        rows = db.query(ApiUsage).filter(
            ApiUsage.user_id == g.current_user.id,
            ApiUsage.date >= thirty_days_ago,
        ).order_by(ApiUsage.date.desc()).all()

        daily = [{"date": r.date, "requests": r.request_count} for r in rows]

        # Aggregates
        today_count = 0
        week_count = 0
        month_count = 0
        for r in rows:
            if r.date == today:
                today_count = r.request_count
            if r.date >= seven_days_ago:
                week_count += r.request_count
            if r.date >= period_start:
                month_count += r.request_count

        # All-time total
        total = db.query(func.sum(ApiUsage.request_count)).filter_by(
            user_id=g.current_user.id
        ).scalar() or 0

        return jsonify({
            "today": today_count,
            "last_7_days": week_count,
            "this_month": month_count,
            "all_time": total,
            "daily": daily,
            "period_start": period_start,
        })
    finally:
        db.close()
