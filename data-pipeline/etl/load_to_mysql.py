from __future__ import annotations

import hashlib
import logging
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine, get_gt_engine, test_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CLEANED_DIR = _PIPELINE_ROOT / "data" / "cleaned"


APP_COLUMNS: dict[str, list[str]] = {
    "product":  ["product_id", "category", "base_price", "base_demand"],
    "customer": ["customer_id"],
    "calendar": [
        "date", "year", "month", "weekday", "weekday_name",
        "is_weekend", "seasonal_factor", "weekday_factor",
        "combined_factor", "festival_flag",
    ],
    "price":    ["product_id", "date", "price", "is_promo", "discount_pct"],
    "stock":    ["product_id", "date", "stock_level", "units_restocked", "stockout_flag"],
    "sales":    [
        "sale_id", "customer_id", "product_id", "date",
        "units_sold", "price_at_sale", "discount_pct", "revenue",
    ],
}

GT_COLUMNS: dict[str, list[str]] = {
    "gt_product_elasticity": ["product_id", "true_elasticity"],
    "gt_customer_segment":   [
        "customer_id", "true_segment", "purchase_rate", "basket_mean", "basket_std"
    ],
}

GT_SOURCE_CSV: dict[str, str] = {
    "gt_product_elasticity": "product",
    "gt_customer_segment":   "customer",
}

APP_LOAD_ORDER = ["product", "customer", "calendar", "price", "stock", "sales"]
GT_LOAD_ORDER  = ["gt_product_elasticity", "gt_customer_segment"]


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def _load_table(
    table_name: str,
    df: pd.DataFrame,
    engine,
    *,
    schema_label: str = "",
    chunk_size: int = 5_000,
) -> int:
    rows = len(df)
    label = f"{schema_label}.{table_name}" if schema_label else table_name

    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    with engine.begin() as conn:
        df.to_sql(
            name=table_name,
            con=conn,
            if_exists="append",
            index=False,
            chunksize=chunk_size,
            method="multi",
        )

    logger.info("[%s] Loaded %d rows.", label, rows)
    return rows


def _verify_count(table_name: str, expected: int, engine) -> bool:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
        actual = result.scalar()
    match = actual == expected
    status = "OK" if match else f"MISMATCH - expected {expected:,}"
    print(f"  {table_name:<30} CSV={expected:>10,}  DB={actual:>10,}  [{status}]")
    return match


def main() -> None:
    t_start = time.time()
    _section("Phase 2b: MySQL Loader")

    app_engine = get_engine()
    gt_engine  = get_gt_engine()

    print("\n  Testing connections...")
    for label, eng in [("revenue_management", app_engine),
                       ("revenue_management_gt", gt_engine)]:
        ok = test_connection(eng)
        print(f"    {label:<30} {'OK' if ok else 'FAILED'}")
        if not ok:
            print("  Aborting - fix DB credentials / connection before rerunning.")
            sys.exit(1)

    _section("Loading cleaned CSVs")
    raw: dict[str, pd.DataFrame] = {}
    DATE_TABLES = {"calendar", "price", "stock", "sales"}
    for name in ["product", "customer", "calendar", "price", "stock", "sales"]:
        path = CLEANED_DIR / f"{name}.csv"
        df = pd.read_csv(path, parse_dates=["date"] if name in DATE_TABLES else False)
        raw[name] = df
        print(f"  {name}.csv  {len(df):>10,} rows")

    _section("Loading into revenue_management")
    app_counts: dict[str, int] = {}

    for table in APP_LOAD_ORDER:
        t0 = time.time()
        df_table = raw[table][APP_COLUMNS[table]].copy()

        for col in df_table.select_dtypes(include=["bool"]).columns:
            df_table[col] = df_table[col].astype(int)

        rows = _load_table(table, df_table, app_engine, schema_label="revenue_management")
        app_counts[table] = rows
        print(f"  {table:<12} {rows:>10,} rows  ({time.time()-t0:.2f}s)")

    _section("Loading into revenue_management_gt")
    gt_counts: dict[str, int] = {}

    for gt_table in GT_LOAD_ORDER:
        t0 = time.time()
        source_csv = GT_SOURCE_CSV[gt_table]
        df_gt = raw[source_csv][GT_COLUMNS[gt_table]].copy()
        rows = _load_table(gt_table, df_gt, gt_engine, schema_label="revenue_management_gt")
        gt_counts[gt_table] = rows
        print(f"  {gt_table:<30} {rows:>10,} rows  ({time.time()-t0:.2f}s)")

    _section("Row-count verification (CSV vs MySQL)")
    all_ok = True

    print(f"\n  {'Table':<30} {'CSV':>10}  {'DB':>10}  Status")
    print(f"  {'-'*30} {'-'*10}  {'-'*10}  ------")

    print("  -- revenue_management --")
    for table in APP_LOAD_ORDER:
        ok = _verify_count(table, app_counts[table], app_engine)
        all_ok = all_ok and ok

    print("  -- revenue_management_gt --")
    for gt_table in GT_LOAD_ORDER:
        ok = _verify_count(gt_table, gt_counts[gt_table], gt_engine)
        all_ok = all_ok and ok

    _section("Referential integrity spot-checks")
    ri_checks = [
        ("sales.product_id -> product",
         "SELECT COUNT(*) FROM sales s LEFT JOIN product p "
         "ON s.product_id = p.product_id WHERE p.product_id IS NULL"),
        ("sales.customer_id -> customer",
         "SELECT COUNT(*) FROM sales s LEFT JOIN customer c "
         "ON s.customer_id = c.customer_id WHERE c.customer_id IS NULL"),
        ("sales.date -> calendar",
         "SELECT COUNT(*) FROM sales s LEFT JOIN calendar cal "
         "ON s.date = cal.date WHERE cal.date IS NULL"),
        ("price.product_id -> product",
         "SELECT COUNT(*) FROM price p LEFT JOIN product pr "
         "ON p.product_id = pr.product_id WHERE pr.product_id IS NULL"),
        ("stock.product_id -> product",
         "SELECT COUNT(*) FROM stock st LEFT JOIN product pr "
         "ON st.product_id = pr.product_id WHERE pr.product_id IS NULL"),
    ]

    with app_engine.connect() as conn:
        for label, query in ri_checks:
            orphans = conn.execute(text(query)).scalar()
            status = "OK" if orphans == 0 else f"VIOLATION - {orphans} orphan rows"
            print(f"  {label:<40} [{status}]")
            if orphans:
                all_ok = False

    _section("Ground-truth isolation check")
    print("  Verifying application tables contain no true_* columns...")
    with app_engine.connect() as conn:
        for tbl in ["product", "customer"]:
            cols = conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl"
                ),
                {"db": "revenue_management", "tbl": tbl},
            ).fetchall()
            col_names = [r[0] for r in cols]
            leaked = [c for c in col_names if c.startswith("true_")]
            if leaked:
                print(f"  [ERR]  {tbl}: ground-truth column(s) present: {leaked}")
                all_ok = False
            else:
                print(f"  [OK]   {tbl}: no true_* columns in application schema")

    elapsed = time.time() - t_start
    _section(f"Load complete  ({elapsed:.1f}s total)")
    print(f"  Result : {'ALL CHECKS PASSED' if all_ok else 'ONE OR MORE CHECKS FAILED'}\n")

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
