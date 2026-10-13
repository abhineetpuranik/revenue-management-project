"""
Pricing business rules — Phase 8 (Module 4b).

Every number the pricing module depends on lives here. These are TEAM-APPROVED
PLACEHOLDERS for the SRS TBD items (Appendix C) — change them here only.

IMPORTANT MODELLING ASSUMPTION — unit cost
------------------------------------------
The dataset has no cost column, so the minimum-margin rule needs an assumed
cost:  unit_cost = base_price × COST_RATIO[category].  The ratios below are
illustrative category-level assumptions, not data, and every margin figure the
system reports depends on them.
"""

# Margin rule: (price − unit_cost) / price must be at least this.
MIN_MARGIN_PCT: float = 0.10

# Max-change rule: |candidate / current_price − 1| must not exceed this.
MAX_PRICE_CHANGE_PCT: float = 0.15

# Candidate grid step, as a fraction of the current price (1 % steps).
PRICE_STEP_PCT: float = 0.01

# Assumed unit cost as a fraction of base_price (keys = product.category values).
COST_RATIO: dict[str, float] = {
    "Staples":       0.70,
    "Personal Care": 0.55,
    "Electronics":   0.75,
    "Clothing":      0.45,
    "Impulse":       0.50,
}

# Price-range rule: neither the elasticity regression nor the forecasting model
# has seen prices outside each product's historical list-price range, so
# extrapolating beyond it is not defensible.
ALLOW_EXTRAPOLATION: bool = False
PRICE_RANGE_TOLERANCE_PCT: float = 0.0   # e.g. 0.02 would allow 2 % beyond the observed range

# Candidate prices are rounded to this many decimals (currency).
PRICE_DECIMALS: int = 2

# Phase 8b: candidates within this relative distance of the best revenue are
# treated as ties; the one closest to the current price wins (smaller moves are safer).
REVENUE_TIE_TOLERANCE: float = 0.001

# Reason codes (used in pricing_candidates.failed_reasons and pricing_recommendation)
REASON_MARGIN = "MARGIN"
REASON_MAX_CHANGE = "MAX_CHANGE"
REASON_PRICE_RANGE = "PRICE_RANGE"
REASON_ELASTICITY_UNRELIABLE = "ELASTICITY_UNRELIABLE"
REASON_STOCK = "STOCK"            # applied in Phase 8b (needs predicted demand)
