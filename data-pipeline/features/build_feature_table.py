from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine
from features.calendar_features import load_calendar_features
from features.lag_features import add_lag_features
from features.price_features import load_price_features
from features.weekly_aggregation import load_weekly_aggregates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

FEATURES_DIR = _PIPELINE_ROOT / "data" / "features"
TABLE_NAME   = "forecast_features"

FINAL_COLUMNS = [
    "product_id", "iso_year", "iso_week", "week_start_date",
    "lag_1_units", "lag_2_units", "lag_3_units",
    "month", "month_sin", "month_cos",
    "seasonal_factor_mean", "festival_week",
    "list_price_mean", "price_change_pct",
    "avg_discount_price", "promo_days",
    "avg_price", "avg_discount",
    "units_sold",
]


def _run_leakage_test(df: pd.DataFrame, df_weekly_raw: pd.DataFrame) -> bool:
    _section("LEAKAGE TEST")

    lookup = df_weekly_raw.set_index(
        ["product_id", "iso_year", "iso_week"]
    )["units_sold"]

    all_pass = True
    sample_products = df["product_id"].unique()[:5]

    for pid in sample_products:
        prod_df = (
            df[df["product_id"] == pid]
            .sort_values(["iso_year", "iso_week"])
            .reset_index(drop=True)
        )
        prod_raw = (
            df_weekly_raw[df_weekly_raw["product_id"] == pid]
            .sort_values(["iso_year", "iso_week"])
            .reset_index(drop=True)
        )
        raw_lookup = prod_raw.set_index(["iso_year", "iso_week"])["units_sold"]

        for lag_n in [1, 2, 3]:
            col = f"lag_{lag_n}_units"
            mismatches = 0
            first_bad = None

            for _, row in prod_df.iterrows():
                yr, wk = int(row["iso_year"]), int(row["iso_week"])
                actual_val = row[col]

                raw_pos = prod_raw[
                    (prod_raw["iso_year"] == yr) & (prod_raw["iso_week"] == wk)
                ].index
                if len(raw_pos) == 0:
                    continue
                prior_pos = raw_pos[0] - lag_n
                if prior_pos < 0:
                    continue

                expected_val = prod_raw.loc[prior_pos, "units_sold"]

                if not np.isclose(actual_val, expected_val):
                    mismatches += 1
                    if first_bad is None:
                        first_bad = (yr, wk, actual_val, expected_val)

            n_checked = len(prod_df) - lag_n
            status = "PASS" if mismatches == 0 else "FAIL"
            if mismatches > 0:
                all_pass = False
                print(f"  [{status}] {pid} {col}: {mismatches} mismatch(es); "
                      f"first bad week ({first_bad[0]},w{first_bad[1]}): "
                      f"got {first_bad[2]:.1f} expected {first_bad[3]:.1f}")
            else:
                print(f"  [{status}] {pid} {col}: all {n_checked} checked rows correct")

    if all_pass:
        print("\n  All leakage checks PASSED - lag features are strictly backward-looking.")
    else:
        print("\n  LEAKAGE TEST FAILED - review lag computation in lag_features.py.")
    return all_pass


def _check_nulls(df: pd.DataFrame) -> None:
    _section("NULL CHECK (dropped rows excluded)")
    nulls = df.isnull().sum()
    if nulls.sum() == 0:
        print("  [OK] No nulls in final feature table.")
    else:
        print("  [WARN] Null counts:")
        print(nulls[nulls > 0].to_string())


def _spot_check_product(df: pd.DataFrame, product_id: str = "P001") -> None:
    _section(f"SPOT CHECK - {product_id} (first 8 weeks after dropping early rows)")
    cols = [
        "iso_year", "iso_week", "week_start_date",
        "units_sold", "lag_1_units", "lag_2_units", "lag_3_units",
        "list_price_mean", "price_change_pct",
        "month", "festival_week",
    ]
    sub = df[df["product_id"] == product_id].sort_values(
        ["iso_year", "iso_week"]
    ).head(8)[cols]
    print(sub.to_string(index=False))


_CREATE_FORECAST_FEATURES = f"""
CREATE TABLE IF NOT EXISTS revenue_management.{TABLE_NAME} (
    product_id           VARCHAR(10)   NOT NULL,
    iso_year             SMALLINT      NOT NULL,
    iso_week             TINYINT       NOT NULL,
    week_start_date      DATE          NOT NULL,
    lag_1_units          INT           NOT NULL,
    lag_2_units          INT           NOT NULL,
    lag_3_units          INT           NOT NULL,
    month                TINYINT       NOT NULL,
    month_sin            DOUBLE        NOT NULL,
    month_cos            DOUBLE        NOT NULL,
    seasonal_factor_mean DOUBLE        NOT NULL,
    festival_week        TINYINT       NOT NULL,
    list_price_mean      DOUBLE        NOT NULL,
    price_change_pct     DOUBLE,                -- NULL for first valid week (price series gap)
    avg_discount_price   DOUBLE        NOT NULL,
    promo_days           INT           NOT NULL,
    avg_price            DOUBLE        NOT NULL,
    avg_discount         DOUBLE        NOT NULL,
    units_sold           INT           NOT NULL,
    CONSTRAINT pk_{TABLE_NAME} PRIMARY KEY (product_id, iso_year, iso_week),
    INDEX idx_ff_product (product_id),
    INDEX idx_ff_week    (iso_year, iso_week)
) ENGINE=InnoDB;
"""


def _write_to_mysql(df: pd.DataFrame, engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text(f"DROP TABLE IF EXISTS revenue_management.{TABLE_NAME}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.execute(text(_CREATE_FORECAST_FEATURES))

    df_out = df.copy()
    df_out["week_start_date"] = df_out["week_start_date"].dt.strftime("%Y-%m-%d")

    with engine.begin() as conn:
        df_out.to_sql(
            name=TABLE_NAME,
            con=conn,
            schema="revenue_management",
            if_exists="append",
            index=False,
            chunksize=2_000,
            method="multi",
        )
    logger.info("Wrote %d rows to revenue_management.%s", len(df_out), TABLE_NAME)


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    t0_total = time.time()
    _section("Phase 4: Feature Engineering")

    engine = get_engine()

    _section("1. Weekly aggregation")
    t0 = time.time()
    df_weekly = load_weekly_aggregates(engine)
    print(f"  {len(df_weekly):,} product-week rows ({time.time()-t0:.1f}s)")
    print(f"  Columns: {list(df_weekly.columns)}")

    _section("2. Lag features")
    df_with_lags = add_lag_features(df_weekly)
    n_flagged = df_with_lags["insufficient_history"].sum()
    print(f"  Flagged {n_flagged} rows as insufficient_history (will be dropped)")

    _section("3. Calendar features")
    t0 = time.time()
    df_calendar = load_calendar_features(engine)
    print(f"  {len(df_calendar):,} week rows ({time.time()-t0:.1f}s)")
    print(f"  Columns: {list(df_calendar.columns)}")

    _section("4. Price features")
    t0 = time.time()
    df_price = load_price_features(engine)
    print(f"  {len(df_price):,} product-week rows ({time.time()-t0:.1f}s)")
    print(f"  Columns: {list(df_price.columns)}")

    _section("5. Joining feature groups")

    df = df_with_lags.copy()

    df = df.merge(
        df_calendar.drop(columns=["week_start_date"]),
        on=["iso_year", "iso_week"],
        how="left",
    )

    df = df.merge(
        df_price,
        on=["product_id", "iso_year", "iso_week"],
        how="left",
    )

    print(f"  Joined shape before dropping early rows: {df.shape}")

    df_clean = df[~df["insufficient_history"]].copy()
    df_clean = df_clean.drop(columns=["insufficient_history"])
    print(f"  Shape after dropping first-3-weeks per product: {df_clean.shape}")

    df_clean = df_clean[FINAL_COLUMNS].copy()

    for col in ["lag_1_units", "lag_2_units", "lag_3_units", "units_sold"]:
        df_clean[col] = df_clean[col].round(0).astype(int)
    df_clean["promo_days"]    = df_clean["promo_days"].astype(int)
    df_clean["festival_week"] = df_clean["festival_week"].astype(int)
    df_clean["month"]         = df_clean["month"].astype(int)

    df_clean = df_clean.sort_values(
        ["product_id", "iso_year", "iso_week"]
    ).reset_index(drop=True)

    _section("6. Writing outputs")

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = FEATURES_DIR / "forecast_features.csv"
    df_clean.to_csv(csv_path, index=False)
    print(f"  CSV written: {csv_path}  ({csv_path.stat().st_size / 1024:,.1f} KB)")

    t0 = time.time()
    _write_to_mysql(df_clean, engine)
    print(f"  MySQL write: {time.time()-t0:.1f}s")

    _section("7. Feature table summary")
    print(f"  Shape  : {df_clean.shape[0]:,} rows x {df_clean.shape[1]} columns")
    print(f"  Columns: {list(df_clean.columns)}")
    print(f"\n  Numeric summary (key columns):")
    key_summary = df_clean[
        ["units_sold", "lag_1_units", "lag_2_units", "lag_3_units",
         "list_price_mean", "price_change_pct", "seasonal_factor_mean"]
    ].describe().round(3)
    print(key_summary.to_string())

    _run_leakage_test(df_clean, df_weekly)

    _check_nulls(df_clean)

    _spot_check_product(df_clean, "P001")

    elapsed = time.time() - t0_total
    _section(f"Phase 4 complete  ({elapsed:.1f}s total)")
    print(f"  Rows  : {df_clean.shape[0]:,}")
    print(f"  Cols  : {df_clean.shape[1]}")
    print(f"  Target: units_sold (column {df_clean.shape[1]})\n")


if __name__ == "__main__":
    main()
