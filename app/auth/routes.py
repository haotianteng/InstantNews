"""Auth API routes."""

from flask import Blueprint, jsonify, g

from app.auth.middleware import require_auth
from app.billing.tiers import get_features, get_tier, get_all_tiers_summary

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/me")
@require_auth
def get_me():
    """Return the current authenticated user's profile."""
    return jsonify({"user": g.current_user.to_dict()})


@auth_bp.route("/api/auth/tier")
def get_user_tier():
    """Return the current user's tier, feature flags, and limits.

    Works for both authenticated and anonymous users.
    """
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
    return jsonify({"tiers": get_all_tiers_summary()})
