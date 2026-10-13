"""
Elasticity data — Phase 7 (Module 4a).

Builds the per-product regression dataset used to estimate price elasticity.

Source tables (application schema revenue_management only):
    sales     — summed to total units per product per day
    price     — LIST price and is_promo per product per day
    product   — base_price, category
    calendar  — seasonal_factor, weekday_factor, festival_flag

Why the LIST price (price table) and not price_at_sale
------------------------------------------------------
The Phase 1b generator (data_generation/sales.py) builds expected demand as

    base_demand × seasonal × weekday × festival_uplift
                × (price / base_price) ^ elasticity   (the hidden per-product value)
                × (PROMO_UPLIFT if is_promo)

so elasticity acts on the list price, and a promotion is a separate
multiplicative uplift. Regressing on price_at_sale (the discounted price)
would credit the promo uplift to the price cut. We therefore regress on the
list price and include promotions as a control.

Zero-sales days and the weekly grain
------------------------------------
log(units) is undefined on days with zero sales. Up to ~9 % of days are
zero for the lowest-volume Electronics products (0 % for every Staples,
Personal Care and Impulse product). Three options were compared on the
synthetic data (see validate_elasticity.py, "design comparison"):

  * daily, dropping zero days  — biased for low-volume products: dropping the
    zeros keeps only the "lucky" high-price days, and log of a small Poisson
    count is itself biased (Jensen's inequality), so slopes drift toward 0.
  * daily with log(units + 1)  — rejected: the +1 distorts the slope most
    exactly where counts are small.
  * WEEKLY totals (chosen)     — summing 7 days makes counts large enough that
    zero weeks essentially never occur and the log-of-count bias shrinks.
    It gave the lowest error against ground truth.

The weekly panel uses ISO weeks (Monday start, matching Phase 4) and keeps
only complete 7-day weeks, so the weekday mix is identical in every row and
weekday_factor drops out (it would be a constant). Controls at weekly grain:

    promo_days      — number of promo days in the week   (is_promo control)
    log_seasonal    — log of the week's mean seasonal_factor
    festival_days   — number of festival days in the week

Ground-truth isolation: this module never reads the ground-truth schema.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Minimum number of days for a week to be used (complete ISO weeks only)
DAYS_PER_FULL_WEEK: int = 7

_DAILY_SQL = """
SELECT
    p.product_id                       AS product_id,
    p.date                             AS date,
    CAST(p.price AS DOUBLE)            AS list_price,
    p.is_promo                         AS is_promo,
    CAST(p.discount_pct AS DOUBLE)     AS discount_pct,
    CAST(pr.base_price AS DOUBLE)      AS base_price,
    pr.category                        AS category,
    CAST(c.seasonal_factor AS DOUBLE)  AS seasonal_factor,
    CAST(c.weekday_factor AS DOUBLE)   AS weekday_factor,
    c.festival_flag                    AS festival_flag
FROM price p
JOIN product  pr ON pr.product_id = p.product_id
JOIN calendar c  ON c.date        = p.date
ORDER BY p.product_id, p.date
"""

_UNITS_SQL = """
SELECT product_id, date, SUM(units_sold) AS units_sold
FROM sales
GROUP BY product_id, date
"""


def load_daily_panel(engine) -> pd.DataFrame:
    """
    One row per product per calendar day, with total units sold (0 on days
    with no sales rows), list price, promo flag and calendar factors.
    """
    with engine.connect() as conn:
        daily = pd.read_sql(text(_DAILY_SQL), conn)
        units = pd.read_sql(text(_UNITS_SQL), conn)

    daily["date"] = pd.to_datetime(daily["date"])
    units["date"] = pd.to_datetime(units["date"])

    df = daily.merge(units, on=["product_id", "date"], how="left")
    # A product-day with no sales rows genuinely sold 0 units.
    df["units_sold"] = df["units_sold"].fillna(0).astype(int)
    df["is_promo"] = df["is_promo"].astype(int)
    df["festival_flag"] = df["festival_flag"].astype(int)
    df["price_at_sale"] = df["list_price"] * (1.0 - df["discount_pct"])

    logger.info("Daily panel: %d rows, %d products.", len(df), df["product_id"].nunique())
    return df


def zero_sales_summary(daily: pd.DataFrame) -> pd.DataFrame:
    """Share of zero-sales days per product (reported, drives the weekly-grain choice)."""
    out = (
        daily.groupby(["product_id", "category"], as_index=False)
        .agg(days=("units_sold", "size"),
             zero_days=("units_sold", lambda s: int((s == 0).sum())),
             mean_daily_units=("units_sold", "mean"))
    )
    out["zero_day_rate"] = out["zero_days"] / out["days"]
    return out.sort_values("zero_day_rate", ascending=False).reset_index(drop=True)


def build_weekly_panel(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate the daily panel to complete ISO weeks per product.

    Columns: product_id, category, iso_year, iso_week, week_start_date,
             units_sold, log_price_ratio, log_sale_price_ratio,
             promo_days, log_seasonal, festival_days, n_days
    """
    df = daily.copy()
    iso = df["date"].dt.isocalendar()
    df["iso_year"] = iso["year"].astype(int)
    df["iso_week"] = iso["week"].astype(int)
    df["week_start_date"] = df["date"] - pd.to_timedelta(df["date"].dt.dayofweek, unit="D")
    df["lpr"] = np.log(df["list_price"] / df["base_price"])
    df["lspr"] = np.log(df["price_at_sale"] / df["base_price"])

    weekly = (
        df.groupby(["product_id", "category", "iso_year", "iso_week", "week_start_date"],
                   as_index=False)
        .agg(units_sold=("units_sold", "sum"),
             log_price_ratio=("lpr", "mean"),          # mean log list-price ratio over the week
             log_sale_price_ratio=("lspr", "mean"),    # only used for the design comparison
             promo_days=("is_promo", "sum"),
             seasonal_mean=("seasonal_factor", "mean"),
             festival_days=("festival_flag", "sum"),
             n_days=("date", "size"))
    )
    n_before = len(weekly)
    weekly = weekly[weekly["n_days"] == DAYS_PER_FULL_WEEK].copy()
    weekly["log_seasonal"] = np.log(weekly["seasonal_mean"])
    weekly = weekly.drop(columns="seasonal_mean")

    logger.info("Weekly panel: %d complete product-weeks (%d partial weeks dropped).",
                len(weekly), n_before - len(weekly))
    return weekly.sort_values(["product_id", "iso_year", "iso_week"]).reset_index(drop=True)
