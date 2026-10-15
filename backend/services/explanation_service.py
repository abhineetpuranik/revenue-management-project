"""
Explanation service — no Flask-specific code.

Strategy
--------
Explanations are read from the revenue_management.llm_explanation MySQL
table (written by Phase 9 run_segmentation / run_pricing).

The table already contains 50 pricing explanations and 4 segment
explanations — both entity types are supported.

On-demand generation is NOT performed here.  The API serves what Phase 9
pre-computed.  If an entity is not in the table, the response indicates
the explanation is unavailable rather than calling the LLM live.

This keeps the API stateless, fast, and free of LLM-timeout risk in
normal operation.  If a user calls /explanation for a product that does
not have a stored row (e.g., because Phase 9 hasn't been run), they get
a graceful "unavailable" response rather than a 500.

Provides
--------
get_pricing_explanation(engine, product_id)        → dict
get_forecast_explanation(engine, product_id)       → dict  (unavailable — see below)
get_segment_explanation(engine, segment_label)     → dict
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── SQL ───────────────────────────────────────────────────────────────────

_EXPLANATION_SQL = text("""
    SELECT entity_type, entity_id, explanation_text, source,
           guardrail_status, payload_json, model_name, attempts, generated_at
    FROM llm_explanation
    WHERE entity_type = :etype AND entity_id = :eid
""")

_SEGMENT_EXISTS_SQL = text("""
    SELECT COUNT(*) AS n FROM segment_summary WHERE segment_label = :label
""")

_PRODUCT_EXISTS_SQL = text("""
    SELECT COUNT(*) AS n FROM product WHERE product_id = :pid
""")


# ── Helpers ───────────────────────────────────────────────────────────────

def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "explanation_available": False,
        "explanation":           None,
        "unavailable_reason":    reason,
        "payload":               None,
        "source":                None,
        "generated_at":          None,
    }


def _explanation_row_to_dict(row) -> dict[str, Any]:
    payload = None
    if row.payload_json:
        try:
            payload = json.loads(row.payload_json)
        except (ValueError, TypeError):
            payload = None

    return {
        "explanation_available": True,
        "explanation":           str(row.explanation_text),
        "source":                str(row.source),          # "llm", "fallback", or "mock"
        "guardrail_status":      str(row.guardrail_status),
        "model_name":            str(row.model_name),
        "attempts":              int(row.attempts),
        "payload":               payload,
        "generated_at":          str(row.generated_at),
    }


# ── Public service functions ──────────────────────────────────────────────

def get_pricing_explanation(engine, product_id: str) -> dict:
    """
    Return the stored LLM explanation for a pricing recommendation.

    If no row exists in llm_explanation, returns a graceful unavailable dict.
    The caller is responsible for verifying the product exists beforehand
    (to distinguish 404 from explanation-not-yet-generated).
    """
    with engine.connect() as conn:
        row = conn.execute(
            _EXPLANATION_SQL,
            {"etype": "pricing", "eid": product_id},
        ).fetchone()

    if row is None:
        logger.info(
            "No stored pricing explanation for %s — "
            "run explanations.generate_explanations to populate.",
            product_id,
        )
        return _unavailable(
            "No explanation has been generated yet. "
            "Run python -m explanations.generate_explanations in the data pipeline."
        )

    result = _explanation_row_to_dict(row)
    result["entity_type"] = "pricing"
    result["entity_id"]   = product_id
    return result


def get_segment_explanation(engine, segment_label: str) -> dict:
    """Return the stored LLM explanation for a customer segment."""
    with engine.connect() as conn:
        row = conn.execute(
            _EXPLANATION_SQL,
            {"etype": "segment", "eid": segment_label},
        ).fetchone()

    if row is None:
        logger.info("No stored segment explanation for %s.", segment_label)
        return _unavailable(
            "No explanation has been generated yet. "
            "Run python -m explanations.generate_explanations in the data pipeline."
        )

    result = _explanation_row_to_dict(row)
    result["entity_type"] = "segment"
    result["entity_id"]   = segment_label
    return result


def get_forecast_explanation(engine, product_id: str) -> dict:
    """
    Forecast explanations are not supported by Phase 9.

    Phase 9 only generates 'pricing' and 'segment' entity types.
    This endpoint returns a well-formed unavailable response so that
    Phase 11 can handle the case gracefully rather than receiving a 404.
    """
    return _unavailable(
        "Forecast explanations are not supported in Phase 9. "
        "Phase 9 generates explanations for 'pricing' and 'segment' entity types only."
    )


def product_exists(engine, product_id: str) -> bool:
    with engine.connect() as conn:
        n = conn.execute(_PRODUCT_EXISTS_SQL, {"pid": product_id}).scalar()
    return int(n) > 0


def segment_label_exists(engine, label: str) -> bool:
    with engine.connect() as conn:
        n = conn.execute(_SEGMENT_EXISTS_SQL, {"label": label}).scalar()
    return int(n) > 0
