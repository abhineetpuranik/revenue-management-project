"""
Forecast service — no Flask-specific code.

Provides:
  get_all_products(engine, category=None)
      → list of dicts for GET /api/products

  get_forecast(engine, model, metadata, product_id, history_weeks)
      → dict with time series for GET /api/forecast/<product_id>

  get_forecast_metrics(metadata)
      → dict for GET /api/forecast/metrics

The forecast endpoint serves two kinds of rows per product:
  - "history": the most recent <history_weeks> training weeks — actual
    units_sold only, no model prediction (the model was trained on these).
  - "test": the held-out 8-week test window — both actual units_sold and
    the model prediction re-derived by calling predict() on the stored
    feature rows.

LIMITATION (reported as required by the spec):
    There is no next-week forecast endpoint in this phase because
    build_next_week_features() in pricing/next_week_features.py borrows
    calendar data from the previous year for weeks beyond 2024-12-31 and
    returns a single aggregate row — not the per-product feature DataFrame
    that predict() needs.  Serving next-week forecasts requires a dedicated
    feature-building path that is out of scope for Phase 10a.  The test-
    window predictions are a faithful representation of held-out accuracy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

# PYTHONPATH is already set by db.py (imported before this module in app.py).
# Guard in case service is imported in a test without going through db.py.
_PIPELINE_ROOT = str(Path(__file__).resolve().parent.parent.parent / "data-pipeline")
if _PIPELINE_ROOT not in sys.path:
    sys.path.insert(0, _PIPELINE_ROOT)

from models.data_split import FEATURE_COLS


# ── SQL ───────────────────────────────────────────────────────────────────

_PRODUCTS_SQL = text("""
    SELECT product_id, category, base_price
    FROM product
    ORDER BY product_id
""")

_PRODUCTS_FILTERED_SQL = text("""
    SELECT product_id, category, base_price
    FROM product
    WHERE category = :category
    ORDER BY product_id
""")

_PRODUCT_EXISTS_SQL = text("""
    SELECT COUNT(*) AS n FROM product WHERE product_id = :pid
""")

_FORECAST_ROWS_SQL = text("""
    SELECT
        product_id, iso_year, iso_week, week_start_date,
        lag_1_units, lag_2_units, lag_3_units,
        month, month_sin, month_cos,
        seasonal_factor_mean, festival_week,
        list_price_mean, price_change_pct,
        avg_discount_price, promo_days,
        avg_price, avg_discount,
        units_sold
    FROM forecast_features
    WHERE product_id = :pid
    ORDER BY week_start_date
""")


# ── Helpers ───────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convert a sqlalchemy Row / RowMapping to a plain dict."""
    return dict(row._mapping)


def _serialize_forecast_row(row: dict, row_type: str, predicted: int | None) -> dict:
    """Build a single entry in the time series list."""
    out: dict = {
        "week_start_date": str(row["week_start_date"])[:10],   # plain YYYY-MM-DD
        "iso_year":        int(row["iso_year"]),
        "iso_week":        int(row["iso_week"]),
        "actual_units":    int(row["units_sold"]),
        "row_type":        row_type,   # "history" or "test"
    }
    if predicted is not None:
        out["predicted_units"] = predicted
    return out


# ── Public service functions ──────────────────────────────────────────────

def get_all_products(engine, category: str | None = None) -> list[dict]:
    """Return all products, optionally filtered by category."""
    with engine.connect() as conn:
        if category:
            rows = conn.execute(_PRODUCTS_FILTERED_SQL, {"category": category}).fetchall()
        else:
            rows = conn.execute(_PRODUCTS_SQL).fetchall()
    return [
        {
            "product_id":  r.product_id,
            "category":    r.category,
            "base_price":  float(r.base_price),
        }
        for r in rows
    ]


def product_exists(engine, product_id: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(_PRODUCT_EXISTS_SQL, {"pid": product_id}).scalar()
    return int(result) > 0


def get_forecast(
    engine,
    model,
    metadata: dict,
    product_id: str,
    history_weeks: int,
) -> dict:
    """
    Return the forecast time series for one product.

    Parameters
    ----------
    engine        : SQLAlchemy engine
    model         : loaded production model (DemandXGBoost)
    metadata      : metadata.json dict from Phase 5
    product_id    : e.g. "P001"
    history_weeks : how many training weeks to include as context

    Returns
    -------
    dict with keys: product_id, model_type, train_end, test_start,
                    test_end, series (list of row dicts)
    """
    with engine.connect() as conn:
        rows = conn.execute(_FORECAST_ROWS_SQL, {"pid": product_id}).fetchall()

    if not rows:
        return {}

    df = pd.DataFrame([_row_to_dict(r) for r in rows])
    df["week_start_date"] = pd.to_datetime(df["week_start_date"])

    test_start = pd.Timestamp(metadata["test_start"])
    test_end   = pd.Timestamp(metadata["test_end"])

    # The partial final week (2024-12-30, only 2 days of data) was excluded
    # from model training by load_features() in data_split.py, but that row
    # is still present in the forecast_features MySQL table.  Apply the same
    # cutoff here so the API serves the same 8 test weeks the model was
    # evaluated on, not 9.
    test_df  = df[(df["week_start_date"] >= test_start) &
                  (df["week_start_date"] <= test_end)].copy()
    train_df = df[df["week_start_date"] <  test_start].copy()

    # Run predict() on the test rows — this is the held-out evaluation
    if not test_df.empty:
        X_test = test_df[FEATURE_COLS].astype(float)
        pids   = test_df["product_id"]
        preds  = model.predict(X_test, pids)
        test_df = test_df.copy()
        test_df["predicted"] = np.round(preds).astype(int)
    else:
        test_df["predicted"] = pd.array([], dtype="int64")

    # Take the most recent <history_weeks> rows from the training portion
    history_df = train_df.tail(history_weeks)

    series: list[dict] = []
    for _, row in history_df.iterrows():
        series.append(_serialize_forecast_row(row.to_dict(), "history", None))
    for _, row in test_df.iterrows():
        series.append(_serialize_forecast_row(row.to_dict(), "test",
                                              int(row["predicted"])))

    return {
        "product_id":  product_id,
        "model_type":  metadata.get("model_type", "unknown"),
        "train_end":   metadata["train_end"],
        "test_start":  metadata["test_start"],
        "test_end":    metadata["test_end"],
        "series":      series,
    }


def get_forecast_metrics(metadata: dict) -> dict:
    """Return model comparison metrics from the Phase 5 metadata file."""
    metrics = metadata.get("metrics", {})
    return {
        "selected_model":   metadata.get("model_type"),
        "selected_reason":  metadata.get("selected_reason"),
        "trained_at":       metadata.get("trained_at"),
        "train_start":      metadata.get("train_start"),
        "train_end":        metadata.get("train_end"),
        "test_start":       metadata.get("test_start"),
        "test_end":         metadata.get("test_end"),
        "n_train":          metadata.get("n_train"),
        "n_test":           metadata.get("n_test"),
        "models": {
            name: {
                "mae":  vals.get("mae"),
                "rmse": vals.get("rmse"),
                "mape": vals.get("mape"),
            }
            for name, vals in metrics.items()
        },
    }
