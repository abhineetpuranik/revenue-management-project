from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


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
    logger.info("Loading daily sales aggregates from MySQL...")
    with engine.connect() as conn:
        df_sales = pd.read_sql(_SALES_SQL, conn, parse_dates=["date"])
        df_promo = pd.read_sql(_PROMO_SQL, conn, parse_dates=["date"])

    logger.info("  sales daily rows: %d", len(df_sales))

    iso = df_sales["date"].dt.isocalendar()
    df_sales["iso_year"] = iso["year"].astype(int)
    df_sales["iso_week"] = iso["week"].astype(int)

    df_sales["week_start_date"] = df_sales["date"] - pd.to_timedelta(
        df_sales["date"].dt.dayofweek, unit="D"
    )

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

    weekly = weekly.sort_values(["product_id", "iso_year", "iso_week"]).reset_index(drop=True)

    n_products = weekly["product_id"].nunique()
    n_weeks    = weekly[["iso_year", "iso_week"]].drop_duplicates().shape[0]
    logger.info(
        "Weekly aggregation complete: %d rows (%d products x ~%d weeks).",
        len(weekly), n_products, n_weeks,
    )
    return weekly
