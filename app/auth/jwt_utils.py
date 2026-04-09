"""App-issued JWT tokens for WeChat-authenticated sessions.

WeChat users don't have Firebase/Cognito tokens, so we issue our own
JWTs signed with APP_JWT_SECRET (HS256).
"""

import logging
from datetime import datetime, timezone, timedelta

import jwt

logger = logging.getLogger("signal.auth")


def create_app_token(user_id, provider, display_name=None):
    """Create a signed JWT for a WeChat-authenticated user.

    Returns the encoded token string.
    """
    from flask import current_app

    secret = current_app.config.get("APP_JWT_SECRET") or ""
    expiry_days = current_app.config.get("APP_JWT_EXPIRY_DAYS", 7)

    if not secret:
        raise ValueError("APP_JWT_SECRET is not configured")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "provider": provider,
        "display_name": display_name,
        "iat": now,
        "exp": now + timedelta(days=expiry_days),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_app_token(token):
    """Verify and decode an app-issued JWT.

    Returns the decoded claims dict.
    Raises jwt.InvalidTokenError on failure.
    """
    from flask import current_app

    secret = current_app.config.get("APP_JWT_SECRET") or ""
    if not secret:
        raise jwt.InvalidTokenError("APP_JWT_SECRET is not configured")

    return jwt.decode(token, secret, algorithms=["HS256"])
