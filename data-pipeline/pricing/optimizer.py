"""
Best-price selection — Phase 8b.

For each product, among candidates that passed every Phase 8a rule:
    1. take the maximum expected_revenue
    2. treat every candidate within REVENUE_TIE_TOLERANCE (relative) of it as a tie
    3. among ties pick the one closest to the current price (smallest |step|);
       a remaining tie (equal distance up and down) goes to the lower price

If NO candidate passed (not the case on the current data, but possible with
stricter rules), the current price is held and flagged NO_FEASIBLE_PRICE.

binding_constraint — why the recommendation stops where it does
-----------------------------------------------------------------
Compare the chosen price with its two neighbours on the full grid (rejected
rows included, since every candidate is scored):
    * a neighbour has HIGHER revenue but was rejected   → its reason code
                                                          (MARGIN, PRICE_RANGE, ...)
    * a neighbour has higher revenue and was allowed     → TIE_TOLERANCE (the extra
      revenue from moving further is below REVENUE_TIE_TOLERANCE, so the smaller
      move was preferred — typical when elasticity is close to −1)
    * chosen price is at the edge of the ±max-change grid and revenue is still
      rising towards that edge                           → MAX_CHANGE
    * neither neighbour is better (a genuine peak)       → STOCK if demand is capped
                                                          by stock there, else NONE
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pricing.pricing_config import REASON_STOCK, REVENUE_TIE_TOLERANCE


def select_best(group: pd.DataFrame, tol: float = REVENUE_TIE_TOLERANCE) -> pd.Series | None:
    ok = group[group["passes_all"] == 1]
    if ok.empty:
        return None
    best_rev = ok["expected_revenue"].max()
    ties = ok[ok["expected_revenue"] >= best_rev * (1 - tol)]
    ties = ties.assign(abs_step=ties["step"].abs()).sort_values(["abs_step", "step"])
    return ties.iloc[0]


def binding_constraint(group: pd.DataFrame, chosen: pd.Series) -> str:
    g = group.set_index("step").sort_index()
    s = int(chosen["step"])
    rev = float(chosen["expected_revenue"])
    eps = 1e-12

    better = []
    for d in (+1, -1):
        if s + d in g.index and g.loc[s + d, "expected_revenue"] > rev * (1 + eps):
            better.append((g.loc[s + d, "expected_revenue"], d))
    if better:
        _, d = max(better)
        nb = g.loc[s + d]
        if nb["passes_all"] == 0:
            return nb["failed_reasons"].split(",")[0]
        return "TIE_TOLERANCE"

    # No better neighbour: either the grid edge stops us, or this is a true peak.
    at_top, at_bottom = s == g.index.max(), s == g.index.min()
    if at_top and (s - 1 not in g.index or g.loc[s - 1, "expected_revenue"] < rev):
        return "MAX_CHANGE"
    if at_bottom and (s + 1 not in g.index or g.loc[s + 1, "expected_revenue"] < rev):
        return "MAX_CHANGE"
    neighbour_capped = any(g.loc[s + d, "stock_limited"] == 1 for d in (+1, -1) if s + d in g.index)
    if chosen["stock_limited"] == 1 or neighbour_capped:
        return REASON_STOCK
    return "NONE"
