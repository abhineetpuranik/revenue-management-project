"""
Elasticity validation — Phase 7 (Module 4a).

THE ONLY Phase 7 FILE ALLOWED TO READ GROUND TRUTH.
It compares the estimated elasticities with revenue_management_gt.gt_product_elasticity
and reports:

    * MAE, RMSE, Pearson correlation
    * % of products within ±0.2 of the true value
    * % with the correct (negative) sign
    * 95 % CI coverage (share of products whose CI contains the true value)
    * per-category table: mean estimate vs. mean true value vs. design anchor
    * a design comparison of alternative specifications (for the viva):
        - PRODUCTION : weekly, list price, promo control
        - DAILY      : daily, list price, promo + weekday controls, zero days dropped
        - SALE_PRICE : weekly, price_at_sale, NO promo control
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from data_generation.config import CATEGORIES  # design anchors (generator config)
from etl.db_connection import get_gt_engine
from pricing.elasticity_model import fit_all, fit_product

logger = logging.getLogger(__name__)

WITHIN_TOLERANCE: float = 0.2

_GT_SQL = "SELECT product_id, true_elasticity FROM gt_product_elasticity"


def load_ground_truth(gt_engine=None) -> pd.DataFrame:
    """Read true elasticity per product from the ground-truth schema."""
    gt_engine = gt_engine or get_gt_engine()
    with gt_engine.connect() as conn:
        gt = pd.read_sql(text(_GT_SQL), conn)
    gt["true_elasticity"] = gt["true_elasticity"].astype(float)
    return gt


def compute_metrics(est: pd.DataFrame, gt: pd.DataFrame, col: str = "elasticity") -> dict:
    """Accuracy metrics of estimates in `col` against true_elasticity."""
    m = est.merge(gt, on="product_id", how="inner").dropna(subset=[col])
    err = m[col] - m["true_elasticity"]
    out = {
        "n_products": int(len(m)),
        "mae": float(err.abs().mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "correlation": float(np.corrcoef(m[col], m["true_elasticity"])[0, 1]),
        "within_0_2_pct": float((err.abs() <= WITHIN_TOLERANCE).mean() * 100),
        "correct_sign_pct": float((np.sign(m[col]) == np.sign(m["true_elasticity"])).mean() * 100),
    }
    if {"ci_low", "ci_high"} <= set(m.columns):
        covered = (m["ci_low"] <= m["true_elasticity"]) & (m["true_elasticity"] <= m["ci_high"])
        out["ci_coverage_pct"] = float(covered.mean() * 100)
    return out


def per_category_table(est: pd.DataFrame, gt: pd.DataFrame) -> pd.DataFrame:
    m = est.merge(gt, on="product_id")
    tbl = (
        m.groupby("category")
        .agg(products=("product_id", "size"),
             mean_estimate=("elasticity", "mean"),
             mean_true=("true_elasticity", "mean"),
             mae=("elasticity", lambda s: float((s - m.loc[s.index, "true_elasticity"]).abs().mean())))
        .reset_index()
    )
    tbl["design_anchor"] = tbl["category"].map(
        {k: v.get("elasticity_anchor") for k, v in CATEGORIES.items()}
    )
    return tbl.sort_values("design_anchor", ascending=False).reset_index(drop=True)


def _daily_variant(daily: pd.DataFrame) -> pd.DataFrame:
    """DAILY spec: one row per product-day, zero days dropped inside fit_product."""
    d = daily.copy()
    d["log_price_ratio"] = np.log(d["list_price"] / d["base_price"])
    d["log_seasonal"] = np.log(d["seasonal_factor"])
    d["log_weekday"] = np.log(d["weekday_factor"])
    return fit_all(d, control_cols=["is_promo", "log_seasonal", "log_weekday", "festival_flag"])


def design_comparison(daily: pd.DataFrame, weekly: pd.DataFrame,
                      production: pd.DataFrame, gt: pd.DataFrame) -> pd.DataFrame:
    """MAE etc. of the production spec vs. two rejected alternatives."""
    variants = {
        "PRODUCTION (weekly, list price, promo control)": production,
        "DAILY (zero days dropped)": _daily_variant(daily),
        "SALE_PRICE (weekly, price_at_sale, no promo control)": fit_all(
            weekly, price_col="log_sale_price_ratio",
            control_cols=["log_seasonal", "festival_days"]),
    }
    rows = []
    for name, est in variants.items():
        met = compute_metrics(est, gt)
        rows.append({"specification": name, **{k: met[k] for k in
                     ["mae", "rmse", "correlation", "within_0_2_pct"]}})
    return pd.DataFrame(rows)


def run_validation(est: pd.DataFrame, daily: pd.DataFrame | None = None,
                   weekly: pd.DataFrame | None = None) -> dict:
    """Print the full validation report; returns the headline metrics."""
    gt = load_ground_truth()
    metrics = compute_metrics(est, gt)

    print("\n  Accuracy vs. ground truth (true_elasticity)")
    print(f"    products evaluated   : {metrics['n_products']}")
    print(f"    MAE                  : {metrics['mae']:.4f}")
    print(f"    RMSE                 : {metrics['rmse']:.4f}")
    print(f"    correlation          : {metrics['correlation']:.4f}")
    print(f"    within ±{WITHIN_TOLERANCE}          : {metrics['within_0_2_pct']:.1f} %")
    print(f"    correct sign         : {metrics['correct_sign_pct']:.1f} %")
    print(f"    95% CI coverage      : {metrics['ci_coverage_pct']:.1f} %")

    print("\n  Per-category (estimate vs. truth vs. generator anchor)")
    print(per_category_table(est, gt).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    worst = est.merge(gt, on="product_id")
    worst["abs_error"] = (worst["elasticity"] - worst["true_elasticity"]).abs()
    print("\n  Five largest errors")
    print(worst.sort_values("abs_error", ascending=False)
          .head(5)[["product_id", "category", "elasticity", "true_elasticity", "abs_error", "n_obs"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    if daily is not None and weekly is not None:
        comp = design_comparison(daily, weekly, est, gt)
        metrics["design_comparison"] = comp.to_dict(orient="records")
        print("\n  Design comparison (why the production specification was chosen)")
        print(comp.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    return metrics
