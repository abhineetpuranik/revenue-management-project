"""
Lag features — Phase 4 feature engineering.

Builds strictly backward-looking lag features for weekly units_sold.

Lag definition
--------------
  lag_1_units  = units_sold from the immediately preceding week
  lag_2_units  = units_sold from 2 weeks prior
  lag_3_units  = units_sold from 3 weeks prior

"Strictly backward-looking" guarantee
--------------------------------------
Lags are computed via pandas GroupBy + shift(n) on a DataFrame that is
sorted ascending by (product_id, iso_year, iso_week).  shift(n) with n > 0
always moves values *forward* in the sorted order — i.e., row i receives the
value from row i-n.  Because the sort is ascending in time, row i-n is always
*earlier* than row i.  There is therefore no possible look-ahead:

    week W receives lag_1 = units_sold from week W-1
    week W receives lag_2 = units_sold from week W-2
    week W receives lag_3 = units_sold from week W-3

A post-computation leakage test in build_feature_table.py independently
verifies this by joining lag values back to the raw weekly series and
checking equality row-by-row.

Missing values
--------------
The first 3 rows per product will have NaN in at least one lag column
(week 1 has no W-1, W-2, W-3; week 2 has no W-2, W-3; week 3 has no W-3).
These rows are flagged with  insufficient_history = True  and are later
DROPPED by build_feature_table.py.  They are never zero-filled, which
would introduce spurious training signal.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LAG_WEEKS = [1, 2, 3]          # extend this list to add more lags


def add_lag_features(df_weekly: pd.DataFrame) -> pd.DataFrame:
    """
    Add lag_1_units, lag_2_units, lag_3_units and an insufficient_history flag.

    Parameters
    ----------
    df_weekly : pd.DataFrame
        Output of weekly_aggregation.load_weekly_aggregates().
        Must contain: product_id, iso_year, iso_week, units_sold.
        Must be sorted ascending by (product_id, iso_year, iso_week)
        — weekly_aggregation already guarantees this.

    Returns
    -------
    pd.DataFrame
        Original DataFrame plus lag columns and insufficient_history (bool).
    """
    df = df_weekly.copy()

    # Verify sort order — critical for correctness
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
            "Re-sorting now — lag features may be incorrect if called out of order."
        )
        df = df.sort_values(["product_id", "iso_year", "iso_week"]).reset_index(drop=True)

    # ── Compute lags via shift within each product group ─────────────────
    # groupby preserves relative order within each group, so shift(n)
    # looks exactly n rows backward (= n weeks earlier).
    for n in LAG_WEEKS:
        col_name = f"lag_{n}_units"
        df[col_name] = (
            df.groupby("product_id", sort=False)["units_sold"]
            .shift(n)          # shift(n>0) → look n steps into the past
        )
        logger.debug("Added %s (NaN count: %d)", col_name, df[col_name].isna().sum())

    # ── Flag rows with insufficient lag history ───────────────────────────
    # A row has insufficient history if ANY lag column is NaN.
    lag_cols = [f"lag_{n}_units" for n in LAG_WEEKS]
    df["insufficient_history"] = df[lag_cols].isna().any(axis=1)

    n_flagged = df["insufficient_history"].sum()
    logger.info(
        "Lag features added. %d rows flagged as insufficient_history "
        "(first %d week(s) per product).",
        n_flagged, max(LAG_WEEKS),
    )
    return df
