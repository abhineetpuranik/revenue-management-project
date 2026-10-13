from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_PRICE_SQL = """
SELECT
    product_id,
    date,
    CAST(price       AS DOUBLE) AS list_price,
    CAST(discount_pct AS DOUBLE) AS discount_pct
FROM revenue_management.price
ORDER BY product_id, date
"""


def load_price_features(engine: Engine) -> pd.DataFrame:
    logger.info("Loading price data from MySQL...")
    with engine.connect() as conn:
        df_price = pd.read_sql(_PRICE_SQL, conn, parse_dates=["date"])

    iso = df_price["date"].dt.isocalendar()
    df_price["iso_year"] = iso["year"].astype(int)
    df_price["iso_week"] = iso["week"].astype(int)

    weekly_price = (
        df_price
        .groupby(["product_id", "iso_year", "iso_week"], as_index=False)
        .agg(
            list_price_mean    =("list_price",   "mean"),
            avg_discount_price =("discount_pct", "mean"),
        )
    )
    weekly_price = weekly_price.sort_values(
        ["product_id", "iso_year", "iso_week"]
    ).reset_index(drop=True)

    prev_price = (
        weekly_price
        .groupby("product_id", sort=False)["list_price_mean"]
        .shift(1)
    )
    weekly_price["price_change_pct"] = (
        (weekly_price["list_price_mean"] - prev_price) / prev_price
    )

    logger.info("Price features built: %d product-week rows.", len(weekly_price))
    return weekly_price[
        [
            "product_id", "iso_year", "iso_week",
            "list_price_mean", "price_change_pct", "avg_discount_price",
        ]
    ]
