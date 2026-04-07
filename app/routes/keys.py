"""API key management routes — create, list, and revoke API keys."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g, current_app

from app.auth.middleware import require_auth
from app.billing.tiers import has_feature
from app.models import ApiKey
from app.services.feed_parser import utc_iso

logger = logging.getLogger("signal.api_keys")

keys_bp = Blueprint("keys", __name__)

# Limits
MAX_KEYS_PER_USER = 5


@keys_bp.route("/api/keys", methods=["GET"])
@require_auth
def list_keys():
    """List the current user's API keys (without the full key)."""
    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        keys = db.query(ApiKey).filter_by(user_id=g.current_user.id).order_by(
            ApiKey.created_at.desc()
        ).all()
        return jsonify({
            "keys": [k.to_dict() for k in keys],
            "max_keys": MAX_KEYS_PER_USER,
        })
    finally:
        db.close()


@keys_bp.route("/api/keys", methods=["POST"])
@require_auth
def create_key():
    """Generate a new API key.

    Body: {"name": "My Bot"} (optional)
    Returns the full key ONCE — it cannot be retrieved again.
    """
    if not has_feature(g.current_user.tier, "api_access"):
        return jsonify({"error": "API access requires Pro or Max plan."}), 403

    data = request.get_json() or {}
    name = (data.get("name") or "Untitled Key").strip()[:50]

    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        count = db.query(ApiKey).filter_by(user_id=g.current_user.id).count()
        if count >= MAX_KEYS_PER_USER:
            return jsonify({
                "error": f"Maximum {MAX_KEYS_PER_USER} API keys allowed.",
            }), 400

        # Generate key: instnews_<32 random hex chars>
        raw_key = "instnews_" + secrets.token_hex(16)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        now = utc_iso(datetime.now(timezone.utc))

        api_key = ApiKey(
            user_id=g.current_user.id,
            name=name,
            key_prefix=raw_key[:12],
            key_hash=key_hash,
            created_at=now,
        )
        db.add(api_key)
        db.commit()

        logger.info("API key created", extra={
            "event": "api_key_created",
            "user_id": g.current_user.id,
            "key_id": api_key.id,
        })

        return jsonify({
            "key": raw_key,  # shown ONCE
            "id": api_key.id,
            "name": name,
            "key_prefix": raw_key[:12],
            "created_at": now,
        }), 201
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@keys_bp.route("/api/keys/<int:key_id>", methods=["DELETE"])
@require_auth
def revoke_key(key_id):
    """Revoke (delete) an API key."""
    session_factory = current_app.config["SESSION_FACTORY"]
    db = session_factory()
    try:
        api_key = db.query(ApiKey).filter_by(
            id=key_id, user_id=g.current_user.id
        ).first()
        if not api_key:
            return jsonify({"error": "Key not found."}), 404

        db.delete(api_key)
        db.commit()

        logger.info("API key revoked", extra={
            "event": "api_key_revoked",
            "user_id": g.current_user.id,
            "key_id": key_id,
        })

        return jsonify({"status": "revoked"})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
