# API Reference — Phase 10a

Base URL: `http://localhost:5000`

All responses are JSON.  All endpoints are read-only (GET).
All error responses share the same shape:

```json
{
  "error": {
    "status": 404,
    "message": "Product 'ZZZZ' not found."
  }
}
```

---

## Health

### `GET /api/health`

Confirms the server is running.

**Response 200**
```json
{
  "status": "ok"
}
```

---

## Products

### `GET /api/products`

Returns all 50 products.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `category` | string | Optional. Filter by category name. Returns empty list (not 404) if no match. |

**Response 200**
```json
[
  {
    "base_price": 3.98,
    "category": "Staples",
    "product_id": "P001"
  },
  {
    "base_price": 0.92,
    "category": "Staples",
    "product_id": "P002"
  }
]
```

**Example with filter** — `GET /api/products?category=Staples` returns 12 products.

Valid category values: `Staples`, `Personal Care`, `Electronics`, `Clothing`, `Impulse`.

---

## Forecast

### `GET /api/forecast/metrics`

Returns the Phase 5 model comparison metadata: metrics for both models, which was selected, and the training/test date ranges.

**Response 200**
```json
{
  "models": {
    "LinearRegression": {
      "mae": 17.6535,
      "mape": 15.261,
      "rmse": 24.2629
    },
    "XGBoost": {
      "mae": 14.7333,
      "mape": 9.7208,
      "rmse": 21.1903
    }
  },
  "n_test": 400,
  "n_train": 7300,
  "selected_model": "XGBoost",
  "selected_reason": "XGBoost wins on RMSE (21.190 vs 24.263, 12.7% improvement)",
  "test_end": "2024-12-23",
  "test_start": "2024-11-04",
  "train_end": "2024-10-28",
  "train_start": "2022-01-17",
  "trained_at": "2026-10-08 12:02:39"
}
```

---

### `GET /api/forecast/<product_id>`

Returns the weekly demand time series for one product.

The `series` array contains two kinds of rows:

- **`"history"`** — the most recent 12 training weeks (configurable via `FORECAST_HISTORY_WEEKS`). Actual units only; no prediction (the model was trained on these weeks).
- **`"test"`** — the held-out 8-week evaluation window (2024-11-04 to 2024-12-23). Both actual units and the model prediction are included.

**Path parameters**

| Name | Description |
|---|---|
| `product_id` | e.g. `P001` – `P050` |

**Response 200**
```json
{
  "model_type": "XGBoost",
  "product_id": "P001",
  "test_end": "2024-12-23",
  "test_start": "2024-11-04",
  "train_end": "2024-10-28",
  "series": [
    {
      "actual_units": 317,
      "iso_week": 33,
      "iso_year": 2024,
      "row_type": "history",
      "week_start_date": "2024-08-12"
    },
    {
      "actual_units": 337,
      "iso_week": 38,
      "iso_year": 2024,
      "row_type": "history",
      "week_start_date": "2024-09-16"
    },
    {
      "actual_units": 397,
      "iso_week": 45,
      "iso_year": 2024,
      "predicted_units": 355,
      "row_type": "test",
      "week_start_date": "2024-11-04"
    },
    {
      "actual_units": 451,
      "iso_week": 52,
      "iso_year": 2024,
      "predicted_units": 458,
      "row_type": "test",
      "week_start_date": "2024-12-23"
    }
  ]
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `product_id` not in the database |

```json
{
  "error": {
    "message": "Product 'ZZZZ' not found.",
    "status": 404
  }
}
```

**Note:** this endpoint serves the held-out test-window predictions only.
There is no next-week forecast yet — the feature-building pipeline for future
weeks is part of Phase 10b.

---

## Segments

### `GET /api/segments`

Returns the segment summary produced by Phase 6 (RFM + K-Means), including
the number of clusters and the Silhouette score.

**Response 200**
```json
{
  "n_clusters": 4,
  "silhouette_score": 0.8573,
  "total_customers": 1000,
  "segments": [
    {
      "customer_count": 160,
      "mean_frequency": 1037.05,
      "mean_monetary": 58087.23,
      "mean_recency_days": 1.02,
      "median_frequency": 1037.0,
      "median_monetary": 58172.01,
      "median_recency_days": 1.0,
      "revenue_share_pct": 40.06,
      "segment_label": "high_value",
      "share_pct": 16.0
    },
    {
      "customer_count": 346,
      "mean_frequency": 851.7,
      "mean_monetary": 29086.92,
      "mean_recency_days": 1.16,
      "median_frequency": 852.0,
      "median_monetary": 28907.62,
      "median_recency_days": 1.0,
      "revenue_share_pct": 43.38,
      "segment_label": "regular",
      "share_pct": 34.6
    },
    {
      "customer_count": 293,
      "mean_frequency": 452.46,
      "mean_monetary": 10136.98,
      "mean_recency_days": 2.22,
      "median_frequency": 452.0,
      "median_monetary": 10171.81,
      "median_recency_days": 2.0,
      "revenue_share_pct": 12.8,
      "segment_label": "occasional",
      "share_pct": 29.3
    },
    {
      "customer_count": 201,
      "mean_frequency": 225.59,
      "mean_monetary": 4339.79,
      "mean_recency_days": 3.6,
      "median_frequency": 226.0,
      "median_monetary": 4248.08,
      "median_recency_days": 3.0,
      "revenue_share_pct": 3.76,
      "segment_label": "at_risk",
      "share_pct": 20.1
    }
  ]
}
```

Segments are always returned in order: `high_value`, `regular`, `occasional`, `at_risk`.

---

### `GET /api/segments/customers`

Paginated list of all customers with their segment label and RFM values.

**Query parameters**

| Name | Type | Default | Max | Description |
|---|---|---|---|---|
| `segment` | string | — | — | Filter by segment label. 404 if the label doesn't exist. |
| `page` | int | `1` | — | Page number (1-based). 400 if < 1. |
| `page_size` | int | `50` | `200` | Rows per page. 400 if < 1 or > 200. |

**Response 200**
```json
{
  "customers": [
    {
      "customer_id": "C0001",
      "frequency": 861,
      "monetary": 31198.8,
      "recency_days": 1,
      "segment_label": "regular"
    },
    {
      "customer_id": "C0002",
      "frequency": 847,
      "monetary": 28506.94,
      "recency_days": 3,
      "segment_label": "regular"
    }
  ],
  "page": 1,
  "page_size": 50,
  "pages": 20,
  "total": 1000
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `segment` parameter value not found |
| 400 | `page` < 1, `page_size` < 1 or > 200, or either is not an integer |

```json
{ "error": { "status": 404, "message": "Segment 'vip' not found." } }
{ "error": { "status": 400, "message": "'page' must be >= 1." } }
{ "error": { "status": 400, "message": "'page_size' must be <= 200." } }
```

---

### `GET /api/customers/<customer_id>/segment`

Returns one customer's segment label and RFM values.

**Path parameters**

| Name | Description |
|---|---|
| `customer_id` | e.g. `C0001` – `C1000` |

**Response 200**
```json
{
  "customer_id": "C0001",
  "frequency": 861,
  "monetary": 31198.8,
  "recency_days": 1,
  "segment_label": "regular"
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `customer_id` not in the database |

```json
{
  "error": {
    "message": "Customer 'ZZZZ' not found.",
    "status": 404
  }
}
```

---

## Field glossary

| Field | Description |
|---|---|
| `recency_days` | Days between the customer's last purchase and the snapshot date (2025-01-01). Lower = more recent. |
| `frequency` | Total number of purchase transactions over the 3-year dataset. |
| `monetary` | Total spend (£) over the 3-year dataset. |
| `actual_units` | True units sold that week (from the sales table). |
| `predicted_units` | XGBoost model prediction for that week. Only present on `"test"` rows. |
| `row_type` | `"history"` = training data (no prediction); `"test"` = held-out evaluation window. |
| `mape` | Mean Absolute Percentage Error (%). |
| `rmse` | Root Mean Square Error (units/week). |
| `mae` | Mean Absolute Error (units/week). |

---

## Notes for the Angular developer

- All field names are `snake_case`.
- Dates are plain `YYYY-MM-DD` strings — no time component, no timezone.
- Monetary values are plain floats (no currency symbol).
- The `monetary` field in customer/segment responses represents total lifetime spend in the dataset, not per-visit basket size.
- The `silhouette_score` in `/api/segments` is a fixed value embedded in the service layer (not stored in MySQL). It reflects the k=4 clustering run during Phase 6.
- Phase 10b will add `/api/pricing` and `/api/explanations` endpoints using the same error format and the same blueprint pattern.

---

# Phase 10b Endpoints

---

## Pricing

### `GET /api/pricing/<product_id>`

Pricing recommendation for one product from Phase 8.

Returns HTTP 200 even when no valid candidate price exists (`recommendation_available: false`). Returns 404 only when the product_id is not in the database.

**Response 200 — normal recommendation**
```json
{
  "product_id": "P001",
  "category": "Staples",
  "recommendation_available": true,
  "no_candidate_reason": null,
  "current_price": 3.28,
  "current_revenue": 1344.12,
  "unit_cost": 2.786,
  "available_stock": 17750,
  "elasticity": -0.4676,
  "baseline_demand": 409.79,
  "recommended_price": 3.77,
  "change_pct": 0.1494,
  "expected_demand": 383.96,
  "expected_revenue": 1447.54,
  "revenue_change_pct": 0.0769,
  "revenue_change_abs": 103.42,
  "margin_pct": 0.261,
  "expected_profit": 377.82,
  "stock_limited": false,
  "binding_constraint": "MAX_CHANGE",
  "reason_codes": [],
  "constraints_applied": {
    "min_margin_pct": 0.1,
    "max_price_change_pct": 0.15
  },
  "model_type": "XGBoost",
  "forecast_week": "2025-W01",
  "generated_at": "2026-10-14 00:03:48"
}
```

**Response 200 — current price already breaks a constraint (P027)**
```json
{
  "product_id": "P027",
  "recommendation_available": true,
  "binding_constraint": "MARGIN",
  "reason_codes": ["CURRENT_PRICE_BREAKS_MARGIN"],
  "change_pct": 0.0699,
  "revenue_change_pct": -0.0487
}
```

**Response 200 — no valid candidate (if it occurs)**
```json
{
  "recommendation_available": false,
  "no_candidate_reason": "NO_FEASIBLE_PRICE",
  "binding_constraint": "NO_FEASIBLE_PRICE"
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `product_id` not in the database |
| 404 | Phase 8 has not been run yet (no row in pricing_recommendation) |

---

### `GET /api/pricing/recommendations`

Paginated list of recommendations for all 50 products.

**Query parameters**

| Name | Type | Default | Max | Description |
|---|---|---|---|---|
| `category` | string | — | — | Filter by category. Returns empty list (not 404) if no match. |
| `page` | int | `1` | — | 400 if < 1. |
| `page_size` | int | `50` | `200` | 400 if < 1 or > 200. |

**Response 200**
```json
{
  "total": 50,
  "page": 1,
  "page_size": 50,
  "pages": 1,
  "recommendations": [
    { "product_id": "P001", "category": "Staples", "recommended_price": 3.77, "..." : "..." }
  ]
}
```

Each item has the same fields as `GET /api/pricing/<product_id>`.

**Error responses** — same as `/api/segments/customers` (400 for bad pagination).

---

## Explanations

Phase 9 supports two entity types: **pricing** and **segment**.
Forecast explanations are not supported — that endpoint returns HTTP 200 with `explanation_available: false` rather than 404, so Phase 11 can always call the same pattern.

All explanation endpoints return HTTP 200 even when no explanation is stored or available. They never return 500 due to an LLM failure.

---

### `GET /api/pricing/<product_id>/explanation`

Natural-language explanation for a product's pricing recommendation.

**Response 200 — explanation available**
```json
{
  "entity_type": "pricing",
  "entity_id": "P027",
  "explanation_available": true,
  "explanation": "Raise the price of P027 (Electronics) by 7.0%, from 53.93 to 57.70, because it is highly price-sensitive. Expected weekly sales are 44 units and weekly revenue should decrease by 4.9% (limit: the minimum profit margin rule).",
  "source": "fallback",
  "guardrail_status": "fallback",
  "model_name": "gemini-3.5-flash",
  "attempts": 2,
  "payload": {
    "action": "raise",
    "category": "Electronics",
    "current_price": "53.93",
    "recommended_price": "57.70",
    "price_change": "7.0%",
    "price_sensitivity": "highly price-sensitive",
    "revenue_direction": "decrease",
    "revenue_change": "4.9%",
    "limited_by": "the minimum profit margin rule",
    "expected_weekly_units": "44",
    "weekly_units_at_current_price": "49",
    "product_id": "P027"
  },
  "generated_at": "2026-10-15 08:38:57"
}
```

**Response 200 — explanation not yet generated**
```json
{
  "entity_type": "pricing",
  "entity_id": "P001",
  "explanation_available": false,
  "explanation": null,
  "unavailable_reason": "No explanation has been generated yet. Run python -m explanations.generate_explanations in the data pipeline.",
  "payload": null,
  "source": null,
  "generated_at": null
}
```

**Response 200 — internal error (graceful degradation, REQ-22)**
```json
{
  "explanation_available": false,
  "explanation": null,
  "unavailable_reason": "An internal error occurred while fetching the explanation."
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `product_id` not in the database |

---

### `GET /api/forecast/<product_id>/explanation`

Forecast explanations are **not supported** by Phase 9. Always returns HTTP 200 with `explanation_available: false` so Phase 11 does not need special-casing.

**Response 200**
```json
{
  "explanation_available": false,
  "explanation": null,
  "unavailable_reason": "Forecast explanations are not supported in Phase 9. Phase 9 generates explanations for 'pricing' and 'segment' entity types only.",
  "payload": null,
  "source": null,
  "generated_at": null
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `product_id` not in the database |

---

### `GET /api/segments/<segment_label>/explanation`

Natural-language description of a customer segment.

**Path parameters**

| Name | Valid values |
|---|---|
| `segment_label` | `high_value`, `regular`, `occasional`, `at_risk` |

**Response 200**
```json
{
  "entity_type": "segment",
  "entity_id": "high_value",
  "explanation_available": true,
  "explanation": "High-value customers: 160 customers (16.0% of customers) bringing 40.1% of revenue. On average they bought on 1,037 days and spent 58,087.23 in total.",
  "source": "fallback",
  "guardrail_status": "fallback",
  "model_name": "gemini-3.5-flash",
  "attempts": 2,
  "payload": {
    "segment": "High-value customers",
    "customers": "160",
    "share_of_customers": "16.0%",
    "share_of_revenue": "40.1%",
    "average_purchase_days": "1,037",
    "average_spend": "58,087.23",
    "typical_days_since_last_purchase": "1"
  },
  "generated_at": "2026-10-15 08:38:57"
}
```

**Error responses**

| Status | When |
|---|---|
| 404 | `segment_label` not found |

---

## Phase 10b notes for the Angular developer

- The `payload` field in explanation responses contains the exact structured numbers the LLM was given. You can use it to cross-check any number that appears in the explanation text.
- `source` tells you the origin: `"llm"` = real Gemini response, `"fallback"` = template sentence (LLM was rejected by guardrails), `"mock"` = no API key configured.
- `binding_constraint` in pricing responses explains what stopped the recommendation from going further. See the constraint table in [results.md](results.md) for all possible values.
- `revenue_change_abs` is `expected_revenue - current_revenue` in £, computed by the API for convenience.
- The `constraints_applied` object always reflects what Phase 8 actually used (read from `pricing_config.py` at import time).
