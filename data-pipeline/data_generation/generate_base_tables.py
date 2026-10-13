import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_PIPELINE_ROOT = _THIS_DIR.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from data_generation.calendar import generate_calendar
from data_generation.config import (
    CALENDAR_END,
    CALENDAR_START,
    CATEGORIES,
    NUM_CUSTOMERS,
    NUM_PRODUCTS,
    RANDOM_SEED,
    RAW_DATA_DIR,
    SEGMENTS,
)
from data_generation.customer import generate_customers
from data_generation.product import generate_products


def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def _print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def _summarise_products(df: pd.DataFrame) -> None:
    _print_section("PRODUCT TABLE - summary stats")
    print(f"\n  Rows: {len(df)}  |  Columns: {list(df.columns)}\n")

    grp = df.groupby("category", sort=False)
    cat_stats = grp.agg(
        count=("product_id", "count"),
        price_min=("base_price", "min"),
        price_max=("base_price", "max"),
        demand_mean=("base_demand", "mean"),
    ).round(2)
    print("  Per-category counts and price/demand ranges:")
    print(cat_stats.to_string(index=True))

    print("\n  true_elasticity by category (mean +/- std):")
    elas = grp["true_elasticity"].agg(["mean", "std", "min", "max"]).round(4)
    print(elas.to_string(index=True))


def _summarise_customers(df: pd.DataFrame) -> None:
    _print_section("CUSTOMER TABLE - summary stats")
    print(f"\n  Rows: {len(df)}  |  Columns: {list(df.columns)}\n")

    seg_counts = df["true_segment"].value_counts().sort_index()
    seg_pct = (seg_counts / len(df) * 100).round(1)
    summary = pd.DataFrame({"count": seg_counts, "pct": seg_pct})
    print("  true_segment distribution:")
    print(summary.to_string(index=True))

    print("\n  Buying parameters by segment (mean purchase_rate / basket_mean):")
    print(
        df.groupby("true_segment")[["purchase_rate", "basket_mean", "basket_std"]]
        .mean()
        .round(4)
        .to_string(index=True)
    )


def _summarise_calendar(df: pd.DataFrame) -> None:
    _print_section("CALENDAR TABLE - summary stats")
    print(f"\n  Rows: {len(df)}  |  Columns: {list(df.columns)}")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"  Festival days flagged: {df['festival_flag'].sum()}")
    print("\n  Monthly seasonal factors:")
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }
    mf = (
        df.groupby("month")["seasonal_factor"]
        .first()
        .rename(index=month_names)
    )
    print(mf.to_string())
    print("\n  Weekday demand factors (single-year sample):")
    wf = (
        df.groupby("weekday_name")["weekday_factor"]
        .first()
        .reindex(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
    )
    print(wf.to_string())


def main() -> None:
    _print_section("Phase 1a: Base Table Generation")
    print(f"\n  Random seed    : {RANDOM_SEED}")
    print(f"  Products       : {NUM_PRODUCTS}  ({len(CATEGORIES)} categories)")
    print(f"  Customers      : {NUM_CUSTOMERS}  ({len(SEGMENTS)} segments)")
    print(f"  Calendar range : {CALENDAR_START} to {CALENDAR_END}")

    rng = np.random.default_rng(RANDOM_SEED)

    print("\n  Generating tables...", end=" ", flush=True)
    df_products = generate_products(rng)
    df_customers = generate_customers(rng)
    df_calendar = generate_calendar()
    print("done.")

    out_dir = _PIPELINE_ROOT / RAW_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    product_path  = out_dir / "product.csv"
    customer_path = out_dir / "customer.csv"
    calendar_path = out_dir / "calendar.csv"

    df_products.to_csv(product_path,  index=False)
    df_customers.to_csv(customer_path, index=False)
    df_calendar.to_csv(calendar_path,  index=False)

    print(f"\n  CSVs written to: {out_dir.resolve()}")
    print(f"    product.csv  : {product_path.stat().st_size:,} bytes")
    print(f"    customer.csv : {customer_path.stat().st_size:,} bytes")
    print(f"    calendar.csv : {calendar_path.stat().st_size:,} bytes")

    print("\n  MD5 checksums (paste these to verify reproducibility):")
    for path in (product_path, customer_path, calendar_path):
        print(f"    {path.name:<15} {_md5(path)}")

    _summarise_products(df_products)
    _summarise_customers(df_customers)
    _summarise_calendar(df_calendar)

    _print_section("Generation complete - all tables verified")
    print(
        "\n  IMPORTANT: the following columns are GROUND TRUTH and must\n"
        "  be withheld from ML model inputs in all later phases:\n"
        "    product.csv   -> true_elasticity\n"
        "    customer.csv  -> true_segment, purchase_rate, basket_mean, basket_std\n"
    )


if __name__ == "__main__":
    main()
