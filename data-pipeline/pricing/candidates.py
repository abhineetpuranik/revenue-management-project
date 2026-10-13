"""
Candidate price grid — Phase 8a.

For each product: current_price × (1 + k · PRICE_STEP_PCT) for every integer k
with |k · PRICE_STEP_PCT| ≤ MAX_PRICE_CHANGE_PCT, rounded to PRICE_DECIMALS
TOWARD the current price (prices above it are rounded down, prices below it are
rounded up), so a boundary candidate such as +15 % never ends up at +15.03 %.
k = 0 (the current price itself) is always included, so "hold the price" is
always an option. The grid deliberately spans exactly the max-change band; the
MAX_CHANGE constraint is still checked explicitly on the ROUNDED price, since
rounding can nudge a boundary candidate just outside the band.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pricing.pricing_config import MAX_PRICE_CHANGE_PCT, PRICE_DECIMALS, PRICE_STEP_PCT


def candidate_steps(max_change: float = MAX_PRICE_CHANGE_PCT,
                    step: float = PRICE_STEP_PCT) -> np.ndarray:
    k_max = int(np.floor(max_change / step + 1e-9))
    return np.arange(-k_max, k_max + 1)


def generate_candidates(state: pd.DataFrame) -> pd.DataFrame:
    """One row per (product, step). Columns: product_id, step, candidate_price, change_pct."""
    steps = candidate_steps()
    rows = []
    for _, p in state.iterrows():
        scale = 10 ** PRICE_DECIMALS
        raw = p["current_price"] * (1 + steps * PRICE_STEP_PCT) * scale
        # round toward the current price; the small epsilon absorbs float noise (e.g. 1.15*100)
        prices = np.where(steps > 0, np.floor(raw + 1e-6), np.ceil(raw - 1e-6)) / scale
        prices[steps == 0] = round(float(p["current_price"]), PRICE_DECIMALS)
        df = pd.DataFrame({"product_id": p["product_id"], "step": steps, "candidate_price": prices})
        # Very cheap items can round two steps to the same price; keep the smaller move.
        df["abs_step"] = df["step"].abs()
        df = (df.sort_values(["abs_step", "step"])
                .drop_duplicates("candidate_price", keep="first")
                .drop(columns="abs_step").sort_values("step"))
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    out = out.merge(state[["product_id", "current_price"]], on="product_id")
    out["change_pct"] = out["candidate_price"] / out["current_price"] - 1.0
    return out.drop(columns="current_price")
