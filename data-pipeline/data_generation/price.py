"""
Price table generator.

Produces a DataFrame with one row per (product_id, date) combination
representing the selling price on that date:

  product_id   : str   — matches product.csv
  date         : datetime64 — calendar date
  price        : float — price in effect on this date (2 d.p.)
  is_promo     : bool  — True if a promotional discount is active
  discount_pct : float — promotional discount as a fraction (0.0 if no promo)
                         e.g. 0.10 means 10 % off the listed price

Design
------
Each product starts at its base_price.  Every PRICE_CHANGE_INTERVAL_DAYS days
the price is eligible to change; a new price is drawn from a Gaussian centred
on the current price (std = PRICE_CHANGE_STD_FRAC × base_price) and clamped to
[base_price × PRICE_MIN_FRAC, base_price × PRICE_MAX_FRAC].

Independently, each product-day may be flagged as a promotion (PROMO_PROB
probability), with a discount drawn uniformly from
[PROMO_DISCOUNT_MIN, PROMO_DISCOUNT_MAX].

Usage
-----
    from data_generation.price import generate_prices
    df_price = generate_prices(df_products, df_calendar, rng)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_generation.config import (
    PRICE_CHANGE_INTERVAL_DAYS,
    PRICE_CHANGE_PROB,
    PRICE_CHANGE_STD_FRAC,
    PRICE_MAX_FRAC,
    PRICE_MIN_FRAC,
    PROMO_DEMAND_UPLIFT,          # imported so callers can access via price module
    PROMO_DISCOUNT_MAX,
    PROMO_DISCOUNT_MIN,
    PROMO_PROB,
)

# Re-export so generate_transactional_tables.py can import from one place
__all__ = ["generate_prices"]


def generate_prices(
    df_products: pd.DataFrame,
    df_calendar: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Return the Price DataFrame.

    Parameters
    ----------
    df_products : pd.DataFrame
        Phase 1a product table — must contain product_id, base_price.
    df_calendar : pd.DataFrame
        Phase 1a calendar table — must contain date column.
    rng : np.random.Generator
        Seeded generator shared across all Phase 1b generators.

    Returns
    -------
    pd.DataFrame
        Columns: product_id, date, price, is_promo, discount_pct.
        One row per (product, date) — 50 × 1096 = 54 800 rows.
    """
    dates = pd.to_datetime(df_calendar["date"].values)
    n_dates = len(dates)
    products = df_products[["product_id", "base_price"]].copy()

    all_rows: list[pd.DataFrame] = []

    for _, prod in products.iterrows():
        pid: str = prod["product_id"]
        base_price: float = prod["base_price"]
        price_floor = base_price * PRICE_MIN_FRAC
        price_ceil  = base_price * PRICE_MAX_FRAC
        price_std   = base_price * PRICE_CHANGE_STD_FRAC

        # --- Build price series -------------------------------------------
        prices = np.empty(n_dates, dtype=np.float64)
        current_price = base_price

        for i in range(n_dates):
            # Price review happens on every PRICE_CHANGE_INTERVAL_DAYS-th day
            if i > 0 and i % PRICE_CHANGE_INTERVAL_DAYS == 0:
                if rng.random() < PRICE_CHANGE_PROB:
                    new_price = rng.normal(loc=current_price, scale=price_std)
                    new_price = float(np.clip(new_price, price_floor, price_ceil))
                    current_price = round(new_price, 2)
            prices[i] = current_price

        # --- Promotional flags (vectorised) ---------------------------------
        promo_mask = rng.random(n_dates) < PROMO_PROB
        discount_pct = np.where(
            promo_mask,
            rng.uniform(PROMO_DISCOUNT_MIN, PROMO_DISCOUNT_MAX, n_dates),
            0.0,
        )

        df_prod = pd.DataFrame(
            {
                "product_id":   pid,
                "date":         dates,
                "price":        np.round(prices, 2),
                "is_promo":     promo_mask,
                "discount_pct": np.round(discount_pct, 4),
            }
        )
        all_rows.append(df_prod)

    df_price = pd.concat(all_rows, ignore_index=True)
    df_price = df_price.astype(
        {
            "product_id":   "string",
            "price":        "float64",
            "is_promo":     "bool",
            "discount_pct": "float64",
        }
    )
    return df_price
