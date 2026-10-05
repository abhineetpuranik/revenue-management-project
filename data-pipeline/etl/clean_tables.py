"""
Phase 2a orchestrator — loads raw CSVs, cleans each table, validates, and
writes cleaned CSVs to data/cleaned/.

Output directory : data/cleaned/  (relative to data-pipeline/ root)
Output files     : product.csv, customer.csv, calendar.csv,
                   price.csv, sales.csv, stock.csv

Columns are NOT renamed or restructured — Phase 2b (MySQL loading) does that.

Run
---
    cd data-pipeline
    python -m etl.clean_tables
"""

from __future__ import annotations

import hashlib
import logging
import sys
import time
from pathlib import Path

import pandas as pd

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.cleaning import (
    clean_calendar,
    clean_customer,
    clean_price,
    clean_product,
    clean_sales,
    clean_stock,
)
from etl.validation import run_validation

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _section(title: str) -> None:
    width = 66
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CLEANERS = {
    "product":  clean_product,
    "customer": clean_customer,
    "calendar": clean_calendar,
    "price":    clean_price,
    "sales":    clean_sales,
    "stock":    clean_stock,
}


def main() -> None:
    t_total = time.time()

    _section("Phase 2a -- ETL Data Cleaning")

    raw_dir     = _PIPELINE_ROOT / "data" / "raw"
    cleaned_dir = _PIPELINE_ROOT / "data" / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load raw tables
    # ------------------------------------------------------------------
    _section("Loading raw tables")
    raw_dfs: dict[str, pd.DataFrame] = {}
    raw_counts: dict[str, int] = {}

    for name in CLEANERS:
        path = raw_dir / f"{name}.csv"
        if not path.exists():
            logger.error("Raw file not found: %s — aborting.", path)
            sys.exit(1)
        df = pd.read_csv(path)
        raw_dfs[name] = df
        raw_counts[name] = len(df)
        print(f"  Loaded  {name}.csv  ({len(df):>10,} rows)")

    # ------------------------------------------------------------------
    # Clean each table
    # ------------------------------------------------------------------
    _section("Cleaning tables")
    cleaned_dfs: dict[str, pd.DataFrame] = {}

    for name, cleaner in CLEANERS.items():
        t0 = time.time()
        print(f"\n  [{name}]")
        cleaned = cleaner(raw_dfs[name])
        cleaned_dfs[name] = cleaned
        elapsed = time.time() - t0
        dropped = raw_counts[name] - len(cleaned)
        print(f"    {raw_counts[name]:>10,} rows in  ->  {len(cleaned):>10,} rows out  "
              f"(dropped {dropped})  {elapsed:.2f}s")

    # ------------------------------------------------------------------
    # Write cleaned CSVs
    # ------------------------------------------------------------------
    _section("Writing cleaned CSVs")
    out_paths: dict[str, Path] = {}

    for name, df in cleaned_dfs.items():
        out_path = cleaned_dir / f"{name}.csv"
        df.to_csv(out_path, index=False)
        out_paths[name] = out_path
        size_kb = out_path.stat().st_size / 1024
        print(f"  {name}.csv  ->  {out_path}  ({size_kb:,.1f} KB)")

    # ------------------------------------------------------------------
    # MD5 checksums
    # ------------------------------------------------------------------
    _section("MD5 checksums (cleaned files)")
    for name, path in out_paths.items():
        print(f"  {name}.csv  {_md5(path)}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    passed = run_validation(raw_counts, cleaned_dfs)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    elapsed_total = time.time() - t_total
    _section(f"Phase 2a complete  ({elapsed_total:.1f}s total)")
    print(f"  Output directory : {cleaned_dir.resolve()}")
    print(f"  Validation       : {'PASSED' if passed else 'FAILED — review output above'}")
    print()


if __name__ == "__main__":
    main()
