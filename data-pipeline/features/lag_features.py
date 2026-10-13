from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LAG_WEEKS = [1, 2, 3]


def add_lag_features(df_weekly: pd.DataFrame) -> pd.DataFrame:
    df = df_weekly.copy()

    expected_order = (
        df.groupby("product_id", sort=False)
        .apply(
            lambda g: g[["iso_year", "iso_week"]].reset_index(drop=True).equals(
                g[["iso_year", "iso_week"]].sort_values(
                    ["iso_year", "iso_week"]
                ).reset_index(drop=True)
            ),
            include_groups=False,
        )
        .all()
    )
    if not expected_order:
        logger.warning(
            "df_weekly was not sorted by (iso_year, iso_week) within each product. "
            "Re-sorting now - lag features may be incorrect if called out of order."
        )
        df = df.sort_values(["product_id", "iso_year", "iso_week"]).reset_index(drop=True)

    for n in LAG_WEEKS:
        col_name = f"lag_{n}_units"
        df[col_name] = (
            df.groupby("product_id", sort=False)["units_sold"]
            .shift(n)
        )
        logger.debug("Added %s (NaN count: %d)", col_name, df[col_name].isna().sum())

    lag_cols = [f"lag_{n}_units" for n in LAG_WEEKS]
    df["insufficient_history"] = df[lag_cols].isna().any(axis=1)

    n_flagged = df["insufficient_history"].sum()
    logger.info(
        "Lag features added. %d rows flagged as insufficient_history "
        "(first %d week(s) per product).",
        n_flagged, max(LAG_WEEKS),
    )
    return df
