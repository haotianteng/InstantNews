"""Rate limiting middleware — enforces per-tier API rate limits.

Uses Flask-Limiter with in-memory storage. Authenticated users are keyed
by user ID; anonymous requests are keyed by IP address. Limits are read
dynamically from the tier definitions in app.billing.tiers.
"""

import logging

from flask import g, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.billing.tiers import get_limit

logger = logging.getLogger("signal.rate_limit")


def _rate_limit_key():
    """Return a unique key for rate limiting.

    Authenticated users are keyed by their user ID.
    Anonymous requests are keyed by IP address.
    """
    user = g.get("current_user")
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{get_remote_address()}"


def _get_tier_rate_limit():
    """Return the rate limit string for the current user's tier.

    Format required by Flask-Limiter: e.g. "10 per minute".
    """
    user = g.get("current_user")
    tier_name = user.tier if user is not None else "free"
    rate = get_limit(tier_name, "api_rate_per_minute")
    if rate is None:
        rate = 10  # Fallback to free tier default
    return f"{rate} per minute"


def _is_non_api_request():
    """Return True if the current request is NOT an API endpoint."""
    return not request.path.startswith("/api/")


# Module-level limiter instance; initialized in init_rate_limiter().
limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=[_get_tier_rate_limit],
    default_limits_exempt_when=_is_non_api_request,
    storage_uri="memory://",
)


def init_rate_limiter(app):
    """Attach the rate limiter to the Flask app.

    Applies dynamic per-tier limits to all /api/* endpoints only.
    Non-API routes (static pages, landing page) are exempt.
    """
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    limiter.init_app(app)

    # Custom 429 error handler with JSON response
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        user = g.get("current_user")
        tier_name = user.tier if user is not None else "free"
        rate = get_limit(tier_name, "api_rate_per_minute") or 10
        logger.warning("Rate limit exceeded", extra={
            "event": "rate_limited",
            "user_id": user.id if user else None,
            "tier": tier_name,
            "ip": request.remote_addr,
            "path": request.path,
        })
        return jsonify({
            "error": "Rate limit exceeded",
            "message": (
                f"You have exceeded {rate} requests per minute "
                f"for the {tier_name.title()} tier"
            ),
            "current_tier": tier_name,
            "limit": rate,
            "upgrade_url": "/pricing",
        }), 429
