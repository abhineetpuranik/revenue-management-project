"""Forecasting evaluation — REQ-7 to REQ-11.

Measures forecasting accuracy for XGBoost and LinearRegression on the Phase 5
held-out test window.  Never re-fits on test data.  Never modifies any file.

DB-dependent steps (per-category breakdown, leakage check) are skipped gracefully
if the database is not available; all CSV/model-based steps always run.

Outputs (evaluation/results/):
  forecasting_metrics.json
  forecasting_by_category.csv          (skipped if no DB)
  forecasting_per_product.csv
  forecasting_mape_zero_analysis.json
  forecasting_leakage_check.json       (skipped if no DB)
  forecasting_actual_vs_pred_best.png
  forecasting_actual_vs_pred_median.png
  forecasting_actual_vs_pred_worst.png
  forecasting_residual_histogram.png
  forecasting_feature_importance.png
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure evaluation/ is on the path so sibling imports work when called from
# the repo root via  `python evaluation/run_evaluation.py`.
_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from utils import (  # noqa: E402
    PIPELINE_ROOT,
    EVAL_RANDOM_SEED,
    get_engine,
    load_metadata,
    save_csv,
    save_fig,
    save_json,
)

logger = logging.getLogger(__name__)

EPSILON = 1e-8  # matches models/evaluate.py


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_pipeline_root() -> None:
    root = str(PIPELINE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _try_get_engine():
    """Return the app DB engine, or None if credentials are not available."""
    try:
        return get_engine()
    except Exception as exc:
        logger.warning("DB not available (%s) — DB-dependent steps will be skipped.", exc)
        return None


def _load_xgboost_model(split=None):
    """Load the production XGBoost model from disk.

    If loading fails (e.g. XGBoost version mismatch between the saved artifact
    and the installed library), refits a fresh DemandXGBoost in-memory using
    the same parameters as Phase 5.  The refitted model is never saved to disk.
    """
    import signal  # noqa: PLC0415
    import joblib  # noqa: PLC0415

    path = PIPELINE_ROOT / "models" / "artifacts" / "production_model.joblib"
    if not path.exists():
        raise FileNotFoundError(f"XGBoost model not found: {path}")

    load_exc = None
    try:
        def _timeout_handler(signum, frame):
            raise TimeoutError("joblib.load timed out — XGBoost version mismatch suspected")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(15)
        try:
            model = joblib.load(path)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        return model
    except Exception as exc:
        load_exc = exc

    logger.warning(
        "Could not load production_model.joblib (%s). "
        "Refitting DemandXGBoost in-memory with Phase 5 params "
        "(evaluation only — model will NOT be saved).",
        load_exc,
    )
    if split is None:
        raise RuntimeError(
            "Cannot refit XGBoost: split was not provided to _load_xgboost_model"
        ) from load_exc

    from models.xgboost_model import DemandXGBoost, XGBOOST_PARAMS  # noqa: PLC0415
    params = dict(XGBOOST_PARAMS)
    params["n_jobs"] = 1  # force single-thread to avoid OpenMP hang on some platforms
    xgb = DemandXGBoost(params=params)
    xgb.fit(split.X_train, split.y_train, split.train_df)
    return xgb


def _load_or_refit_lr(split):
    """Load LR model if saved; otherwise refit in-memory (never saved)."""
    import joblib  # noqa: PLC0415
    lr_path = PIPELINE_ROOT / "models" / "artifacts" / "lr_model.joblib"
    if lr_path.exists():
        try:
            logger.info("Loading LinearRegression from %s", lr_path)
            return joblib.load(lr_path)
        except Exception as exc:
            logger.warning("Could not load lr_model.joblib (%s) — refitting in-memory.", exc)

    logger.warning(
        "lr_model.joblib not found or unloadable — refitting DemandLinearRegression in-memory "
        "(for evaluation only; model will NOT be saved)."
    )
    from models.baseline_model import DemandLinearRegression  # noqa: PLC0415
    lr = DemandLinearRegression(random_state=EVAL_RANDOM_SEED)
    lr.fit(split.X_train, split.y_train, split.train_df)
    return lr


def _product_time_series(test_df: pd.DataFrame, y_pred: np.ndarray, product_id: str):
    """Return (actual, predicted, dates) series for one product over the test weeks."""
    mask = test_df["product_id"].values == product_id
    sub = test_df[mask].copy()
    sub["y_pred"] = y_pred[mask]
    sub = sub.sort_values("week_start_date")
    return sub["units_sold"].values, sub["y_pred"].values, sub["week_start_date"].values


def _plot_actual_vs_pred(test_df, y_pred, product_id, title_suffix, filename):
    """Plot actual vs. predicted weekly units for one product."""
    import matplotlib.pyplot as plt  # noqa: PLC0415
    actual, predicted, dates = _product_time_series(test_df, y_pred, product_id)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, actual, marker="o", label="Actual", linewidth=1.5)
    ax.plot(dates, predicted, marker="s", linestyle="--", label="Predicted (XGBoost)", linewidth=1.5)
    ax.set_title(f"Actual vs. Predicted — {product_id} ({title_suffix})")
    ax.set_xlabel("Week start date")
    ax.set_ylabel("Units sold")
    ax.legend()
    fig.tight_layout()
    save_fig(fig, filename)


def _get_feature_importance(xgb_model, feature_cols: list[str]) -> pd.DataFrame:
    """Extract feature importance from the DemandXGBoost wrapper."""
    booster = xgb_model.model  # XGBRegressor
    raw_imp = booster.feature_importances_
    # DemandXGBoost prepends product_id_encoded before the 14 feature cols
    names = ["product_id_encoded"] + list(feature_cols)
    if len(raw_imp) == len(names):
        return pd.DataFrame({"feature": names, "importance": raw_imp}).sort_values(
            "importance", ascending=False
        )
    return pd.DataFrame(
        {"feature": [f"f{i}" for i in range(len(raw_imp))], "importance": raw_imp}
    ).sort_values("importance", ascending=False)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(args=None) -> None:
    """Run all forecasting evaluations and save outputs to evaluation/results/."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    _insert_pipeline_root()

    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")  # non-interactive backend; safe for scripts
    import matplotlib.pyplot as plt  # noqa: PLC0415

    from models.data_split import load_features, time_split, FEATURE_COLS, TEST_WEEKS  # noqa: PLC0415
    from models.evaluate import compute_metrics, evaluate_per_product  # noqa: PLC0415

    # ------------------------------------------------------------------
    # 1. Load data and reproduce the train/test split
    # ------------------------------------------------------------------
    logger.info("Loading forecast features …")
    df = load_features()
    split = time_split(df, TEST_WEEKS)
    meta = load_metadata()

    logger.info(
        "Split: TRAIN %s–%s (%d rows) | TEST %s–%s (%d rows)",
        split.train_start, split.train_end, split.n_train,
        split.test_start, split.test_end, split.n_test,
    )

    # ------------------------------------------------------------------
    # 2. Load models (with in-memory fallback if artifact unloadable)
    # ------------------------------------------------------------------
    xgb_model = _load_xgboost_model(split=split)
    lr_model = _load_or_refit_lr(split)

    # ------------------------------------------------------------------
    # 3. Predict
    # ------------------------------------------------------------------
    y_pred_xgb = xgb_model.predict(split.X_test, split.test_df["product_id"])
    y_pred_lr = lr_model.predict(split.X_test, split.test_df["product_id"])

    # ------------------------------------------------------------------
    # 4. Overall metrics
    # ------------------------------------------------------------------
    m_xgb = compute_metrics(split.y_test, y_pred_xgb, "XGBoost")
    m_lr = compute_metrics(split.y_test, y_pred_lr, "LinearRegression")

    meta_xgb = meta["metrics"]["XGBoost"]
    meta_lr = meta["metrics"]["LinearRegression"]

    def _diff(computed: float, stored: float) -> dict:
        return {"computed": round(computed, 4), "stored": stored,
                "abs_diff": round(abs(computed - stored), 4)}

    metrics_comparison = {
        "XGBoost": {
            "mae": _diff(m_xgb.mae, meta_xgb["mae"]),
            "rmse": _diff(m_xgb.rmse, meta_xgb["rmse"]),
            "mape": _diff(m_xgb.mape, meta_xgb["mape"]),
        },
        "LinearRegression": {
            "mae": _diff(m_lr.mae, meta_lr["mae"]),
            "rmse": _diff(m_lr.rmse, meta_lr["rmse"]),
            "mape": _diff(m_lr.mape, meta_lr["mape"]),
        },
    }

    for model_name, diffs in metrics_comparison.items():
        for metric, d in diffs.items():
            if d["abs_diff"] > 0.01:
                logger.warning(
                    "%s %s mismatch: computed=%.4f stored=%.4f diff=%.4f "
                    "(model was refitted in-memory — artifact version mismatch)",
                    model_name, metric.upper(), d["computed"], d["stored"], d["abs_diff"],
                )

    # ------------------------------------------------------------------
    # 5. Per-category breakdown  (DB-dependent; skipped gracefully if no DB)
    # ------------------------------------------------------------------
    engine = _try_get_engine()
    products_df = pd.DataFrame(columns=["product_id", "category"])

    if engine is not None:
        try:
            from sqlalchemy import text  # noqa: PLC0415
            with engine.connect() as conn:
                products_df = pd.read_sql(
                    text("SELECT product_id, category FROM product ORDER BY product_id"), conn
                )
        except Exception as exc:
            logger.warning("Could not query product table (%s) — category breakdown skipped.", exc)

    test_df_cat = split.test_df.merge(products_df, on="product_id", how="left")
    test_df_cat["y_pred_xgb"] = y_pred_xgb
    test_df_cat["y_pred_lr"] = y_pred_lr

    if "category" in test_df_cat.columns and test_df_cat["category"].notna().any():
        def _cat_metrics(grp: pd.DataFrame) -> pd.Series:
            yt = grp["units_sold"].values.astype(float)
            rows: dict = {}
            for name, preds in [("xgb", grp["y_pred_xgb"].values),
                                  ("lr", grp["y_pred_lr"].values)]:
                err = yt - preds
                rows[f"mae_{name}"] = float(np.mean(np.abs(err)))
                rows[f"rmse_{name}"] = float(np.sqrt(np.mean(err ** 2)))
                rows[f"mape_{name}"] = float(np.mean(np.abs(err) / (np.abs(yt) + EPSILON)) * 100)
            rows["n_rows"] = len(grp)
            return pd.Series(rows)

        by_category = test_df_cat.groupby("category", sort=True).apply(
            _cat_metrics, include_groups=False
        ).reset_index()
        save_csv(by_category, "forecasting_by_category.csv")
    else:
        save_csv(pd.DataFrame({"note": ["DB not available — category data not loaded"]}),
                 "forecasting_by_category.csv")

    # ------------------------------------------------------------------
    # 6. Per-product distribution
    # ------------------------------------------------------------------
    pp_xgb = evaluate_per_product(split.test_df, y_pred_xgb, "XGBoost")
    pp_lr = evaluate_per_product(split.test_df, y_pred_lr, "LinearRegression")

    pp_merged = pp_xgb.rename(columns={
        "mae": "mae_xgb", "rmse": "rmse_xgb", "mape": "mape_xgb", "n_rows": "n_rows"
    })[["product_id", "mae_xgb", "rmse_xgb", "mape_xgb", "n_rows"]].merge(
        pp_lr[["product_id", "mae", "rmse", "mape"]].rename(
            columns={"mae": "mae_lr", "rmse": "rmse_lr", "mape": "mape_lr"}
        ),
        on="product_id", how="left",
    )
    if products_df is not None and len(products_df) > 0:
        pp_merged = pp_merged.merge(products_df, on="product_id", how="left")
    save_csv(pp_merged, "forecasting_per_product.csv")

    mape_xgb_vals = pp_xgb["mape"].values
    lr_indexed = pp_lr.set_index("product_id")
    mape_lr_vals = lr_indexed.reindex(pp_xgb["product_id"])["mape"].values
    valid = ~np.isnan(mape_lr_vals)
    xgb_wins_share = float((mape_xgb_vals[valid] < mape_lr_vals[valid]).mean()) if valid.any() else 0.0

    distribution = {
        "XGBoost_MAPE_median": float(np.median(mape_xgb_vals)),
        "XGBoost_MAPE_p90": float(np.percentile(mape_xgb_vals, 90)),
        "XGBoost_MAPE_worst10": pp_xgb.nlargest(10, "mape")[
            ["product_id", "mape"]
        ].to_dict(orient="records"),
        "share_products_xgb_beats_lr": round(xgb_wins_share, 4),
    }

    # ------------------------------------------------------------------
    # 7. MAPE zero-actual analysis
    # ------------------------------------------------------------------
    y_test_arr = split.y_test.values.astype(float)
    zero_mask = y_test_arr == 0
    small_mask = (y_test_arr > 0) & (y_test_arr <= 1)
    errors_xgb = np.abs(y_test_arr - y_pred_xgb)

    def _safe_mean(arr):
        return float(arr.mean()) if len(arr) > 0 else None

    mape_zero_analysis = {
        "n_zero_actuals": int(zero_mask.sum()),
        "n_small_actuals_le1": int(small_mask.sum()),
        "n_normal_actuals": int((~zero_mask & ~small_mask).sum()),
        "mean_mape_zero_rows": _safe_mean(
            errors_xgb[zero_mask] / (np.abs(y_test_arr[zero_mask]) + EPSILON) * 100),
        "mean_mape_small_rows": _safe_mean(
            errors_xgb[small_mask] / (np.abs(y_test_arr[small_mask]) + EPSILON) * 100),
        "mean_mape_normal_rows": _safe_mean(
            errors_xgb[~zero_mask & ~small_mask]
            / (np.abs(y_test_arr[~zero_mask & ~small_mask]) + EPSILON) * 100),
        "epsilon_used": EPSILON,
        "note": (
            "EPSILON=1e-8 prevents division-by-zero but inflates MAPE when y_true is 0 or very "
            "small.  Zero actuals produce MAPE ≈ |y_pred| / EPSILON which can be very large.  "
            "The overall MAPE is computed identically to Phase 5 so numbers are directly "
            "comparable to metadata."
        ),
    }
    save_json(mape_zero_analysis, "forecasting_mape_zero_analysis.json")

    # ------------------------------------------------------------------
    # 8. Leakage check (DB-dependent; skipped if no DB)
    # ------------------------------------------------------------------
    leakage_result: dict = {}
    if engine is not None:
        try:
            from features.weekly_aggregation import load_weekly_aggregates  # noqa: PLC0415
            from features.build_feature_table import _run_leakage_test  # noqa: PLC0415
            logger.info("Re-running Phase 4 leakage check …")
            df_weekly = load_weekly_aggregates(engine)
            leakage_pass = _run_leakage_test(df, df_weekly)
            leakage_result = {
                "result": "PASS" if leakage_pass else "FAIL",
                "description": (
                    "Checked lag_1_units, lag_2_units, lag_3_units for the first 5 products. "
                    "Each lag column must equal the units_sold from the correct prior week."
                ),
                "train_end": split.train_end,
                "test_start": split.test_start,
                "train_test_no_overlap": split.train_end < split.test_start,
            }
        except Exception as exc:
            logger.warning("Leakage check failed (%s).", exc)
            leakage_result = {"result": "ERROR", "error": str(exc)}
    else:
        # Still record the structural leakage result from the split assertion
        leakage_result = {
            "result": "PASS_STRUCTURAL",
            "description": (
                "Full lag feature check skipped (DB unavailable). "
                "The time_split() assertion already verifies train_end < test_start "
                "(no temporal overlap between train and test sets)."
            ),
            "train_end": split.train_end,
            "test_start": split.test_start,
            "train_test_no_overlap": split.train_end < split.test_start,
        }
    save_json(leakage_result, "forecasting_leakage_check.json")

    # ------------------------------------------------------------------
    # 9. Figures
    # ------------------------------------------------------------------
    pp_sorted = pp_xgb.sort_values("mape").reset_index(drop=True)
    best_pid = pp_sorted.iloc[0]["product_id"]
    median_pid = pp_sorted.iloc[len(pp_sorted) // 2]["product_id"]
    worst_pid = pp_sorted.iloc[-1]["product_id"]

    _plot_actual_vs_pred(split.test_df, y_pred_xgb, best_pid,
                         "best MAPE", "forecasting_actual_vs_pred_best.png")
    _plot_actual_vs_pred(split.test_df, y_pred_xgb, median_pid,
                         "median MAPE", "forecasting_actual_vs_pred_median.png")
    _plot_actual_vs_pred(split.test_df, y_pred_xgb, worst_pid,
                         "worst MAPE", "forecasting_actual_vs_pred_worst.png")

    # Residual histogram
    residuals = split.y_test.values.astype(float) - y_pred_xgb
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(residuals, bins=40, edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1.2, label="Zero error")
    ax.set_title("XGBoost Forecast Residuals (actual − predicted, test set)")
    ax.set_xlabel("Residual (units)")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    save_fig(fig, "forecasting_residual_histogram.png")

    # Feature importance
    imp_df = _get_feature_importance(xgb_model, FEATURE_COLS)
    top_n = min(15, len(imp_df))
    fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.35)))
    ax.barh(imp_df["feature"].iloc[:top_n][::-1],
            imp_df["importance"].iloc[:top_n][::-1])
    ax.set_title("XGBoost Feature Importance (gain, top features)")
    ax.set_xlabel("Importance")
    fig.tight_layout()
    save_fig(fig, "forecasting_feature_importance.png")

    # ------------------------------------------------------------------
    # 10. Save master metrics JSON
    # ------------------------------------------------------------------
    forecasting_metrics = {
        "XGBoost": {
            "mae": round(m_xgb.mae, 4),
            "rmse": round(m_xgb.rmse, 4),
            "mape": round(m_xgb.mape, 4),
        },
        "LinearRegression": {
            "mae": round(m_lr.mae, 4),
            "rmse": round(m_lr.rmse, 4),
            "mape": round(m_lr.mape, 4),
        },
        "metadata_comparison": metrics_comparison,
        "per_product_distribution": distribution,
        "split": {
            "train_start": split.train_start,
            "train_end": split.train_end,
            "test_start": split.test_start,
            "test_end": split.test_end,
            "n_train": split.n_train,
            "n_test": split.n_test,
        },
        "leakage_check": leakage_result.get("result", "UNKNOWN"),
    }
    save_json(forecasting_metrics, "forecasting_metrics.json")

    logger.info("Forecasting evaluation complete.")
    logger.info("  XGBoost   — MAE=%.4f  RMSE=%.4f  MAPE=%.4f%%",
                m_xgb.mae, m_xgb.rmse, m_xgb.mape)
    logger.info("  LinearReg — MAE=%.4f  RMSE=%.4f  MAPE=%.4f%%",
                m_lr.mae, m_lr.rmse, m_lr.mape)
    logger.info("  XGBoost beats LR on MAPE for %.1f%% of products",
                distribution["share_products_xgb_beats_lr"] * 100)
    logger.info("  Leakage check: %s", leakage_result.get("result", "UNKNOWN"))


if __name__ == "__main__":
    run()
