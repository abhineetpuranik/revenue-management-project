"""
Pricing ground-truth sanity check — Phase 8b.

THE ONLY PRICING FILE (besides validate_elasticity.py) ALLOWED TO READ GROUND TRUTH.

Question answered: does the elasticity ESTIMATION error change the pricing
DECISION? We re-run the same selection with true_elasticity in place of the
Phase 7 estimate (same baseline demand, same candidates, same rules) and report:

    * how many products get the same direction (raise / cut / hold)
    * mean absolute difference in recommended price (%)
    * revenue lost by deciding with the estimate: both decisions are evaluated
      under the TRUE demand curve, and the loss is
          1 − revenue_true(p_estimated) / revenue_true(p_true_optimal)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_gt_engine
from pricing.demand_response import elasticity_scaled_demand
from pricing.optimizer import select_best
from pricing.revenue import score_candidates


def _direction(change: float) -> str:
    return "hold" if abs(change) < 1e-9 else ("raise" if change > 0 else "cut")


def run_validation(scored: pd.DataFrame, recs: pd.DataFrame) -> dict:
    """
    scored : every candidate with candidate_price, current_price, baseline_demand,
             available_stock, unit_cost, passes_all, step (as built by run_pricing)
    recs   : the production recommendations (product_id, recommended_price, change_pct)
    """
    with get_gt_engine().connect() as conn:
        gt = pd.read_sql(text("SELECT product_id, true_elasticity FROM gt_product_elasticity"), conn)
    gt["true_elasticity"] = gt["true_elasticity"].astype(float)

    s = scored.merge(gt, on="product_id")
    s["expected_demand"] = elasticity_scaled_demand(s["baseline_demand"], s["candidate_price"],
                                                    s["current_price"], s["true_elasticity"])
    s = score_candidates(s)                        # revenue under the TRUE demand curve

    rows = []
    for pid, g in s.groupby("product_id"):
        best_true = select_best(g)
        est_price = float(recs.loc[recs["product_id"] == pid, "recommended_price"].iloc[0])
        rev_at_est = float(g.loc[np.isclose(g["candidate_price"], est_price), "expected_revenue"].iloc[0])
        rows.append({
            "product_id": pid,
            "price_estimated": est_price,
            "price_true": float(best_true["candidate_price"]),
            "dir_estimated": _direction(est_price / g["current_price"].iloc[0] - 1),
            "dir_true": _direction(float(best_true["change_pct"])),
            "revenue_true_optimal": float(best_true["expected_revenue"]),
            "revenue_true_at_estimated": rev_at_est,
        })
    v = pd.DataFrame(rows)
    v["price_diff_pct"] = (v["price_estimated"] / v["price_true"] - 1).abs() * 100
    v["revenue_loss_pct"] = (1 - v["revenue_true_at_estimated"] / v["revenue_true_optimal"]) * 100

    out = {
        "same_direction": int((v["dir_estimated"] == v["dir_true"]).sum()),
        "n_products": int(len(v)),
        "same_price": int((v["price_diff_pct"] < 1e-9).sum()),
        "mean_abs_price_diff_pct": float(v["price_diff_pct"].mean()),
        "total_revenue_loss_pct": float((1 - v["revenue_true_at_estimated"].sum()
                                         / v["revenue_true_optimal"].sum()) * 100),
        "max_revenue_loss_pct": float(v["revenue_loss_pct"].max()),
    }
    print(f"  Same direction (raise/cut/hold) : {out['same_direction']} / {out['n_products']}")
    print(f"  Identical recommended price     : {out['same_price']} / {out['n_products']}")
    print(f"  Mean |price difference|         : {out['mean_abs_price_diff_pct']:.2f} %")
    print(f"  Revenue lost vs. true-optimal   : {out['total_revenue_loss_pct']:.3f} % overall, "
          f"worst product {out['max_revenue_loss_pct']:.3f} %")
    diff = v[v["dir_estimated"] != v["dir_true"]]
    if len(diff):
        print("\n  Products where the estimate leads to a different direction")
        print(diff[["product_id", "price_estimated", "price_true", "dir_estimated", "dir_true",
                    "revenue_loss_pct"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    return out
