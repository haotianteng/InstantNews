"""Auth middleware — extracts and verifies Firebase tokens from requests."""

import logging
import os
import re
from functools import wraps
from datetime import datetime, timezone

from flask import request, g, jsonify, current_app

from app.models import User
from app.services.feed_parser import utc_iso

# Test account auto-detection patterns
_TEST_PATTERNS_RAW = os.environ.get("TEST_EMAIL_PATTERNS", r"\+test.*@,\+qa.*@")
TEST_EMAIL_PATTERNS = [
    re.compile(p.strip(), re.IGNORECASE)
    for p in _TEST_PATTERNS_RAW.split(",") if p.strip()
]


def is_test_email(email):
    """Check if an email matches test account patterns."""
    if not email:
        return False
    return any(p.search(email) for p in TEST_EMAIL_PATTERNS)

logger = logging.getLogger("signal.auth")


class CurrentUser:
    """Lightweight user object detached from SQLAlchemy session."""

    def __init__(self, id, firebase_uid, email, display_name, photo_url, tier, created_at, is_test_account=False, role="user"):
        self.id = id
        self.firebase_uid = firebase_uid
        self.email = email
        self.display_name = display_name
        self.photo_url = photo_url
        self.tier = tier
        self.is_test_account = is_test_account
        self.role = role
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "photo_url": self.photo_url,
            "tier": self.tier,
            "created_at": self.created_at,
        }


def load_current_user():
    """Extract credentials from request headers and load user.

    Supports two auth methods:
    1. Authorization: Bearer <firebase_token>
    2. X-API-Key: <user_generated_api_key>

    Sets g.current_user to a CurrentUser object, or None for anonymous requests.
    Called before each request.
    """
    g.current_user = None
    g.auth_via_api_key = False

    # Try API key first
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        _load_user_from_api_key(api_key)
        if g.current_user is not None:
            g.auth_via_api_key = True
            return

    # Fall back to Firebase Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return  # Anonymous — Free tier

    token = auth_header[7:]  # Strip "Bearer "
    try:
        from app.auth.firebase import verify_id_token
        decoded = verify_id_token(token)
    except Exception:
        logger.warning("Invalid auth token", extra={
            "event": "auth_invalid_token",
            "ip": request.remote_addr,
        })
        return  # Invalid token — treat as anonymous

    # Look up or create user
    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        user = session.query(User).filter_by(
            firebase_uid=decoded["uid"]
        ).first()

        if user is None:
            now = utc_iso(datetime.now(timezone.utc))
            email = decoded.get("email", "")
            test_detected = is_test_email(email)
            user = User(
                firebase_uid=decoded["uid"],
                email=email,
                display_name=decoded.get("name"),
                photo_url=decoded.get("picture"),
                tier="free",
                is_test_account=test_detected,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.commit()
            logger.info("New user registered", extra={
                "event": "user_registered",
                "user_id": user.id,
                "tier": "free",
                "is_test": test_detected,
            })
        else:
            # Update profile if changed
            changed = False
            if decoded.get("name") and decoded["name"] != user.display_name:
                user.display_name = decoded["name"]
                changed = True
            if decoded.get("picture") and decoded["picture"] != user.photo_url:
                user.photo_url = decoded["picture"]
                changed = True
            # Always update last_login_at
            now_str = utc_iso(datetime.now(timezone.utc))
            user.last_login_at = now_str
            user.updated_at = now_str
            session.commit()

        # Detach from session into a plain object
        # Test accounts use tier override if set
        effective_tier = user.tier
        is_test = getattr(user, "is_test_account", False)
        if is_test and getattr(user, "test_tier_override", None):
            effective_tier = user.test_tier_override

        g.current_user = CurrentUser(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url,
            tier=effective_tier,
            created_at=user.created_at,
            is_test_account=is_test,
            role=getattr(user, "role", "user"),
        )
    except Exception:
        session.rollback()
    finally:
        session.close()


def _load_user_from_api_key(raw_key):
    """Authenticate via a user-generated API key (X-API-Key header)."""
    import hashlib
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        from app.models import ApiKey, User
        api_key = session.query(ApiKey).filter_by(key_hash=key_hash).first()
        if api_key is None:
            logger.warning("Invalid API key", extra={
                "event": "auth_invalid_api_key",
                "ip": request.remote_addr,
            })
            return

        user = session.query(User).filter_by(id=api_key.user_id).first()
        if user is None:
            return

        # Check tier has API access
        from app.billing.tiers import has_feature
        if not has_feature(user.tier, "api_access"):
            logger.warning("API key used without api_access feature", extra={
                "event": "auth_api_key_no_access",
                "user_id": user.id,
                "tier": user.tier,
            })
            return

        # Update last_used_at
        from app.services.feed_parser import utc_iso
        api_key.last_used_at = utc_iso(datetime.now(timezone.utc))
        session.commit()

        effective_tier = user.tier
        is_test = getattr(user, "is_test_account", False)
        if is_test and getattr(user, "test_tier_override", None):
            effective_tier = user.test_tier_override

        g.current_user = CurrentUser(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url,
            tier=effective_tier,
            created_at=user.created_at,
            is_test_account=is_test,
            role=getattr(user, "role", "user"),
        )
    except Exception:
        session.rollback()
    finally:
        session.close()


def require_auth(f):
    """Decorator that requires a valid authenticated user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.current_user is None:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated
