"""Serve the frontend SPA."""

from flask import Blueprint, send_from_directory, current_app

static_bp = Blueprint("static_pages", __name__)


@static_bp.route("/")
def index():
    return send_from_directory(current_app.static_folder, "index.html")


@static_bp.route("/pricing")
def pricing():
    return send_from_directory(current_app.static_folder, "pricing.html")


@static_bp.route("/privacy")
def privacy():
    return send_from_directory(current_app.static_folder, "privacy.html")


@static_bp.route("/terms")
def terms():
    return send_from_directory(current_app.static_folder, "terms.html")
