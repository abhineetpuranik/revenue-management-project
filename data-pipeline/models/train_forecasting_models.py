"""
Phase 5 orchestrator — trains, evaluates, and saves the demand forecasting model.

Pipeline
--------
1.  Load forecast_features CSV (Phase 4 output).
2.  Time-based train / test split (last 8 weeks as test).
3.  Train LinearRegression baseline.
4.  Train XGBoost model.
5.  Evaluate both on test set (MAE, RMSE, MAPE).
6.  Compare and select production model.
7.  Save production model to  models/artifacts/production_model.joblib
8.  Save metadata JSON to     models/artifacts/metadata.json
9.  Print full report, per-product breakdown, and spot-check predictions.

Saved artefacts
---------------
production_model.joblib
    A fitted DemandXGBoost or DemandLinearRegression instance.
    Load with:
        from models.train_forecasting_models import load_production_model
        model = load_production_model()
        preds = model.predict(X_df, product_ids_series)

metadata.json
    {
        "model_type":    "XGBoost" | "LinearRegression",
        "selected_reason": "...",
        "train_start": "YYYY-MM-DD", "train_end": "YYYY-MM-DD",
        "test_start":  "YYYY-MM-DD", "test_end":  "YYYY-MM-DD",
        "n_train": int, "n_test": int,
        "metrics": {
            "XGBoost":          {"mae": ..., "rmse": ..., "mape": ...},
            "LinearRegression": {"mae": ..., "rmse": ..., "mape": ...}
        },
        "feature_cols": [...],
        "trained_at": "YYYY-MM-DD HH:MM:SS",
        "test_weeks": 8
    }

Run
---
    cd data-pipeline
    python -m models.train_forecasting_models
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from models.baseline_model import DemandLinearRegression
from models.data_split import FEATURE_COLS, TARGET_COL, load_features, time_split
from models.evaluate import ModelMetrics, compare_models, compute_metrics, evaluate_per_product
from models.xgboost_model import DemandXGBoost

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH    = ARTIFACTS_DIR / "production_model.joblib"
METADATA_PATH = ARTIFACTS_DIR / "metadata.json"


# ─────────────────────────────────────────────────────────────────────────────
# Public load interface (for Phase 8 / Phase 10)
# ─────────────────────────────────────────────────────────────────────────────

def load_production_model(path: Path = MODEL_PATH):
    """
    Load the saved production model.

    Returns a fitted model object with a .predict(X, product_ids) interface.
    Raises FileNotFoundError if the model hasn't been trained yet.

    Usage (Phase 8 / Phase 10):
        from models.train_forecasting_models import load_production_model
        model = load_production_model()
        # X must be a DataFrame with FEATURE_COLS columns
        preds = model.predict(X, product_ids)  # returns np.ndarray
    """
    import joblib
    if not Path(path).exists():
        raise FileNotFoundError(
            f"No trained model found at {path}.\n"
            "Run models/train_forecasting_models.py first."
        )
    return joblib.load(path)


def load_model_metadata(path: Path = METADATA_PATH) -> dict:
    """Load the JSON metadata file saved alongside the model artifact."""
    with open(path, "r") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    w = 66
    print(f"\n{'=' * w}\n  {title}\n{'=' * w}")


def _print_metrics(m: ModelMetrics) -> None:
    print(f"  {m}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    t_total = time.time()
    _section("Phase 5 — Demand Forecasting")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load features ─────────────────────────────────────────────────
    _section("1. Loading forecast features")
    df = load_features()
    print(f"  Rows: {len(df):,}  |  Products: {df['product_id'].nunique()}")
    print(f"  Date range: {df['week_start_date'].min().date()} "
          f"to {df['week_start_date'].max().date()}")
    print(f"  Feature cols ({len(FEATURE_COLS)}): {FEATURE_COLS}")

    # ── 2. Train / test split ────────────────────────────────────────────
    _section("2. Time-based train / test split")
    split = time_split(df)

    print(f"\n  TRAIN: {split.train_start}  to  {split.train_end}"
          f"  ({split.n_train:,} rows)")
    print(f"  TEST : {split.test_start}  to  {split.test_end}"
          f"  ({split.n_test:,} rows)")

    # Leakage confirmation
    assert split.train_end < split.test_start, "OVERLAP — split is leaking!"
    print(f"\n  [OK] No overlap: train ends {split.train_end}, "
          f"test starts {split.test_start}")

    # ── 3. Train Linear Regression ───────────────────────────────────────
    _section("3. Training Linear Regression baseline")
    t0 = time.time()
    lr_model = DemandLinearRegression(random_state=42)
    lr_model.fit(split.X_train, split.y_train, split.train_df)
    lr_elapsed = time.time() - t0
    print(f"  Trained in {lr_elapsed:.2f}s")

    lr_preds   = lr_model.predict(split.X_test, split.test_df["product_id"])
    lr_metrics = compute_metrics(split.y_test, lr_preds, model_name="LinearRegression")
    _print_metrics(lr_metrics)

    # ── 4. Train XGBoost ─────────────────────────────────────────────────
    _section("4. Training XGBoost")
    t0 = time.time()
    xgb_model = DemandXGBoost()
    xgb_model.fit(split.X_train, split.y_train, split.train_df)
    xgb_elapsed = time.time() - t0
    print(f"  Trained in {xgb_elapsed:.2f}s")

    xgb_preds   = xgb_model.predict(split.X_test, split.test_df["product_id"])
    xgb_metrics = compute_metrics(split.y_test, xgb_preds, model_name="XGBoost")
    _print_metrics(xgb_metrics)

    # ── 5. Compare and select ─────────────────────────────────────────────
    _section("5. Model comparison and selection")
    winner_metrics, loser_metrics, rationale = compare_models(
        lr_metrics, xgb_metrics, primary_metric="rmse"
    )
    print(f"\n  LinearRegression : {lr_metrics}")
    print(f"  XGBoost          : {xgb_metrics}")
    print(f"\n  Winner : {winner_metrics.model_name}")
    print(f"  Reason : {rationale}")

    # Per spec: explicitly flag if XGBoost does NOT win
    xgb_is_winner = (winner_metrics.model_name == "XGBoost")
    if not xgb_is_winner:
        print(
            "\n  [FLAG] XGBoost did NOT outperform LinearRegression on RMSE.\n"
            "         Selecting XGBoost anyway as the production model\n"
            "         per project design (expected to be better on new data).\n"
            "         Review hyperparameters if this persists across runs."
        )
        production_model = xgb_model
        selection_reason = (
            f"XGBoost selected by design despite RMSE={xgb_metrics.rmse:.3f} "
            f"> LR RMSE={lr_metrics.rmse:.3f}. Flagged for review."
        )
    else:
        production_model = xgb_model   # XGBoost is always the production model per spec
        selection_reason = rationale

    # ── 6. Per-product breakdown ─────────────────────────────────────────
    _section("6. Per-product RMSE (worst 10 products)")
    per_prod_xgb = evaluate_per_product(
        split.test_df, xgb_preds, model_name="XGBoost"
    )
    per_prod_lr  = evaluate_per_product(
        split.test_df, lr_preds, model_name="LinearRegression"
    )
    print("\n  XGBoost (sorted by RMSE, worst first):")
    print(per_prod_xgb.head(10)[["product_id", "mae", "rmse", "mape", "n_rows"]].to_string(index=False))

    # ── 7. Spot-check predictions ────────────────────────────────────────
    _section("7. Spot-check predictions (P001, last 8 test weeks)")
    p001_test = split.test_df[split.test_df["product_id"] == "P001"].copy()
    p001_test_idx = p001_test.index.tolist()
    # Map to positions in test_df
    test_positions = [split.test_df.index.get_loc(i) for i in p001_test_idx]

    p001_test["xgb_pred"]    = np.round(xgb_preds[test_positions]).astype(int)
    p001_test["lr_pred"]     = np.round(lr_preds[test_positions]).astype(int)
    p001_test["xgb_err"]     = p001_test["units_sold"] - p001_test["xgb_pred"]
    p001_test["lr_err"]      = p001_test["units_sold"] - p001_test["lr_pred"]

    cols_to_show = ["week_start_date", "units_sold", "xgb_pred", "xgb_err",
                    "lr_pred", "lr_err", "list_price_mean"]
    print(p001_test[cols_to_show].to_string(index=False))

    # ── 8. Save artifacts ────────────────────────────────────────────────
    _section("8. Saving model artifacts")
    production_model.save(MODEL_PATH)
    print(f"  Model saved    : {MODEL_PATH}")

    metadata = {
        "model_type":       production_model.name,
        "selected_reason":  selection_reason,
        "xgb_won":          xgb_is_winner,
        "train_start":      split.train_start,
        "train_end":        split.train_end,
        "test_start":       split.test_start,
        "test_end":         split.test_end,
        "n_train":          split.n_train,
        "n_test":           split.n_test,
        "metrics": {
            "XGBoost": {
                "mae":  round(xgb_metrics.mae,  4),
                "rmse": round(xgb_metrics.rmse, 4),
                "mape": round(xgb_metrics.mape, 4),
            },
            "LinearRegression": {
                "mae":  round(lr_metrics.mae,  4),
                "rmse": round(lr_metrics.rmse, 4),
                "mape": round(lr_metrics.mape, 4),
            },
        },
        "feature_cols":  FEATURE_COLS,
        "test_weeks":    8,
        "trained_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Metadata saved : {METADATA_PATH}")

    # ── 9. Final summary ─────────────────────────────────────────────────
    _section(f"Phase 5 complete  ({time.time() - t_total:.1f}s total)")
    print(f"\n  Production model : {production_model.name}")
    print(f"  Test RMSE        : {xgb_metrics.rmse:.3f}")
    print(f"  Test MAE         : {xgb_metrics.mae:.3f}")
    print(f"  Test MAPE        : {xgb_metrics.mape:.2f}%")
    print(f"  Artifact         : {MODEL_PATH}")
    print()


if __name__ == "__main__":
    main()
