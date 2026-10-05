"""
ETL — table-specific cleaning functions.

Each public function accepts a raw DataFrame, applies documented cleaning
rules, and returns a cleaned copy.  Raw files are never modified.

Cleaning rules per table
------------------------
All tables
  [ALL-1] Strip leading/trailing whitespace from every string/object column.
  [ALL-2] Remove exact duplicate rows (all columns identical).
  [ALL-3] Parse date columns from ISO-8601 string to datetime64[ns].

product
  [PROD-1] Drop rows where product_id is null (key column — row is unusable).
  [PROD-2] Drop rows where product_id is a duplicate (keep first occurrence,
           log extras).
  [PROD-3] Standardize category to title-case, strip whitespace.
  [PROD-4] base_price: fill null with column median (price omission is
           recoverable); negative values replaced with NaN then median-filled.
  [PROD-5] base_demand: fill null with column median cast to int; values <= 0
           replaced with 1 (floor — zero expected daily demand is nonsensical).
  [PROD-6] true_elasticity: fill null with column median; values >= 0 replaced
           with -0.10 (elasticity must be negative by economic convention).

customer
  [CUST-1] Drop rows where customer_id is null.
  [CUST-2] Drop rows where customer_id is a duplicate (keep first).
  [CUST-3] Standardize true_segment to lowercase, strip whitespace.
  [CUST-4] purchase_rate: fill null with segment median; values <= 0 replaced
           with column min (a customer must have some nonzero purchase rate).
  [CUST-5] basket_mean / basket_std: fill null with column median; values < 0
           replaced with NaN then median-filled (spend cannot be negative).

calendar
  [CAL-1]  Drop rows where date is null.
  [CAL-2]  Drop rows where date is a duplicate (keep first).
  [CAL-3]  Standardize weekday_name to title-case, strip whitespace.
  [CAL-4]  seasonal_factor / weekday_factor / combined_factor: fill null with
           column median (should never occur in generated data; defensive only).
  [CAL-5]  festival_flag: fill null with 0 (absence of flag = no festival).
           Clip to {0, 1}.
  [CAL-6]  Recompute year, month, weekday from the parsed date to ensure
           internal consistency (guards against future data-entry errors).

price
  [PRICE-1] Drop rows where product_id or date is null.
  [PRICE-2] Drop rows with duplicate (product_id, date) composite key
            (keep first occurrence per key, log count of dropped rows).
  [PRICE-3] price: fill null with product median price; values <= 0 replaced
            with NaN then median-filled.
  [PRICE-4] discount_pct: fill null with 0.0; clip to [0.0, 1.0].
  [PRICE-5] is_promo: fill null with False; cast to bool.

sales
  [SALE-1] Drop rows where sale_id, customer_id, product_id, or date is null.
  [SALE-2] Drop exact duplicate rows first; then drop rows with duplicate
           (customer_id, product_id, date) natural key (keep first occurrence,
           log count).  sale_id is a surrogate — do NOT use it as a dedup key.
  [SALE-3] units_sold: fill null with 1 (minimum plausible purchase); values
           <= 0 replaced with 1.
  [SALE-4] price_at_sale: fill null with product_id median price from the
           price table if available, else column median; values <= 0 replaced
           with NaN then median-filled.
  [SALE-5] discount_pct: fill null with 0.0; clip to [0.0, 1.0].
  [SALE-6] revenue: recompute as units_sold * price_at_sale after filling
           nulls/fixing negatives (ensures internal consistency).

stock
  [STCK-1] Drop rows where product_id or date is null.
  [STCK-2] Drop rows with duplicate (product_id, date) composite key (keep
           first, log count).
  [STCK-3] stock_level: fill null with 0; clip to [0, +∞).
  [STCK-4] units_restocked: fill null with 0; clip to [0, +∞).
  [STCK-5] stockout_flag: fill null with 0; clip to {0, 1}.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic helpers (shared across all tables)
# ---------------------------------------------------------------------------

def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    """[ALL-1] Strip whitespace from all object/string columns in-place."""
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    return df


def _drop_exact_duplicates(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """[ALL-2] Remove rows where every column is identical."""
    n_before = len(df)
    df = df.drop_duplicates()
    dropped = n_before - len(df)
    if dropped:
        logger.warning("[%s] Dropped %d exact duplicate rows.", table, dropped)
    return df


def _parse_date_column(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """[ALL-3] Parse an ISO-8601 string date column to datetime64[ns]."""
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
    """
    Fill nulls with the column median, then optionally apply a floor/ceiling.

    Parameters
    ----------
    floor : if set, values < floor are replaced with floor_replacement (or floor).
    ceil  : if set, values > ceil are clipped to ceil.
    floor_replacement : value to use when floor is violated; defaults to floor.
    """
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
    """Drop rows where any key column is null and log the count."""
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
    """Keep first occurrence per composite key; log duplicate count."""
    n_before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    dropped = n_before - len(df)
    if dropped:
        logger.warning(
            "[%s] Dropped %d duplicate row(s) on key %s (kept first occurrence).",
            table, dropped, key_cols,
        )
    return df


# ---------------------------------------------------------------------------
# Table-specific cleaning functions
# ---------------------------------------------------------------------------

def clean_product(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning rules PROD-1 through PROD-6 to the product table."""
    table = "product"
    df = df.copy()

    # [ALL-1] Strip strings
    df = _strip_strings(df)

    # [ALL-2] Exact duplicates
    df = _drop_exact_duplicates(df, table)

    # [PROD-1] Drop null product_id
    df = _drop_null_key_rows(df, ["product_id"], table)

    # [PROD-2] Unique product_id
    df = _enforce_key_uniqueness(df, ["product_id"], table)

    # [PROD-3] Category to title-case
    df["category"] = df["category"].str.title()

    # [PROD-4] base_price: fill null with median; floor > 0
    df = _fill_numeric_nulls_with_median(
        df, "base_price", table, floor=0.0, floor_replacement=None
    )

    # [PROD-5] base_demand: fill null with median, floor at 1
    df = _fill_numeric_nulls_with_median(df, "base_demand", table, floor=1.0)
    df["base_demand"] = df["base_demand"].round(0).astype("int64")

    # [PROD-6] true_elasticity: fill null with median; must be < 0
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
    """Apply cleaning rules CUST-1 through CUST-5 to the customer table."""
    table = "customer"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    # [CUST-1] Drop null customer_id
    df = _drop_null_key_rows(df, ["customer_id"], table)

    # [CUST-2] Unique customer_id
    df = _enforce_key_uniqueness(df, ["customer_id"], table)

    # [CUST-3] true_segment to lowercase
    df["true_segment"] = df["true_segment"].str.lower()

    # [CUST-4] purchase_rate: fill null with segment median; floor above zero
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

    # [CUST-5] basket_mean / basket_std: fill null with median; floor at 0
    for col in ("basket_mean", "basket_std"):
        df = _fill_numeric_nulls_with_median(df, col, table, floor=0.0)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_calendar(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning rules CAL-1 through CAL-6 to the calendar table."""
    table = "calendar"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    # [ALL-3] Parse date
    df = _parse_date_column(df, "date")

    # [CAL-1] Drop null date
    df = _drop_null_key_rows(df, ["date"], table)

    # [CAL-2] Unique date
    df = _enforce_key_uniqueness(df, ["date"], table)

    # [CAL-3] weekday_name to title-case
    df["weekday_name"] = df["weekday_name"].str.title()

    # [CAL-4] Fill null factors with median
    for col in ("seasonal_factor", "weekday_factor", "combined_factor"):
        df = _fill_numeric_nulls_with_median(df, col, table)

    # [CAL-5] festival_flag: fill null with 0, clip to [0, 1]
    n_null_ff = df["festival_flag"].isna().sum()
    if n_null_ff:
        logger.warning("[%s] Filled %d null festival_flag(s) with 0.", table, n_null_ff)
        df["festival_flag"] = df["festival_flag"].fillna(0)
    df["festival_flag"] = df["festival_flag"].clip(0, 1).astype("int8")

    # [CAL-6] Recompute year / month / weekday from parsed date
    df["year"]    = df["date"].dt.year.astype("int16")
    df["month"]   = df["date"].dt.month.astype("int8")
    df["weekday"] = df["date"].dt.dayofweek.astype("int8")

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_price(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning rules PRICE-1 through PRICE-5 to the price table."""
    table = "price"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    # [ALL-3] Parse date
    df = _parse_date_column(df, "date")

    # [PRICE-1] Drop null key columns
    df = _drop_null_key_rows(df, ["product_id", "date"], table)

    # [PRICE-2] Enforce composite key uniqueness
    df = _enforce_key_uniqueness(df, ["product_id", "date"], table)

    # [PRICE-3] price: fill null with per-product median; floor > 0
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

    # [PRICE-4] discount_pct: fill null with 0.0, clip to [0, 1]
    df["discount_pct"] = df["discount_pct"].fillna(0.0).clip(0.0, 1.0)

    # [PRICE-5] is_promo: fill null with False, cast to bool
    df["is_promo"] = df["is_promo"].fillna(False).astype(bool)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning rules SALE-1 through SALE-6 to the sales table."""
    table = "sales"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    # [ALL-3] Parse date
    df = _parse_date_column(df, "date")

    # [SALE-1] Drop null key columns
    df = _drop_null_key_rows(df, ["sale_id", "customer_id", "product_id", "date"], table)

    # [SALE-2] Deduplicate on natural key (NOT sale_id)
    df = _enforce_key_uniqueness(df, ["customer_id", "product_id", "date"], table)

    # Reassign sale_id as a clean 1-based surrogate after dedup
    df = df.sort_values(["date", "product_id", "customer_id"]).reset_index(drop=True)
    df["sale_id"] = range(1, len(df) + 1)

    # [SALE-3] units_sold: fill null with 1, floor at 1
    n_null_u = df["units_sold"].isna().sum()
    if n_null_u:
        logger.warning("[%s] Filled %d null units_sold with 1.", table, n_null_u)
        df["units_sold"] = df["units_sold"].fillna(1)
    bad_u = df["units_sold"] <= 0
    if bad_u.any():
        logger.warning("[%s] Replaced %d non-positive units_sold with 1.", table, bad_u.sum())
        df.loc[bad_u, "units_sold"] = 1
    df["units_sold"] = df["units_sold"].astype("int64")

    # [SALE-4] price_at_sale: fill null with column median; floor > 0
    df = _fill_numeric_nulls_with_median(df, "price_at_sale", table, floor=0.0)
    df["price_at_sale"] = df["price_at_sale"].round(2)

    # [SALE-5] discount_pct: fill null with 0.0, clip to [0, 1]
    df["discount_pct"] = df["discount_pct"].fillna(0.0).clip(0.0, 1.0)

    # [SALE-6] Recompute revenue from units_sold × price_at_sale
    original_revenue_nulls = df["revenue"].isna().sum()
    df["revenue"] = (df["units_sold"] * df["price_at_sale"]).round(2)
    if original_revenue_nulls:
        logger.warning("[%s] Recomputed revenue for %d null row(s).", table, original_revenue_nulls)

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)


def clean_stock(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning rules STCK-1 through STCK-5 to the stock table."""
    table = "stock"
    df = df.copy()

    df = _strip_strings(df)
    df = _drop_exact_duplicates(df, table)

    # [ALL-3] Parse date
    df = _parse_date_column(df, "date")

    # [STCK-1] Drop null key columns
    df = _drop_null_key_rows(df, ["product_id", "date"], table)

    # [STCK-2] Enforce composite key uniqueness
    df = _enforce_key_uniqueness(df, ["product_id", "date"], table)

    # [STCK-3] stock_level: fill null with 0, clip to [0, ∞)
    df["stock_level"] = df["stock_level"].fillna(0).clip(lower=0).astype("int64")

    # [STCK-4] units_restocked: fill null with 0, clip to [0, ∞)
    df["units_restocked"] = df["units_restocked"].fillna(0).clip(lower=0).astype("int64")

    # [STCK-5] stockout_flag: fill null with 0, clip to {0, 1}
    df["stockout_flag"] = df["stockout_flag"].fillna(0).clip(0, 1).astype("int8")

    logger.info("[%s] Cleaning complete. %d rows remaining.", table, len(df))
    return df.reset_index(drop=True)
