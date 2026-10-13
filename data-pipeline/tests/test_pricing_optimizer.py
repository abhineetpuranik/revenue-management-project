"""
Phase 8b tests — demand scaling, stock cap, revenue, best-price selection.

Run:  cd data-pipeline && pytest tests/test_pricing_optimizer.py -v
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from pricing.demand_response import elasticity_scaled_demand  # noqa: E402
from pricing.next_week_features import _calendar_for_week, rows_at_prices  # noqa: E402
from pricing.optimizer import binding_constraint, select_best  # noqa: E402
from pricing.revenue import available_stock, score_candidates  # noqa: E402


def test_elasticity_scaling_returns_baseline_at_current_price():
    assert elasticity_scaled_demand(120.0, 10.0, 10.0, -1.7) == 120.0
    # 10 % price rise with β = −2  →  demand × 1.1^−2
    assert np.isclose(elasticity_scaled_demand(100.0, 11.0, 10.0, -2.0), 100.0 / 1.21)


def test_revenue_without_stock_limit():
    df = pd.DataFrame({"candidate_price": [10.0], "expected_demand": [50.0],
                       "available_stock": [1000.0], "unit_cost": [6.0]})
    out = score_candidates(df).iloc[0]
    assert out["expected_revenue"] == 500.0 and out["expected_profit"] == 200.0
    assert out["stock_limited"] == 0


def test_revenue_capped_by_stock():
    df = pd.DataFrame({"candidate_price": [10.0], "expected_demand": [50.0],
                       "available_stock": [30.0], "unit_cost": [6.0]})
    out = score_candidates(df).iloc[0]
    assert out["sellable_units"] == 30.0 and out["expected_revenue"] == 300.0
    assert out["stock_limited"] == 1


def test_available_stock_adds_one_restock():
    assert available_stock(100, 40) == 140


def _grid(beta, d0=100.0, current=10.0, stock=1e9, steps=range(-15, 16), fail=None):
    fail = fail or {}
    rows = []
    for k in steps:
        p = round(current * (1 + k / 100), 2)
        rows.append({"step": k, "candidate_price": p, "change_pct": p / current - 1,
                     "expected_demand": d0 * (p / current) ** beta, "available_stock": stock,
                     "unit_cost": 1.0, "passes_all": 0 if k in fail else 1,
                     "failed_reasons": fail.get(k, ""), "is_current": int(k == 0)})
    return score_candidates(pd.DataFrame(rows))


def test_inelastic_goes_to_upper_bound():
    g = _grid(-0.5)
    best = select_best(g)
    assert best["step"] == 15 and binding_constraint(g, best) == "MAX_CHANGE"


def test_elastic_goes_to_lower_bound():
    g = _grid(-2.0)
    best = select_best(g)
    assert best["step"] == -15 and binding_constraint(g, best) == "MAX_CHANGE"


def test_rejected_neighbour_is_the_binding_constraint():
    g = _grid(-2.0, fail={k: "MARGIN" for k in range(-15, -6)})
    best = select_best(g)
    assert best["step"] == -6 and binding_constraint(g, best) == "MARGIN"


def test_stock_cap_creates_interior_optimum():
    # elastic product, but stock only covers ~105 units → cutting past ~-2.4 % adds no units
    g = _grid(-2.0, stock=105.0)
    best = select_best(g)
    assert -5 <= best["step"] <= -1
    assert binding_constraint(g, best) == "STOCK"


def test_tie_break_prefers_smallest_move():
    g = _grid(-1.0)                       # revenue identical at every price (β = −1)
    best = select_best(g)
    assert best["step"] == 0
    g2 = _grid(-1.02)                     # tiny gain from cutting: within tolerance near 0
    assert abs(select_best(g2)["step"]) < 15
    assert binding_constraint(g2, select_best(g2)) in {"TIE_TOLERANCE", "MAX_CHANGE"}


def test_no_feasible_candidate_returns_none():
    g = _grid(-1.5, fail={k: "PRICE_RANGE" for k in range(-15, 16)})
    assert select_best(g) is None


def test_calendar_borrows_previous_year_for_missing_days():
    cal = pd.DataFrame({"date": pd.date_range("2024-01-01", "2024-12-31"),
                        "month": 1, "seasonal_factor": 1.0, "festival_flag": 0})
    cal.loc[cal["date"] == "2024-01-01", "festival_flag"] = 1
    days = _calendar_for_week(cal, pd.Timestamp("2024-12-30"))
    assert len(days) == 7
    assert days.loc[days["date"] == "2025-01-01", "source_date"].iloc[0] == pd.Timestamp("2024-01-01")
    assert days["festival_flag"].max() == 1


def test_rows_at_prices_sets_price_features():
    base = pd.DataFrame({"product_id": ["P1"], "prev_list_price_mean": [10.0], "lag_1_units": [5.0]})
    r = rows_at_prices(base, pd.DataFrame({"product_id": ["P1"], "price": [11.0]})).iloc[0]
    assert r["list_price_mean"] == 11.0 and np.isclose(r["price_change_pct"], 0.1)
    assert r["promo_days"] == 0 and r["avg_discount"] == 0.0


def test_pricing_ground_truth_isolation():
    """Only the validate_*.py files in pricing/ may reference ground truth."""
    forbidden = re.compile(r"revenue_management_gt|true_elasticity|gt_product_elasticity")
    for f in (PIPELINE_ROOT / "pricing").glob("*.py"):
        if f.name.startswith("validate_"):
            continue
        hits = forbidden.findall(f.read_text(encoding="utf-8"))
        assert not hits, f"{f.name} references ground truth: {set(hits)}"
