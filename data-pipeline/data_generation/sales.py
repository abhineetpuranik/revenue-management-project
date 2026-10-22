from __future__ import annotations

import numpy as np
import pandas as pd

from data_generation.config import (
    FESTIVAL_DEMAND_UPLIFT,
    MIN_EXPECTED_DEMAND,
    PRICE_DECIMALS,
    PROMO_DEMAND_UPLIFT,
)

__all__ = ["generate_sales"]


def generate_sales(
    df_products: pd.DataFrame,
    df_customers: pd.DataFrame,
    df_calendar: pd.DataFrame,
    df_price: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(df_calendar["date"].values)
    n_dates = len(dates)

    combined_factor = df_calendar["combined_factor"].values.astype(np.float64)
    festival_flag   = df_calendar["festival_flag"].values.astype(np.float64)

    customer_ids    = df_customers["customer_id"].values
    purchase_rates  = df_customers["purchase_rate"].values.astype(np.float64)
    rate_weights    = purchase_rates / purchase_rates.sum()
    n_customers     = len(customer_ids)

    df_price_indexed = df_price.set_index(["product_id", "date"])

    product_rows = df_products.reset_index(drop=True)

    sales_chunks: list[pd.DataFrame] = []
    daily_agg_chunks: list[pd.DataFrame] = []

    for _, prod in product_rows.iterrows():
        pid:          str   = prod["product_id"]
        base_demand:  float = float(prod["base_demand"])
        base_price:   float = float(prod["base_price"])
        elasticity:   float = float(prod["true_elasticity"])

        prod_price_df = df_price_indexed.loc[pid]
        prod_price_df = prod_price_df.reindex(dates)

        prices       = prod_price_df["price"].values.astype(np.float64)
        is_promo     = prod_price_df["is_promo"].values.astype(bool)
        discount_pct = prod_price_df["discount_pct"].values.astype(np.float64)

        price_ratio = prices / base_price

        price_at_sale = np.round(prices * (1.0 - discount_pct), PRICE_DECIMALS)

        festival_mult = 1.0 + (FESTIVAL_DEMAND_UPLIFT - 1.0) * festival_flag
        promo_mult    = np.where(is_promo, PROMO_DEMAND_UPLIFT, 1.0)

        lam = (
            base_demand
            * combined_factor
            * festival_mult
            * np.power(price_ratio, elasticity)
            * promo_mult
        )
        lam = np.maximum(lam, MIN_EXPECTED_DEMAND)

        total_units = rng.poisson(lam).astype(np.int64)

        daily_agg_chunks.append(
            pd.DataFrame(
                {
                    "product_id": pid,
                    "date":       dates,
                    "units_sold": total_units,
                }
            )
        )

        nonzero_days = np.nonzero(total_units)[0]

        if len(nonzero_days) == 0:
            continue

        prod_sales_rows: list[dict] = []

        for day_i in nonzero_days:
            n_units = int(total_units[day_i])
            day_date = dates[day_i]

            assignment = rng.multinomial(n_units, rate_weights)

            buyers = np.nonzero(assignment)[0]
            for cust_i in buyers:
                u = int(assignment[cust_i])
                rev = round(u * float(price_at_sale[day_i]), 2)
                prod_sales_rows.append(
                    {
                        "customer_id":   customer_ids[cust_i],
                        "product_id":    pid,
                        "date":          day_date,
                        "units_sold":    u,
                        "price_at_sale": float(price_at_sale[day_i]),
                        "discount_pct":  float(discount_pct[day_i]),
                        "revenue":       rev,
                    }
                )

        if prod_sales_rows:
            sales_chunks.append(pd.DataFrame(prod_sales_rows))

    if not sales_chunks:
        df_sales = pd.DataFrame(
            columns=[
                "sale_id", "customer_id", "product_id", "date",
                "units_sold", "price_at_sale", "discount_pct", "revenue",
            ]
        )
    else:
        df_sales = pd.concat(sales_chunks, ignore_index=True)
        df_sales.insert(0, "sale_id", range(1, len(df_sales) + 1))
        df_sales = df_sales.sort_values(["date", "product_id", "customer_id"]).reset_index(drop=True)
        df_sales["sale_id"] = range(1, len(df_sales) + 1)

        df_sales = df_sales.astype(
            {
                "sale_id":       "int64",
                "customer_id":   "string",
                "product_id":    "string",
                "units_sold":    "int64",
                "price_at_sale": "float64",
                "discount_pct":  "float64",
                "revenue":       "float64",
            }
        )

    df_daily_units = pd.concat(daily_agg_chunks, ignore_index=True)
    df_daily_units = df_daily_units.astype(
        {"product_id": "string", "units_sold": "int64"}
    )

    return df_sales, df_daily_units
