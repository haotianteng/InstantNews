"""Auth API routes.

Supports three auth methods:
- Email/password (own bcrypt auth — works globally)
- Google OAuth (Firebase popup — global only)
- WeChat QR (CN only, pending approval)
"""

import logging
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, g, redirect, request, current_app

from app.auth.middleware import require_auth
from app.billing.tiers import get_features, get_tier, get_all_tiers_summary

logger = logging.getLogger("signal.auth")

auth_bp = Blueprint("auth", __name__)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ── Existing endpoints ─────────────────────────────────────────────

@auth_bp.route("/api/auth/me")
@require_auth
def get_me():
    """Return the current authenticated user's profile."""
    return jsonify({"user": g.current_user.to_dict()})


@auth_bp.route("/api/auth/tier")
def get_user_tier():
    """Return the current user's tier, feature flags, and limits."""
    if g.current_user:
        tier_name = g.current_user.tier
    else:
        tier_name = "free"

    tier_def = get_tier(tier_name)
    return jsonify({
        "tier": tier_name,
        "features": tier_def["features"],
        "limits": tier_def["limits"],
    })


@auth_bp.route("/api/pricing")
def get_pricing():
    """Return all tier definitions for the pricing page."""
    tiers = get_all_tiers_summary()
    max_tier = get_tier("max")
    return jsonify({
        "tiers": tiers,
        "max_limits": max_tier["limits"],
    })


# ── Region Detection ───────────────────────────────────────────────

@auth_bp.route("/api/auth/region")
def get_region():
    """Return region info for the frontend.

    Frontend uses this to decide which social login button to show
    (Google vs WeChat). Email/password works in all regions.
    """
    override = request.args.get("region", "")
    if override in ("cn", "global"):
        is_china = override == "cn"
    else:
        country = request.headers.get("CloudFront-Viewer-Country", "")
        if not country:
            country = request.headers.get("X-Country-Code", "")
        is_china = country.upper() == "CN"

    return jsonify({
        "region": "cn" if is_china else "global",
        "wechat_enabled": is_china and bool(current_app.config.get("WECHAT_APP_ID")),
    })


# ── Email/Password Auth (own) ─────────────────────────────────────

@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    """Start email/password signup — sends verification email.

    The user is NOT created in the DB until the verification link is clicked.
    This prevents orphan rows and email squatting.
    """
    from app.auth.own_auth import hash_password, validate_password, generate_signup_token
    from app.services.email import send_verification_email, send_provider_conflict_email
    from app.models import User

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not _EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    ok, msg = validate_password(password)
    if not ok:
        return jsonify({"error": msg}), 400

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        existing = session.query(User).filter_by(email=email).first()
        if existing:
            if existing.auth_method == "email":
                return jsonify({"error": "An account with this email already exists. Please sign in."}), 409

            # Different provider — send conflict email
            send_provider_conflict_email(email, existing.auth_method)
            return jsonify({
                "error": f"This email is registered with {existing.auth_method} sign-in. Check your email for details."
            }), 409
    finally:
        session.close()

    # No DB row created yet — encode email + password_hash into the token
    secret = current_app.config.get("APP_JWT_SECRET", "")
    pw_hash = hash_password(password)
    token = generate_signup_token(email, pw_hash, secret)
    send_verification_email(email, token)

    logger.info("Signup verification email sent", extra={
        "event": "signup_verification_sent", "email": email,
    })

    return jsonify({
        "message": "Please check your email to verify your address and activate your account."
    }), 200


@auth_bp.route("/api/auth/signin", methods=["POST"])
def signin():
    """Sign in with email and password. Returns an app JWT."""
    from app.auth.own_auth import verify_password
    from app.auth.jwt_utils import create_app_token
    from app.models import User
    from app.services.feed_parser import utc_iso

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        user = session.query(User).filter_by(email=email).first()

        if not user:
            return jsonify({"error": "Invalid email or password."}), 401

        if user.auth_method != "email":
            return jsonify({
                "error": f"This email uses {user.auth_method} sign-in. Please use that method instead."
            }), 401

        if getattr(user, "disabled", False):
            return jsonify({"error": "This account has been disabled."}), 403

        if not user.password_hash or not verify_password(password, user.password_hash):
            return jsonify({"error": "Invalid email or password."}), 401

        # Update last login
        now = utc_iso(datetime.now(timezone.utc))
        user.last_login_at = now
        user.updated_at = now
        session.commit()

        # Issue app JWT
        token = create_app_token(user.id, "email", user.display_name)

        logger.info("Email user signed in", extra={
            "event": "user_signin",
            "user_id": user.id,
            "auth_method": "email",
        })

        return jsonify({
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "tier": user.tier,
                "auth_method": user.auth_method,
            },
        })
    except Exception:
        session.rollback()
        logger.exception("Signin failed")
        return jsonify({"error": "An error occurred. Please try again."}), 500
    finally:
        session.close()


@auth_bp.route("/api/auth/verify-email")
def verify_email():
    """Verify email, create the user account, and auto-sign in.

    The signup token carries email + password_hash. The user is only
    created in the DB when this link is clicked. After creation, an
    app JWT is issued and the user is redirected with the token so
    the frontend auto-signs them in.
    """
    from app.auth.own_auth import verify_signup_token
    from app.auth.jwt_utils import create_app_token
    from app.models import User
    from app.services.feed_parser import utc_iso

    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "Missing token"}), 400

    secret = current_app.config.get("APP_JWT_SECRET", "")
    email, password_hash = verify_signup_token(token, secret)
    if email is None:
        return jsonify({"error": "Invalid or expired verification link."}), 400

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        # Check if user was already created (link clicked twice)
        existing = session.query(User).filter_by(email=email).first()
        if existing:
            # Already verified — issue token and auto-sign in
            jwt = create_app_token(existing.id, "email", existing.display_name)
            base = current_app.config.get("BASE_URL", "") or ""
            return redirect(f"{base}/?verified=true&token={jwt}")

        now = utc_iso(datetime.now(timezone.utc))
        user = User(
            email=email,
            password_hash=password_hash,
            auth_method="email",
            email_verified=True,
            display_name=email.split("@")[0],
            tier="free",
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.commit()

        logger.info("Email verified, user created", extra={
            "event": "user_registered",
            "user_id": user.id,
            "auth_method": "email",
        })

        # Issue JWT and redirect with auto-sign-in
        jwt = create_app_token(user.id, "email", user.display_name)
        return redirect(f"/?verified=true&token={jwt}")
    except Exception:
        session.rollback()
        logger.exception("Email verification failed")
        return jsonify({"error": "Verification failed."}), 500
    finally:
        session.close()


@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    """Send password reset email."""
    from app.auth.own_auth import generate_password_reset_token
    from app.services.email import send_password_reset_email, send_provider_conflict_email
    from app.models import User

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or not _EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    # Always return success to prevent email enumeration
    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        user = session.query(User).filter_by(email=email).first()
        if user:
            if user.auth_method != "email":
                # Email belongs to a social login — send conflict notice
                send_provider_conflict_email(email, user.auth_method)
            else:
                secret = current_app.config.get("APP_JWT_SECRET", "")
                token = generate_password_reset_token(user.id, secret)
                send_password_reset_email(email, token)
    except Exception:
        logger.exception("Forgot password error")
    finally:
        session.close()

    return jsonify({"message": "If an account exists with this email, we've sent reset instructions."})


@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    """Reset password using a token."""
    from app.auth.own_auth import verify_reset_token, hash_password, validate_password
    from app.models import User
    from app.services.feed_parser import utc_iso

    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    new_password = data.get("password", "")

    if not token:
        return jsonify({"error": "Missing reset token."}), 400

    ok, msg = validate_password(new_password)
    if not ok:
        return jsonify({"error": msg}), 400

    secret = current_app.config.get("APP_JWT_SECRET", "")
    user_id = verify_reset_token(token, secret)
    if user_id is None:
        return jsonify({"error": "Invalid or expired reset link."}), 400

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user or user.auth_method != "email":
            return jsonify({"error": "Invalid reset link."}), 400

        user.password_hash = hash_password(new_password)
        user.updated_at = utc_iso(datetime.now(timezone.utc))
        session.commit()

        logger.info("Password reset", extra={
            "event": "password_reset", "user_id": user_id
        })
        return jsonify({"message": "Password updated. You can now sign in."})
    except Exception:
        session.rollback()
        return jsonify({"error": "Password reset failed."}), 500
    finally:
        session.close()


@auth_bp.route("/api/auth/resend-verification", methods=["POST"])
def resend_verification():
    """Resend email verification link.

    Since the user doesn't exist in DB until verified, this is essentially
    the same as signing up again. The caller must provide the password.
    """
    from app.auth.own_auth import hash_password, generate_signup_token
    from app.services.email import send_verification_email
    from app.models import User

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email:
        return jsonify({"error": "Email is required."}), 400

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        # If user already exists (already verified), no need to resend
        existing = session.query(User).filter_by(email=email).first()
        if not existing and password:
            secret = current_app.config.get("APP_JWT_SECRET", "")
            pw_hash = hash_password(password)
            token = generate_signup_token(email, pw_hash, secret)
            send_verification_email(email, token)
    except Exception:
        logger.exception("Resend verification error")
    finally:
        session.close()

    return jsonify({"message": "If your account needs verification, we've sent a new link."})


# ── Token Refresh ──────────────────────────────────────────────────

@auth_bp.route("/api/auth/refresh", methods=["POST"])
@require_auth
def refresh_token():
    """Refresh an app JWT for email/password or WeChat users."""
    from app.auth.jwt_utils import create_app_token

    user = g.current_user
    if user.auth_method not in ("email", "wechat"):
        return jsonify({"error": "Token refresh not available for this auth method."}), 400

    token = create_app_token(user.id, user.auth_method, user.display_name)
    return jsonify({"token": token})


# ── WeChat OAuth ───────────────────────────────────────────────────

@auth_bp.route("/api/auth/wechat/login")
def wechat_login():
    """Redirect user to WeChat QR code authorization page."""
    from app.auth.wechat import get_authorize_url, generate_state

    app_id = current_app.config.get("WECHAT_APP_ID", "")
    secret = current_app.config.get("APP_JWT_SECRET", "")
    redirect_uri = current_app.config.get("WECHAT_REDIRECT_URI", "")

    if not app_id:
        return jsonify({"error": "WeChat login not configured"}), 503

    state = generate_state(secret)
    url = get_authorize_url(app_id, redirect_uri, state)

    logger.info("WeChat login initiated", extra={"event": "wechat_login_start"})
    return redirect(url)


@auth_bp.route("/api/auth/wechat/callback")
def wechat_callback():
    """Handle WeChat OAuth callback after QR scan."""
    from app.auth.wechat import (
        exchange_code_for_token, fetch_user_info, verify_state,
    )
    from app.auth.jwt_utils import create_app_token
    from app.models import User
    from app.services.feed_parser import utc_iso
    from app.services.email import send_provider_conflict_email

    code = request.args.get("code")
    state = request.args.get("state", "")

    if not code:
        return jsonify({"error": "Missing authorization code"}), 400

    secret = current_app.config.get("APP_JWT_SECRET", "")
    if not verify_state(state, secret):
        return jsonify({"error": "Invalid state parameter"}), 400

    app_id = current_app.config.get("WECHAT_APP_ID", "")
    app_secret = current_app.config.get("WECHAT_APP_SECRET", "")

    try:
        token_data = exchange_code_for_token(app_id, app_secret, code)
    except Exception as e:
        logger.error("WeChat token exchange failed", extra={"error": str(e)})
        return redirect("/?auth_error=wechat_failed")

    openid = token_data["openid"]
    access_token = token_data["access_token"]
    unionid = token_data.get("unionid")

    try:
        user_info = fetch_user_info(access_token, openid)
    except Exception as e:
        logger.error("WeChat user info failed", extra={"error": str(e)})
        return redirect("/?auth_error=wechat_failed")

    nickname = user_info.get("nickname", "WeChat User")
    headimgurl = user_info.get("headimgurl", "")

    session_factory = current_app.config["SESSION_FACTORY"]
    session = session_factory()
    try:
        user = session.query(User).filter_by(wechat_openid=openid).first()
        now = utc_iso(datetime.now(timezone.utc))

        if user:
            user.display_name = nickname
            user.photo_url = headimgurl
            user.last_login_at = now
            user.updated_at = now
            if unionid and not user.wechat_unionid:
                user.wechat_unionid = unionid
        else:
            # Check if email conflicts (WeChat may not provide email, but check unionid-linked email)
            user = User(
                firebase_uid=None,
                email=None,
                display_name=nickname,
                photo_url=headimgurl,
                tier="free",
                auth_method="wechat",
                email_verified=True,  # WeChat verifies identity via phone
                wechat_openid=openid,
                wechat_unionid=unionid,
                created_at=now,
                updated_at=now,
            )
            session.add(user)

        session.commit()
        user_id = user.id
        display_name = user.display_name

        logger.info("WeChat login success", extra={
            "event": "wechat_login_success", "user_id": user_id,
        })
    except Exception:
        session.rollback()
        logger.exception("WeChat user sync failed")
        return redirect("/?auth_error=wechat_failed")
    finally:
        session.close()

    token = create_app_token(user_id, "wechat", display_name)
    return redirect(f"/terminal?wechat_token={token}")
