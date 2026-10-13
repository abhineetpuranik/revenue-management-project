"""
Template fallback — Phase 9.

Used when the LLM errors, times out, or its output fails the guardrails twice,
so every product and segment ALWAYS has an explanation (SRS REQ-22). The text
is built only from the payload, so it passes the same guardrails by construction.
"""

from __future__ import annotations


def pricing_fallback(p: dict) -> str:
    action = p["action"]
    if action == "hold":
        first = (f"Keep the price of {p['product_id']} ({p['category']}) at {p['current_price']}; "
                 f"it is {p['price_sensitivity']}.")
    else:
        verb = "Raise" if action == "raise" else "Cut"
        first = (f"{verb} the price of {p['product_id']} ({p['category']}) by {p['price_change']}, "
                 f"from {p['current_price']} to {p['recommended_price']}, because it is "
                 f"{p['price_sensitivity']}.")
    if p["revenue_direction"] == "no change":
        second = f"Weekly revenue is expected to stay about the same (limit: {p['limited_by']})."
    else:
        second = (f"Expected weekly sales are {p['expected_weekly_units']} units and weekly revenue "
                  f"should {p['revenue_direction']} by {p['revenue_change']} "
                  f"(limit: {p['limited_by']}).")
    return f"{first} {second}"


def segment_fallback(p: dict) -> str:
    return (f"{p['segment']}: {p['customers']} customers ({p['share_of_customers']} of customers) "
            f"bringing {p['share_of_revenue']} of revenue. On average they bought on "
            f"{p['average_purchase_days']} days and spent {p['average_spend']} in total.")


def fallback_text(entity_type: str, payload: dict) -> str:
    return pricing_fallback(payload) if entity_type == "pricing" else segment_fallback(payload)
