"""
Phase 1b orchestrator — reads Phase 1a CSVs, generates Price/Sales/Stock
tables, writes them to data/raw/.

Output files (written to data/raw/ relative to data-pipeline/):
  price.csv   — 54 800 rows  (50 products × 1 096 dates)
  sales.csv   — ~500 k–2 M rows  (sparse customer-product-date transactions)
  stock.csv   — 54 800 rows  (50 products × 1 096 dates)

Ground-truth reminder
---------------------
This orchestrator reads but NEVER writes back the following columns:
  product.csv  :: true_elasticity — used only to compute expected demand
  customer.csv :: true_segment, purchase_rate, basket_mean, basket_std
                  — purchase_rate is used for customer attribution weights.
These columns must remain withheld from ML model inputs in all later phases.

Run
---
    cd data-pipeline
    python -m data_generation.generate_transactional_tables
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running as a script from data-pipeline/ root
_THIS_DIR    = Path(__file__).resolve().parent
_PIPELINE_ROOT = _THIS_DIR.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from data_generation.config import (
    INITIAL_STOCK_MULTIPLIER,
    NUM_CUSTOMERS,
    NUM_PRODUCTS,
    PRICE_CHANGE_INTERVAL_DAYS,
    PRICE_CHANGE_PROB,
    PROMO_PROB,
    RANDOM_SEED,
    RAW_DATA_DIR,
    RESTOCK_INTERVAL_DAYS,
)
from data_generation.price import generate_prices
from data_generation.sales import generate_sales
from data_generation.stock import generate_stock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def _print_section(title: str) -> None:
    width = 66
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


# ---------------------------------------------------------------------------
# Verification / summary helpers
# ---------------------------------------------------------------------------

def _summarise_price(df: pd.DataFrame, df_products: pd.DataFrame) -> None:
    _print_section("PRICE TABLE -- summary stats")
    print(f"\n  Rows: {len(df):,}  |  Columns: {list(df.columns)}")
    promo_days = df["is_promo"].sum()
    print(f"  Promo product-days: {promo_days:,}  "
          f"({100 * promo_days / len(df):.1f} %)")
    # Per-product price range — spot-check 3 products
    sample = df_products[["product_id", "base_price"]].head(3)
    print("\n  Price range sample (first 3 products):")
    for _, row in sample.iterrows():
        pid = row["product_id"]
        bp  = row["base_price"]
        sub = df[df["product_id"] == pid]["price"]
        print(f"    {pid}  base={bp:.2f}  "
              f"min={sub.min():.2f}  max={sub.max():.2f}  "
              f"unique={sub.nunique()} levels")


def _summarise_sales(
    df_sales: pd.DataFrame,
    df_products: pd.DataFrame,
    df_customers: pd.DataFrame,
) -> None:
    _print_section("SALES TABLE -- summary stats")
    print(f"\n  Rows: {len(df_sales):,}  |  Columns: {list(df_sales.columns)}")
    print(f"  Total units sold : {df_sales['units_sold'].sum():,}")
    print(f"  Total revenue    : £{df_sales['revenue'].sum():,.2f}")

    # Per-category average units/day
    print("\n  Average daily units sold per category (elasticity check):")
    merged = df_sales.merge(
        df_products[["product_id", "category", "true_elasticity"]],
        on="product_id",
    )
    # Number of product-days in each category
    n_dates = df_sales["date"].nunique()
    cat_products = df_products.groupby("category")["product_id"].count().rename("n_products")
    cat_stats = (
        merged.groupby("category")["units_sold"]
        .sum()
        .rename("total_units")
        .to_frame()
        .join(cat_products)
    )
    cat_stats["avg_daily_units_per_product"] = (
        cat_stats["total_units"] / (cat_stats["n_products"] * n_dates)
    ).round(2)
    cat_elasticity = df_products.groupby("category")["true_elasticity"].mean().round(4)
    cat_stats = cat_stats.join(cat_elasticity)
    print(cat_stats[["avg_daily_units_per_product", "true_elasticity"]].to_string())

    # Elasticity vs price-response check
    print("\n  Elasticity vs price-response check:")
    print("  (Products with more-negative elasticity should show a stronger")
    print("   correlation between price-ratio and relative demand change.)")
    merged2 = df_sales.merge(
        df_products[["product_id", "base_demand", "true_elasticity"]],
        on="product_id",
    )
    # Correlation of price_at_sale with units_sold, per product
    corr_per_product = (
        merged2.groupby("product_id")
        .apply(lambda g: g["price_at_sale"].corr(g["units_sold"]), include_groups=False)
        .rename("price_units_corr")
    )
    corr_df = corr_per_product.reset_index().merge(
        df_products[["product_id", "true_elasticity", "category"]], on="product_id"
    )
    cat_corr = corr_df.groupby("category").agg(
        mean_corr=("price_units_corr", "mean"),
        mean_elasticity=("true_elasticity", "mean"),
    ).round(4)
    print(cat_corr.to_string())
    print("\n  (Expect mean_corr to be negative and more negative for more-elastic categories.)")

    # Segment purchase behaviour check
    print("\n  Segment purchase behaviour check:")
    seg_stats = (
        df_sales.merge(
            df_customers[["customer_id", "true_segment"]], on="customer_id"
        )
        .groupby("true_segment")
        .agg(
            total_transactions=("sale_id", "count"),
            total_units=("units_sold", "sum"),
            total_revenue=("revenue", "sum"),
            avg_units_per_txn=("units_sold", "mean"),
        )
        .round(2)
    )
    # Divide by number of customers per segment for per-customer metric
    seg_counts = df_customers["true_segment"].value_counts().rename("n_customers")
    seg_stats = seg_stats.join(seg_counts)
    seg_stats["transactions_per_customer"] = (
        seg_stats["total_transactions"] / seg_stats["n_customers"]
    ).round(2)
    seg_stats["revenue_per_customer"] = (
        seg_stats["total_revenue"] / seg_stats["n_customers"]
    ).round(2)
    print(seg_stats[
        ["n_customers", "transactions_per_customer", "revenue_per_customer"]
    ].to_string())
    print("\n  (Expect high_value > regular > occasional > at_risk for both metrics.)")


def _summarise_stock(df: pd.DataFrame) -> None:
    _print_section("STOCK TABLE -- summary stats")
    print(f"\n  Rows: {len(df):,}  |  Columns: {list(df.columns)}")
    neg_stock = (df["stock_level"] < 0).sum()
    print(f"  Rows with stock_level < 0 : {neg_stock}  (must be 0)")
    stockouts = df["stockout_flag"].sum()
    print(f"  Stockout events           : {stockouts:,}")
    print(f"  Total units restocked     : {df['units_restocked'].sum():,}")
    print(f"  Min stock level           : {df['stock_level'].min()}")
    print(f"  Max stock level           : {df['stock_level'].max()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    t_start = time.time()

    _print_section("Phase 1b -- Transactional Table Generation")
    print(f"\n  Random seed           : {RANDOM_SEED}")
    print(f"  Price review interval : every {PRICE_CHANGE_INTERVAL_DAYS} days "
          f"(change prob {PRICE_CHANGE_PROB})")
    print(f"  Promo probability     : {PROMO_PROB * 100:.0f}% of product-days")
    print(f"  Restock interval      : every {RESTOCK_INTERVAL_DAYS} days")
    print(f"  Initial stock         : base_demand x {INITIAL_STOCK_MULTIPLIER}")

    out_dir = _PIPELINE_ROOT / RAW_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load Phase 1a outputs
    # ------------------------------------------------------------------
    print("\n  Loading Phase 1a base tables...", end=" ", flush=True)
    df_products  = pd.read_csv(out_dir / "product.csv")
    df_customers = pd.read_csv(out_dir / "customer.csv")
    df_calendar  = pd.read_csv(out_dir / "calendar.csv")
    df_calendar["date"] = pd.to_datetime(df_calendar["date"])
    print("done.")
    print(f"    product.csv  : {len(df_products):,} rows")
    print(f"    customer.csv : {len(df_customers):,} rows")
    print(f"    calendar.csv : {len(df_calendar):,} rows")

    # ------------------------------------------------------------------
    # Single shared RNG — same seed as Phase 1a for end-to-end reproducibility
    # ------------------------------------------------------------------
    rng = np.random.default_rng(RANDOM_SEED)

    # ------------------------------------------------------------------
    # Generate: Price
    # ------------------------------------------------------------------
    print("\n  Generating Price table...", end=" ", flush=True)
    t0 = time.time()
    df_price = generate_prices(df_products, df_calendar, rng)
    print(f"done ({time.time() - t0:.1f}s)  {len(df_price):,} rows")

    # ------------------------------------------------------------------
    # Generate: Sales
    # ------------------------------------------------------------------
    print("  Generating Sales table (this is the slow step)...",
          end=" ", flush=True)
    t0 = time.time()
    df_sales, df_daily_units = generate_sales(
        df_products, df_customers, df_calendar, df_price, rng
    )
    print(f"done ({time.time() - t0:.1f}s)  {len(df_sales):,} rows")

    # ------------------------------------------------------------------
    # Generate: Stock
    # ------------------------------------------------------------------
    print("  Generating Stock table...", end=" ", flush=True)
    t0 = time.time()
    df_stock = generate_stock(df_products, df_calendar, df_daily_units)
    print(f"done ({time.time() - t0:.1f}s)  {len(df_stock):,} rows")

    # ------------------------------------------------------------------
    # Write CSVs
    # ------------------------------------------------------------------
    price_path = out_dir / "price.csv"
    sales_path = out_dir / "sales.csv"
    stock_path = out_dir / "stock.csv"

    df_price.to_csv(price_path,  index=False)
    df_sales.to_csv(sales_path,  index=False)
    df_stock.to_csv(stock_path,  index=False)

    print(f"\n  CSVs written to: {out_dir.resolve()}")
    for path in (price_path, sales_path, stock_path):
        print(f"    {path.name:<15} {path.stat().st_size:>12,} bytes")

    print("\n  MD5 checksums:")
    for path in (price_path, sales_path, stock_path):
        print(f"    {path.name:<15} {_md5(path)}")

    # ------------------------------------------------------------------
    # Summary / verification output
    # ------------------------------------------------------------------
    _summarise_price(df_price, df_products)
    _summarise_sales(df_sales, df_products, df_customers)
    _summarise_stock(df_stock)

    elapsed = time.time() - t_start
    _print_section(f"Generation complete  ({elapsed:.1f}s total)")
    print(
        "\n  REMINDER: the following Phase 1a columns were used to SIMULATE\n"
        "  behaviour and must still be withheld from ML model inputs:\n"
        "    product.csv   -> true_elasticity\n"
        "    customer.csv  -> true_segment, purchase_rate, basket_mean, basket_std\n"
    )


if __name__ == "__main__":
    main()
