"""
Price features — Phase 4 feature engineering.

Builds weekly price and discount features from the MySQL price table.

Features produced
-----------------
  list_price_mean    : float — mean listed price (from price.price) over the week
  price_change_pct   : float — % change in list_price_mean vs. previous week
                               for the same product
                               NaN for week 1 per product (no prior week)
  avg_discount_price : float — mean discount_pct from the price table
                               (complements the sales-table discount already
                               in weekly_aggregation; captures listed discount
                               on days the product was not actually purchased)

Leakage note
------------
price_change_pct uses the PREVIOUS week's list_price_mean, computed with
shift(1) on the ascending time-sorted product series — identical pattern to
lag_features.py.  No same-week or future price information enters the feature.

The first week per product will have NaN for price_change_pct.
build_feature_table.py drops those rows anyway (they already have NaN lags),
so this NaN is resolved for free.
"""

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
    """
    Return a DataFrame of price features at weekly per-product granularity.

    Parameters
    ----------
    engine : SQLAlchemy Engine connected to revenue_management.

    Returns
    -------
    pd.DataFrame with columns:
        product_id, iso_year, iso_week,
        list_price_mean, price_change_pct, avg_discount_price
    """
    logger.info("Loading price data from MySQL...")
    with engine.connect() as conn:
        df_price = pd.read_sql(_PRICE_SQL, conn, parse_dates=["date"])

    # ── ISO week ──────────────────────────────────────────────────────────
    iso = df_price["date"].dt.isocalendar()
    df_price["iso_year"] = iso["year"].astype(int)
    df_price["iso_week"] = iso["week"].astype(int)

    # ── Aggregate to weekly ───────────────────────────────────────────────
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

    # ── Price change % vs prior week (strictly backward-looking) ─────────
    prev_price = (
        weekly_price
        .groupby("product_id", sort=False)["list_price_mean"]
        .shift(1)      # shift(1) → previous week's mean price
    )
    # pct change: (current - previous) / previous
    weekly_price["price_change_pct"] = (
        (weekly_price["list_price_mean"] - prev_price) / prev_price
    )
    # First week per product → NaN (no prior week); leave as-is — will be
    # dropped with the lag-NaN rows in build_feature_table.py

    logger.info("Price features built: %d product-week rows.", len(weekly_price))
    return weekly_price[
        [
            "product_id", "iso_year", "iso_week",
            "list_price_mean", "price_change_pct", "avg_discount_price",
        ]
    ]
