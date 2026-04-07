"""Serve the frontend pages."""

from flask import Blueprint, send_from_directory, current_app, g, redirect

from app.billing.tiers import has_feature

static_bp = Blueprint("static_pages", __name__)


@static_bp.route("/")
def landing():
    return send_from_directory(current_app.static_folder, "index.html")


@static_bp.route("/terminal")
def terminal():
    """Serve the terminal UI.

    Auth and tier checks happen client-side — Firebase tokens are only
    available in JS, not on page navigation requests.
    """
    return send_from_directory(current_app.static_folder, "terminal.html")


@static_bp.route("/account")
def account():
    """Serve the account management page.

    Auth is checked client-side — Firebase tokens are only available
    in JS, not on page navigation requests.
    """
    return send_from_directory(current_app.static_folder, "account.html")


@static_bp.route("/pricing")
def pricing():
    return send_from_directory(current_app.static_folder, "pricing.html")


@static_bp.route("/privacy")
def privacy():
    return send_from_directory(current_app.static_folder, "privacy.html")


@static_bp.route("/terms")
def terms():
    return send_from_directory(current_app.static_folder, "terms.html")


@static_bp.route("/docs")
@static_bp.route("/docs/")
def docs_index():
    return send_from_directory(current_app.static_folder, "docs.html")


@static_bp.route("/docs/<path:page>")
def docs_page(page):
    return send_from_directory(current_app.static_folder, "docs.html")


@static_bp.route("/admin")
@static_bp.route("/admin/<path:page>")
def admin_page(page=None):
    import os
    if os.environ.get("ADMIN_ENABLED", "true").lower() != "true":
        return redirect("/")
    return send_from_directory(current_app.static_folder, "admin.html")
