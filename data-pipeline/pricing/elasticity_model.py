"""
Elasticity model — Phase 7 (Module 4a).

Fits one log-log OLS regression per product on the weekly panel from
elasticity_data.build_weekly_panel():

    log(units_sold) = a + β · log_price_ratio
                        + γ1 · promo_days + γ2 · log_seasonal + γ3 · festival_days

β is the price elasticity of demand (expected negative: a 1 % price rise
changes demand by β %).

The coefficients are fitted with scikit-learn's LinearRegression; standard
errors are computed with numpy from the classical OLS formula
    Var(b) = σ² (XᵀX)⁻¹,  σ² = RSS / (n − k)
because LinearRegression does not expose them. The 95 % CI uses the
Student-t critical value with n − k degrees of freedom.

Reliability flag
----------------
An estimate is marked unreliable (reliable_flag = 0) if ANY of:
    * POSITIVE_BETA        — β > 0 (demand rising with price is not credible here)
    * CI_CROSSES_ZERO      — the 95 % CI contains 0 (sign not established)
    * LOW_PRICE_VARIATION  — std of log_price_ratio < MIN_LOG_PRICE_STD
    * FEW_OBSERVATIONS     — fewer than MIN_OBS weekly rows
Phase 8a will refuse to move the price of a product whose estimate is unreliable.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats            # scipy is a scikit-learn dependency — no new install
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

PRICE_COL: str = "log_price_ratio"
CONTROL_COLS: list[str] = ["promo_days", "log_seasonal", "festival_days"]
TARGET_COL: str = "units_sold"

MIN_OBS: int = 52                 # at least a year of weekly data
MIN_LOG_PRICE_STD: float = 0.02   # ~2 % typical price movement
CI_LEVEL: float = 0.95


def fit_product(
    df: pd.DataFrame,
    price_col: str = PRICE_COL,
    control_cols: list[str] | None = None,
) -> dict:
    """
    Fit the log-log regression for a single product.

    Parameters
    ----------
    df : weekly rows for ONE product (must have units_sold > 0 in every row).
    price_col : name of the log price-ratio column (the design comparison
                passes log_sale_price_ratio here).
    control_cols : controls; defaults to CONTROL_COLS.

    Returns a dict with elasticity, std_error, ci_low, ci_high, r_squared,
    n_obs, reliable_flag, unreliable_reasons.
    """
    controls = CONTROL_COLS if control_cols is None else control_cols
    d = df[df[TARGET_COL] > 0]
    n_dropped = len(df) - len(d)

    # Drop controls that are constant for this product (e.g. no festival weeks),
    # otherwise XᵀX is singular.
    usable_controls = [c for c in controls if d[c].nunique() > 1]
    cols = [price_col] + usable_controls
    X = d[cols].to_numpy(dtype=float)
    y = np.log(d[TARGET_COL].to_numpy(dtype=float))
    n, k = X.shape[0], X.shape[1] + 1  # + intercept

    reasons: list[str] = []
    if n < max(MIN_OBS, k + 2):
        return {"elasticity": np.nan, "std_error": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                "r_squared": np.nan, "n_obs": n, "reliable_flag": 0,
                "unreliable_reasons": "FEW_OBSERVATIONS", "zero_weeks_dropped": n_dropped}

    model = LinearRegression().fit(X, y)
    beta = float(model.coef_[0])

    resid = y - model.predict(X)
    rss = float(resid @ resid)
    dof = n - k
    sigma2 = rss / dof
    Xd = np.column_stack([np.ones(n), X])
    cov = sigma2 * np.linalg.inv(Xd.T @ Xd)
    se = float(np.sqrt(cov[1, 1]))
    t_crit = float(stats.t.ppf(0.5 + CI_LEVEL / 2, dof))
    ci_low, ci_high = beta - t_crit * se, beta + t_crit * se
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - rss / tss if tss > 0 else np.nan

    if beta > 0:
        reasons.append("POSITIVE_BETA")
    if ci_low <= 0 <= ci_high:
        reasons.append("CI_CROSSES_ZERO")
    if d[price_col].std() < MIN_LOG_PRICE_STD:
        reasons.append("LOW_PRICE_VARIATION")

    return {
        "elasticity": beta,
        "std_error": se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "r_squared": r2,
        "n_obs": n,
        "reliable_flag": 0 if reasons else 1,
        "unreliable_reasons": ",".join(reasons),
        "zero_weeks_dropped": n_dropped,
    }


def fit_all(
    weekly: pd.DataFrame,
    price_col: str = PRICE_COL,
    control_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Fit fit_product() for every product; one row per product, sorted by product_id."""
    rows = []
    for pid, g in weekly.groupby("product_id", sort=True):
        res = fit_product(g, price_col=price_col, control_cols=control_cols)
        res["product_id"] = pid
        res["category"] = g["category"].iloc[0]
        rows.append(res)
    out = pd.DataFrame(rows)
    front = ["product_id", "category", "elasticity", "std_error", "ci_low", "ci_high",
             "r_squared", "n_obs", "reliable_flag", "unreliable_reasons", "zero_weeks_dropped"]
    out = out[front]
    logger.info("Fitted %d products (%d flagged unreliable).",
                len(out), int((out["reliable_flag"] == 0).sum()))
    return out
