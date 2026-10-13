from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    return df


def _drop_exact_duplicates(df: pd.DataFrame, table: str) -> pd.DataFrame:
    n_before = len(df)
    df = df.drop_duplicates()
    dropped = n_before - len(df)
    if dropped:
        logger.warning("[%s] Dropped %d exact duplicate rows.", table, dropped)
    return df


def _parse_date_column(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
    n_bad = df[col].isna().sum()
    if n_bad:
        logger.warning("  %d unparseable date values coerced to NaT in column '%s'.", n_bad, col)
    return df


def _fill_numeric_nulls_with_median(
    df: pd.DataFrame,
    col: str,
    table: str,
    *,
    floor: float | None = None,
    ceil: float | None = None,
    floor_replacement: float | None = None,
) -> pd.DataFrame:
    n_null = df[col].isna().sum()
    if n_null:
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)
        logger.warning("[%s] Filled %d null(s) in '%s' with median %.4f.",
                       table, n_null, col, median_val)
    if floor is not None:
        repl = floor_replacement if floor_replacement is not None else floor
        bad = df[col] < floor
        if bad.any():
            logger.warning("[%s] Replaced %d value(s) in '%s' below floor %.4f with %.4f.",
                           table, bad.sum(), col, floor, repl)
            df.loc[bad, col] = np.nan
            df[col] = df[col].fillna(df[col].median())
    if ceil is not None:
        df[col] = df[col].clip(upper=ceil)
    return df


def _drop_null_key_rows(df: pd.DataFrame, key_cols: list[str], table: str) -> pd.DataFrame:
    mask = df[key_cols].isna().any(axis=1)
    n = mask.sum()
    if n:
        logger.warning("[%s] Dropped %d row(s) with null key column(s): %s.", table, n, key_cols)
        df = df[~mask].copy()
    return df


def _enforce_key_uniqueness(
    df: pd.DataFrame,
    key_cols: list[str],
    table: str,
) -> pd.DataFrame:
    n_before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    dropped = n_before - len(df)
    if dropped:
        logger.warning(
            "[%s] Dropped %d duplicate row(s) on key %s (kept first occurrence).",
            table, dropped, key_cols,
        )
    return df


def clean_product(df: pd.DataFrame) -> pd.DataFrame:
    table = "product"
    df = df.copy()

    df = _strip_strings(df)

    df = _drop_exact_duplicates(df, table)

    df = _drop_null_key_rows(df, ["product_id"], table)

    df = _enforce_key_uniqueness(df, ["product_id"], table)

    df["category"] = df["category"].str.title()

    df = _fill_numeric_nulls_with_median(
        df, "base_price", table, floor=0.0, floor_replacement=None
    )

    df = _fill_numeric_nulls_with_median(df, "base_demand", table, floor=1.0)
    df["base_demand"] = df["base_demand"].round(0).astype("int64")

    n_non_neg = (df["true_elasticity"] >= 0).sum()
    if n_non_neg:
        logger.warning(
            "[%s] Replaced %d non-negative true_elasticity value(s) with -0.10.",
            table, n_non_neg,
        )
        df.loc[df["true_elasticity"] >= 0, "true_elasticity"] = np.nan
    df = _fill_numeric_nulls_with_median(df, "true_elasticity", table)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_customer(df: pd.DataFrame) -> pd.DataFrame:
    table = "customer"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    df = _drop_null_key_rows(df, ["customer_id"], table)

    df = _enforce_key_uniqueness(df, ["customer_id"], table)

    df["true_segment"] = df["true_segment"].str.lower()

    for seg in df["true_segment"].dropna().unique():
        seg_mask = df["true_segment"] == seg
        seg_median = df.loc[seg_mask, "purchase_rate"].median()
        null_in_seg = seg_mask & df["purchase_rate"].isna()
        if null_in_seg.any():
            df.loc[null_in_seg, "purchase_rate"] = seg_median
            logger.warning(
                "[%s] Filled %d null purchase_rate(s) in segment '%s' with %.4f.",
                table, null_in_seg.sum(), seg, seg_median,
            )
    col_min = df["purchase_rate"].min()
    bad_rate = df["purchase_rate"] <= 0
    if bad_rate.any():
        logger.warning(
            "[%s] Replaced %d non-positive purchase_rate(s) with column min %.4f.",
            table, bad_rate.sum(), col_min,
        )
        df.loc[bad_rate, "purchase_rate"] = col_min

    for col in ("basket_mean", "basket_std"):
        df = _fill_numeric_nulls_with_median(df, col, table, floor=0.0)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_calendar(df: pd.DataFrame) -> pd.DataFrame:
    table = "calendar"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    df = _parse_date_column(df, "date")

    df = _drop_null_key_rows(df, ["date"], table)

    df = _enforce_key_uniqueness(df, ["date"], table)

    df["weekday_name"] = df["weekday_name"].str.title()

    for col in ("seasonal_factor", "weekday_factor", "combined_factor"):
        df = _fill_numeric_nulls_with_median(df, col, table)

    n_null_ff = df["festival_flag"].isna().sum()
    if n_null_ff:
        logger.warning("[%s] Filled %d null festival_flag(s) with 0.", table, n_null_ff)
        df["festival_flag"] = df["festival_flag"].fillna(0)
    df["festival_flag"] = df["festival_flag"].clip(0, 1).astype("int8")

    df["year"]    = df["date"].dt.year.astype("int16")
    df["month"]   = df["date"].dt.month.astype("int8")
    df["weekday"] = df["date"].dt.dayofweek.astype("int8")

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_price(df: pd.DataFrame) -> pd.DataFrame:
    table = "price"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    df = _parse_date_column(df, "date")

    df = _drop_null_key_rows(df, ["product_id", "date"], table)

    df = _enforce_key_uniqueness(df, ["product_id", "date"], table)

    null_prices = df["price"].isna()
    if null_prices.any():
        prod_medians = df.groupby("product_id")["price"].transform("median")
        global_median = df["price"].median()
        df.loc[null_prices, "price"] = prod_medians[null_prices].fillna(global_median)
        logger.warning("[%s] Filled %d null price(s) with per-product median.", table, null_prices.sum())
    bad_price = df["price"] <= 0
    if bad_price.any():
        logger.warning("[%s] Replaced %d non-positive price(s) with NaN then median.", table, bad_price.sum())
        df.loc[bad_price, "price"] = np.nan
        prod_medians = df.groupby("product_id")["price"].transform("median")
        df["price"] = df["price"].fillna(prod_medians).fillna(df["price"].median())
    df["price"] = df["price"].round(2)

    df["discount_pct"] = df["discount_pct"].fillna(0.0).clip(0.0, 1.0)

    df["is_promo"] = df["is_promo"].fillna(False).astype(bool)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    table = "sales"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    df = _parse_date_column(df, "date")

    df = _drop_null_key_rows(df, ["sale_id", "customer_id", "product_id", "date"], table)

    df = _enforce_key_uniqueness(df, ["customer_id", "product_id", "date"], table)

    df = df.sort_values(["date", "product_id", "customer_id"]).reset_index(drop=True)
    df["sale_id"] = range(1, len(df) + 1)

    n_null_u = df["units_sold"].isna().sum()
    if n_null_u:
        logger.warning("[%s] Filled %d null units_sold with 1.", table, n_null_u)
        df["units_sold"] = df["units_sold"].fillna(1)
    bad_u = df["units_sold"] <= 0
    if bad_u.any():
        logger.warning("[%s] Replaced %d non-positive units_sold with 1.", table, bad_u.sum())
        df.loc[bad_u, "units_sold"] = 1
    df["units_sold"] = df["units_sold"].astype("int64")

    df = _fill_numeric_nulls_with_median(df, "price_at_sale", table, floor=0.0)
    df["price_at_sale"] = df["price_at_sale"].round(2)

    df["discount_pct"] = df["discount_pct"].fillna(0.0).clip(0.0, 1.0)

    original_revenue_nulls = df["revenue"].isna().sum()
    df["revenue"] = (df["units_sold"] * df["price_at_sale"]).round(2)
    if original_revenue_nulls:
        logger.warning("[%s] Recomputed revenue for %d null row(s).", table, original_revenue_nulls)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_stock(df: pd.DataFrame) -> pd.DataFrame:
    table = "stock"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    df = _parse_date_column(df, "date")

    df = _drop_null_key_rows(df, ["product_id", "date"], table)

    df = _enforce_key_uniqueness(df, ["product_id", "date"], table)

    df["stock_level"] = df["stock_level"].fillna(0).clip(lower=0).astype("int64")

    df["units_restocked"] = df["units_restocked"].fillna(0).clip(lower=0).astype("int64")

    df["stockout_flag"] = df["stockout_flag"].fillna(0).clip(0, 1).astype("int8")

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)
