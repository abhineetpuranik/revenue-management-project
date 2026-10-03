"""
Central configuration for the synthetic dataset generator.

All magic numbers live here.  Import this module in product.py, customer.py,
calendar.py, and generate_base_tables.py instead of hard-coding values.
"""

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED: int = 42

# ---------------------------------------------------------------------------
# Output paths (relative to the data-pipeline/ root)
# ---------------------------------------------------------------------------
RAW_DATA_DIR: str = "data/raw"

# ---------------------------------------------------------------------------
# Product configuration
# ---------------------------------------------------------------------------

# Number of products to generate (spread across categories below)
NUM_PRODUCTS: int = 50

# Category definitions.
# Each entry drives:
#   price_min / price_max  — uniform draw for base_price
#   demand_mean            — Poisson mean for base_demand (units/day)
#   elasticity_anchor      — centre of the true_elasticity distribution
#   elasticity_noise_std   — std of Gaussian noise added around the anchor
#
# Design rationale
#   Staples     : low price, high volume, low elasticity (-0.5)  — customers
#                 buy regardless of small price changes.
#   Personal Care: mid price, moderate volume, moderate elasticity (-1.0).
#   Electronics : high price, low volume, high elasticity (-1.5) — price-
#                 sensitive big-ticket items.
#   Clothing    : mid-high price, low-moderate volume, high elasticity (-1.8).
#   Impulse     : low-mid price, moderate volume, very high elasticity (-2.0)
#                 — discretionary treats that vanish at higher prices.

CATEGORIES: dict = {
    "Staples": {
        "price_min": 0.50,
        "price_max": 5.00,
        "demand_mean": 40,
        "elasticity_anchor": -0.5,
        "elasticity_noise_std": 0.10,
        "product_count": 12,          # largest slice — staples are numerous
    },
    "Personal Care": {
        "price_min": 2.00,
        "price_max": 15.00,
        "demand_mean": 20,
        "elasticity_anchor": -1.0,
        "elasticity_noise_std": 0.15,
        "product_count": 10,
    },
    "Electronics": {
        "price_min": 50.00,
        "price_max": 500.00,
        "demand_mean": 5,
        "elasticity_anchor": -1.5,
        "elasticity_noise_std": 0.20,
        "product_count": 8,
    },
    "Clothing": {
        "price_min": 10.00,
        "price_max": 80.00,
        "demand_mean": 10,
        "elasticity_anchor": -1.8,
        "elasticity_noise_std": 0.20,
        "product_count": 10,
    },
    "Impulse": {
        "price_min": 0.50,
        "price_max": 8.00,
        "demand_mean": 25,
        "elasticity_anchor": -2.0,
        "elasticity_noise_std": 0.25,
        "product_count": 10,
    },
}

# Sanity-check: product_count values must sum to NUM_PRODUCTS
assert sum(v["product_count"] for v in CATEGORIES.values()) == NUM_PRODUCTS, (
    "CATEGORIES product_count values must sum to NUM_PRODUCTS"
)

# ---------------------------------------------------------------------------
# Customer configuration
# ---------------------------------------------------------------------------

NUM_CUSTOMERS: int = 1_000

# Segment definitions.
# Each segment carries parameters Phase 1b will use when generating Sales:
#   weight          — proportion of customers assigned to this segment
#   purchase_rate   — expected purchases per day (Poisson lambda)
#   basket_mean     — mean spend per basket (£)
#   basket_std      — std of spend per basket (£)
#
# NOTE: these parameters are ground-truth — they must NOT be used as ML
# features.  They are stored in customer.csv but labelled clearly and will
# be held back from model training in later phases.

SEGMENTS: dict = {
    "high_value": {
        "weight": 0.15,          # 15 % of customers
        "purchase_rate": 0.4,    # buys frequently
        "basket_mean": 85.0,
        "basket_std": 20.0,
    },
    "regular": {
        "weight": 0.35,          # 35 %
        "purchase_rate": 0.2,
        "basket_mean": 40.0,
        "basket_std": 12.0,
    },
    "occasional": {
        "weight": 0.30,          # 30 %
        "purchase_rate": 0.07,
        "basket_mean": 25.0,
        "basket_std": 8.0,
    },
    "at_risk": {
        "weight": 0.20,          # 20 %
        "purchase_rate": 0.03,   # rarely buys, churning
        "basket_mean": 15.0,
        "basket_std": 5.0,
    },
}

# Sanity-check: weights must sum to 1.0
assert abs(sum(v["weight"] for v in SEGMENTS.values()) - 1.0) < 1e-9, (
    "SEGMENTS weights must sum to 1.0"
)

# ---------------------------------------------------------------------------
# Calendar configuration
# ---------------------------------------------------------------------------

CALENDAR_START: str = "2022-01-01"
CALENDAR_END: str   = "2024-12-31"   # inclusive → 3 full years, 1096 rows

# Monthly seasonal factors (index 1 = January … 12 = December).
# Values > 1.0 represent above-average demand months.
# Design: December peak (Christmas), January trough (post-holiday), summer
# slight uplift, Q3 back-to-school bump.
MONTHLY_SEASONAL_FACTORS: dict[int, float] = {
    1:  0.80,   # January   — post-holiday slump
    2:  0.85,   # February
    3:  0.95,   # March     — slight spring pick-up
    4:  1.00,   # April
    5:  1.05,   # May
    6:  1.10,   # June      — summer begins
    7:  1.10,   # July
    8:  1.05,   # August    — back-to-school
    9:  1.00,   # September
    10: 1.05,   # October   — pre-holiday build-up
    11: 1.15,   # November  — Black Friday
    12: 1.30,   # December  — Christmas peak
}

# Weekday factors (0 = Monday … 6 = Sunday).
# Weekends see higher foot traffic.
WEEKDAY_FACTORS: dict[int, float] = {
    0: 0.90,   # Monday
    1: 0.90,   # Tuesday
    2: 0.95,   # Wednesday
    3: 0.95,   # Thursday
    4: 1.10,   # Friday    — payday / pre-weekend
    5: 1.25,   # Saturday  — peak
    6: 1.20,   # Sunday
}

# Festival dates (YYYY-MM-DD).  Flag = 1 on these dates (and optionally ±1 day
# around them — kept simple here: exact date only).
# Covers 2022-2024 for the three-year window.
FESTIVAL_DATES: list[str] = [
    # Christmas Eve / Day / Boxing Day
    "2022-12-24", "2022-12-25", "2022-12-26",
    "2023-12-24", "2023-12-25", "2023-12-26",
    "2024-12-24", "2024-12-25", "2024-12-26",
    # New Year's Eve / Day
    "2022-01-01",
    "2022-12-31", "2023-01-01",
    "2023-12-31", "2024-01-01",
    "2024-12-31",
    # Black Friday (approximate — last Friday of November)
    "2022-11-25",
    "2023-11-24",
    "2024-11-29",
    # Easter Sunday (approximate)
    "2022-04-17",
    "2023-04-09",
    "2024-03-31",
    # Valentine's Day
    "2022-02-14", "2023-02-14", "2024-02-14",
    # Mother's Day UK (3rd Sunday of March)
    "2022-03-27", "2023-03-19", "2024-03-10",
    # Halloween
    "2022-10-31", "2023-10-31", "2024-10-31",
    # Summer Bank Holiday UK (last Monday of August)
    "2022-08-29", "2023-08-28", "2024-08-26",
]
