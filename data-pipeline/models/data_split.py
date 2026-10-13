from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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


@dataclass
class SplitResult:
    X_train:        pd.DataFrame
    X_test:         pd.DataFrame
    y_train:        pd.Series
    y_test:         pd.Series
    train_df:       pd.DataFrame
    test_df:        pd.DataFrame
    train_start:    str
    train_end:      str
    test_start:     str
    test_end:       str
    n_train:        int
    n_test:         int
    feature_cols:   list[str] = field(default_factory=lambda: list(FEATURE_COLS))
    target_col:     str = TARGET_COL


def load_features(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or FEATURES_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"forecast_features.csv not found at {csv_path}.\n"
            "Run Phase 4 (features/build_feature_table.py) first."
        )
    df = pd.read_csv(csv_path, parse_dates=["week_start_date"])
    df = df.sort_values(["product_id", "week_start_date"]).reset_index(drop=True)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    last_week_start = df["week_start_date"].max()
    last_week_end   = last_week_start + pd.Timedelta(days=6)
    dataset_end     = df["week_start_date"].max()

    final_week_count       = df[df["week_start_date"] == last_week_start].shape[0]
    penult_week_start      = sorted(df["week_start_date"].unique())[-2]
    penultimate_week_count = df[df["week_start_date"] == penult_week_start].shape[0]

    if final_week_count == penultimate_week_count:
        final_median   = df[df["week_start_date"] == last_week_start]["units_sold"].median()
        penult_median  = df[df["week_start_date"] == penult_week_start]["units_sold"].median()
        is_partial = (final_median < penult_median * 0.5)
    else:
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
    unique_weeks = sorted(df["week_start_date"].unique())
    if test_weeks >= len(unique_weeks):
        raise ValueError(
            f"test_weeks={test_weeks} is >= total weeks={len(unique_weeks)}.  "
            "Reduce TEST_WEEKS."
        )

    cutoff_date: pd.Timestamp = unique_weeks[-test_weeks]

    train_df = df[df["week_start_date"] < cutoff_date].copy()
    test_df  = df[df["week_start_date"] >= cutoff_date].copy()

    assert len(train_df) + len(test_df) == len(df), "Split rows don't sum to total"
    assert train_df["week_start_date"].max() < test_df["week_start_date"].min(), \
        "Train/test date ranges OVERLAP - leakage detected in split logic"
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
