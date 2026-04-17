"""Register all route blueprints."""

from app.routes.news import news_bp
from app.routes.sources import sources_bp
from app.routes.stats import stats_bp
from app.routes.refresh import refresh_bp
from app.routes.docs import docs_bp
from app.routes.keys import keys_bp
from app.routes.usage import usage_bp
from app.routes.market import market_bp
from app.routes.company import company_bp
from app.routes.health import health_bp
from app.routes.static_pages import static_bp
import os


def register_routes(app):
    app.register_blueprint(news_bp)
    app.register_blueprint(sources_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(refresh_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(keys_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(health_bp)

    # Admin routes only load when ADMIN_ENABLED=true (admin ECS service)
    if os.environ.get("ADMIN_ENABLED", "true").lower() == "true":
        from app.admin.routes import admin_bp
        from app.admin.metrics import metrics_bp as admin_metrics_bp
        app.register_blueprint(admin_bp)
        app.register_blueprint(admin_metrics_bp)

    app.register_blueprint(static_bp)
