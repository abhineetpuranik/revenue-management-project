"""
Tests for Phase 10b pricing endpoints.

GET /api/pricing/<product_id>
GET /api/pricing/recommendations
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND  = str(Path(__file__).resolve().parent.parent)
_PIPELINE = str(Path(__file__).resolve().parent.parent.parent / "data-pipeline")
for p in (_BACKEND, _PIPELINE):
    if p not in sys.path:
        sys.path.insert(0, p)

FORBIDDEN = {"true_elasticity", "true_segment", "purchase_rate",
             "basket_mean", "basket_std"}

REQUIRED_FIELDS = {
    "product_id", "category", "recommendation_available",
    "current_price", "recommended_price", "change_pct",
    "current_revenue", "expected_revenue", "revenue_change_pct",
    "revenue_change_abs", "elasticity", "binding_constraint",
    "constraints_applied", "model_type", "forecast_week",
}


def get_json(client, url):
    resp = client.get(url)
    return resp, resp.get_json()


def _no_gt(body: str) -> None:
    for f in FORBIDDEN:
        assert f not in body, f"Ground-truth field '{f}' leaked: {body[:200]}"


# ── Single product ────────────────────────────────────────────────────────

class TestSingleRecommendation:
    def test_known_product_200(self, client):
        resp, data = get_json(client, "/api/pricing/P001")
        assert resp.status_code == 200

    def test_required_fields_present(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        assert REQUIRED_FIELDS.issubset(set(data.keys())), \
            f"Missing: {REQUIRED_FIELDS - set(data.keys())}"

    def test_recommendation_available_true_for_normal_product(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        assert data["recommendation_available"] is True

    def test_numeric_types(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        assert isinstance(data["current_price"],     float)
        assert isinstance(data["recommended_price"], float)
        assert isinstance(data["change_pct"],        float)
        assert isinstance(data["revenue_change_pct"], float)
        assert isinstance(data["revenue_change_abs"], float)
        assert isinstance(data["elasticity"],         float)

    def test_elasticity_negative(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        assert data["elasticity"] < 0, "All products should have negative elasticity"

    def test_constraints_applied_shape(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        c = data["constraints_applied"]
        assert "min_margin_pct" in c
        assert "max_price_change_pct" in c

    def test_revenue_change_abs_consistent(self, client):
        """revenue_change_abs must equal expected_revenue - current_revenue."""
        _, data = get_json(client, "/api/pricing/P001")
        expected_abs = round(data["expected_revenue"] - data["current_revenue"], 2)
        assert abs(data["revenue_change_abs"] - expected_abs) < 0.02

    def test_unknown_product_404(self, client):
        resp, data = get_json(client, "/api/pricing/ZZZZ")
        assert resp.status_code == 404
        assert data["error"]["status"] == 404

    def test_no_ground_truth(self, client):
        resp = client.get("/api/pricing/P001")
        _no_gt(resp.get_data(as_text=True))

    def test_product_with_reason_code(self, client):
        """P027 has CURRENT_PRICE_BREAKS_MARGIN in reason_codes — check it appears."""
        _, data = get_json(client, "/api/pricing/P027")
        assert resp.status_code == 200 if (resp := client.get("/api/pricing/P027")) else True
        assert "CURRENT_PRICE_BREAKS_MARGIN" in data.get("reason_codes", [])

    def test_stock_limited_is_bool(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        assert isinstance(data["stock_limited"], bool)

    def test_binding_constraint_string(self, client):
        _, data = get_json(client, "/api/pricing/P001")
        assert isinstance(data["binding_constraint"], str)
        assert len(data["binding_constraint"]) > 0


# ── All products list ─────────────────────────────────────────────────────

class TestRecommendationsList:
    def test_default_returns_200(self, client):
        resp, data = get_json(client, "/api/pricing/recommendations")
        assert resp.status_code == 200

    def test_pagination_shape(self, client):
        _, data = get_json(client, "/api/pricing/recommendations")
        assert {"total", "page", "page_size", "pages", "recommendations"} \
               == set(data.keys())
        assert data["total"] == 50
        assert data["page"]  == 1

    def test_default_page_size_50(self, client):
        _, data = get_json(client, "/api/pricing/recommendations")
        assert len(data["recommendations"]) == 50

    def test_category_filter(self, client):
        _, data = get_json(client, "/api/pricing/recommendations?category=Staples")
        assert data["total"] == 12
        assert all(r["category"] == "Staples"
                   for r in data["recommendations"])

    def test_category_filter_unknown_empty(self, client):
        _, data = get_json(client, "/api/pricing/recommendations?category=Nonexistent")
        assert data["total"] == 0
        assert data["recommendations"] == []

    def test_pagination_page2(self, client):
        _, data = get_json(client, "/api/pricing/recommendations?page=2&page_size=10")
        assert data["page"] == 2
        assert len(data["recommendations"]) == 10

    def test_bad_page_400(self, client):
        resp, data = get_json(client, "/api/pricing/recommendations?page=0")
        assert resp.status_code == 400
        assert data["error"]["status"] == 400

    def test_bad_page_size_str_400(self, client):
        resp, _ = get_json(client, "/api/pricing/recommendations?page_size=abc")
        assert resp.status_code == 400

    def test_page_size_too_large_400(self, client):
        resp, _ = get_json(client, "/api/pricing/recommendations?page_size=9999")
        assert resp.status_code == 400

    def test_item_has_required_fields(self, client):
        _, data = get_json(client, "/api/pricing/recommendations")
        item = data["recommendations"][0]
        assert REQUIRED_FIELDS.issubset(set(item.keys()))

    def test_no_ground_truth(self, client):
        resp = client.get("/api/pricing/recommendations")
        _no_gt(resp.get_data(as_text=True))

    def test_all_elasticities_negative(self, client):
        _, data = get_json(client, "/api/pricing/recommendations?page_size=200")
        bad = [r["product_id"] for r in data["recommendations"]
               if r["elasticity"] >= 0]
        assert bad == [], f"Non-negative elasticities found: {bad}"
