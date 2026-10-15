"""
Pricing service — no Flask-specific code.

Reads pre-computed pricing recommendations from the
revenue_management.pricing_recommendation MySQL table (written by Phase 8).
Never re-runs the optimizer at request time.

Provides
--------
get_recommendation(engine, product_id)      → dict | None
get_all_recommendations(engine, category)   → list[dict]
recommendation_exists(engine, product_id)   → bool
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import text

# ── SQL ───────────────────────────────────────────────────────────────────

_REC_SQL = text("""
    SELECT
        r.product_id,
        r.category,
        r.current_price,
        r.recommended_price,
        r.change_pct,
        r.elasticity,
        r.baseline_demand,
        r.expected_demand,
        r.available_stock,
        r.current_revenue,
        r.expected_revenue,
        r.revenue_change_pct,
        r.unit_cost,
        r.margin_pct,
        r.expected_profit,
        r.stock_limited,
        r.binding_constraint,
        r.reason_codes,
        r.model_type,
        r.forecast_week,
        r.generated_at
    FROM pricing_recommendation r
    WHERE r.product_id = :pid
""")

_ALL_RECS_SQL = text("""
    SELECT
        r.product_id,
        r.category,
        r.current_price,
        r.recommended_price,
        r.change_pct,
        r.elasticity,
        r.baseline_demand,
        r.expected_demand,
        r.available_stock,
        r.current_revenue,
        r.expected_revenue,
        r.revenue_change_pct,
        r.unit_cost,
        r.margin_pct,
        r.expected_profit,
        r.stock_limited,
        r.binding_constraint,
        r.reason_codes,
        r.model_type,
        r.forecast_week,
        r.generated_at
    FROM pricing_recommendation r
    ORDER BY r.product_id
""")

_ALL_RECS_FILTERED_SQL = text("""
    SELECT
        r.product_id,
        r.category,
        r.current_price,
        r.recommended_price,
        r.change_pct,
        r.elasticity,
        r.baseline_demand,
        r.expected_demand,
        r.available_stock,
        r.current_revenue,
        r.expected_revenue,
        r.revenue_change_pct,
        r.unit_cost,
        r.margin_pct,
        r.expected_profit,
        r.stock_limited,
        r.binding_constraint,
        r.reason_codes,
        r.model_type,
        r.forecast_week,
        r.generated_at
    FROM pricing_recommendation r
    WHERE r.category = :category
    ORDER BY r.product_id
""")

_COUNT_SQL = text("""
    SELECT COUNT(*) AS n FROM pricing_recommendation
    WHERE (:category IS NULL OR category = :category)
""")

_EXISTS_SQL = text("""
    SELECT COUNT(*) AS n FROM pricing_recommendation WHERE product_id = :pid
""")

# Constraints are read from the pipeline config so the API always reflects
# whatever values Phase 8 actually used.  Import lazily to avoid hard
# dependency at module load time.
def _constraints() -> dict:
    try:
        from pricing.pricing_config import (
            MAX_PRICE_CHANGE_PCT,
            MIN_MARGIN_PCT,
        )
        return {
            "min_margin_pct":      MIN_MARGIN_PCT,
            "max_price_change_pct": MAX_PRICE_CHANGE_PCT,
        }
    except ImportError:
        return {
            "min_margin_pct":      0.10,
            "max_price_change_pct": 0.15,
        }


# ── Serialisation ─────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict[str, Any]:
    """Convert a SQLAlchemy Row to a clean API dict."""
    reason_codes_raw = str(row.reason_codes or "")
    reason_list = [r for r in reason_codes_raw.split(",") if r]
    binding = str(row.binding_constraint or "")
    no_valid = binding == "NO_FEASIBLE_PRICE"

    return {
        "product_id":           row.product_id,
        "category":             row.category,
        "recommendation_available": not no_valid,
        "no_candidate_reason":  reason_codes_raw if no_valid else None,

        # Current state
        "current_price":        float(row.current_price),
        "current_revenue":      float(row.current_revenue),
        "unit_cost":            float(row.unit_cost),
        "available_stock":      int(row.available_stock),
        "elasticity":           float(row.elasticity),
        "baseline_demand":      float(row.baseline_demand),

        # Recommendation
        "recommended_price":    float(row.recommended_price),
        "change_pct":           float(row.change_pct),
        "expected_demand":      float(row.expected_demand),
        "expected_revenue":     float(row.expected_revenue),
        "revenue_change_pct":   float(row.revenue_change_pct),
        "revenue_change_abs":   round(
            float(row.expected_revenue) - float(row.current_revenue), 2
        ),
        "margin_pct":           float(row.margin_pct),
        "expected_profit":      float(row.expected_profit),
        "stock_limited":        bool(row.stock_limited),

        # Constraint explanation
        "binding_constraint":   binding,
        "reason_codes":         reason_list,

        # Applied constraints (from Phase 8 config)
        "constraints_applied":  _constraints(),

        # Provenance
        "model_type":           str(row.model_type),
        "forecast_week":        str(row.forecast_week),
        "generated_at":         str(row.generated_at),
    }


# ── Public service functions ──────────────────────────────────────────────

def recommendation_exists(engine, product_id: str) -> bool:
    with engine.connect() as conn:
        n = conn.execute(_EXISTS_SQL, {"pid": product_id}).scalar()
    return int(n) > 0


def get_recommendation(engine, product_id: str) -> dict | None:
    """Return recommendation dict for one product, or None if not found."""
    with engine.connect() as conn:
        row = conn.execute(_REC_SQL, {"pid": product_id}).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def get_all_recommendations(
    engine,
    category: str | None,
    page: int,
    page_size: int,
) -> dict:
    """Return paginated recommendations, optionally filtered by category."""
    params_count = {"category": category}
    with engine.connect() as conn:
        total = int(conn.execute(_COUNT_SQL, params_count).scalar())
        if category:
            rows = conn.execute(
                _ALL_RECS_FILTERED_SQL, {"category": category}
            ).fetchall()
        else:
            rows = conn.execute(_ALL_RECS_SQL).fetchall()

    all_dicts = [_row_to_dict(r) for r in rows]
    offset = (page - 1) * page_size
    page_items = all_dicts[offset: offset + page_size]

    return {
        "total":           total,
        "page":            page,
        "page_size":       page_size,
        "pages":           math.ceil(total / page_size) if page_size else 1,
        "recommendations": page_items,
    }
