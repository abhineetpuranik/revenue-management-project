from __future__ import annotations

import numpy as np
import pandas as pd

from data_generation.config import (
    PRICE_CHANGE_INTERVAL_DAYS,
    PRICE_CHANGE_PROB,
    PRICE_CHANGE_STD_FRAC,
    PRICE_DECIMALS,
    PRICE_MAX_FRAC,
    PRICE_MIN_FRAC,
    PROMO_DEMAND_UPLIFT,
    PROMO_DISCOUNT_MAX,
    PROMO_DISCOUNT_MIN,
    PROMO_PROB,
)

__all__ = ["generate_prices"]


def generate_prices(
    df_products: pd.DataFrame,
    df_calendar: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
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

        prices = np.empty(n_dates, dtype=np.float64)
        current_price = base_price

        for i in range(n_dates):
            if i > 0 and i % PRICE_CHANGE_INTERVAL_DAYS == 0:
                if rng.random() < PRICE_CHANGE_PROB:
                    new_price = rng.normal(loc=current_price, scale=price_std)
                    new_price = float(np.clip(new_price, price_floor, price_ceil))
                    current_price = round(new_price, PRICE_DECIMALS)
            prices[i] = current_price

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
                "price":        np.round(prices, PRICE_DECIMALS),
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
