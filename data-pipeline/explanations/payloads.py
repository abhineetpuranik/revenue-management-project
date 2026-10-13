"""
Payloads — Phase 9.

Builds the EXACT JSON object the LLM sees for each explanation. Rules:
  * only the fields the sentence needs — no raw tables, no customer-level data,
    no ground truth;
  * every number is pre-rounded and pre-formatted as a string ("14.9%", "3.77"),
    so the LLM never has to calculate or round anything;
  * signs are removed from percentages and carried by words instead
    (action = "raise"/"cut"/"hold", revenue_direction = "increase"/...), which
    avoids the LLM mangling "-6%" vs "6%";
  * the price-sensitivity band is computed here from the elasticity.
"""

from __future__ import annotations

import pandas as pd

from explanations.explanation_config import SENSITIVITY_HIGH_ABOVE, SENSITIVITY_MODERATE_FROM

BINDING_TEXT = {
    "MAX_CHANGE": "the maximum allowed price change of {max_change}",
    "MARGIN": "the minimum profit margin rule",
    "PRICE_RANGE": "the range of prices this product has sold at before",
    "STOCK": "the stock available next week",
    "TIE_TOLERANCE": "moving further would barely change revenue",
    "NONE": "this is the revenue-maximising price",
    "NO_FEASIBLE_PRICE": "no alternative price satisfies the pricing rules",
}

SEGMENT_NAMES = {
    "high_value": "High-value customers",
    "regular": "Regular customers",
    "occasional": "Occasional customers",
    "at_risk": "At-risk (least engaged) customers",
}


def sensitivity_band(elasticity: float) -> str:
    a = abs(float(elasticity))
    if a < SENSITIVITY_MODERATE_FROM:
        return "not very price-sensitive"
    if a <= SENSITIVITY_HIGH_ABOVE:
        return "moderately price-sensitive"
    return "highly price-sensitive"


def _pct(x: float, decimals: int = 1) -> str:
    return f"{abs(float(x)) * 100:.{decimals}f}%"


def _money(x: float) -> str:
    return f"{float(x):,.2f}"


def _action(change_pct: float) -> str:
    if abs(change_pct) < 1e-9:
        return "hold"
    return "raise" if change_pct > 0 else "cut"


def _revenue_direction(change: float) -> str:
    if abs(change) < 0.0005:
        return "no change"
    return "increase" if change > 0 else "decrease"


def pricing_payload(rec: dict, max_change_pct: float) -> dict:
    """One pricing recommendation (a row of pricing_recommendation) → LLM payload."""
    change = float(rec["change_pct"])
    rev_change = float(rec["revenue_change_pct"])
    binding = str(rec["binding_constraint"])
    payload = {
        "product_id": str(rec["product_id"]),
        "category": str(rec["category"]),
        "action": _action(change),
        "current_price": _money(rec["current_price"]),
        "recommended_price": _money(rec["recommended_price"]),
        "price_change": _pct(change),
        "price_sensitivity": sensitivity_band(rec["elasticity"]),
        "expected_weekly_units": f"{float(rec['expected_demand']):,.0f}",
        "weekly_units_at_current_price": f"{float(rec['baseline_demand']):,.0f}",
        "revenue_direction": _revenue_direction(rev_change),
        "revenue_change": _pct(rev_change),
        "limited_by": BINDING_TEXT.get(binding, BINDING_TEXT["NONE"]).format(
            max_change=_pct(max_change_pct, 0)),
    }
    if payload["action"] == "hold":
        payload.pop("price_change")
    if payload["revenue_direction"] == "no change":
        payload.pop("revenue_change")
    return payload


def segment_payload(row: dict) -> dict:
    """One row of segment_summary → LLM payload."""
    return {
        "segment": SEGMENT_NAMES.get(str(row["segment_label"]), str(row["segment_label"])),
        "customers": f"{int(row['customer_count']):,}",
        "share_of_customers": f"{float(row['share_pct']):.1f}%",
        "share_of_revenue": f"{float(row['revenue_share_pct']):.1f}%",
        "average_purchase_days": f"{float(row['mean_frequency']):,.0f}",
        "average_spend": _money(row["mean_monetary"]),
        "typical_days_since_last_purchase": f"{float(row['median_recency_days']):,.0f}",
    }


def build_all_payloads(recs: pd.DataFrame, segments: pd.DataFrame, max_change_pct: float):
    """[(entity_type, entity_id, payload), ...] in a stable order."""
    out = []
    for rec in recs.sort_values("product_id").to_dict(orient="records"):
        out.append(("pricing", rec["product_id"], pricing_payload(rec, max_change_pct)))
    for row in segments.to_dict(orient="records"):
        out.append(("segment", row["segment_label"], segment_payload(row)))
    return out
