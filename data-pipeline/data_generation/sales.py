"""
Sales table generator.

Produces a DataFrame of individual customer-product-date transactions:

  sale_id        : int   — surrogate key (1-based)
  customer_id    : str   — matches customer.csv
  product_id     : str   — matches product.csv
  date           : datetime64
  units_sold     : int   — units purchased by this customer on this date
  price_at_sale  : float — effective price after any promotional discount
  discount_pct   : float — discount applied (0.0 if no promo)
  revenue        : float — units_sold × price_at_sale

Design (vectorised two-step approach)
--------------------------------------
Step 1 — Product-day demand (fully vectorised, no Python loops over dates):
  For every (product, date) pair compute:
    lambda = base_demand
            × combined_factor          (seasonal × weekday)
            × (1 + 0.25 × festival_flag)
            × (price / base_price) ^ true_elasticity   # elasticity effect
            × (PROMO_DEMAND_UPLIFT if is_promo else 1)
    units_sold_total ~ Poisson(max(lambda, MIN_EXPECTED_DEMAND))

Step 2 — Customer attribution (sparse multinomial per product-day):
  For each product-day where units_sold_total > 0, draw a multinomial
  split across customers using their purchase_rate as relative weights.
  Only customers assigned ≥ 1 unit are kept (sparse rows).

The price_at_sale is price × (1 - discount_pct).

Performance note
----------------
With 50 products × 1 096 dates = 54 800 product-day rows, step 1 runs
entirely in numpy (<1 s).  Step 2 iterates over the ~54 800 product-day
combos but skips any with units_sold == 0 and uses numpy multinomial
rather than Python loops over customers.  On an 8 GB laptop this produces
~500 k–2 M sales rows in under 60 seconds.

Usage
-----
    from data_generation.sales import generate_sales
    df_sales, df_daily_units = generate_sales(
        df_products, df_customers, df_calendar, df_price, rng
    )
    # df_daily_units is the (product_id, date, units_sold) aggregate
    # needed by stock.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_generation.config import (
    FESTIVAL_DEMAND_UPLIFT,
    MIN_EXPECTED_DEMAND,
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
    """Return (Sales DataFrame, daily-units-sold aggregate).

    Parameters
    ----------
    df_products  : product table from Phase 1a
    df_customers : customer table from Phase 1a
    df_calendar  : calendar table from Phase 1a
    df_price     : price table from price.py (this phase)
    rng          : seeded numpy Generator

    Returns
    -------
    df_sales : pd.DataFrame
        One row per customer-product-date transaction with units_sold > 0.
    df_daily_units : pd.DataFrame
        Aggregated (product_id, date, units_sold) — consumed by stock.py.
    """
    # ------------------------------------------------------------------
    # 1. Prepare lookup arrays
    # ------------------------------------------------------------------
    dates = pd.to_datetime(df_calendar["date"].values)
    n_dates = len(dates)

    # Calendar factors as numpy arrays indexed by position
    combined_factor = df_calendar["combined_factor"].values.astype(np.float64)
    festival_flag   = df_calendar["festival_flag"].values.astype(np.float64)

    # Customer purchase-rate weights (shape: n_customers)
    customer_ids    = df_customers["customer_id"].values
    purchase_rates  = df_customers["purchase_rate"].values.astype(np.float64)
    # Normalise once so multinomial draws are cheap
    rate_weights    = purchase_rates / purchase_rates.sum()
    n_customers     = len(customer_ids)

    # Price table: pivot to (n_products × n_dates) matrices
    # Merge price onto product × date grid
    df_price_indexed = df_price.set_index(["product_id", "date"])

    # ------------------------------------------------------------------
    # 2. Step 1 — vectorised product-day demand
    # ------------------------------------------------------------------
    product_rows = df_products.reset_index(drop=True)

    # Will accumulate per-product results then concat once at the end
    sales_chunks: list[pd.DataFrame] = []
    daily_agg_chunks: list[pd.DataFrame] = []

    for _, prod in product_rows.iterrows():
        pid:          str   = prod["product_id"]
        base_demand:  float = float(prod["base_demand"])
        base_price:   float = float(prod["base_price"])
        elasticity:   float = float(prod["true_elasticity"])

        # Fetch this product's price series (aligned to calendar dates)
        prod_price_df = df_price_indexed.loc[pid]          # 1096-row df
        # Re-index to calendar date order to guarantee alignment
        prod_price_df = prod_price_df.reindex(dates)

        prices       = prod_price_df["price"].values.astype(np.float64)
        is_promo     = prod_price_df["is_promo"].values.astype(bool)
        discount_pct = prod_price_df["discount_pct"].values.astype(np.float64)

        # Price ratio relative to base (the input to the elasticity formula)
        price_ratio = prices / base_price                  # shape (n_dates,)

        # Effective price after discount
        price_at_sale = np.round(prices * (1.0 - discount_pct), 2)

        # Expected demand per day — fully vectorised
        # lambda_t = base_demand
        #          × combined_factor_t
        #          × (1 + (FESTIVAL_UPLIFT - 1) × festival_flag_t)
        #          × price_ratio_t ^ elasticity
        #          × (PROMO_UPLIFT if is_promo_t else 1)
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

        # Draw total units per product-day
        total_units = rng.poisson(lam).astype(np.int64)   # shape (n_dates,)

        # Daily aggregate (product_id, date, units_sold) for stock.py
        daily_agg_chunks.append(
            pd.DataFrame(
                {
                    "product_id": pid,
                    "date":       dates,
                    "units_sold": total_units,
                }
            )
        )

        # ------------------------------------------------------------------
        # 3. Step 2 — sparse customer attribution for this product
        # ------------------------------------------------------------------
        # Only iterate over days where at least 1 unit was sold
        nonzero_days = np.nonzero(total_units)[0]

        if len(nonzero_days) == 0:
            continue

        prod_sales_rows: list[dict] = []

        for day_i in nonzero_days:
            n_units = int(total_units[day_i])
            day_date = dates[day_i]

            # Multinomial draw: distribute n_units across customers
            # shape (n_customers,) — most entries will be 0
            assignment = rng.multinomial(n_units, rate_weights)

            # Keep only customers who bought ≥ 1 unit (sparse)
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

    # ------------------------------------------------------------------
    # 4. Assemble final DataFrames
    # ------------------------------------------------------------------
    if not sales_chunks:
        df_sales = pd.DataFrame(
            columns=[
                "sale_id", "customer_id", "product_id", "date",
                "units_sold", "price_at_sale", "discount_pct", "revenue",
            ]
        )
    else:
        df_sales = pd.concat(sales_chunks, ignore_index=True)
        # Add surrogate key
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
