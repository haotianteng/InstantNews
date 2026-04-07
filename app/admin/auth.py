"""Admin authentication — role-based access control via DB.

Users sign in via Google Workspace SSO (same Firebase auth).
Access is determined by the `role` column in the users table:
  - "user"       → no admin access
  - "admin"      → manage test accounts, view users, change tiers
  - "superadmin" → all admin powers + promote/demote admins

The first superadmin is seeded via: python scripts/seed_admin.py <email>
"""

import logging
from functools import wraps

from flask import request, jsonify, g

logger = logging.getLogger("signal.admin")


def require_admin(f):
    """Decorator that requires admin or superadmin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = g.get("current_user")
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if user.role not in ("admin", "superadmin"):
            logger.warning("Unauthorized admin access", extra={
                "event": "admin_unauthorized",
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "ip": request.remote_addr,
            })
            return jsonify({"error": "Admin access required"}), 403
        g.admin_user = user.email
        return f(*args, **kwargs)
    return decorated


def require_superadmin(f):
    """Decorator that requires superadmin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = g.get("current_user")
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "superadmin":
            return jsonify({"error": "Superadmin access required"}), 403
        g.admin_user = user.email
        return f(*args, **kwargs)
    return decorated
