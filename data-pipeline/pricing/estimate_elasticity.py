from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine
from pricing.elasticity_data import build_weekly_panel, load_daily_panel, zero_sales_summary
from pricing.elasticity_model import fit_all

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

TABLE_NAME = "product_elasticity"
OUTPUT_DIR = _PIPELINE_ROOT / "data" / "elasticity"
CSV_PATH = OUTPUT_DIR / "product_elasticity.csv"

OUTPUT_COLUMNS = ["product_id", "category", "elasticity", "std_error", "ci_low", "ci_high",
                  "r_squared", "n_obs", "reliable_flag", "unreliable_reasons", "estimated_at"]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product_elasticity (
    product_id          VARCHAR(10)   NOT NULL,
    category            VARCHAR(30)   NOT NULL,
    elasticity          DECIMAL(8,4)  NULL,
    std_error           DECIMAL(8,4)  NULL,
    ci_low              DECIMAL(8,4)  NULL,
    ci_high             DECIMAL(8,4)  NULL,
    r_squared           DECIMAL(6,4)  NULL,
    n_obs               INT           NOT NULL,
    reliable_flag       TINYINT(1)    NOT NULL,
    unreliable_reasons  VARCHAR(100)  NOT NULL DEFAULT '',
    estimated_at        DATETIME      NOT NULL,
    CONSTRAINT pk_product_elasticity PRIMARY KEY (product_id),
    CONSTRAINT fk_elasticity_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB
"""


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def save_estimates(est: pd.DataFrame, engine) -> None:
    out = est[OUTPUT_COLUMNS].copy()
    out[["elasticity", "std_error", "ci_low", "ci_high", "r_squared"]] = (
        out[["elasticity", "std_error", "ci_low", "ci_high", "r_squared"]].round(4))

    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(f"DELETE FROM {TABLE_NAME}"))
        out.to_sql(TABLE_NAME, conn, if_exists="append", index=False, method="multi")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(CSV_PATH, index=False)
    logger.info("Saved %d rows to %s and %s", len(out), TABLE_NAME, CSV_PATH)


def load_elasticities(source: str = "db", engine=None) -> pd.DataFrame:
    if source == "csv":
        return pd.read_csv(CSV_PATH)
    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM {TABLE_NAME} ORDER BY product_id"), conn)


def get_elasticity(product_id: str, source: str = "db", engine=None) -> dict:
    df = load_elasticities(source=source, engine=engine)
    row = df[df["product_id"] == product_id]
    if row.empty:
        raise KeyError(f"No elasticity estimate for product_id={product_id!r}. "
                       "Run python -m pricing.estimate_elasticity first.")
    return row.iloc[0].to_dict()


def main() -> None:
    t0 = time.time()
    _section("Phase 7: Price elasticity estimation")
    engine = get_engine()

    daily = load_daily_panel(engine)

    _section("Zero-sales days per product (top 10)")
    zs = zero_sales_summary(daily)
    print(zs.head(10).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\n  Products with any zero-sales day: {(zs['zero_days'] > 0).sum()} / {len(zs)}")
    print("  Using weekly totals for every product.")

    weekly = build_weekly_panel(daily)
    zero_weeks = int((weekly["units_sold"] == 0).sum())
    print(f"  Weekly panel: {len(weekly):,} product-weeks, zero-sales weeks: {zero_weeks}")

    _section("Fitting log-log OLS per product")
    est = fit_all(weekly)
    est["estimated_at"] = datetime.now().replace(microsecond=0)
    print(est.drop(columns=["estimated_at"]).to_string(
        index=False, float_format=lambda v: f"{v:.4f}"))

    flagged = est[est["reliable_flag"] == 0]
    print(f"\n  Unreliable estimates: {len(flagged)}")
    if len(flagged):
        print(flagged[["product_id", "category", "elasticity", "ci_low", "ci_high",
                       "unreliable_reasons"]].to_string(index=False))
    print(f"  Negative estimates : {(est['elasticity'] < 0).sum()} / {len(est)}")

    _section("Saving")
    save_estimates(est, engine)

    _section("Validation against ground truth")
    from pricing.validate_elasticity import run_validation
    run_validation(est, daily=daily, weekly=weekly)

    _section(f"Phase 7 complete ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
