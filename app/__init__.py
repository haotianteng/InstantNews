"""Flask application factory."""

import logging
import os

from flask import Flask

from app.config import Config
from app.database import init_db, create_tables, get_session
from app.logging_config import configure_logging
from app.routes import register_routes

logger = logging.getLogger("signal")


def create_app(config_class=None):
    """Create and configure the Flask application.

    Args:
        config_class: Configuration class. Defaults to Config.
    """
    if config_class is None:
        config_class = Config

    # Set up structured JSON logging before anything else
    log_level = "DEBUG" if getattr(config_class, "TESTING", False) else "INFO"
    configure_logging(level=log_level)

    # Resolve static folder relative to project root
    # Vite builds to static/; fall back to static/ for backward compat
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_folder = os.path.join(project_root, "static")

    app = Flask(
        __name__,
        static_folder=static_folder,
        static_url_path="",
    )

    # Store config for access in routes via current_app.config
    app.config["APP_CONFIG"] = config_class

    # Initialize database (primary)
    engine = init_db(config_class.DATABASE_URL)
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine)
    app.config["SESSION_FACTORY"] = session_factory

    # Initialize read replica (for admin/analytics, falls back to primary if not set)
    replica_host = os.environ.get("DB_REPLICA_HOST", "")
    if replica_host:
        from app.database import init_replica_db
        replica_port = os.environ.get("DB_PORT", "5432")
        replica_db = os.environ.get("DB_NAME", "signal_news")
        replica_user = os.environ.get("DB_USER", "signal")
        replica_pw = os.environ.get("DB_PASSWORD", "")
        replica_url = f"postgresql://{replica_user}:{replica_pw}@{replica_host}:{replica_port}/{replica_db}"
        init_replica_db(replica_url)
        logger.info("Read replica initialized", extra={"host": replica_host})

    # Create tables (dev/test bootstrap — in prod, use alembic)
    create_tables()

    # Register auth middleware and routes
    _init_auth(app, config_class)

    # Initialize request logging (must come after auth so user is available)
    from app.middleware.request_logger import init_request_logger
    init_request_logger(app)

    # Initialize rate limiting (must come after auth middleware)
    from app.middleware.rate_limit import init_rate_limiter
    init_rate_limiter(app)

    # Register billing routes
    from app.billing.routes import billing_bp
    app.register_blueprint(billing_bp)

    # Register routes
    register_routes(app)

    # Start background worker if enabled
    if getattr(config_class, "WORKER_ENABLED", False):
        _start_background_worker(app, session_factory, config_class)

    logger.info("Application initialized", extra={"event": "app_start"})

    return app


def _init_auth(app, config_class):
    """Set up auth middleware and routes."""
    from app.auth.middleware import load_current_user
    from app.auth.routes import auth_bp

    app.before_request(load_current_user)
    app.register_blueprint(auth_bp)

    # Initialize Firebase Admin SDK (skip in tests)
    if not getattr(config_class, "TESTING", False):
        try:
            from app.auth.firebase import init_firebase
            init_firebase()
            logger.info("Firebase Admin SDK initialized")
        except Exception:
            logger.warning("Firebase not configured — auth will treat all as anonymous")


def _start_background_worker(app, session_factory, config):
    """Start APScheduler for periodic feed refresh."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.services.feed_refresh import refresh_feeds_parallel

        scheduler = BackgroundScheduler(daemon=True)

        def refresh_job():
            with app.app_context():
                try:
                    refresh_feeds_parallel(session_factory, config)
                except Exception:
                    logger.exception("Background feed refresh failed")

        scheduler.add_job(
            refresh_job,
            "interval",
            seconds=config.WORKER_INTERVAL_SECONDS,
            id="feed_refresh",
            replace_existing=True,
        )
        scheduler.start()
        app.extensions["scheduler"] = scheduler
        logger.info("Background scheduler started (interval=%ds)",
                     config.WORKER_INTERVAL_SECONDS)
    except ImportError:
        logger.warning("APScheduler not installed — background worker disabled")
