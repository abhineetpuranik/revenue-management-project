"""
Explanations blueprint — route handlers only, no business logic.

Phase 9 supports two entity types: 'pricing' and 'segment'.
Forecast explanations are not supported; the endpoint returns a graceful
"unavailable" 200 response rather than a 404, so Phase 11 can always call
the same pattern without conditional logic.

Endpoints
---------
GET /api/pricing/<product_id>/explanation
GET /api/forecast/<product_id>/explanation    (graceful unavailable — see service)
GET /api/segments/<segment_label>/explanation
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify

from services.explanation_service import (
    get_forecast_explanation,
    get_pricing_explanation,
    get_segment_explanation,
    product_exists,
    segment_label_exists,
)

explanations_bp = Blueprint("explanations", __name__)


@explanations_bp.get("/api/pricing/<string:product_id>/explanation")
def pricing_explanation(product_id: str):
    """
    Natural-language explanation for a product's pricing recommendation.

    Returns HTTP 200 always (provided the product exists).
    If no stored explanation is available, returns:
        {"explanation_available": false, "explanation": null, ...}
    Never crashes or returns 500 because of an LLM failure.
    """
    engine = current_app.config["DB_ENGINE"]

    if not product_exists(engine, product_id):
        abort(404, description=f"Product '{product_id}' not found.")

    return jsonify(get_pricing_explanation(engine, product_id))


@explanations_bp.get("/api/forecast/<string:product_id>/explanation")
def forecast_explanation(product_id: str):
    """
    Forecast explanations are not supported by Phase 9.

    Always returns HTTP 200 with explanation_available: false so Phase 11
    can call this endpoint without needing to special-case its absence.
    """
    engine = current_app.config["DB_ENGINE"]

    if not product_exists(engine, product_id):
        abort(404, description=f"Product '{product_id}' not found.")

    return jsonify(get_forecast_explanation(engine, product_id))


@explanations_bp.get("/api/segments/<string:segment_label>/explanation")
def segment_explanation(segment_label: str):
    """Natural-language description of a customer segment."""
    engine = current_app.config["DB_ENGINE"]

    if not segment_label_exists(engine, segment_label):
        abort(404, description=f"Segment '{segment_label}' not found.")

    return jsonify(get_segment_explanation(engine, segment_label))
