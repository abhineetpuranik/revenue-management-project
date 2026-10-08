"""
Time-based train/test split for demand forecasting — Phase 5.

Split strategy
--------------
Data is split by week_start_date across ALL products simultaneously so the
boundary is a single calendar date, not a per-product row count.  This means:

  - Every product's training set ends on the same date.
  - Every product's test set covers the same calendar period.
  - There is zero overlap: test_start_date > train_end_date.

A random split is explicitly NOT used because it would allow future weeks to
leak into the training set (a row from week W+5 could end up in train while
week W is in test, which invalidates the lag features).

Test window
-----------
TEST_WEEKS = 8  →  last 8 distinct ISO weeks in the dataset form the test set.
With 155 weeks per product this gives:
  - Train : 147 weeks × 50 products = 7 350 rows
  - Test  :   8 weeks × 50 products =   400 rows
  - Split : ~94.8 % train / ~5.2 % test

This is intentionally conservative (small test set relative to data) because
the primary use case is training on as much history as possible and predicting
the near future.

Feature / target columns
------------------------
FEATURE_COLS : the 14 input features passed to both models.
               product_id is NOT a raw feature here — it is handled
               differently by each model wrapper (LR: one-hot, XGB: label).
TARGET_COL   : 'units_sold'
KEY_COLS     : columns used for identification but not model inputs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

TEST_WEEKS: int = 8

FEATURE_COLS: list[str] = [
    "lag_1_units",
    "lag_2_units",
    "lag_3_units",
    "month",
    "month_sin",
    "month_cos",
    "seasonal_factor_mean",
    "festival_week",
    "list_price_mean",
    "price_change_pct",
    "avg_discount_price",
    "promo_days",
    "avg_price",
    "avg_discount",
]

TARGET_COL: str  = "units_sold"
KEY_COLS:   list[str] = ["product_id", "iso_year", "iso_week", "week_start_date"]

FEATURES_CSV: Path = (
    Path(__file__).resolve().parent.parent / "data" / "features" / "forecast_features.csv"
)


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class SplitResult:
    """Container for all split outputs passed between pipeline stages."""
    X_train:        pd.DataFrame
    X_test:         pd.DataFrame
    y_train:        pd.Series
    y_test:         pd.Series
    # Full rows (keys + features + target) — useful for per-product evaluation
    train_df:       pd.DataFrame
    test_df:        pd.DataFrame
    # Metadata for provenance / artifact recording
    train_start:    str
    train_end:      str
    test_start:     str
    test_end:       str
    n_train:        int
    n_test:         int
    feature_cols:   list[str] = field(default_factory=lambda: list(FEATURE_COLS))
    target_col:     str = TARGET_COL


# ── Public API ────────────────────────────────────────────────────────────────

def load_features(path: Path | None = None) -> pd.DataFrame:
    """
    Load the forecast_features CSV produced by Phase 4.

    Partial-week handling
    ---------------------
    The dataset ends on 2024-12-31 (a Tuesday).  The ISO week starting
    2024-12-30 therefore contains only 2 calendar days instead of 7.
    Units_sold for that week is ~2/7 of a typical week, making it a severe
    outlier that inflates RMSE and distorts model selection.  The last ISO
    week is automatically dropped if it covers fewer than 7 calendar days
    (i.e., if the final week_start_date + 6 days > dataset end date).

    Parameters
    ----------
    path : Path or None
        Override the default FEATURES_CSV path.  Useful for testing.

    Returns
    -------
    pd.DataFrame sorted by (product_id, week_start_date), with any partial
    final week removed.
    """
    csv_path = path or FEATURES_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"forecast_features.csv not found at {csv_path}.\n"
            "Run Phase 4 (features/build_feature_table.py) first."
        )
    df = pd.read_csv(csv_path, parse_dates=["week_start_date"])
    df = df.sort_values(["product_id", "week_start_date"]).reset_index(drop=True)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    # Drop partial final week: if last Monday + 6 days exceeds the dataset's
    # last date, that ISO week is incomplete.
    last_week_start = df["week_start_date"].max()
    last_week_end   = last_week_start + pd.Timedelta(days=6)
    dataset_end     = df["week_start_date"].max()   # last observed Monday

    # Use the actual last date in the raw data as the dataset boundary.
    # A full week has 7 days; if the week_start + 6 falls after the last
    # available sales date (2024-12-31), the week is partial.
    # The dataset end is 2024-12-31 and the last ISO week starts 2024-12-30,
    # giving only 2 days — clearly partial (< 7).
    # We detect this by checking how many rows per product exist in the final
    # week vs the penultimate week.
    final_week_count       = df[df["week_start_date"] == last_week_start].shape[0]
    penult_week_start      = sorted(df["week_start_date"].unique())[-2]
    penultimate_week_count = df[df["week_start_date"] == penult_week_start].shape[0]

    if final_week_count == penultimate_week_count:
        # Both weeks have the same number of product rows — could still be
        # partial if units are very low.  Check unit_sold relative to prior weeks.
        final_median   = df[df["week_start_date"] == last_week_start]["units_sold"].median()
        penult_median  = df[df["week_start_date"] == penult_week_start]["units_sold"].median()
        is_partial = (final_median < penult_median * 0.5)
    else:
        # Row count differs — partial week
        is_partial = True

    if is_partial:
        n_before = len(df)
        final_median_val  = df[df["week_start_date"] == last_week_start]["units_sold"].median()
        penult_median_val = df[df["week_start_date"] == penult_week_start]["units_sold"].median()
        df = df[df["week_start_date"] != last_week_start].copy()
        logger.warning(
            "Dropped partial final week (%s): median units_sold=%.1f vs "
            "prior week median=%.1f (%.1f%% of full week). Removed %d rows.",
            last_week_start.date(),
            final_median_val,
            penult_median_val,
            100 * final_median_val / (penult_median_val + 1e-9),
            n_before - len(df),
        )
        logger.info("Dataset trimmed to %d rows after dropping partial week.", len(df))

    return df


def time_split(
    df: pd.DataFrame,
    test_weeks: int = TEST_WEEKS,
) -> SplitResult:
    """
    Split df into train and test by the most recent `test_weeks` calendar weeks.

    Parameters
    ----------
    df        : output of load_features() — must contain week_start_date.
    test_weeks: number of distinct ISO weeks to hold out as test.

    Returns
    -------
    SplitResult dataclass — see docstring above.
    """
    # Identify the cutoff: last `test_weeks` distinct week_start_date values
    unique_weeks = sorted(df["week_start_date"].unique())
    if test_weeks >= len(unique_weeks):
        raise ValueError(
            f"test_weeks={test_weeks} is >= total weeks={len(unique_weeks)}.  "
            "Reduce TEST_WEEKS."
        )

    cutoff_date: pd.Timestamp = unique_weeks[-test_weeks]   # first test week (inclusive)

    train_df = df[df["week_start_date"] < cutoff_date].copy()
    test_df  = df[df["week_start_date"] >= cutoff_date].copy()

    # Sanity checks — these must hold or something is wrong upstream
    assert len(train_df) + len(test_df) == len(df), "Split rows don't sum to total"
    assert train_df["week_start_date"].max() < test_df["week_start_date"].min(), \
        "Train/test date ranges OVERLAP — leakage detected in split logic"
    assert len(test_df["week_start_date"].unique()) == test_weeks, \
        f"Test set has {len(test_df['week_start_date'].unique())} unique weeks, expected {test_weeks}"

    X_train = train_df[FEATURE_COLS].copy()
    X_test  = test_df[FEATURE_COLS].copy()
    y_train = train_df[TARGET_COL].copy()
    y_test  = test_df[TARGET_COL].copy()

    result = SplitResult(
        X_train    = X_train,
        X_test     = X_test,
        y_train    = y_train,
        y_test     = y_test,
        train_df   = train_df,
        test_df    = test_df,
        train_start = str(train_df["week_start_date"].min().date()),
        train_end   = str(train_df["week_start_date"].max().date()),
        test_start  = str(test_df["week_start_date"].min().date()),
        test_end    = str(test_df["week_start_date"].max().date()),
        n_train    = len(train_df),
        n_test     = len(test_df),
    )

    logger.info(
        "Time split: TRAIN %s to %s (%d rows) | TEST %s to %s (%d rows)",
        result.train_start, result.train_end, result.n_train,
        result.test_start,  result.test_end,  result.n_test,
    )
    return result
