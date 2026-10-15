"""
Pricing blueprint — route handlers only, no business logic.

Endpoints
---------
GET /api/pricing/recommendations          paginated list of all recommendations
GET /api/pricing/<product_id>             one product's recommendation
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request

from config import Config
from services.forecast_service import product_exists
from services.pricing_service import (
    get_all_recommendations,
    get_recommendation,
)

pricing_bp = Blueprint("pricing", __name__)


def _parse_pagination(args):
    """Reuse 10a validation pattern — raises 400 via abort() on bad input."""
    try:
        page      = int(args.get("page",      1))
        page_size = int(args.get("page_size", Config.DEFAULT_PAGE_SIZE))
    except (ValueError, TypeError):
        abort(400, description="'page' and 'page_size' must be positive integers.")
    if page < 1:
        abort(400, description="'page' must be >= 1.")
    if page_size < 1:
        abort(400, description="'page_size' must be >= 1.")
    if page_size > Config.MAX_PAGE_SIZE:
        abort(400, description=f"'page_size' must be <= {Config.MAX_PAGE_SIZE}.")
    return page, page_size


@pricing_bp.get("/api/pricing/recommendations")
def recommendations_list():
    """
    Paginated pricing recommendations for all products.

    Query params
    ------------
    category  : optional filter (e.g. Staples, Electronics)
    page      : default 1
    page_size : default 50, max 200
    """
    engine   = current_app.config["DB_ENGINE"]
    category = request.args.get("category", "").strip() or None
    page, page_size = _parse_pagination(request.args)

    return jsonify(get_all_recommendations(engine, category, page, page_size))


@pricing_bp.get("/api/pricing/<string:product_id>")
def recommendation(product_id: str):
    """
    Pricing recommendation for one product.

    Returns HTTP 200 even when no valid candidate price exists
    (recommendation_available: false).  Returns HTTP 404 only when the
    product_id is not in the database at all.
    """
    engine = current_app.config["DB_ENGINE"]

    if not product_exists(engine, product_id):
        abort(404, description=f"Product '{product_id}' not found.")

    result = get_recommendation(engine, product_id)
    if result is None:
        # Product exists in the products table but has no recommendation row.
        # This means Phase 8 hasn't been run yet.
        abort(
            404,
            description=(
                f"No pricing recommendation found for '{product_id}'. "
                "Run python -m pricing.run_pricing in the data pipeline."
            ),
        )

    return jsonify(result)
