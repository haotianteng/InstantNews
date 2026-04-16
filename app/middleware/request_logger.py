"""Request logging middleware — logs every request with structured fields.

Attaches a unique request ID, records timing, user identity, and tier.
Produces JSON logs parseable by CloudWatch Logs Insights.
Also tracks per-user API usage counts.
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, g, request, current_app

logger = logging.getLogger("signal.requests")


def init_request_logger(app: Flask) -> None:
    """Register before/after hooks for structured request logging."""

    @app.before_request
    def _start_timer():
        g.request_id = uuid.uuid4().hex[:12]
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        # Skip health-check noise
        if request.path == "/api/stats" and request.args.get("health") == "1":
            return response

        latency_ms = round(
            (time.monotonic() - getattr(g, "request_start", time.monotonic())) * 1000, 1
        )

        user = g.get("current_user")
        user_id = user.id if user else None
        tier = user.tier if user else "anonymous"

        logger.info(
            "%s %s → %s (%.1fms)",
            request.method,
            request.path,
            response.status_code,
            latency_ms,
            extra={
                "request_id": getattr(g, "request_id", None),
                "method": request.method,
                "path": request.path,
                "endpoint": request.endpoint,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "user_id": user_id,
                "tier": tier,
                "ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", "")[:200],
            },
        )

        # Track API usage for authenticated non-test users on /api/* endpoints
        is_test = getattr(user, "is_test_account", False) if user else False
        if user_id and request.path.startswith("/api/") and not is_test:
            _increment_usage(user_id)

        return response


def _increment_usage(user_id):
    """Increment the daily API request counter for a user."""
    try:
        from app.models import ApiUsage
        session_factory = current_app.config["SESSION_FACTORY"]
        session = session_factory()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            row = session.query(ApiUsage).filter_by(
                user_id=user_id, date=today
            ).first()
            if row:
                row.request_count += 1
            else:
                session.add(ApiUsage(
                    user_id=user_id, date=today, request_count=1
                ))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        pass  # Usage tracking must never break requests
