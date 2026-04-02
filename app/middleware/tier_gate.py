"""Tier-based feature gating decorators."""

from functools import wraps

from flask import g, jsonify

from app.billing.tiers import has_feature, get_limit


def _current_tier():
    """Get the current user's tier, defaulting to free."""
    if g.get("current_user") and g.current_user is not None:
        return g.current_user.tier
    return "free"


def require_feature(feature_name):
    """Decorator that blocks access if the user's tier lacks the feature.

    Returns 403 with an upgrade prompt if the feature is not available.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            tier = _current_tier()
            if not has_feature(tier, feature_name):
                return jsonify({
                    "error": "Feature not available on your current plan",
                    "feature": feature_name,
                    "current_tier": tier,
                    "upgrade_url": "/pricing",
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_tier(min_tier):
    """Decorator that requires at least the specified tier.

    Tier order: free < plus < max
    """
    tier_order = {"free": 0, "plus": 1, "max": 2}

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current = _current_tier()
            if tier_order.get(current, 0) < tier_order.get(min_tier, 0):
                return jsonify({
                    "error": f"This feature requires the {min_tier.title()} plan or higher",
                    "current_tier": current,
                    "required_tier": min_tier,
                    "upgrade_url": "/pricing",
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def tier_limit(limit_key):
    """Get a limit value for the current user's tier."""
    return get_limit(_current_tier(), limit_key)
