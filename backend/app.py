"""
Flask application factory.

Usage
-----
    # development
    python app.py

    # production / WSGI
    from app import create_app
    app = create_app()

The app factory pattern lets tests instantiate isolated app instances
without starting a real server.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

# ── PYTHONPATH: make data-pipeline importable before any other import ─────
_PIPELINE_ROOT = str(Path(__file__).resolve().parent.parent / "data-pipeline")
if _PIPELINE_ROOT not in sys.path:
    sys.path.insert(0, _PIPELINE_ROOT)

from config import Config
from errors import register_error_handlers
from routes.explanations import explanations_bp
from routes.forecast import forecast_bp
from routes.pricing import pricing_bp
from routes.segments import segments_bp

logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _load_model():
    """Load the Phase 5 production model once at startup."""
    from models.train_forecasting_models import load_model_metadata, load_production_model
    model    = load_production_model(Config.MODEL_ARTIFACT_PATH)
    metadata = load_model_metadata(Config.MODEL_METADATA_PATH)
    logger.info(
        "Loaded %s model (trained %s, test RMSE %.3f)",
        metadata.get("model_type", "?"),
        metadata.get("trained_at", "?"),
        metadata.get("metrics", {}).get("XGBoost", {}).get("rmse", float("nan")),
    )
    return model, metadata


def _get_engine():
    """Return the SQLAlchemy engine for the application database."""
    from etl.db_connection import get_engine
    return get_engine(Config.DB_NAME)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}})

    # ── Load Phase 5 model (once) ─────────────────────────────────────────
    model, metadata = _load_model()
    app.config["FORECAST_MODEL"]      = model
    app.config["MODEL_METADATA"]      = metadata
    app.config["FORECAST_HISTORY_WEEKS"] = Config.FORECAST_HISTORY_WEEKS

    # ── Database engine ────────────────────────────────────────────────────
    app.config["DB_ENGINE"] = _get_engine()

    # ── Blueprints ─────────────────────────────────────────────────────────
    app.register_blueprint(forecast_bp)
    app.register_blueprint(segments_bp)
    app.register_blueprint(pricing_bp)
    app.register_blueprint(explanations_bp)

    # ── Health check (kept from Phase 0) ──────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    # ── Error handlers ─────────────────────────────────────────────────────
    register_error_handlers(app)

    logger.info("App ready — CORS origins: %s", Config.CORS_ORIGINS)
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.DEBUG,
    )
