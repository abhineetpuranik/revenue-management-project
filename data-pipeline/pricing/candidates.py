from __future__ import annotations

import numpy as np
import pandas as pd

from pricing.pricing_config import MAX_PRICE_CHANGE_PCT, PRICE_DECIMALS, PRICE_STEP_PCT


def candidate_steps(max_change: float = MAX_PRICE_CHANGE_PCT,
                    step: float = PRICE_STEP_PCT) -> np.ndarray:
    k_max = int(np.floor(max_change / step + 1e-9))
    return np.arange(-k_max, k_max + 1)


def generate_candidates(state: pd.DataFrame) -> pd.DataFrame:
    steps = candidate_steps()
    rows = []
    for _, p in state.iterrows():
        scale = 10 ** PRICE_DECIMALS
        raw = p["current_price"] * (1 + steps * PRICE_STEP_PCT) * scale
        prices = np.where(steps > 0, np.floor(raw + 1e-6), np.ceil(raw - 1e-6)) / scale
        prices[steps == 0] = round(float(p["current_price"]), PRICE_DECIMALS)
        df = pd.DataFrame({"product_id": p["product_id"], "step": steps, "candidate_price": prices})
        df["abs_step"] = df["step"].abs()
        df = (df.sort_values(["abs_step", "step"])
                .drop_duplicates("candidate_price", keep="first")
                .drop(columns="abs_step").sort_values("step"))
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    out = out.merge(state[["product_id", "current_price"]], on="product_id")
    out["change_pct"] = out["candidate_price"] / out["current_price"] - 1.0
    return out.drop(columns="current_price")
