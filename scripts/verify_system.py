"""
verify_system.py -- read-only end-to-end verification script.

Prints PASS/FAIL for every check, then exits with code 0 (all pass)
or 1 (any failure).  Run from the REPO ROOT:

    python scripts/verify_system.py

The backend must be running separately for the API checks:
    cd backend && python app.py

Checks are grouped:
  A  Database table row counts match cleaned CSVs
  B  Ground-truth columns absent from application tables
  C  Model artifact loads correctly
  D  API endpoints respond with the documented shape   [SKIP if backend not running]
  E  Forecast predictions match the stored model       [requires DB]
  F  Pricing recommendations match the optimiser       [requires DB + backend]
  G  Segment customer counts sum to total
  H  No API response contains 'true_elasticity' or 'true_segment'
  I  Explanation endpoint degrades gracefully
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---- Repo layout ------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "data-pipeline"
BACKEND_BASE = "http://localhost:5000"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

# ---- Result tracking --------------------------------------------------------
_results: list[tuple[str, bool, str]] = []
_skipped: list[tuple[str, str]] = []


def _pass(check_id: str, detail: str = "") -> None:
    _results.append((check_id, True, detail))
    suffix = f"  -- {detail}" if detail else ""
    print(f"  [PASS] {check_id}{suffix}")


def _fail(check_id: str, detail: str = "") -> None:
    _results.append((check_id, False, detail))
    suffix = f"  -- {detail}" if detail else ""
    print(f"  [FAIL] {check_id}{suffix}")


def _skip(check_id: str, reason: str) -> None:
    _skipped.append((check_id, reason))
    print(f"  [SKIP] {check_id}  -- {reason}")


def _section(title: str) -> None:
    print("\n" + "-" * 66)
    print(f"  {title}")
    print("-" * 66)


def _get(url: str, *, timeout: int = 10) -> tuple[int, Any]:
    """HTTP GET -- returns (status_code, json_body). Returns (-1, None) on error."""
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.urlopen(url, timeout=timeout)
        return req.status, json.loads(req.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception:
        return -1, None


def _backend_running() -> bool:
    status, _ = _get(f"{BACKEND_BASE}/api/health")
    return status == 200


# ---- A: Database row counts -------------------------------------------------
def check_A_row_counts() -> None:
    _section("A -- Database row counts match cleaned CSVs")
    try:
        from dotenv import load_dotenv
        load_dotenv(PIPELINE_DIR / ".env")
        from etl.db_connection import get_engine
        from sqlalchemy import text
        import pandas as pd
    except Exception as e:
        _skip("A-db-import", f"Cannot import pipeline modules: {e}")
        return

    try:
        engine = get_engine()
    except Exception as e:
        _skip("A-db-connect", f"DB connection failed: {e}")
        return

    cleaned_dir = PIPELINE_DIR / "data" / "cleaned"

    # Core tables: check DB count > 0; compare to CSV if present
    core_tables = ["product", "customer", "calendar", "price", "stock", "sales"]
    with engine.connect() as conn:
        for table in core_tables:
            db_count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            csv_path = cleaned_dir / f"{table}.csv"
            if csv_path.exists():
                csv_count = len(pd.read_csv(csv_path))
                if db_count == csv_count:
                    _pass(f"A-{table}", f"{db_count:,} rows match CSV")
                else:
                    _fail(f"A-{table}", f"DB={db_count:,}  CSV={csv_count:,}")
            else:
                if db_count and db_count > 0:
                    _pass(f"A-{table}", f"{db_count:,} rows (no CSV to compare)")
                else:
                    _fail(f"A-{table}", "table is empty")

        # Derived tables -- just check non-empty
        for table in [
            "forecast_features", "product_elasticity",
            "customer_rfm_segment", "segment_summary",
            "pricing_candidates", "pricing_recommendation",
        ]:
            try:
                db_count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
                if db_count and db_count > 0:
                    _pass(f"A-{table}", f"{db_count:,} rows")
                else:
                    _fail(f"A-{table}", "table exists but is empty")
            except Exception as e:
                _fail(f"A-{table}", str(e))


# ---- B: Ground-truth isolation ----------------------------------------------
def check_B_ground_truth_isolation() -> None:
    _section("B -- Ground-truth columns absent from application tables")
    try:
        from dotenv import load_dotenv
        load_dotenv(PIPELINE_DIR / ".env")
        from etl.db_connection import get_engine
        from sqlalchemy import text
        import os
        db_name = os.getenv("DB_NAME", "revenue_management")
    except Exception as e:
        _skip("B-gt-isolation", f"Cannot import: {e}")
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            for tbl in ["product", "customer"]:
                cols = conn.execute(
                    text(
                        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :t"
                    ),
                    {"db": db_name, "t": tbl},
                ).fetchall()
                leaked = [r[0] for r in cols if r[0].startswith("true_")]
                if leaked:
                    _fail(f"B-{tbl}-no-gt-cols", f"Found: {leaked}")
                else:
                    _pass(f"B-{tbl}-no-gt-cols")
    except Exception as e:
        _fail("B-gt-isolation", str(e))


# ---- C: Model artifact ------------------------------------------------------
def check_C_model_artifact() -> None:
    _section("C -- Model artifact loads correctly")
    artifact_dir = PIPELINE_DIR / "models" / "artifacts"
    model_path = artifact_dir / "production_model.joblib"
    meta_path = artifact_dir / "metadata.json"

    for path in [model_path, meta_path]:
        if path.exists():
            _pass(f"C-exists-{path.name}", f"{path.stat().st_size:,} bytes")
        else:
            _fail(f"C-exists-{path.name}", f"Not found at {path}")
            return

    try:
        with open(meta_path) as f:
            meta = json.load(f)
        expected_keys = ["model_type", "metrics", "feature_cols", "n_train", "n_test"]
        missing = [k for k in expected_keys if k not in meta]
        if missing:
            _fail("C-metadata-keys", f"Missing: {missing}")
        else:
            _pass("C-metadata-keys",
                  f"model={meta['model_type']}  "
                  f"RMSE={meta['metrics']['XGBoost']['rmse']}")
    except Exception as e:
        _fail("C-metadata-load", str(e))
        return

    try:
        import joblib
        model = joblib.load(model_path)
        if hasattr(model, "predict"):
            _pass("C-model-loads", f"type={type(model).__name__}")
        else:
            _fail("C-model-loads", "Object has no .predict() method")
    except Exception as e:
        _fail("C-model-loads", str(e))


# ---- D: API endpoints -------------------------------------------------------
def check_D_api_endpoints() -> None:
    _section("D -- API endpoints respond with the documented shape")

    if not _backend_running():
        skip_list = [
            "D-health", "D-products", "D-products-filter",
            "D-forecast-metrics", "D-forecast-P001", "D-forecast-404",
            "D-segments", "D-segments-customers", "D-customer-C0001",
            "D-customer-404", "D-pricing-P001", "D-pricing-404",
            "D-pricing-recs", "D-pricing-expl-P001", "D-segment-expl-hv",
        ]
        for s in skip_list:
            _skip(s, "backend not running")
        return

    tests: list[tuple[str, str, int, list[str]]] = [
        ("D-health",
         "/api/health", 200, ["status"]),
        ("D-products",
         "/api/products", 200, []),
        ("D-products-filter",
         "/api/products?category=Staples", 200, []),
        ("D-forecast-metrics",
         "/api/forecast/metrics", 200,
         ["models", "selected_model", "n_train", "n_test"]),
        ("D-forecast-P001",
         "/api/forecast/P001", 200,
         ["product_id", "series"]),
        ("D-forecast-404",
         "/api/forecast/ZZZZ", 404, ["error"]),
        ("D-segments",
         "/api/segments", 200,
         ["total_customers", "n_clusters", "silhouette_score", "segments"]),
        ("D-segments-customers",
         "/api/segments/customers", 200,
         ["customers", "total", "page", "pages"]),
        ("D-customer-C0001",
         "/api/customers/C0001/segment", 200,
         ["customer_id", "segment_label"]),
        ("D-customer-404",
         "/api/customers/ZZZZ/segment", 404, ["error"]),
        ("D-pricing-P001",
         "/api/pricing/P001", 200,
         ["product_id", "recommendation_available", "current_price"]),
        ("D-pricing-404",
         "/api/pricing/ZZZZ", 404, ["error"]),
        ("D-pricing-recs",
         "/api/pricing/recommendations", 200,
         ["recommendations", "total", "page"]),
        ("D-pricing-expl-P001",
         "/api/pricing/P001/explanation", 200,
         ["explanation_available", "entity_type"]),
        ("D-segment-expl-hv",
         "/api/segments/high_value/explanation", 200,
         ["explanation_available"]),
    ]

    for check_id, url, expected_status, required_keys in tests:
        status, body = _get(f"{BACKEND_BASE}{url}")
        if status != expected_status:
            _fail(check_id, f"expected HTTP {expected_status}, got {status}")
            continue
        if body is None:
            _fail(check_id, "no JSON body")
            continue
        if isinstance(body, list):
            _pass(check_id, f"{len(body)} items")
            continue
        missing = [k for k in required_keys if k not in body]
        if missing:
            _fail(check_id, f"missing keys: {missing}")
        else:
            _pass(check_id)


# ---- E: Forecast predictions match stored model ----------------------------
def check_E_forecast_consistency() -> None:
    _section("E -- Forecast predictions match the stored model")
    try:
        from dotenv import load_dotenv
        load_dotenv(PIPELINE_DIR / ".env")
        from etl.db_connection import get_engine
        from sqlalchemy import text
        import numpy as np
        import pandas as pd
        import joblib
    except Exception as e:
        _skip("E-forecast-consistency", f"Cannot import: {e}")
        return

    try:
        meta_path = PIPELINE_DIR / "models" / "artifacts" / "metadata.json"
        model_path = PIPELINE_DIR / "models" / "artifacts" / "production_model.joblib"
        with open(meta_path) as f:
            meta = json.load(f)
        model = joblib.load(model_path)
        feature_cols = meta["feature_cols"]
        test_start = meta["test_start"]

        engine = get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(
                text(
                    "SELECT * FROM forecast_features "
                    "WHERE product_id='P001' AND week_start_date >= :ts "
                    "ORDER BY iso_year, iso_week LIMIT 8"
                ),
                conn,
                params={"ts": test_start},
            )
        if df.empty:
            _skip("E-forecast-model-predict", "No test rows for P001 in DB")
            return

        X = df[feature_cols].fillna(0)          # keep as DataFrame
        product_ids = df["product_id"]
        preds = model.predict(X, product_ids)
        preds_rounded = np.round(preds).astype(int)
        _pass("E-forecast-model-predict",
              f"P001 test-window predictions: {preds_rounded.tolist()}")

        if _backend_running():
            _, body = _get(f"{BACKEND_BASE}/api/forecast/P001")
            test_series = [
                r for r in body.get("series", [])
                if r["row_type"] == "test" and "predicted_units" in r
            ]
            api_preds = [r["predicted_units"] for r in test_series]
            if len(api_preds) == len(preds_rounded):
                mismatches = int(np.sum(np.abs(np.array(api_preds) - preds_rounded) > 1))
                if mismatches == 0:
                    _pass("E-forecast-api-match",
                          f"All {len(api_preds)} P001 predictions match API")
                else:
                    _fail("E-forecast-api-match",
                          f"{mismatches}/{len(api_preds)} mismatches")
            else:
                _fail("E-forecast-api-match",
                      f"API returned {len(api_preds)} rows, model gave {len(preds_rounded)}")
        else:
            _skip("E-forecast-api-match", "backend not running")
    except Exception as e:
        _fail("E-forecast-consistency", str(e))


# ---- F: Pricing recommendations match the optimiser ------------------------
def check_F_pricing_consistency() -> None:
    _section("F -- Pricing recommendations match the optimiser")
    if not _backend_running():
        _skip("F-pricing-api-match", "backend not running")
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(PIPELINE_DIR / ".env")
        from etl.db_connection import get_engine
        from sqlalchemy import text
        import pandas as pd
    except Exception as e:
        _skip("F-pricing-consistency", f"Cannot import: {e}")
        return

    sample_products = ["P001", "P023", "P027"]
    try:
        engine = get_engine()
        with engine.connect() as conn:
            db_recs = pd.read_sql(
                text(
                    "SELECT product_id, recommended_price FROM pricing_recommendation "
                    "WHERE product_id IN ('P001','P023','P027')"
                ),
                conn,
            )

        for pid in sample_products:
            _, body = _get(f"{BACKEND_BASE}/api/pricing/{pid}")
            if body is None or "recommended_price" not in body:
                _fail(f"F-{pid}", "API missing recommended_price")
                continue
            db_row = db_recs[db_recs["product_id"] == pid]
            if db_row.empty:
                _fail(f"F-{pid}", "Not in DB")
                continue
            api_price = round(float(body["recommended_price"]), 2)
            db_price = round(float(db_row["recommended_price"].iloc[0]), 2)
            if abs(api_price - db_price) < 0.01:
                _pass(f"F-{pid}", f"recommended_price={api_price}")
            else:
                _fail(f"F-{pid}", f"API={api_price}  DB={db_price}")
    except Exception as e:
        _fail("F-pricing-consistency", str(e))


# ---- G: Segment counts sum to total -----------------------------------------
def check_G_segment_totals() -> None:
    _section("G -- Segment customer counts sum to total customers")
    try:
        from dotenv import load_dotenv
        load_dotenv(PIPELINE_DIR / ".env")
        from etl.db_connection import get_engine
        from sqlalchemy import text
    except Exception as e:
        _skip("G-segment-totals", f"Cannot import: {e}")
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(
                text("SELECT COUNT(*) FROM customer")
            ).scalar()
            seg_total = conn.execute(
                text("SELECT SUM(customer_count) FROM segment_summary")
            ).scalar()
            assigned = conn.execute(
                text("SELECT COUNT(*) FROM customer_rfm_segment")
            ).scalar()

        if seg_total == total:
            _pass("G-summary-sums-to-total",
                  f"segment_summary total {seg_total:,} = customer count")
        else:
            _fail("G-summary-sums-to-total",
                  f"summary={seg_total}  customers={total}")

        if assigned == total:
            _pass("G-rfm-assigned-all",
                  f"All {assigned:,} customers assigned a segment")
        else:
            _fail("G-rfm-assigned-all",
                  f"rfm_segment rows={assigned}  customers={total}")

        if _backend_running():
            _, body = _get(f"{BACKEND_BASE}/api/segments")
            if body:
                api_total = body.get("total_customers", 0)
                api_sum = sum(s["customer_count"] for s in body.get("segments", []))
                if api_total == api_sum:
                    _pass("G-api-segment-totals",
                          f"API total={api_total:,} sums correctly")
                else:
                    _fail("G-api-segment-totals",
                          f"API total={api_total}  sum={api_sum}")
        else:
            _skip("G-api-segment-totals", "backend not running")
    except Exception as e:
        _fail("G-segment-totals", str(e))


# ---- H: No ground-truth strings in API responses ---------------------------
def check_H_no_ground_truth_in_api() -> None:
    _section("H -- No API response contains 'true_elasticity' or 'true_segment'")
    if not _backend_running():
        _skip("H-gt-in-api", "backend not running")
        return

    endpoints = [
        "/api/products",
        "/api/forecast/P001",
        "/api/segments",
        "/api/segments/customers?page_size=5",
        "/api/customers/C0001/segment",
        "/api/pricing/P001",
        "/api/pricing/recommendations?page_size=5",
        "/api/pricing/P001/explanation",
        "/api/segments/high_value/explanation",
    ]
    any_fail = False
    for url in endpoints:
        _, body = _get(f"{BACKEND_BASE}{url}")
        raw = json.dumps(body) if body else ""
        found = [s for s in ["true_elasticity", "true_segment"] if s in raw]
        if found:
            _fail(f"H{url}", f"Contains: {found}")
            any_fail = True
    if not any_fail:
        _pass("H-no-gt-strings",
              f"Checked {len(endpoints)} endpoints -- none contain ground-truth strings")


# ---- I: Explanation graceful degradation ------------------------------------
def check_I_explanation_graceful_degradation() -> None:
    _section("I -- Explanation endpoint degrades gracefully")
    if not _backend_running():
        _skip("I-explanation-degradation", "backend not running")
        return

    for pid in ["P001", "P027"]:
        status, body = _get(f"{BACKEND_BASE}/api/pricing/{pid}/explanation")
        if status != 200:
            _fail(f"I-expl-{pid}", f"HTTP {status}")
        elif "explanation_available" not in (body or {}):
            _fail(f"I-expl-{pid}", "missing 'explanation_available' key")
        else:
            avail = body["explanation_available"]
            _pass(f"I-expl-{pid}", f"explanation_available={avail}")

    for seg in ["high_value", "at_risk"]:
        status, body = _get(f"{BACKEND_BASE}/api/segments/{seg}/explanation")
        if status != 200:
            _fail(f"I-expl-seg-{seg}", f"HTTP {status}")
        elif "explanation_available" not in (body or {}):
            _fail(f"I-expl-seg-{seg}", "missing 'explanation_available' key")
        else:
            avail = body["explanation_available"]
            _pass(f"I-expl-seg-{seg}", f"explanation_available={avail}")


# ---- Main -------------------------------------------------------------------
def main() -> None:
    print("\n" + "=" * 66)
    print("  verify_system.py  --  end-to-end system verification")
    print("=" * 66)

    check_A_row_counts()
    check_B_ground_truth_isolation()
    check_C_model_artifact()
    check_D_api_endpoints()
    check_E_forecast_consistency()
    check_F_pricing_consistency()
    check_G_segment_totals()
    check_H_no_ground_truth_in_api()
    check_I_explanation_graceful_degradation()

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    skipped = len(_skipped)

    print("\n" + "=" * 66)
    print(f"  RESULT   PASS={passed}   FAIL={failed}   SKIP={skipped}")
    print("=" * 66)

    if _skipped:
        print("\n  Skipped checks (reason):")
        for check_id, reason in _skipped:
            print(f"    {check_id}  -- {reason}")

    if failed > 0:
        print("\n  Failed checks:")
        for check_id, ok, detail in _results:
            if not ok:
                print(f"    {check_id}  -- {detail}")
        print()
        sys.exit(1)

    print("\n  All executed checks passed.\n")
    sys.exit(0)


if __name__ == "__main__":
    # Force stdout to flush immediately (important on Windows)
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    main()
