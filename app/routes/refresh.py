"""POST /api/refresh — force refresh all feeds."""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, current_app

from app.auth.middleware import require_auth
from app.services.feed_refresh import refresh_feeds_parallel
from app.services.feed_parser import utc_iso

refresh_bp = Blueprint("refresh", __name__)


@refresh_bp.route("/api/refresh", methods=["POST"])
@require_auth
def api_refresh():
    config = current_app.config["APP_CONFIG"]
    session_factory = current_app.config["SESSION_FACTORY"]
    new_count, status = refresh_feeds_parallel(session_factory, config)
    return jsonify({
        "refreshed": True,
        "new_items": new_count,
        "source_status": status,
        "timestamp": utc_iso(datetime.now(timezone.utc)),
    })
