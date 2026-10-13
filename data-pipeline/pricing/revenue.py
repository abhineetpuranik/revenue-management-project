"""
Expected revenue and the stock rule — Phase 8b.

available_stock = latest stock_level + weekly_restock
    Stock is replenished every 7 days by a fixed quantity (data_generation/
    stock.py), so exactly one restock arrives during any forecast week. Its
    size is read from the data (the most recent restock), not from config.

sellable_units  = min(expected_demand, available_stock)
expected_revenue = price × sellable_units          ← the objective
expected_profit  = (price − unit_cost) × sellable_units   (displayed, not optimised)
stock_limited    = 1 if expected_demand > available_stock

Capping at stock is what makes a price cut pointless once demand outruns
supply: past that point a lower price only lowers revenue.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def available_stock(stock_level, weekly_restock):
    return np.asarray(stock_level, float) + np.asarray(weekly_restock, float)


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Needs columns: candidate_price, expected_demand, available_stock, unit_cost.
    Adds sellable_units, expected_revenue, expected_profit, stock_limited.
    """
    out = df.copy()
    out["sellable_units"] = np.minimum(out["expected_demand"], out["available_stock"])
    out["expected_revenue"] = out["candidate_price"] * out["sellable_units"]
    out["expected_profit"] = (out["candidate_price"] - out["unit_cost"]) * out["sellable_units"]
    out["stock_limited"] = (out["expected_demand"] > out["available_stock"]).astype(int)
    return out
