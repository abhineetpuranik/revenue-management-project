"""Phase 13 — Item 13: pricing constraint compliance on stored DB data.

Loads the 50 stored recommendations from the ``pricing_recommendation``
table and asserts zero constraint violations (minimum margin and maximum
price change), and that every recommendation carries a negative elasticity.
Requires DB access.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def _db_ready() -> bool:
    """True when DB credentials are available (env or data-pipeline/.env)."""
    from dotenv import load_dotenv

    load_dotenv(PIPELINE_ROOT / ".env")
    return bool(os.getenv("DB_USER") and os.getenv("DB_PASSWORD"))


NEEDS_DB = pytest.mark.skipif(
    not _db_ready(), reason="requires live MySQL + DB credentials"
)


@NEEDS_DB
def test_all_stored_recommendations_satisfy_constraints():
    from dotenv import load_dotenv

    from etl.db_connection import get_engine
    from pricing.constraints import check_margin, check_max_change
    from pricing.pricing_config import MAX_PRICE_CHANGE_PCT, MIN_MARGIN_PCT
    from pricing.run_pricing import get_all_recommendations

    load_dotenv(PIPELINE_ROOT / ".env")
    engine = get_engine()
    recs = get_all_recommendations(engine)
    violations = []
    for _, row in recs.iterrows():
        if row["binding_constraint"] == "NO_FEASIBLE_PRICE":
            continue
        p, cost = float(row["recommended_price"]), float(row["unit_cost"])
        current = float(row["current_price"])
        ok_margin, _ = check_margin(p, cost, MIN_MARGIN_PCT)
        ok_change, _ = check_max_change(p, current, MAX_PRICE_CHANGE_PCT)
        if not ok_margin:
            violations.append(
                f"{row['product_id']}: MARGIN violated (p={p}, cost={cost})"
            )
        if not ok_change:
            violations.append(
                f"{row['product_id']}: MAX_CHANGE violated (p={p}, current={current})"
            )
    assert not violations, "Constraint violations found:\n" + "\n".join(violations)


@NEEDS_DB
def test_all_recommendations_have_negative_elasticity():
    from dotenv import load_dotenv

    from etl.db_connection import get_engine
    from pricing.run_pricing import get_all_recommendations

    load_dotenv(PIPELINE_ROOT / ".env")
    engine = get_engine()
    recs = get_all_recommendations(engine)
    bad = recs[recs["elasticity"] >= 0]
    assert bad.empty, f"Non-negative elasticities: {bad['product_id'].tolist()}"
