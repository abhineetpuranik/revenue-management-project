from __future__ import annotations

import pandas as pd

from pricing.pricing_config import (ALLOW_EXTRAPOLATION, MAX_PRICE_CHANGE_PCT, MIN_MARGIN_PCT,
                                    PRICE_RANGE_TOLERANCE_PCT, REASON_ELASTICITY_UNRELIABLE,
                                    REASON_MARGIN, REASON_MAX_CHANGE, REASON_PRICE_RANGE)

_EPS = 1e-9


def margin_pct(price: float, unit_cost: float) -> float:
    return (price - unit_cost) / price


def check_margin(price: float, unit_cost: float, min_margin: float = MIN_MARGIN_PCT):
    ok = price > 0 and margin_pct(price, unit_cost) >= min_margin - _EPS
    return ok, None if ok else REASON_MARGIN


def check_max_change(price: float, current_price: float, max_change: float = MAX_PRICE_CHANGE_PCT):
    ok = abs(price / current_price - 1.0) <= max_change + _EPS
    return ok, None if ok else REASON_MAX_CHANGE


def check_price_range(price: float, hist_min: float, hist_max: float,
                      tolerance: float = PRICE_RANGE_TOLERANCE_PCT,
                      allow_extrapolation: bool = ALLOW_EXTRAPOLATION):
    if allow_extrapolation:
        return True, None
    ok = hist_min * (1 - tolerance) - _EPS <= price <= hist_max * (1 + tolerance) + _EPS
    return ok, None if ok else REASON_PRICE_RANGE


def check_elasticity_reliable(price: float, current_price: float, reliable_flag: int):
    ok = bool(reliable_flag) or abs(price - current_price) < 1e-9
    return ok, None if ok else REASON_ELASTICITY_UNRELIABLE


def apply_constraints(candidates: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    df = candidates.merge(
        state[["product_id", "current_price", "unit_cost", "hist_min_price",
               "hist_max_price", "reliable_flag"]], on="product_id")
    reasons = []
    for r in df.itertuples(index=False):
        checks = [
            check_margin(r.candidate_price, r.unit_cost),
            check_max_change(r.candidate_price, r.current_price),
            check_price_range(r.candidate_price, r.hist_min_price, r.hist_max_price),
            check_elasticity_reliable(r.candidate_price, r.current_price, r.reliable_flag),
        ]
        reasons.append(",".join(code for ok, code in checks if not ok))
    df["margin_pct"] = (df["candidate_price"] - df["unit_cost"]) / df["candidate_price"]
    df["failed_reasons"] = reasons
    df["passes_all"] = (df["failed_reasons"] == "").astype(int)
    df["is_current"] = (df["step"] == 0).astype(int)
    return df[["product_id", "step", "candidate_price", "change_pct", "unit_cost", "margin_pct",
               "is_current", "passes_all", "failed_reasons"]]
