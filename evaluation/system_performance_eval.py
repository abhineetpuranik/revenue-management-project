"""System performance evaluation.

Measures training times (in-memory only — models not saved), API response
times (if backend is running), hardware info, and a parameter table from
all config files.

Outputs (evaluation/results/):
  system_training_times.json
  system_api_response_times.json
  system_hardware_info.json
  system_parameter_table.json
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from utils import (  # noqa: E402
    PIPELINE_ROOT,
    load_metadata,
    save_json,
)

logger = logging.getLogger(__name__)


def _insert_pipeline_root() -> None:
    root = str(PIPELINE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def run(args=None) -> None:
    """Run system performance evaluation and save outputs to evaluation/results/."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    _insert_pipeline_root()

    from models.data_split import load_features, time_split, TEST_WEEKS, FEATURE_COLS  # noqa: PLC0415

    # ------------------------------------------------------------------
    # 1. Training times (in-memory refit — models NOT saved)
    # ------------------------------------------------------------------
    logger.info("Timing model training (in-memory only) …")
    df = load_features()
    split = time_split(df, TEST_WEEKS)

    # XGBoost
    from models.xgboost_model import DemandXGBoost, XGBOOST_PARAMS  # noqa: PLC0415
    xgb_params = dict(XGBOOST_PARAMS)
    xgb_params["n_jobs"] = 1  # force single-thread to avoid OpenMP hang on some platforms
    xgb = DemandXGBoost(params=xgb_params)
    t0 = time.perf_counter()
    xgb.fit(split.X_train, split.y_train, split.train_df)
    xgb_train_sec = time.perf_counter() - t0
    logger.info("  XGBoost training: %.2fs", xgb_train_sec)
    del xgb  # discard — evaluation only

    # LinearRegression
    from models.baseline_model import DemandLinearRegression  # noqa: PLC0415
    lr = DemandLinearRegression(random_state=42)
    t0 = time.perf_counter()
    lr.fit(split.X_train, split.y_train, split.train_df)
    lr_train_sec = time.perf_counter() - t0
    logger.info("  LinearRegression training: %.2fs", lr_train_sec)
    del lr  # discard — evaluation only

    training_times = {
        "XGBoost_training_seconds": round(xgb_train_sec, 3),
        "LinearRegression_training_seconds": round(lr_train_sec, 3),
        "n_train_rows": split.n_train,
        "n_features": len(FEATURE_COLS),
        "note": "Models fitted in-memory for timing only.  No model artifact is saved.",
    }
    save_json(training_times, "system_training_times.json")

    # ------------------------------------------------------------------
    # 2. API response times (skip if backend not running)
    # ------------------------------------------------------------------
    logger.info("Checking API response times …")
    import urllib.request  # noqa: PLC0415
    import urllib.error    # noqa: PLC0415
    import numpy as np     # noqa: PLC0415

    endpoints = [
        ("GET", "http://localhost:5000/api/health"),
        ("GET", "http://localhost:5000/api/products"),
        ("GET", "http://localhost:5000/api/forecast/metrics"),
        ("GET", "http://localhost:5000/api/forecast/P001"),
        ("GET", "http://localhost:5000/api/segments"),
        ("GET", "http://localhost:5000/api/segments/customers"),
        ("GET", "http://localhost:5000/api/pricing"),
        ("GET", "http://localhost:5000/api/pricing/P001"),
        ("GET", "http://localhost:5000/api/explanations/pricing/P001"),
    ]
    api_results: dict = {}
    backend_available = False
    try:
        urllib.request.urlopen("http://localhost:5000/api/health", timeout=2)
        backend_available = True
    except Exception:
        pass

    if backend_available:
        for method, url in endpoints:
            times = []
            for _ in range(10):
                t0 = time.perf_counter()
                try:
                    urllib.request.urlopen(url, timeout=10)
                    elapsed = time.perf_counter() - t0
                    times.append(elapsed * 1000)
                except Exception:
                    times.append(None)
            valid = [t for t in times if t is not None]
            endpoint_key = url.replace("http://localhost:5000", "")
            if valid:
                api_results[endpoint_key] = {
                    "median_ms": round(float(np.median(valid)), 2),
                    "p95_ms": round(float(np.percentile(valid, 95)), 2),
                    "n_ok": len(valid),
                    "n_failed": 10 - len(valid),
                }
            else:
                api_results[endpoint_key] = {"result": "ALL_FAILED"}
    else:
        api_results["_note"] = "SKIP: backend not running at localhost:5000"
        logger.info("  Backend not running — API response time tests skipped.")

    save_json(api_results, "system_api_response_times.json")

    # ------------------------------------------------------------------
    # 3. Hardware info
    # ------------------------------------------------------------------
    import platform  # noqa: PLC0415
    import os        # noqa: PLC0415

    hw: dict = {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
    try:
        import psutil  # noqa: PLC0415
        vm = psutil.virtual_memory()
        hw["ram_total_gb"] = round(vm.total / (1024 ** 3), 1)
        hw["ram_available_gb"] = round(vm.available / (1024 ** 3), 1)
    except ImportError:
        hw["ram_total_gb"] = "psutil not installed"
    save_json(hw, "system_hardware_info.json")
    logger.info("  Hardware: %s %s, %d CPUs", hw["os"], hw["machine"], hw.get("cpu_count", 0))

    # ------------------------------------------------------------------
    # 4. Parameter table (reads from config files only — no DB)
    # ------------------------------------------------------------------
    meta = load_metadata()

    from data_generation.config import RANDOM_SEED as DG_RANDOM_SEED  # noqa: PLC0415
    from data_generation.config import NUM_PRODUCTS, NUM_CUSTOMERS     # noqa: PLC0415
    from pricing.pricing_config import MIN_MARGIN_PCT, MAX_PRICE_CHANGE_PCT, COST_RATIO  # noqa: PLC0415
    from segmentation.clustering import RANDOM_STATE, PRODUCTION_K     # noqa: PLC0415
    from models.data_split import TEST_WEEKS                           # noqa: PLC0415
    from models.evaluate import EPSILON                                # noqa: PLC0415

    parameter_table = {
        "data_generation": {
            "RANDOM_SEED": DG_RANDOM_SEED,
            "NUM_PRODUCTS": NUM_PRODUCTS,
            "NUM_CUSTOMERS": NUM_CUSTOMERS,
        },
        "pricing": {
            "MIN_MARGIN_PCT": MIN_MARGIN_PCT,
            "MAX_PRICE_CHANGE_PCT": MAX_PRICE_CHANGE_PCT,
            "COST_RATIO": COST_RATIO,
        },
        "segmentation": {
            "RANDOM_STATE": RANDOM_STATE,
            "PRODUCTION_K": PRODUCTION_K,
        },
        "forecasting": {
            "TEST_WEEKS": TEST_WEEKS,
            "EPSILON": EPSILON,
            "test_start": meta["test_start"],
            "test_end": meta["test_end"],
            "n_train": meta["n_train"],
            "n_test": meta["n_test"],
        },
        "model_metrics_from_metadata": meta.get("metrics", {}),
    }
    save_json(parameter_table, "system_parameter_table.json")
    logger.info("  Parameter table saved.")

    logger.info("System performance evaluation complete.")
    logger.info("  XGBoost train: %.2fs  |  LR train: %.2fs", xgb_train_sec, lr_train_sec)


if __name__ == "__main__":
    run()
