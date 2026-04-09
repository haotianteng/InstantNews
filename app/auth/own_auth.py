"""Own email/password authentication — bcrypt hashing + HMAC tokens.

This module handles password hashing and secure token generation for
email verification and password reset flows. No external auth provider needed.

Signup flow: email + password_hash are encoded into the verification token.
The user is only created in the DB when the verification link is clicked.
"""

import base64
import hashlib
import hmac
import json
import time

import bcrypt


def hash_password(password):
    """Hash a password with bcrypt. Returns the hash string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    """Verify a password against a bcrypt hash. Returns True if correct."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ── Signup verification tokens (carry email + password_hash) ──────

def generate_signup_token(email, password_hash, secret):
    """Generate a signed token that carries email + password_hash.

    Token format: base64({email, password_hash, ts}).signature
    The user is NOT created in the DB until this token is verified.
    Expires in 24 hours.
    """
    ts = int(time.time())
    payload = json.dumps({"email": email, "ph": password_hash, "ts": ts}, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload_b64}.{sig}"


def verify_signup_token(token, secret, max_age_seconds=86400):
    """Verify a signup token. Returns (email, password_hash) or (None, None)."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None, None
        payload_b64, sig = parts

        # Verify signature
        expected = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None, None

        # Decode payload
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        email = payload.get("email")
        password_hash = payload.get("ph")
        ts = payload.get("ts", 0)

        # Check expiry
        if time.time() - ts > max_age_seconds:
            return None, None

        return email, password_hash
    except Exception:
        return None, None


# ── Password reset tokens (carry user_id) ─────────────────────────

def generate_token(user_id, purpose, secret, expiry_seconds=86400):
    """Generate an HMAC-signed token.

    Token format: {user_id}:{timestamp}:{signature}
    """
    ts = str(int(time.time()))
    msg = f"{user_id}:{purpose}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{user_id}:{ts}:{sig}"


def verify_token(token, purpose, secret, max_age_seconds=86400):
    """Verify an HMAC-signed token. Returns user_id (int) or None if invalid."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        user_id_str, ts, sig = parts
        user_id = int(user_id_str)

        if time.time() - int(ts) > max_age_seconds:
            return None

        msg = f"{user_id}:{purpose}:{ts}"
        expected = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None

        return user_id
    except (ValueError, TypeError):
        return None


def generate_password_reset_token(user_id, secret):
    """Generate a 1-hour password reset token."""
    return generate_token(user_id, "reset_password", secret, expiry_seconds=3600)


def verify_reset_token(token, secret):
    """Verify a password reset token. Returns user_id or None."""
    return verify_token(token, "reset_password", secret, max_age_seconds=3600)


def validate_password(password):
    """Validate password strength. Returns (ok, message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    return True, ""
