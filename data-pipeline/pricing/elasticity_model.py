from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

PRICE_COL: str = "log_price_ratio"
CONTROL_COLS: list[str] = ["promo_days", "log_seasonal", "festival_days"]
TARGET_COL: str = "units_sold"

MIN_OBS: int = 52
MIN_LOG_PRICE_STD: float = 0.02
CI_LEVEL: float = 0.95


def fit_product(
    df: pd.DataFrame,
    price_col: str = PRICE_COL,
    control_cols: list[str] | None = None,
) -> dict:
    controls = CONTROL_COLS if control_cols is None else control_cols
    d = df[df[TARGET_COL] > 0]
    n_dropped = len(df) - len(d)

    usable_controls = [c for c in controls if d[c].nunique() > 1]
    cols = [price_col] + usable_controls
    X = d[cols].to_numpy(dtype=float)
    y = np.log(d[TARGET_COL].to_numpy(dtype=float))
    n, k = X.shape[0], X.shape[1] + 1

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
