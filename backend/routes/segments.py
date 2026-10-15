"""
Segments blueprint — route handlers only, no business logic.

Endpoints
---------
GET /api/segments
GET /api/segments/customers
GET /api/customers/<customer_id>/segment
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request

from config import Config
from services.segment_service import (
    get_customer_segment,
    get_customers_page,
    get_segment_summary,
    segment_label_exists,
)

segments_bp = Blueprint("segments", __name__)


def _parse_pagination(args) -> tuple[int, int]:
    """
    Parse and validate ?page= and ?page_size= query parameters.
    Returns (page, page_size) or raises a 400 via abort().
    """
    try:
        page = int(args.get("page", 1))
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


@segments_bp.get("/api/segments")
def segments():
    """Return segment summary with Silhouette score and cluster count."""
    engine = current_app.config["DB_ENGINE"]
    return jsonify(get_segment_summary(engine))


@segments_bp.get("/api/segments/customers")
def customers_list():
    """
    Paginated customer list.

    Query params:
        segment   optional — filter by segment label
        page      default 1
        page_size default 50, max 200
    """
    engine  = current_app.config["DB_ENGINE"]
    segment = request.args.get("segment", "").strip() or None
    page, page_size = _parse_pagination(request.args)

    # Validate the segment label if supplied
    if segment and not segment_label_exists(engine, segment):
        abort(404, description=f"Segment '{segment}' not found.")

    return jsonify(get_customers_page(engine, segment, page, page_size))


@segments_bp.get("/api/customers/<string:customer_id>/segment")
def customer_segment(customer_id: str):
    """Return one customer's segment label and RFM values."""
    engine = current_app.config["DB_ENGINE"]
    result = get_customer_segment(engine, customer_id)

    if result is None:
        abort(404, description=f"Customer '{customer_id}' not found.")

    return jsonify(result)
