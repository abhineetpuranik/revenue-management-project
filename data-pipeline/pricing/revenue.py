from __future__ import annotations

import numpy as np
import pandas as pd


def available_stock(stock_level, weekly_restock):
    return np.asarray(stock_level, float) + np.asarray(weekly_restock, float)


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["sellable_units"] = np.minimum(out["expected_demand"], out["available_stock"])
    out["expected_revenue"] = out["candidate_price"] * out["sellable_units"]
    out["expected_profit"] = (out["candidate_price"] - out["unit_cost"]) * out["sellable_units"]
    out["stock_limited"] = (out["expected_demand"] > out["available_stock"]).astype(int)
    return out
