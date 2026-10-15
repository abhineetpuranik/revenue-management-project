"""
API tests — covers all Phase 10a endpoints.

Tests are grouped by endpoint and cover:
  - Successful response shape and content
  - 404 for unknown IDs / labels
  - 400 for invalid pagination parameters
  - Ground-truth isolation (no true_elasticity / true_segment in any response)
  - Model loaded once at startup (not per request)
  - Forecast predictions match predict() for P001
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND  = str(Path(__file__).resolve().parent.parent)
_PIPELINE = str(Path(__file__).resolve().parent.parent.parent / "data-pipeline")
for p in (_BACKEND, _PIPELINE):
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Helpers ───────────────────────────────────────────────────────────────

FORBIDDEN_FIELDS = {"true_elasticity", "true_segment", "purchase_rate",
                    "basket_mean", "basket_std"}


def _check_no_ground_truth(body: str) -> None:
    """Fail if any ground-truth key appears anywhere in the response body."""
    for field in FORBIDDEN_FIELDS:
        assert field not in body, f"Ground-truth field '{field}' leaked into response"


def get_json(client, url: str):
    resp = client.get(url)
    return resp, resp.get_json()


# ── /api/health ───────────────────────────────────────────────────────────

class TestHealth:
    def test_ok(self, client):
        resp, data = get_json(client, "/api/health")
        assert resp.status_code == 200
        assert data == {"status": "ok"}


# ── /api/products ─────────────────────────────────────────────────────────

class TestProducts:
    def test_returns_list(self, client):
        resp, data = get_json(client, "/api/products")
        assert resp.status_code == 200
        assert isinstance(data, list)
        assert len(data) == 50

    def test_product_shape(self, client):
        _, data = get_json(client, "/api/products")
        p = data[0]
        assert set(p.keys()) == {"product_id", "category", "base_price"}
        assert isinstance(p["base_price"], float)

    def test_category_filter(self, client):
        _, data = get_json(client, "/api/products?category=Staples")
        assert len(data) == 12
        assert all(p["category"] == "Staples" for p in data)

    def test_category_filter_unknown_returns_empty(self, client):
        resp, data = get_json(client, "/api/products?category=Nonexistent")
        assert resp.status_code == 200
        assert data == []

    def test_no_ground_truth(self, client):
        resp = client.get("/api/products")
        _check_no_ground_truth(resp.get_data(as_text=True))


# ── /api/forecast/metrics ─────────────────────────────────────────────────

class TestForecastMetrics:
    def test_shape(self, client):
        resp, data = get_json(client, "/api/forecast/metrics")
        assert resp.status_code == 200
        assert "selected_model" in data
        assert "models" in data
        assert "XGBoost" in data["models"]
        assert "LinearRegression" in data["models"]

    def test_metric_keys(self, client):
        _, data = get_json(client, "/api/forecast/metrics")
        for model_data in data["models"].values():
            assert {"mae", "rmse", "mape"} == set(model_data.keys())

    def test_xgboost_selected(self, client):
        _, data = get_json(client, "/api/forecast/metrics")
        assert data["selected_model"] == "XGBoost"

    def test_no_ground_truth(self, client):
        resp = client.get("/api/forecast/metrics")
        _check_no_ground_truth(resp.get_data(as_text=True))


# ── /api/forecast/<product_id> ────────────────────────────────────────────

class TestForecast:
    def test_known_product_ok(self, client):
        resp, data = get_json(client, "/api/forecast/P001")
        assert resp.status_code == 200
        assert data["product_id"] == "P001"

    def test_response_shape(self, client):
        _, data = get_json(client, "/api/forecast/P001")
        assert "series" in data
        assert "model_type" in data
        assert "train_end" in data
        assert "test_start" in data
        assert "test_end" in data

    def test_series_has_history_and_test(self, client):
        _, data = get_json(client, "/api/forecast/P001")
        types = {row["row_type"] for row in data["series"]}
        assert "history" in types
        assert "test" in types

    def test_test_rows_have_predicted(self, client):
        _, data = get_json(client, "/api/forecast/P001")
        test_rows = [r for r in data["series"] if r["row_type"] == "test"]
        assert len(test_rows) == 8
        for row in test_rows:
            assert "predicted_units" in row
            assert isinstance(row["predicted_units"], int)
            assert row["predicted_units"] >= 0

    def test_history_rows_no_predicted(self, client):
        _, data = get_json(client, "/api/forecast/P001")
        hist = [r for r in data["series"] if r["row_type"] == "history"]
        assert len(hist) == 12   # FORECAST_HISTORY_WEEKS default
        for row in hist:
            assert "predicted_units" not in row

    def test_unknown_product_404(self, client):
        resp, data = get_json(client, "/api/forecast/ZZZZ")
        assert resp.status_code == 404
        assert "error" in data
        assert data["error"]["status"] == 404

    def test_predictions_match_model(self, client, app):
        """Predictions in the response must match model.predict() directly."""
        import numpy as np
        import pandas as pd
        from models.data_split import FEATURE_COLS

        _, data = get_json(client, "/api/forecast/P001")
        test_rows = [r for r in data["series"] if r["row_type"] == "test"]
        api_preds = [r["predicted_units"] for r in test_rows]

        engine   = app.config["DB_ENGINE"]
        model    = app.config["FORECAST_MODEL"]
        metadata = app.config["MODEL_METADATA"]

        from sqlalchemy import text
        sql = text("""
            SELECT * FROM forecast_features
            WHERE product_id = 'P001'
              AND week_start_date >= :ts
              AND week_start_date <= :te
            ORDER BY week_start_date
        """)
        with engine.connect() as conn:
            rows = conn.execute(sql, {
                "ts": metadata["test_start"],
                "te": metadata["test_end"],
            }).fetchall()

        df = pd.DataFrame([dict(r._mapping) for r in rows])
        X  = df[FEATURE_COLS].astype(float)
        direct_preds = np.round(model.predict(X, df["product_id"])).astype(int).tolist()

        assert api_preds == direct_preds

    def test_no_ground_truth(self, client):
        resp = client.get("/api/forecast/P001")
        _check_no_ground_truth(resp.get_data(as_text=True))


# ── /api/segments ─────────────────────────────────────────────────────────

class TestSegments:
    def test_ok(self, client):
        resp, data = get_json(client, "/api/segments")
        assert resp.status_code == 200

    def test_shape(self, client):
        _, data = get_json(client, "/api/segments")
        assert "n_clusters" in data
        assert "silhouette_score" in data
        assert "total_customers" in data
        assert "segments" in data
        assert data["n_clusters"] == 4
        assert data["total_customers"] == 1000

    def test_four_segments(self, client):
        _, data = get_json(client, "/api/segments")
        labels = {s["segment_label"] for s in data["segments"]}
        assert labels == {"high_value", "regular", "occasional", "at_risk"}

    def test_segment_shape(self, client):
        _, data = get_json(client, "/api/segments")
        s = data["segments"][0]
        required = {"segment_label", "customer_count", "share_pct", "revenue_share_pct",
                    "mean_recency_days", "median_recency_days",
                    "mean_frequency", "median_frequency",
                    "mean_monetary", "median_monetary"}
        assert required.issubset(set(s.keys()))

    def test_no_ground_truth(self, client):
        resp = client.get("/api/segments")
        _check_no_ground_truth(resp.get_data(as_text=True))


# ── /api/segments/customers ───────────────────────────────────────────────

class TestCustomersList:
    def test_default_page(self, client):
        resp, data = get_json(client, "/api/segments/customers")
        assert resp.status_code == 200
        assert data["page"] == 1
        assert len(data["customers"]) == data["page_size"]
        assert data["total"] == 1000

    def test_pagination_shape(self, client):
        _, data = get_json(client, "/api/segments/customers?page=2&page_size=10")
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert len(data["customers"]) == 10

    def test_segment_filter(self, client):
        _, data = get_json(client, "/api/segments/customers?segment=high_value&page_size=200")
        assert data["total"] == 160
        assert all(c["segment_label"] == "high_value" for c in data["customers"])

    def test_unknown_segment_404(self, client):
        resp, data = get_json(client, "/api/segments/customers?segment=vip")
        assert resp.status_code == 404
        assert data["error"]["status"] == 404

    def test_bad_page_400(self, client):
        resp, data = get_json(client, "/api/segments/customers?page=0")
        assert resp.status_code == 400
        assert data["error"]["status"] == 400

    def test_bad_page_size_str_400(self, client):
        resp, data = get_json(client, "/api/segments/customers?page_size=abc")
        assert resp.status_code == 400

    def test_page_size_too_large_400(self, client):
        resp, data = get_json(client, "/api/segments/customers?page_size=9999")
        assert resp.status_code == 400

    def test_customer_shape(self, client):
        _, data = get_json(client, "/api/segments/customers?page_size=1")
        c = data["customers"][0]
        assert set(c.keys()) == {"customer_id", "segment_label",
                                  "recency_days", "frequency", "monetary"}

    def test_no_ground_truth(self, client):
        resp = client.get("/api/segments/customers")
        _check_no_ground_truth(resp.get_data(as_text=True))


# ── /api/customers/<id>/segment ───────────────────────────────────────────

class TestCustomerSegment:
    def test_known_customer(self, client):
        resp, data = get_json(client, "/api/customers/C0001/segment")
        assert resp.status_code == 200
        assert data["customer_id"] == "C0001"

    def test_shape(self, client):
        _, data = get_json(client, "/api/customers/C0001/segment")
        assert set(data.keys()) == {"customer_id", "segment_label",
                                     "recency_days", "frequency", "monetary"}

    def test_rfm_types(self, client):
        _, data = get_json(client, "/api/customers/C0001/segment")
        assert isinstance(data["recency_days"], int)
        assert isinstance(data["frequency"], int)
        assert isinstance(data["monetary"], float)

    def test_unknown_customer_404(self, client):
        resp, data = get_json(client, "/api/customers/ZZZZ/segment")
        assert resp.status_code == 404
        assert data["error"]["status"] == 404

    def test_no_ground_truth(self, client):
        resp = client.get("/api/customers/C0001/segment")
        _check_no_ground_truth(resp.get_data(as_text=True))


# ── Model loaded once ─────────────────────────────────────────────────────

class TestModelLoadedOnce:
    def test_model_in_app_config(self, app):
        """The model object must exist in app.config — not None."""
        assert app.config["FORECAST_MODEL"] is not None
        assert app.config["MODEL_METADATA"] is not None

    def test_multiple_requests_same_model_object(self, client, app):
        """Two requests must use the identical model object (same id())."""
        model_id = id(app.config["FORECAST_MODEL"])
        client.get("/api/forecast/P001")
        client.get("/api/forecast/P002")
        assert id(app.config["FORECAST_MODEL"]) == model_id
