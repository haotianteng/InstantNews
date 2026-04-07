"""GET /api/sources — list active feed sources with item counts."""

import json
import time
from typing import Any

from flask import Blueprint, jsonify, current_app
from sqlalchemy import func

from app.models import News, Meta

sources_bp = Blueprint("sources", __name__)

# Simple in-memory cache: {"data": ..., "ts": float}
_sources_cache: dict[str, Any] = {}
SOURCES_CACHE_TTL = 30  # seconds


@sources_bp.route("/api/sources")
def api_sources():
    config = current_app.config["APP_CONFIG"]
    session_factory = current_app.config["SESSION_FACTORY"]

    now = time.monotonic()
    cached = _sources_cache.get("data")
    if cached and (now - _sources_cache.get("ts", 0)) < SOURCES_CACHE_TTL:
        return jsonify({"sources": cached})

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

    _sources_cache["data"] = sources
    _sources_cache["ts"] = now

    return jsonify({"sources": sources})
