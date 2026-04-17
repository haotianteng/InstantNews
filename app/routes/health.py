"""GET /health — liveness probe reporting Redis + DB status.

Separate from ``/api/stats`` (which requires a tier check and touches the
News/Meta tables). ``/health`` is cheap, anonymous, and designed for
container + load-balancer health probes.

Response shape::

    {"status": "ok",    "redis": "ok", "db": "ok"}
    {"status": "error", "redis": "error: ...", "db": "ok"}

HTTP status is 200 when both subsystems are healthy, 503 otherwise.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

logger = logging.getLogger("signal")

health_bp = Blueprint("health", __name__)


def _check_redis() -> str:
    try:
        from app.cache.redis_client import get_redis

        client = get_redis()
        client.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001 — health check surfaces all errors
        msg = f"error: {type(exc).__name__}: {exc}"
        logger.warning("Redis health check failed: %s", msg)
        return msg


def _check_db() -> str:
    try:
        session_factory = current_app.config.get("SESSION_FACTORY")
        if session_factory is None:
            return "error: session factory not configured"
        session = session_factory()
        try:
            session.execute(text("SELECT 1"))
        finally:
            session.close()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        msg = f"error: {type(exc).__name__}: {exc}"
        logger.warning("DB health check failed: %s", msg)
        return msg


@health_bp.route("/health")
def health() -> Any:
    redis_status = _check_redis()
    db_status = _check_db()

    overall = "ok" if redis_status == "ok" and db_status == "ok" else "error"
    payload = {
        "status": overall,
        "redis": redis_status,
        "db": db_status,
    }
    http_code = 200 if overall == "ok" else 503
    return jsonify(payload), http_code
