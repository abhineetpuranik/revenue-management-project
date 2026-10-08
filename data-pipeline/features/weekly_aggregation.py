"""
Weekly aggregation — Phase 4 feature engineering.

Reads raw sales and price data from MySQL and aggregates to one row per
(product_id, iso_year, iso_week).

Output columns
--------------
  product_id       : str
  iso_year         : int   — ISO year (differs from calendar year near Jan 1)
  iso_week         : int   — ISO week number 1-53
  week_start_date  : date  — Monday of the ISO week (for time-series plots)
  units_sold       : int   — total units sold that week  ← TARGET VARIABLE
  avg_price        : float — mean price_at_sale across all transactions
  avg_discount     : float — mean discount_pct across all transactions
  promo_days       : int   — number of distinct days in the week with is_promo=1
                             (from the price table, not sales)

Design notes
------------
- ISO week via pandas DateOffset / isocalendar() so Python and MySQL agree.
- Aggregation is a pure GROUP BY — no look-ahead of any kind.
- The sales table has one row per customer-product-date transaction;
  summing units_sold across all customers gives the true weekly total.
- price_at_sale (from sales) is used for avg_price because it captures
  actual effective price after any same-day discount.  The price table's
  `price` column is used separately in price_features.py for the
  list-price signal.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ── SQL queries ──────────────────────────────────────────────────────────────

_SALES_SQL = """
SELECT
    product_id,
    date,
    SUM(units_sold)                     AS units_sold,
    AVG(CAST(price_at_sale AS DOUBLE))  AS avg_price,
    AVG(CAST(discount_pct  AS DOUBLE))  AS avg_discount
FROM revenue_management.sales
GROUP BY product_id, date
ORDER BY product_id, date
"""

_PROMO_SQL = """
SELECT
    product_id,
    date,
    is_promo
FROM revenue_management.price
ORDER BY product_id, date
"""


def load_weekly_aggregates(engine: Engine) -> pd.DataFrame:
    """
    Return a DataFrame aggregated to one row per (product_id, iso_year, iso_week).

    Parameters
    ----------
    engine : SQLAlchemy Engine connected to revenue_management.

    Returns
    -------
    pd.DataFrame with columns:
        product_id, iso_year, iso_week, week_start_date,
        units_sold, avg_price, avg_discount, promo_days
    """
    logger.info("Loading daily sales aggregates from MySQL...")
    with engine.connect() as conn:
        df_sales = pd.read_sql(_SALES_SQL, conn, parse_dates=["date"])
        df_promo = pd.read_sql(_PROMO_SQL, conn, parse_dates=["date"])

    logger.info("  sales daily rows: %d", len(df_sales))

    # ── Derive ISO year/week from date ────────────────────────────────────
    iso = df_sales["date"].dt.isocalendar()          # returns year, week, day
    df_sales["iso_year"] = iso["year"].astype(int)
    df_sales["iso_week"] = iso["week"].astype(int)

    # ── Week-start date (Monday) — useful for plotting and joining ────────
    # pandas isocalendar week starts on Monday (ISO standard)
    df_sales["week_start_date"] = df_sales["date"] - pd.to_timedelta(
        df_sales["date"].dt.dayofweek, unit="D"
    )

    # ── Aggregate to weekly ───────────────────────────────────────────────
    weekly = (
        df_sales
        .groupby(["product_id", "iso_year", "iso_week", "week_start_date"],
                 as_index=False)
        .agg(
            units_sold=("units_sold",  "sum"),
            avg_price =("avg_price",   "mean"),
            avg_discount=("avg_discount", "mean"),
        )
    )

    # ── Promo days per product-week (from price table) ────────────────────
    iso_p = df_promo["date"].dt.isocalendar()
    df_promo["iso_year"] = iso_p["year"].astype(int)
    df_promo["iso_week"] = iso_p["week"].astype(int)

    promo_agg = (
        df_promo
        .groupby(["product_id", "iso_year", "iso_week"], as_index=False)
        .agg(promo_days=("is_promo", "sum"))
    )
    promo_agg["promo_days"] = promo_agg["promo_days"].astype(int)

    weekly = weekly.merge(promo_agg, on=["product_id", "iso_year", "iso_week"], how="left")
    weekly["promo_days"] = weekly["promo_days"].fillna(0).astype(int)

    # ── Sort for downstream lag computation ──────────────────────────────
    weekly = weekly.sort_values(["product_id", "iso_year", "iso_week"]).reset_index(drop=True)

    n_products = weekly["product_id"].nunique()
    n_weeks    = weekly[["iso_year", "iso_week"]].drop_duplicates().shape[0]
    logger.info(
        "Weekly aggregation complete: %d rows (%d products × ~%d weeks).",
        len(weekly), n_products, n_weeks,
    )
    return weekly
