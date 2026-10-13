from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

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
    with engine.connect() as conn:
        daily = pd.read_sql(text(_DAILY_SQL), conn)
        units = pd.read_sql(text(_UNITS_SQL), conn)

    daily["date"] = pd.to_datetime(daily["date"])
    units["date"] = pd.to_datetime(units["date"])

    df = daily.merge(units, on=["product_id", "date"], how="left")
    df["units_sold"] = df["units_sold"].fillna(0).astype(int)
    df["is_promo"] = df["is_promo"].astype(int)
    df["festival_flag"] = df["festival_flag"].astype(int)
    df["price_at_sale"] = df["list_price"] * (1.0 - df["discount_pct"])

    logger.info("Daily panel: %d rows, %d products.", len(df), df["product_id"].nunique())
    return df


def zero_sales_summary(daily: pd.DataFrame) -> pd.DataFrame:
    out = (
        daily.groupby(["product_id", "category"], as_index=False)
        .agg(days=("units_sold", "size"),
             zero_days=("units_sold", lambda s: int((s == 0).sum())),
             mean_daily_units=("units_sold", "mean"))
    )
    out["zero_day_rate"] = out["zero_days"] / out["days"]
    return out.sort_values("zero_day_rate", ascending=False).reset_index(drop=True)


def build_weekly_panel(daily: pd.DataFrame) -> pd.DataFrame:
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
             log_price_ratio=("lpr", "mean"),
             log_sale_price_ratio=("lspr", "mean"),
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
