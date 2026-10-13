"""
Current product state — Phase 8a.

One row per product with everything the pricing rules need:

    product_id, category, base_price, unit_cost,
    current_price      — list price on the latest date in the price table
    price_date         — that date
    hist_min_price, hist_max_price — observed list-price range
    stock_level        — stock on the latest date in the stock table
    weekly_restock     — size of the most recent restock (restocks are weekly)
    elasticity, reliable_flag — from Phase 7 (product_elasticity)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from pricing.pricing_config import COST_RATIO

logger = logging.getLogger(__name__)

_STATE_SQL = """
SELECT
    pr.product_id                        AS product_id,
    pr.category                          AS category,
    CAST(pr.base_price AS DOUBLE)        AS base_price,
    CAST(cur.price AS DOUBLE)            AS current_price,
    cur.date                             AS price_date,
    CAST(rng.hist_min_price AS DOUBLE)   AS hist_min_price,
    CAST(rng.hist_max_price AS DOUBLE)   AS hist_max_price,
    st.stock_level                       AS stock_level,
    CAST(e.elasticity AS DOUBLE)         AS elasticity,
    e.reliable_flag                      AS reliable_flag
FROM product pr
JOIN price cur
  ON cur.product_id = pr.product_id
 AND cur.date = (SELECT MAX(p2.date) FROM price p2 WHERE p2.product_id = pr.product_id)
JOIN (SELECT product_id, MIN(price) AS hist_min_price, MAX(price) AS hist_max_price
      FROM price GROUP BY product_id) rng
  ON rng.product_id = pr.product_id
JOIN stock st
  ON st.product_id = pr.product_id
 AND st.date = (SELECT MAX(s2.date) FROM stock s2 WHERE s2.product_id = pr.product_id)
LEFT JOIN product_elasticity e
  ON e.product_id = pr.product_id
ORDER BY pr.product_id
"""

_RESTOCK_SQL = """
SELECT s.product_id, s.units_restocked AS weekly_restock
FROM stock s
JOIN (SELECT product_id, MAX(date) AS last_restock
      FROM stock WHERE units_restocked > 0 GROUP BY product_id) lr
  ON lr.product_id = s.product_id AND lr.last_restock = s.date
"""


def load_current_state(engine) -> pd.DataFrame:
    with engine.connect() as conn:
        state = pd.read_sql(text(_STATE_SQL), conn)
        restock = pd.read_sql(text(_RESTOCK_SQL), conn)

    state = state.merge(restock, on="product_id", how="left")
    state["weekly_restock"] = state["weekly_restock"].fillna(0).astype(int)
    state["price_date"] = pd.to_datetime(state["price_date"])

    missing_cost = sorted(set(state["category"]) - set(COST_RATIO))
    if missing_cost:
        raise KeyError(f"COST_RATIO has no entry for categories {missing_cost} — "
                       "add them to pricing/pricing_config.py")
    state["unit_cost"] = (state["base_price"] * state["category"].map(COST_RATIO)).round(4)

    if state["elasticity"].isna().any():
        missing = state.loc[state["elasticity"].isna(), "product_id"].tolist()
        raise RuntimeError(f"No Phase 7 elasticity for {missing}. "
                           "Run python -m pricing.estimate_elasticity first.")
    state["reliable_flag"] = state["reliable_flag"].astype(int)
    logger.info("Current state loaded for %d products (prices as of %s).",
                len(state), state["price_date"].max().date())
    return state
