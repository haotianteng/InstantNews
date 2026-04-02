"""Auth middleware — extracts and verifies Firebase tokens from requests."""

from functools import wraps
from datetime import datetime, timezone

from flask import request, g, jsonify, current_app

from app.models import User
from app.services.feed_parser import utc_iso


class CurrentUser:
    """Lightweight user object detached from SQLAlchemy session."""

    def __init__(self, id, firebase_uid, email, display_name, photo_url, tier, created_at):
        self.id = id
        self.firebase_uid = firebase_uid
        self.email = email
        self.display_name = display_name
        self.photo_url = photo_url
        self.tier = tier
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
    """Extract Firebase token from Authorization header and load user.

    Sets g.current_user to a CurrentUser object, or None for anonymous requests.
    Called before each request.
    """
    g.current_user = None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return  # Anonymous — Free tier

    token = auth_header[7:]  # Strip "Bearer "
    try:
        from app.auth.firebase import verify_id_token
        decoded = verify_id_token(token)
    except Exception:
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
            user = User(
                firebase_uid=decoded["uid"],
                email=decoded.get("email", ""),
                display_name=decoded.get("name"),
                photo_url=decoded.get("picture"),
                tier="free",
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.commit()
        else:
            # Update profile if changed
            changed = False
            if decoded.get("name") and decoded["name"] != user.display_name:
                user.display_name = decoded["name"]
                changed = True
            if decoded.get("picture") and decoded["picture"] != user.photo_url:
                user.photo_url = decoded["picture"]
                changed = True
            if changed:
                user.updated_at = utc_iso(datetime.now(timezone.utc))
                session.commit()

        # Detach from session into a plain object
        g.current_user = CurrentUser(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url,
            tier=user.tier,
            created_at=user.created_at,
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
