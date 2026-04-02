"""GET /api/sources — list active feed sources with item counts."""

import json

from flask import Blueprint, jsonify, current_app
from sqlalchemy import func

from app.models import News, Meta
from app.services.feed_refresh import maybe_refresh

sources_bp = Blueprint("sources", __name__)


@sources_bp.route("/api/sources")
def api_sources():
    config = current_app.config["APP_CONFIG"]
    session_factory = current_app.config["SESSION_FACTORY"]
    maybe_refresh(session_factory, config)

    session = session_factory()
    try:
        row = session.query(Meta).filter_by(key="source_status").first()
        status = json.loads(row.value) if row else {}

        sources = []
        for name, url in config.FEEDS.items():
            count = session.query(func.count(News.id)).filter(
                News.source == name
            ).scalar()
            sources.append({
                "name": name,
                "url": url,
                "last_fetch_items": status.get(name, 0),
                "total_items": count,
                "active": True,
            })
    finally:
        session.close()

    return jsonify({"sources": sources})
