"""Admin panel API routes — user management, test accounts, system stats."""

import json
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app, g as flask_g
from sqlalchemy import func, text

from app.admin.auth import require_admin, require_superadmin
from app.models import User, Subscription, News, ApiKey, ApiUsage, AuditLog
from app.services.feed_parser import utc_iso

logger = logging.getLogger("signal.admin")

admin_bp = Blueprint("admin", __name__, url_prefix="/admin/api")


def _get_read_db():
    from app.database import get_replica_session
    return get_replica_session()


def _get_write_db():
    return current_app.config["SESSION_FACTORY"]()


# ── Dashboard Stats ──────────────────────────────────────────────

@admin_bp.route("/stats")
@require_admin
def admin_stats():
    """Overview stats: totals, active today, new this month, MRR, tier breakdown."""
    db = _get_read_db()
    try:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        # Core counts (exclude test accounts from business metrics)
        total_users = db.query(func.count(User.id)).filter(User.is_test_account == False).scalar() or 0
        test_users = db.query(func.count(User.id)).filter(User.is_test_account == True).scalar() or 0

        # Active today (logged in today, non-test)
        active_today = db.query(func.count(User.id)).filter(
            User.is_test_account == False,
            User.last_login_at >= today,
        ).scalar() or 0

        # New this month (non-test)
        new_this_month = db.query(func.count(User.id)).filter(
            User.is_test_account == False,
            User.created_at >= month_start,
        ).scalar() or 0

        # Users by tier (non-test)
        tier_rows = db.query(User.tier, func.count(User.id)).filter(
            User.is_test_account == False
        ).group_by(User.tier).all()
        tiers = {tier: count for tier, count in tier_rows}

        # MRR from active/trialing subscriptions
        from app.billing.tiers import TIERS
        mrr_cents = 0
        subs = db.query(Subscription).filter(
            Subscription.status.in_(["active", "trialing"])
        ).all()
        for sub in subs:
            tier_def = TIERS.get(sub.tier, {})
            mrr_cents += tier_def.get("price_monthly_cents", 0)
        mrr_dollars = mrr_cents / 100

        # News stats
        total_news = db.query(func.count(News.id)).scalar() or 0
        ai_analyzed = db.query(func.count(News.id)).filter(News.ai_analyzed == True).scalar() or 0

        return jsonify({
            "users": {
                "total": total_users,
                "test": test_users,
                "active_today": active_today,
                "new_this_month": new_this_month,
                "by_tier": tiers,
            },
            "mrr": mrr_dollars,
            "news": {"total": total_news, "ai_analyzed": ai_analyzed},
            "api_keys": db.query(func.count(ApiKey.id)).scalar() or 0,
        })
    finally:
        db.close()


@admin_bp.route("/stats/signups")
@require_admin
def signup_stats():
    """Daily signup counts for the last N days (default 30)."""
    days = min(int(request.args.get("days", 30)), 90)
    db = _get_read_db()
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = db.query(
            func.substr(User.created_at, 1, 10).label("date"),
            func.count(User.id).label("count"),
        ).filter(
            User.created_at >= since,
            User.is_test_account == False,
        ).group_by("date").order_by("date").all()

        return jsonify({"signups": [{"date": r.date, "count": r.count} for r in rows]})
    finally:
        db.close()


# ── User Management ─────────────────────────────────────────────

@admin_bp.route("/users")
@require_admin
def list_users():
    """List users with search and filters."""
    db = _get_read_db()
    try:
        q = db.query(User)

        test_only = request.args.get("test", "").lower() == "true"
        tier = request.args.get("tier", "")
        status = request.args.get("status", "")
        search = request.args.get("q", "")

        if test_only:
            q = q.filter(User.is_test_account == True)
        if tier:
            q = q.filter(User.tier == tier)
        if status == "disabled":
            q = q.filter(User.disabled == True)
        elif status == "active":
            q = q.filter(User.disabled == False)
        if search:
            q = q.filter(User.email.ilike(f"%{search}%"))

        q = q.order_by(User.created_at.desc())
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
        total = q.count()
        users = q.offset(offset).limit(limit).all()

        return jsonify({
            "users": [_user_to_admin_dict(u) for u in users],
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>")
@require_admin
def get_user(user_id):
    """Get full user details including subscription, keys, usage, and activity."""
    db = _get_read_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        sub = db.query(Subscription).filter_by(user_id=user_id).first()
        keys = db.query(ApiKey).filter_by(user_id=user_id).all()
        total_requests = db.query(func.sum(ApiUsage.request_count)).filter_by(user_id=user_id).scalar() or 0

        # Activity log from audit table (as target)
        audit_rows = db.query(AuditLog).filter_by(target_user_id=user_id).order_by(
            AuditLog.created_at.desc()
        ).limit(20).all()

        activity = [{"action": r.action, "details": r.details,
                     "admin": r.admin_email, "at": r.created_at} for r in audit_rows]

        result = _user_to_admin_dict(user)
        result["subscription"] = sub.to_dict() if sub else None
        result["api_keys"] = [k.to_dict() for k in keys]
        result["total_api_requests"] = total_requests
        result["activity"] = activity
        return jsonify(result)
    finally:
        db.close()


# ── Test Account Management ──────────────────────────────────────

@admin_bp.route("/test-accounts", methods=["POST"])
@require_admin
def create_test_account():
    """Create a real Firebase test account with email/password.

    Body: {
        "username": "dev",
        "tier": "pro",
        "display_name": "Test User",
        "password": "optional-pass",   (auto-generated if omitted)
        "notes": "Testing upgrade flow",
        "expire_days": 30
    }
    Returns: user dict + plaintext password (shown once).
    """
    data = request.get_json() or {}
    username = data.get("username", "test")
    tier = data.get("tier", "pro")
    display_name = data.get("display_name", f"Test {tier.title()}")
    password = data.get("password") or secrets.token_urlsafe(12)
    notes = data.get("notes", "")
    expire_days = int(data.get("expire_days", 0))

    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    email = f"{username}+test{suffix}@gmail.com"
    now = datetime.now(timezone.utc)
    now_str = utc_iso(now)
    expires_at = utc_iso(now + timedelta(days=expire_days)) if expire_days > 0 else None

    # Step 1: Create real Firebase user
    try:
        from app.auth.firebase import create_firebase_user
        fb_user = create_firebase_user(email, password, display_name)
        firebase_uid = fb_user.uid
    except Exception as e:
        logger.warning("Firebase user creation failed", extra={
            "event": "firebase_create_failed", "email": email, "error": str(e)
        })
        return jsonify({"error": f"Firebase user creation failed: {str(e)}"}), 400

    # Step 2: Create DB record
    db = _get_write_db()
    try:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            display_name=display_name,
            tier=tier,
            is_test_account=True,
            test_tier_override=tier,
            notes=notes,
            expires_at=expires_at,
            created_at=now_str,
            updated_at=now_str,
        )
        db.add(user)
        db.commit()

        _audit(db, "create_test_account", user.id, {
            "email": email, "tier": tier, "firebase_uid": firebase_uid,
        })
        db.commit()

        logger.info("Test account created", extra={
            "event": "admin_test_account_created",
            "user_id": user.id, "email": email, "tier": tier,
        })

        return jsonify({
            "user": _user_to_admin_dict(user),
            "password": password,  # returned once for admin to record
            "message": f"Created: {email}",
        }), 201
    except Exception as e:
        db.rollback()
        # Rollback: delete the Firebase user we just created
        try:
            from app.auth.firebase import delete_firebase_user
            delete_firebase_user(firebase_uid)
        except Exception:
            pass
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/tier", methods=["PUT"])
@require_admin
def update_user_tier(user_id):
    """Change a user's tier. Body: {"tier": "pro"}"""
    data = request.get_json() or {}
    new_tier = data.get("tier", "")
    if new_tier not in ("free", "pro", "max"):
        return jsonify({"error": "Invalid tier."}), 400

    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        old_tier = user.tier
        if user.is_test_account:
            user.test_tier_override = new_tier
        user.tier = new_tier
        user.updated_at = utc_iso(datetime.now(timezone.utc))
        _audit(db, "update_tier", user_id, {"old": old_tier, "new": new_tier})
        db.commit()
        return jsonify({"user": _user_to_admin_dict(user)})
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/disable", methods=["PUT"])
@require_admin
def toggle_disable(user_id):
    """Enable or disable a user. Body: {"disabled": true}"""
    data = request.get_json() or {}
    disabled = bool(data.get("disabled", True))

    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        if user.role in ("admin", "superadmin") and disabled:
            return jsonify({"error": "Cannot disable admin accounts."}), 403

        user.disabled = disabled
        user.updated_at = utc_iso(datetime.now(timezone.utc))
        _audit(db, "disable_user" if disabled else "enable_user", user_id, {})
        db.commit()
        return jsonify({"user": _user_to_admin_dict(user)})
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/test-flag", methods=["PUT"])
@require_admin
def toggle_test_flag(user_id):
    """Toggle is_test_account. Body: {"is_test": true}"""
    data = request.get_json() or {}
    is_test = bool(data.get("is_test", False))

    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        user.is_test_account = is_test
        if not is_test:
            user.test_tier_override = None
        user.updated_at = utc_iso(datetime.now(timezone.utc))
        db.commit()
        return jsonify({"user": _user_to_admin_dict(user)})
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    """Delete a test account from both DB and Firebase."""
    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        if not user.is_test_account:
            return jsonify({"error": "Can only delete test accounts."}), 403

        firebase_uid = user.firebase_uid
        email = user.email

        # Delete from DB first
        _audit(db, "delete_user", user_id, {"email": email, "firebase_uid": firebase_uid})
        db.delete(user)
        db.commit()

        # Delete from Firebase (non-fatal if it fails)
        firebase_deleted = False
        firebase_error = None
        try:
            from app.auth.firebase import delete_firebase_user
            delete_firebase_user(firebase_uid)
            firebase_deleted = True
        except Exception as e:
            firebase_error = str(e)
            logger.warning("Firebase delete failed after DB delete", extra={
                "event": "firebase_delete_failed",
                "firebase_uid": firebase_uid,
                "email": email,
                "error": firebase_error,
            })

        return jsonify({
            "status": "deleted",
            "firebase_deleted": firebase_deleted,
            "firebase_error": firebase_error,
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/notes", methods=["PUT"])
@require_admin
def update_notes(user_id):
    """Update admin notes on a user. Body: {"notes": "..."}"""
    data = request.get_json() or {}
    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        user.notes = data.get("notes", "")
        user.updated_at = utc_iso(datetime.now(timezone.utc))
        db.commit()
        return jsonify({"user": _user_to_admin_dict(user)})
    finally:
        db.close()


# ── Role Management (superadmin only) ────────────────────────────

@admin_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@require_superadmin
def update_user_role(user_id):
    """Promote or demote a user's role. Body: {"role": "admin"}"""
    data = request.get_json() or {}
    new_role = data.get("role", "")
    if new_role not in ("user", "admin", "superadmin"):
        return jsonify({"error": "Invalid role."}), 400
    if user_id == flask_g.current_user.id and new_role != "superadmin":
        return jsonify({"error": "Cannot demote yourself."}), 400

    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        old_role = user.role
        user.role = new_role
        user.updated_at = utc_iso(datetime.now(timezone.utc))
        _audit(db, "update_role", user_id, {"old": old_role, "new": new_role})
        db.commit()
        return jsonify({"user": _user_to_admin_dict(user)})
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_superadmin
def permanently_delete_user(user_id):
    """Permanently delete any user account (superadmin only).

    Requires typing "DELETE ACCOUNT <email>" as confirmation.
    Body: {"confirmation": "DELETE ACCOUNT user@example.com"}
    """
    data = request.get_json() or {}
    confirmation = data.get("confirmation", "").strip()

    db = _get_write_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Cannot delete yourself
        if user_id == flask_g.current_user.id:
            return jsonify({"error": "Cannot delete your own account."}), 400

        # Verify confirmation string
        expected = f"DELETE ACCOUNT {user.email or user.display_name or user.id}"
        if confirmation != expected:
            return jsonify({
                "error": "Confirmation does not match.",
                "expected_format": f"DELETE ACCOUNT {user.email or user.display_name or user.id}",
            }), 400

        email = user.email
        firebase_uid = user.firebase_uid
        auth_method = getattr(user, "auth_method", "unknown")

        # Delete related records
        db.query(ApiUsage).filter_by(user_id=user_id).delete()
        db.query(ApiKey).filter_by(user_id=user_id).delete()
        db.query(Subscription).filter_by(user_id=user_id).delete()

        # Audit before delete
        _audit(db, "permanently_delete_user", user_id, {
            "email": email,
            "auth_method": auth_method,
            "firebase_uid": firebase_uid,
        })

        db.delete(user)
        db.commit()

        # Clean up Firebase if applicable
        firebase_deleted = False
        if firebase_uid:
            try:
                from app.auth.firebase import delete_firebase_user
                delete_firebase_user(firebase_uid)
                firebase_deleted = True
            except Exception as e:
                logger.warning("Firebase delete failed", extra={
                    "event": "firebase_delete_failed",
                    "firebase_uid": firebase_uid,
                    "error": str(e),
                })

        logger.info("User permanently deleted by superadmin", extra={
            "event": "user_permanently_deleted",
            "deleted_user_id": user_id,
            "deleted_email": email,
            "deleted_by": flask_g.current_user.email,
        })

        return jsonify({
            "status": "deleted",
            "email": email,
            "firebase_deleted": firebase_deleted,
        })
    except Exception as e:
        db.rollback()
        logger.exception("Permanent user deletion failed")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route("/admins")
@require_admin
def list_admins():
    """List all admin and superadmin users."""
    db = _get_read_db()
    try:
        admins = db.query(User).filter(User.role.in_(["admin", "superadmin"])).all()
        return jsonify({"admins": [_user_to_admin_dict(u) for u in admins]})
    finally:
        db.close()


# ── Firebase Sync Check ──────────────────────────────────────────

@admin_bp.route("/sync/check")
@require_admin
def sync_check():
    """Check Firebase ↔ DB sync status.

    Finds:
    - DB users whose firebase_uid doesn't exist in Firebase (orphaned DB rows)
    - Returns summary counts and a sample of orphaned records

    Note: Firebase list_users() is rate-limited; this checks a sample of
    recently created users by looking up UIDs individually.
    """
    db = _get_read_db()
    try:
        from app.auth.firebase import get_firebase_user

        # Get recently created users (last 100) to check
        sample = db.query(User).order_by(User.created_at.desc()).limit(100).all()

        orphaned_db = []  # in DB but not Firebase
        synced = 0
        test_skipped = 0

        for user in sample:
            # Skip fake test UIDs that were created before this fix
            if user.firebase_uid and user.firebase_uid.startswith("test_"):
                test_skipped += 1
                continue

            fb_user = get_firebase_user(user.firebase_uid)
            if fb_user is None:
                orphaned_db.append({
                    "id": user.id,
                    "email": user.email,
                    "firebase_uid": user.firebase_uid,
                    "is_test_account": user.is_test_account,
                    "created_at": user.created_at,
                })
            else:
                synced += 1

        total_db = db.query(func.count(User.id)).scalar() or 0

        return jsonify({
            "total_db_users": total_db,
            "sample_checked": len(sample),
            "synced": synced,
            "test_skipped": test_skipped,
            "orphaned_db": orphaned_db,
            "orphaned_count": len(orphaned_db),
            "healthy": len(orphaned_db) == 0,
        })
    finally:
        db.close()


@admin_bp.route("/sync/repair", methods=["POST"])
@require_admin
def sync_repair():
    """Delete DB-only orphaned test accounts (no Firebase counterpart).

    Only removes test accounts — never touches real users.
    Body: {"confirm": true}
    """
    data = request.get_json() or {}
    if not data.get("confirm"):
        return jsonify({"error": "Send {\"confirm\": true} to proceed."}), 400

    db = _get_write_db()
    try:
        from app.auth.firebase import get_firebase_user

        # Find test accounts with fake UIDs (created before Firebase integration)
        fake_uid_users = db.query(User).filter(
            User.is_test_account == True,
            User.firebase_uid.like("test_%"),
        ).all()

        removed = []
        for user in fake_uid_users:
            _audit(db, "sync_repair_delete", user.id, {
                "email": user.email, "reason": "fake_firebase_uid"
            })
            db.delete(user)
            removed.append({"id": user.id, "email": user.email})

        db.commit()

        return jsonify({
            "removed": removed,
            "count": len(removed),
            "message": f"Removed {len(removed)} orphaned test accounts with fake Firebase UIDs.",
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


# ── Audit Log ────────────────────────────────────────────────────

@admin_bp.route("/audit-log")
@require_admin
def get_audit_log():
    """Recent admin actions."""
    db = _get_read_db()
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
        return jsonify({"log": [
            {"id": r.id, "admin": r.admin_email, "action": r.action,
             "target_user_id": r.target_user_id, "details": r.details,
             "ip": r.ip_address, "at": r.created_at}
            for r in rows
        ]})
    finally:
        db.close()


# ── Helpers ──────────────────────────────────────────────────────

def _user_to_admin_dict(user):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "firebase_uid": user.firebase_uid,
        "tier": user.tier,
        "role": getattr(user, "role", "user"),
        "is_test_account": user.is_test_account,
        "test_tier_override": user.test_tier_override,
        "disabled": getattr(user, "disabled", False),
        "last_login_at": getattr(user, "last_login_at", None),
        "notes": getattr(user, "notes", None),
        "expires_at": getattr(user, "expires_at", None),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _audit(db, action, target_user_id=None, details=None):
    user = flask_g.get("current_user")
    db.add(AuditLog(
        admin_user_id=user.id if user else 0,
        admin_email=getattr(flask_g, "admin_user", user.email if user else "unknown"),
        action=action,
        target_user_id=target_user_id,
        details=json.dumps(details) if details else None,
        ip_address=request.remote_addr,
        created_at=utc_iso(datetime.now(timezone.utc)),
    ))
