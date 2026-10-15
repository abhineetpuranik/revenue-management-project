"""
Forecast blueprint — route handlers only, no business logic.

Endpoints
---------
GET /api/products
GET /api/forecast/metrics
GET /api/forecast/<product_id>
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request

from services.forecast_service import (
    get_all_products,
    get_forecast,
    get_forecast_metrics,
    product_exists,
)

forecast_bp = Blueprint("forecast", __name__)


@forecast_bp.get("/api/products")
def products():
    """List all products with optional ?category= filter."""
    category = request.args.get("category", "").strip() or None
    engine   = current_app.config["DB_ENGINE"]
    return jsonify(get_all_products(engine, category=category))


@forecast_bp.get("/api/forecast/metrics")
def forecast_metrics():
    """Return Phase 5 model comparison metadata."""
    metadata = current_app.config["MODEL_METADATA"]
    return jsonify(get_forecast_metrics(metadata))


@forecast_bp.get("/api/forecast/<string:product_id>")
def forecast(product_id: str):
    """Return the forecast time series for one product."""
    engine   = current_app.config["DB_ENGINE"]
    model    = current_app.config["FORECAST_MODEL"]
    metadata = current_app.config["MODEL_METADATA"]
    history  = current_app.config["FORECAST_HISTORY_WEEKS"]

    if not product_exists(engine, product_id):
        abort(404, description=f"Product '{product_id}' not found.")

    result = get_forecast(engine, model, metadata, product_id, history)
    return jsonify(result)
