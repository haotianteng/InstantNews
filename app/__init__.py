"""Flask application factory."""

import os

from flask import Flask

from app.config import Config
from app.database import init_db, create_tables, get_session
from app.routes import register_routes


def create_app(config_class=None):
    """Create and configure the Flask application.

    Args:
        config_class: Configuration class. Defaults to Config.
    """
    if config_class is None:
        config_class = Config

    # Resolve static folder relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_folder = os.path.join(project_root, "static")

    app = Flask(
        __name__,
        static_folder=static_folder,
        static_url_path="",
    )

    # Store config for access in routes via current_app.config
    app.config["APP_CONFIG"] = config_class

    # Initialize database
    engine = init_db(config_class.DATABASE_URL)
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine)
    app.config["SESSION_FACTORY"] = session_factory

    # Create tables (dev/test bootstrap — in prod, use alembic)
    create_tables()

    # Register auth middleware and routes
    _init_auth(app, config_class)

    # Register billing routes
    from app.billing.routes import billing_bp
    app.register_blueprint(billing_bp)

    # Register routes
    register_routes(app)

    # Start background worker if enabled
    if getattr(config_class, "WORKER_ENABLED", False):
        _start_background_worker(app, session_factory, config_class)

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
        except Exception:
            pass  # Firebase not configured — auth will treat all as anonymous


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
                    pass

        scheduler.add_job(
            refresh_job,
            "interval",
            seconds=config.WORKER_INTERVAL_SECONDS,
            id="feed_refresh",
            replace_existing=True,
        )
        scheduler.start()
        app.extensions["scheduler"] = scheduler
    except ImportError:
        pass
