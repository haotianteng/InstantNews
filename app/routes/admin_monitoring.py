"""Admin monitoring dashboard — HTML route.

Serves the /admin/monitoring single-page dashboard (built by Vite into
``static/admin-monitoring.html``). Page content is empty scaffolding in
US-008 — panels US-009..US-013 populate the tiles in-place.

Access control: ``@require_admin`` from ``app.admin.auth`` relies on the
auth middleware populating ``g.current_user`` from the Bearer token carried
in the request. Anonymous navigation returns 401; authenticated non-admin
users see 403.

Blueprint is only registered when ``ADMIN_ENABLED=true`` — same guard that
gates the admin API routes. On the production admin ECS service this page
is reachable at ``https://admin.instnews.net/admin/monitoring`` (behind the
internal ALB + VPN).
"""

from __future__ import annotations

from flask import Blueprint, current_app, send_from_directory

from app.admin.auth import require_admin

admin_monitoring_bp = Blueprint("admin_monitoring", __name__)


@admin_monitoring_bp.route("/admin/monitoring")
@require_admin
def monitoring_page():
    """Serve the monitoring dashboard HTML (Vite-built entry)."""
    return send_from_directory(
        current_app.static_folder, "admin-monitoring.html"
    )
