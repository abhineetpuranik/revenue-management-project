from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")
    logger.warning(msg)


def _err(msg: str) -> None:
    print(f"  [ERR]  {msg}")
    logger.error(msg)


def check_row_counts(
    raw_counts: dict[str, int],
    cleaned_dfs: dict[str, pd.DataFrame],
) -> bool:
    _section("1. Row counts - before vs after cleaning")
    all_ok = True
    print(f"  {'Table':<12} {'Raw':>10} {'Cleaned':>10} {'Dropped':>10}  Status")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10}  ------")
    for name, raw_n in raw_counts.items():
        cleaned_n = len(cleaned_dfs[name])
        dropped = raw_n - cleaned_n
        pct = 100 * dropped / raw_n if raw_n else 0
        status = "OK"
        if pct > 5:
            status = "WARN: >5% rows dropped"
            all_ok = False
        print(f"  {name:<12} {raw_n:>10,} {cleaned_n:>10,} {dropped:>10,}  {status}")
    return all_ok


def check_nulls(cleaned_dfs: dict[str, pd.DataFrame]) -> bool:
    _section("2. Null counts after cleaning")
    all_ok = True
    for name, df in cleaned_dfs.items():
        nulls = df.isnull().sum()
        total_nulls = nulls.sum()
        if total_nulls == 0:
            _ok(f"{name}: 0 nulls")
        else:
            _err(f"{name}: {total_nulls} null(s) remain - {nulls[nulls > 0].to_dict()}")
            all_ok = False
    return all_ok


def check_key_uniqueness(cleaned_dfs: dict[str, pd.DataFrame]) -> bool:
    _section("3. Key uniqueness")
    KEY_MAP: dict[str, list[str]] = {
        "product":  ["product_id"],
        "customer": ["customer_id"],
        "calendar": ["date"],
        "price":    ["product_id", "date"],
        "sales":    ["customer_id", "product_id", "date"],
        "stock":    ["product_id", "date"],
    }
    all_ok = True
    for name, keys in KEY_MAP.items():
        df = cleaned_dfs[name]
        dups = df.duplicated(subset=keys).sum()
        if dups == 0:
            _ok(f"{name}: no duplicate keys on {keys}")
        else:
            _err(f"{name}: {dups} duplicate key(s) on {keys} - cleaning failed to deduplicate")
            all_ok = False
    return all_ok


def check_referential_integrity(cleaned_dfs: dict[str, pd.DataFrame]) -> bool:
    _section("4. Referential integrity")

    product_ids  = set(cleaned_dfs["product"]["product_id"].dropna())
    customer_ids = set(cleaned_dfs["customer"]["customer_id"].dropna())
    calendar_dates = set(cleaned_dfs["calendar"]["date"].dropna())

    checks = [
        ("sales",  "product_id",  product_ids,   "product.product_id"),
        ("sales",  "customer_id", customer_ids,  "customer.customer_id"),
        ("sales",  "date",        calendar_dates, "calendar.date"),
        ("price",  "product_id",  product_ids,   "product.product_id"),
        ("price",  "date",        calendar_dates, "calendar.date"),
        ("stock",  "product_id",  product_ids,   "product.product_id"),
        ("stock",  "date",        calendar_dates, "calendar.date"),
    ]

    all_ok = True
    for table_name, col, ref_set, ref_label in checks:
        df = cleaned_dfs[table_name]
        orphans = ~df[col].isin(ref_set)
        n_orphans = orphans.sum()
        label = f"{table_name}.{col} -> {ref_label}"
        if n_orphans == 0:
            _ok(f"{label}:  0 violations")
        else:
            _err(
                f"{label}:  {n_orphans} orphan value(s) - "
                f"these IDs are not in the reference table. "
                f"Sample: {df.loc[orphans, col].unique()[:5].tolist()}"
            )
            all_ok = False

    return all_ok


def check_value_ranges(cleaned_dfs: dict[str, pd.DataFrame]) -> bool:
    _section("5. Business-rule range checks")
    all_ok = True

    bad = (cleaned_dfs["price"]["price"] <= 0).sum()
    if bad:
        _err(f"price.price: {bad} value(s) <= 0"); all_ok = False
    else:
        _ok("price.price: all values > 0")

    bad = (cleaned_dfs["sales"]["units_sold"] < 1).sum()
    if bad:
        _err(f"sales.units_sold: {bad} value(s) < 1"); all_ok = False
    else:
        _ok("sales.units_sold: all values >= 1")

    bad = (cleaned_dfs["sales"]["revenue"] < 0).sum()
    if bad:
        _err(f"sales.revenue: {bad} value(s) < 0"); all_ok = False
    else:
        _ok("sales.revenue: all values >= 0")

    bad = (cleaned_dfs["stock"]["stock_level"] < 0).sum()
    if bad:
        _err(f"stock.stock_level: {bad} value(s) < 0"); all_ok = False
    else:
        _ok("stock.stock_level: all values >= 0")

    bad = (cleaned_dfs["product"]["true_elasticity"] >= 0).sum()
    if bad:
        _err(f"product.true_elasticity: {bad} value(s) >= 0"); all_ok = False
    else:
        _ok("product.true_elasticity: all values < 0")

    for tbl in ("price", "sales"):
        bad = (
            (cleaned_dfs[tbl]["discount_pct"] < 0) |
            (cleaned_dfs[tbl]["discount_pct"] > 1)
        ).sum()
        if bad:
            _err(f"{tbl}.discount_pct: {bad} value(s) outside [0, 1]"); all_ok = False
        else:
            _ok(f"{tbl}.discount_pct: all values in [0, 1]")

    return all_ok


def run_validation(
    raw_counts: dict[str, int],
    cleaned_dfs: dict[str, pd.DataFrame],
) -> bool:
    _section("POST-CLEANING VALIDATION REPORT")

    results = [
        check_row_counts(raw_counts, cleaned_dfs),
        check_nulls(cleaned_dfs),
        check_key_uniqueness(cleaned_dfs),
        check_referential_integrity(cleaned_dfs),
        check_value_ranges(cleaned_dfs),
    ]

    all_passed = all(results)
    _section("VALIDATION SUMMARY")
    if all_passed:
        print("  ALL CHECKS PASSED - cleaned tables are consistent.\n")
    else:
        print("  ONE OR MORE CHECKS FAILED - review [WARN]/[ERR] lines above.\n")

    return all_passed


if __name__ == "__main__":
    if str(_PIPELINE_ROOT) not in sys.path:
        sys.path.insert(0, str(_PIPELINE_ROOT))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cleaned_dir = _PIPELINE_ROOT / "data" / "cleaned"
    raw_dir     = _PIPELINE_ROOT / "data" / "raw"

    TABLES = ["product", "customer", "calendar", "price", "sales", "stock"]

    missing = [t for t in TABLES if not (cleaned_dir / f"{t}.csv").exists()]
    if missing:
        print(f"ERROR: cleaned CSVs not found for: {missing}")
        print("       Run clean_tables.py first.")
        sys.exit(1)

    raw_counts: dict[str, int] = {}
    cleaned_dfs: dict[str, pd.DataFrame] = {}

    for t in TABLES:
        raw_counts[t] = len(pd.read_csv(raw_dir / f"{t}.csv"))
        df = pd.read_csv(cleaned_dir / f"{t}.csv")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        cleaned_dfs[t] = df

    run_validation(raw_counts, cleaned_dfs)
