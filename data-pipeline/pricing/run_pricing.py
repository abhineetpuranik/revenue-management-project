"""
Phase 8b orchestrator — expected revenue + best-price selection.

Steps
-----
1. Current state (8a) and ALL candidates from pricing_candidates (8a)
2. Next-week feature rows (next_week_features) and the Phase 5 model
3. Baseline D0 at the current price; expected demand at every candidate via
   D0 × (p / p_current) ^ β (Phase 7 elasticity)
4. Stock cap, revenue, profit (revenue.score_candidates)
5. Best feasible price per product (optimizer.select_best) + binding constraint
6. Save pricing_recommendation (MySQL, delete-and-reload, one transaction) + CSV
7. Reports: distribution, corner-solution check, XGBoost-direct diagnostic,
   ground-truth sanity check (validate_pricing — the only GT reader here)

Run
---
    cd data-pipeline
    python -m pricing.build_candidates      # Phase 8a first
    python -m pricing.run_pricing

Public interface (Phase 9 / Phase 10)
-------------------------------------
    from pricing.run_pricing import get_recommendation, get_all_recommendations
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine
from pricing.build_candidates import load_candidates
from pricing.constraints import (check_elasticity_reliable, check_margin, check_max_change,
                                 check_price_range)
from pricing.current_state import load_current_state
from pricing.demand_response import (baseline_forecast, elasticity_scaled_demand,
                                     load_forecast_model, xgb_direct_demand)
from pricing.next_week_features import build_base_rows, rows_at_prices
from pricing.optimizer import binding_constraint, select_best
from pricing.revenue import available_stock, score_candidates

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

TABLE_NAME = "pricing_recommendation"
OUTPUT_DIR = _PIPELINE_ROOT / "data" / "pricing"
CSV_PATH = OUTPUT_DIR / "pricing_recommendation.csv"

OUTPUT_COLUMNS = [
    "product_id", "category", "current_price", "recommended_price", "change_pct", "elasticity",
    "baseline_demand", "expected_demand", "available_stock", "current_revenue", "expected_revenue",
    "revenue_change_pct", "unit_cost", "margin_pct", "expected_profit", "stock_limited",
    "binding_constraint", "reason_codes", "model_type", "forecast_week", "generated_at",
]

# Kept identical to database/schema.sql (section 4c).
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pricing_recommendation (
    product_id          VARCHAR(10)    NOT NULL,
    category            VARCHAR(30)    NOT NULL,
    current_price       DECIMAL(10,2)  NOT NULL,
    recommended_price   DECIMAL(10,2)  NOT NULL,
    change_pct          DECIMAL(8,4)   NOT NULL,
    elasticity          DECIMAL(8,4)   NOT NULL,
    baseline_demand     DECIMAL(12,2)  NOT NULL,
    expected_demand     DECIMAL(12,2)  NOT NULL,
    available_stock     INT            NOT NULL,
    current_revenue     DECIMAL(14,2)  NOT NULL,
    expected_revenue    DECIMAL(14,2)  NOT NULL,
    revenue_change_pct  DECIMAL(8,4)   NOT NULL,
    unit_cost           DECIMAL(10,4)  NOT NULL,
    margin_pct          DECIMAL(8,4)   NOT NULL,
    expected_profit     DECIMAL(14,2)  NOT NULL,
    stock_limited       TINYINT(1)     NOT NULL,
    binding_constraint  VARCHAR(30)    NOT NULL,
    reason_codes        VARCHAR(100)   NOT NULL DEFAULT '',
    model_type          VARCHAR(30)    NOT NULL,
    forecast_week       VARCHAR(10)    NOT NULL,
    generated_at        DATETIME       NOT NULL,
    CONSTRAINT pk_pricing_recommendation PRIMARY KEY (product_id),
    CONSTRAINT fk_recommendation_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB
"""


def _section(title: str) -> None:
    print(f"\n{'=' * 66}\n  {title}\n{'=' * 66}")


def build_scored_candidates(state, cands, base_rows, model, metadata):
    """All candidates (passing and rejected) with demand, revenue and the diagnostic."""
    cur_rows = rows_at_prices(base_rows, state[["product_id"]].assign(price=state["current_price"]))
    d0 = baseline_forecast(model, metadata, cur_rows)

    df = cands.merge(state[["product_id", "category", "current_price", "elasticity",
                            "stock_level", "weekly_restock"]], on="product_id")
    df["baseline_demand"] = df["product_id"].map(d0)
    df["available_stock"] = available_stock(df["stock_level"], df["weekly_restock"])
    df["expected_demand"] = elasticity_scaled_demand(df["baseline_demand"], df["candidate_price"],
                                                     df["current_price"], df["elasticity"])
    diag_rows = rows_at_prices(base_rows, df[["product_id"]].assign(price=df["candidate_price"]))
    df["xgb_direct_demand"] = xgb_direct_demand(model, metadata, diag_rows)
    return score_candidates(df), d0


def recommend(scored: pd.DataFrame, state: pd.DataFrame, model_type: str, forecast_week: str):
    recs = []
    st = state.set_index("product_id")
    for pid, g in scored.groupby("product_id", sort=True):
        cur = g[g["is_current"] == 1].iloc[0]
        best = select_best(g)
        reasons = []
        if cur["passes_all"] == 0:
            reasons.append(f"CURRENT_PRICE_BREAKS_{cur['failed_reasons'].split(',')[0]}")
        if best is None:
            best, binding = cur, "NO_FEASIBLE_PRICE"
            reasons.append("NO_FEASIBLE_PRICE")
        else:
            binding = binding_constraint(g, best)
        if st.loc[pid, "reliable_flag"] == 0:
            reasons.append("ELASTICITY_UNRELIABLE")
        cur_rev = float(cur["expected_revenue"])
        recs.append({
            "product_id": pid,
            "category": cur["category"],
            "current_price": float(cur["current_price"]),
            "recommended_price": float(best["candidate_price"]),
            "change_pct": float(best["change_pct"]),
            "elasticity": float(cur["elasticity"]),
            "baseline_demand": float(cur["baseline_demand"]),
            "expected_demand": float(best["expected_demand"]),
            "available_stock": int(best["available_stock"]),
            "current_revenue": cur_rev,
            "expected_revenue": float(best["expected_revenue"]),
            "revenue_change_pct": (float(best["expected_revenue"]) / cur_rev - 1.0) if cur_rev else 0.0,
            "unit_cost": float(best["unit_cost"]),
            "margin_pct": float(best["margin_pct"]),
            "expected_profit": float(best["expected_profit"]),
            "stock_limited": int(best["stock_limited"]),
            "binding_constraint": binding,
            "reason_codes": ",".join(reasons),
            "model_type": model_type,
            "forecast_week": forecast_week,
        })
    return pd.DataFrame(recs)


def assert_recommendations_valid(recs: pd.DataFrame, state: pd.DataFrame) -> None:
    """No recommendation may break an 8a rule (unless explicitly flagged NO_FEASIBLE_PRICE)."""
    m = recs.merge(state, on="product_id", suffixes=("", "_s"))
    for r in m.itertuples(index=False):
        if r.binding_constraint == "NO_FEASIBLE_PRICE":
            continue
        p = r.recommended_price
        assert check_margin(p, r.unit_cost)[0], r.product_id
        assert check_max_change(p, r.current_price)[0], r.product_id
        assert check_price_range(p, r.hist_min_price, r.hist_max_price)[0], r.product_id
        assert check_elasticity_reliable(p, r.current_price, r.reliable_flag)[0], r.product_id


def save_recommendations(recs: pd.DataFrame, engine) -> None:
    out = recs[OUTPUT_COLUMNS].copy()
    for c, d in [("change_pct", 4), ("elasticity", 4), ("baseline_demand", 2),
                 ("expected_demand", 2), ("current_revenue", 2), ("expected_revenue", 2),
                 ("revenue_change_pct", 4), ("unit_cost", 4), ("margin_pct", 4),
                 ("expected_profit", 2)]:
        out[c] = out[c].round(d)
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(f"DELETE FROM {TABLE_NAME}"))
        out.to_sql(TABLE_NAME, conn, if_exists="append", index=False, method="multi")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(CSV_PATH, index=False)
    logger.info("Saved %d recommendations to %s and %s", len(out), TABLE_NAME, CSV_PATH)


def get_all_recommendations(engine=None) -> pd.DataFrame:
    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM {TABLE_NAME} ORDER BY product_id"), conn)


def get_recommendation(product_id: str, engine=None) -> dict:
    df = get_all_recommendations(engine)
    row = df[df["product_id"] == product_id]
    if row.empty:
        raise KeyError(f"No recommendation for {product_id!r}. Run python -m pricing.run_pricing.")
    return row.iloc[0].to_dict()


def _corner_check(recs: pd.DataFrame) -> pd.DataFrame:
    """Revenue ∝ p^(1+β): inelastic (β > −1) should go UP, elastic (β < −1) DOWN."""
    r = recs.copy()
    r["expected_direction"] = np.where(r["elasticity"] > -1, "raise", "cut")
    r["direction"] = np.where(r["change_pct"] > 1e-9, "raise",
                              np.where(r["change_pct"] < -1e-9, "cut", "hold"))
    r["follows_pattern"] = r["direction"] == r["expected_direction"]
    return r


def main() -> None:
    t0 = time.time()
    _section("Phase 8b -- Expected revenue + best-price selection")
    engine = get_engine()

    state = load_current_state(engine)
    cands = load_candidates(engine)
    base_rows, info = build_base_rows(engine)
    model, metadata = load_forecast_model()
    model_type = str(metadata.get("model_type", type(model).__name__))
    print(f"  Forecast model         : {model_type}")
    print(f"  Forecast week          : {info['forecast_week']} (starts {info['forecast_week_start']})")
    print(f"  Lags from weeks ending : {info['last_complete_week_start']} (last complete week)")
    print(f"  Calendar days borrowed from the previous year: "
          f"{info['calendar_days_borrowed_from_previous_year']} of 7")
    print(f"  Week features          : month={info['month']}, "
          f"seasonal_factor_mean={info['seasonal_factor_mean']:.3f}, "
          f"festival_week={info['festival_week']}")

    scored, d0 = build_scored_candidates(state, cands, base_rows, model, metadata)
    recs = recommend(scored, state, model_type, info["forecast_week"])
    assert_recommendations_valid(recs, state)
    recs["generated_at"] = datetime.now().replace(microsecond=0)

    _section("Recommendations")
    show = recs[["product_id", "category", "elasticity", "current_price", "recommended_price",
                 "change_pct", "baseline_demand", "expected_demand", "revenue_change_pct",
                 "stock_limited", "binding_constraint", "reason_codes"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    _section("Summary")
    direction = np.sign(recs["change_pct"].round(9))
    print(f"  Raised : {(direction > 0).sum()}   Cut : {(direction < 0).sum()}   "
          f"Held : {(direction == 0).sum()}")
    print("\n  change_pct distribution")
    print((recs["change_pct"] * 100).describe().round(2).to_string())
    tot_cur, tot_new = recs["current_revenue"].sum(), recs["expected_revenue"].sum()
    print(f"\n  Total expected weekly revenue: {tot_cur:,.2f} -> {tot_new:,.2f} "
          f"({(tot_new / tot_cur - 1) * 100:+.2f} %)")
    print("\n  Binding constraint counts")
    print(recs["binding_constraint"].value_counts().to_string())

    _section("Corner-solution check (revenue ∝ p^(1+β))")
    cc = _corner_check(recs)
    print(f"  Follow the expected direction: {int(cc['follows_pattern'].sum())} / {len(cc)}")
    off = cc[~cc["follows_pattern"]]
    if len(off):
        print("  Exceptions (explained by the binding constraint / reason codes):")
        print(off[["product_id", "elasticity", "change_pct", "direction", "expected_direction",
                   "binding_constraint", "reason_codes"]]
              .to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    _section("Diagnostic: forecasting model swept directly vs. elasticity scaling")
    ok = scored[scored["passes_all"] == 1].copy()
    ok["rel_gap"] = (ok["xgb_direct_demand"] - ok["expected_demand"]).abs() / ok["expected_demand"]
    print(f"  Mean |gap| between the two demand estimates : {ok['rel_gap'].mean() * 100:.2f} %")
    print(f"  Largest gap                                 : {ok['rel_gap'].max() * 100:.2f} %")
    nonmono = 0
    for _, g in ok.groupby("product_id"):
        diffs = np.diff(g.sort_values("candidate_price")["xgb_direct_demand"].to_numpy())
        nonmono += int((diffs > 1e-9).any())
    print(f"  Products where direct model demand RISES with price somewhere: {nonmono} / "
          f"{ok['product_id'].nunique()}")

    _section("Saving")
    save_recommendations(recs, engine)

    _section("Ground-truth sanity check (decisions with estimated vs. true elasticity)")
    from pricing.validate_pricing import run_validation      # only GT reader in Phase 8
    run_validation(scored, recs)

    _section(f"Phase 8b complete ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
