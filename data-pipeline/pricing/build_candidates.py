"""
Phase 8a orchestrator — candidate prices + constraint filtering.

Steps
-----
1. Load each product's current state (current_state.load_current_state)
2. Generate the candidate grid (candidates.generate_candidates)
3. Apply MARGIN, MAX_CHANGE, PRICE_RANGE, ELASTICITY_UNRELIABLE (constraints.py)
4. Save ALL candidates, rejected ones included, to MySQL pricing_candidates
   (delete-and-reload, one transaction) and data/pricing/pricing_candidates.csv.
   Rejected rows are kept on purpose: the dashboard / viva can show WHY a
   price was ruled out.
5. Report pass/fail counts, rejections per reason, and products with no
   feasible price change.

The STOCK rule is not applied here — it needs predicted demand (Phase 8b).

Run
---
    cd data-pipeline
    python -m pricing.build_candidates
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine
from pricing import pricing_config as cfg
from pricing.candidates import generate_candidates
from pricing.constraints import (apply_constraints, check_elasticity_reliable, check_margin,
                                 check_max_change, check_price_range)
from pricing.current_state import load_current_state

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

TABLE_NAME = "pricing_candidates"
OUTPUT_DIR = _PIPELINE_ROOT / "data" / "pricing"
CSV_PATH = OUTPUT_DIR / "pricing_candidates.csv"

# Kept identical to database/schema.sql (section 4b).
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pricing_candidates (
    product_id       VARCHAR(10)    NOT NULL,
    step             INT            NOT NULL,
    candidate_price  DECIMAL(10,2)  NOT NULL,
    change_pct       DECIMAL(8,4)   NOT NULL,
    unit_cost        DECIMAL(10,4)  NOT NULL,
    margin_pct       DECIMAL(8,4)   NOT NULL,
    is_current       TINYINT(1)     NOT NULL,
    passes_all       TINYINT(1)     NOT NULL,
    failed_reasons   VARCHAR(100)   NOT NULL DEFAULT '',
    CONSTRAINT pk_pricing_candidates PRIMARY KEY (product_id, step),
    CONSTRAINT fk_candidates_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB
"""


def _section(title: str) -> None:
    print(f"\n{'=' * 66}\n  {title}\n{'=' * 66}")


def save_candidates(cands: pd.DataFrame, engine) -> None:
    out = cands.copy()
    out["change_pct"] = out["change_pct"].round(4)
    out["margin_pct"] = out["margin_pct"].round(4)
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(f"DELETE FROM {TABLE_NAME}"))
        out.to_sql(TABLE_NAME, conn, if_exists="append", index=False, method="multi",
                   chunksize=1000)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(CSV_PATH, index=False)
    logger.info("Saved %d candidates to %s and %s", len(out), TABLE_NAME, CSV_PATH)


def load_candidates(engine=None, passing_only: bool = False) -> pd.DataFrame:
    engine = engine or get_engine()
    where = " WHERE passes_all = 1" if passing_only else ""
    with engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT * FROM {TABLE_NAME}{where} ORDER BY product_id, step"), conn)
    for c in ["candidate_price", "change_pct", "unit_cost", "margin_pct"]:
        df[c] = df[c].astype(float)
    return df


def assert_passing_rows_valid(cands: pd.DataFrame, state: pd.DataFrame) -> None:
    """Independent re-check: no passing candidate may violate any rule."""
    df = cands[cands["passes_all"] == 1].merge(state, on="product_id", suffixes=("", "_s"))
    for r in df.itertuples(index=False):
        assert check_margin(r.candidate_price, r.unit_cost)[0], r
        assert check_max_change(r.candidate_price, r.current_price)[0], r
        assert check_price_range(r.candidate_price, r.hist_min_price, r.hist_max_price)[0], r
        assert check_elasticity_reliable(r.candidate_price, r.current_price, r.reliable_flag)[0], r


def main() -> None:
    t0 = time.time()
    _section("Phase 8a -- Candidate prices + constraints")
    print(f"  MIN_MARGIN_PCT       = {cfg.MIN_MARGIN_PCT:.0%}")
    print(f"  MAX_PRICE_CHANGE_PCT = ±{cfg.MAX_PRICE_CHANGE_PCT:.0%}")
    print(f"  PRICE_STEP_PCT       = {cfg.PRICE_STEP_PCT:.0%}")
    print(f"  ALLOW_EXTRAPOLATION  = {cfg.ALLOW_EXTRAPOLATION}")
    print("  ASSUMPTION: no cost data exists; unit_cost = base_price × COST_RATIO[category]")
    for cat, r in cfg.COST_RATIO.items():
        print(f"      {cat:<14} {r:.2f}")

    engine = get_engine()
    state = load_current_state(engine)
    cands = apply_constraints(generate_candidates(state), state)
    assert_passing_rows_valid(cands, state)

    _section("Summary")
    n, n_pass = len(cands), int(cands["passes_all"].sum())
    print(f"  Candidates generated : {n:,}  ({cands['product_id'].nunique()} products)")
    print(f"  Passing all rules    : {n_pass:,}")
    print(f"  Rejected             : {n - n_pass:,}")
    codes = cands.loc[cands["failed_reasons"] != "", "failed_reasons"].str.split(",").explode()
    print("\n  Rejections per reason code (a candidate can fail several)")
    print(codes.value_counts().to_string())

    cur = cands[cands["is_current"] == 1]
    bad_current = cur[cur["passes_all"] == 0]
    print(f"\n  Current price present for every product: "
          f"{cur['product_id'].nunique() == state['product_id'].nunique()}")
    if len(bad_current):
        print(f"  [FLAG] {len(bad_current)} product(s) whose CURRENT price already breaks a rule "
              "(Phase 8b will move them into compliance if a feasible price exists):")
        print(bad_current[["product_id", "candidate_price", "margin_pct", "failed_reasons"]]
              .to_string(index=False))

    per = (cands.groupby("product_id")
           .apply(lambda g: pd.Series({
               "passing": int(g["passes_all"].sum()),
               "feasible_changes": int(((g["passes_all"] == 1) & (g["is_current"] == 0)).sum()),
               "min_ok": g.loc[g["passes_all"] == 1, "change_pct"].min(),
               "max_ok": g.loc[g["passes_all"] == 1, "change_pct"].max()}),
               include_groups=False)
           .reset_index())
    print("\n  Per product: passing candidates and feasible change range")
    per[["passing", "feasible_changes"]] = per[["passing", "feasible_changes"]].astype(int)
    per["min_ok"] = per["min_ok"].map(lambda v: f"{v:+.2%}")
    per["max_ok"] = per["max_ok"].map(lambda v: f"{v:+.2%}")
    print(per.to_string(index=False))

    no_change = per[per["feasible_changes"] == 0]
    print(f"\n  Products with NO feasible price change: {len(no_change)}"
          + (f" -> {no_change['product_id'].tolist()}" if len(no_change) else ""))

    _section("Saving")
    save_candidates(cands, engine)
    _section(f"Phase 8a complete ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
