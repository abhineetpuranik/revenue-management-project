RANDOM_SEED: int = 42

RAW_DATA_DIR: str = "data/raw"


NUM_PRODUCTS: int = 50
PRICE_DECIMALS: int = 0

CATEGORIES: dict = {
    "Staples": {
        "price_min": 50,
        "price_max": 500,
        "demand_mean": 40,
        "elasticity_anchor": -0.5,
        "elasticity_noise_std": 0.10,
        "product_count": 12,
    },
    "Personal Care": {
        "price_min": 200,
        "price_max": 1500,
        "demand_mean": 20,
        "elasticity_anchor": -1.0,
        "elasticity_noise_std": 0.15,
        "product_count": 10,
    },
    "Electronics": {
        "price_min": 5000,
        "price_max": 50000,
        "demand_mean": 5,
        "elasticity_anchor": -1.5,
        "elasticity_noise_std": 0.20,
        "product_count": 8,
    },
    "Clothing": {
        "price_min": 1000,
        "price_max": 8000,
        "demand_mean": 10,
        "elasticity_anchor": -1.8,
        "elasticity_noise_std": 0.20,
        "product_count": 10,
    },
    "Impulse": {
        "price_min": 50,
        "price_max": 800,
        "demand_mean": 25,
        "elasticity_anchor": -2.0,
        "elasticity_noise_std": 0.25,
        "product_count": 10,
    },
}

assert sum(v["product_count"] for v in CATEGORIES.values()) == NUM_PRODUCTS, (
    "CATEGORIES product_count values must sum to NUM_PRODUCTS"
)


NUM_CUSTOMERS: int = 1_000


SEGMENTS: dict = {
    "high_value": {
        "weight": 0.15,
        "purchase_rate": 0.4,
        "basket_mean": 85.0,
        "basket_std": 20.0,
    },
    "regular": {
        "weight": 0.35,
        "purchase_rate": 0.2,
        "basket_mean": 40.0,
        "basket_std": 12.0,
    },
    "occasional": {
        "weight": 0.30,
        "purchase_rate": 0.07,
        "basket_mean": 25.0,
        "basket_std": 8.0,
    },
    "at_risk": {
        "weight": 0.20,
        "purchase_rate": 0.03,
        "basket_mean": 15.0,
        "basket_std": 5.0,
    },
}

assert abs(sum(v["weight"] for v in SEGMENTS.values()) - 1.0) < 1e-9, (
    "SEGMENTS weights must sum to 1.0"
)


CALENDAR_START: str = "2022-01-01"
CALENDAR_END: str   = "2024-12-31"

MONTHLY_SEASONAL_FACTORS: dict[int, float] = {
    1:  0.80,
    2:  0.85,
    3:  0.95,
    4:  1.00,
    5:  1.05,
    6:  1.10,
    7:  1.10,
    8:  1.05,
    9:  1.00,
    10: 1.05,
    11: 1.15,
    12: 1.30,
}

WEEKDAY_FACTORS: dict[int, float] = {
    0: 0.90,
    1: 0.90,
    2: 0.95,
    3: 0.95,
    4: 1.10,
    5: 1.25,
    6: 1.20,
}

FESTIVAL_DATES: list[str] = [
    "2022-12-24", "2022-12-25", "2022-12-26",
    "2023-12-24", "2023-12-25", "2023-12-26",
    "2024-12-24", "2024-12-25", "2024-12-26",
    "2022-01-01",
    "2022-12-31", "2023-01-01",
    "2023-12-31", "2024-01-01",
    "2024-12-31",
    "2022-11-25",
    "2023-11-24",
    "2024-11-29",
    "2022-04-17",
    "2023-04-09",
    "2024-03-31",
    "2022-02-14", "2023-02-14", "2024-02-14",
    "2022-03-27", "2023-03-19", "2024-03-10",
    "2022-10-31", "2023-10-31", "2024-10-31",
    "2022-08-29", "2023-08-28", "2024-08-26",
]


PRICE_CHANGE_INTERVAL_DAYS: int = 14

PRICE_CHANGE_PROB: float = 0.60

PRICE_CHANGE_STD_FRAC: float = 0.08

PRICE_MIN_FRAC: float = 0.70
PRICE_MAX_FRAC: float = 1.40


PROMO_PROB: float = 0.05

PROMO_DISCOUNT_MIN: float = 0.05
PROMO_DISCOUNT_MAX: float = 0.25

PROMO_DEMAND_UPLIFT: float = 1.20


FESTIVAL_DEMAND_UPLIFT: float = 1.25

MIN_EXPECTED_DEMAND: float = 0.01


INITIAL_STOCK_MULTIPLIER: int = 30

RESTOCK_INTERVAL_DAYS: int = 7

RESTOCK_PERIOD_MULTIPLIER: float = 1.5
