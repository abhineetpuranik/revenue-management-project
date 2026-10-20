# Chapter 4 — System Design

## 4.1 Architectural Overview

The system is organised as a three-tier architecture. Each tier has a distinct responsibility and communicates only with the tier adjacent to it.

**Tier 1 — Data Pipeline.** All data preparation, model training, and result generation is carried out by a collection of Python modules: `data_generation`, ETL (`etl/`), feature engineering, `models/`, `pricing/`, `segmentation/`, and `explanations/`. The pipeline runs offline as a one-shot process: it generates synthetic data, trains models, computes recommendations and explanations, and writes every result to MySQL. It is not a streaming or online-learning system. Once the pipeline has run, the database is fully populated and no further writes occur during normal operation.

**Tier 2 — API Tier.** A Flask application (`backend/app.py`) reads from MySQL and serves results over HTTP. All endpoints are read-only GET requests. The API tier performs no computation beyond assembling query results and computing one derived field (`revenue_change_abs`). Blueprint-based routing keeps each resource group in a separate module.

**Tier 3 — Presentation Tier.** An Angular 21 single-page application (`frontend/`) retrieves data exclusively from the Flask API and renders it in the browser. The SPA has no direct database access.

The separation between tiers means the pipeline can be re-run to refresh results without modifying the API or frontend code. See Figure 1 (`diagrams/architecture.mmd`) for the architecture diagram.

## 4.2 Module Responsibilities and Interfaces

| Module | Purpose | Inputs | Outputs | Key files |
|---|---|---|---|---|
| Dataset Generator | Produce a synthetic 3-year retail dataset with embedded ground truth | `config.py` constants | 6 raw CSVs; ground-truth fields in `gt_product_elasticity` and `gt_customer_segment` | `data_generation/generate_data.py`, `data_generation/config.py` |
| ETL | Clean raw CSVs and load to MySQL | 6 raw CSVs | 6 cleaned CSVs; all 12 application tables in `revenue_management`; 2 GT tables in `revenue_management_gt` | `etl/cleaning.py`, `etl/load_to_mysql.py` |
| Feature Engineering | Build the weekly feature table for forecasting | `sales` table (MySQL) | `forecast_features` table (7 750 rows) | `models/feature_engineering.py` |
| Demand Forecasting | Train and evaluate XGBoost and Linear Regression models | `forecast_features` table | `production_model.joblib`; predictions in `forecast_features`; metrics in `metadata.json` | `models/xgboost_model.py`, `models/linear_model.py`, `models/evaluate.py`, `models/artifacts/metadata.json` |
| Customer Segmentation | Assign 1 000 customers to behavioural segments via RFM + K-Means | `sales` table (MySQL) | `customer_rfm_segment` table; `segment_summary` table | `segmentation/rfm.py`, `segmentation/clustering.py`, `segmentation/label_clusters.py` |
| Price Elasticity | Estimate constant price elasticity for each product via log-log OLS | `sales`, `price`, `calendar` tables (MySQL) | `product_elasticity` table | `pricing/elasticity_model.py` |
| Pricing Optimisation | Recommend a revenue-maximising price for each product subject to business constraints | `product_elasticity`, `forecast_features`, `pricing_config.py` | `pricing_candidates` table; `pricing_recommendation` table | `pricing/optimiser.py`, `pricing/pricing_config.py` |
| LLM Explanation Layer | Generate plain-English explanations of pricing recommendations and segment profiles | `pricing_recommendation`, `segment_summary` tables | `llm_explanation` table | `explanations/generate_explanations.py`, `explanations/guardrails.py`, `explanations/llm_client.py` |
| Flask API | Serve pre-computed results from MySQL over HTTP | MySQL (`revenue_management` schema only) | JSON HTTP responses | `backend/app.py`, `backend/blueprints/` |
| Angular Dashboard | Present all results in a browser UI | Flask API endpoints | Rendered SPA views | `frontend/src/app/features/`, `frontend/src/app/core/api.service.ts` |

## 4.3 Database Design

The schema is split across two MySQL schemas. Application code reads only from `revenue_management`. Evaluation code reads from `revenue_management_gt` to compare estimated values against the known true values. No foreign keys exist between the two schemas, which prevents any accidental join in application queries. See Figure 3 (`diagrams/er-diagram.mmd`) for the entity-relationship diagram.

### Application schema: `revenue_management`

The schema contains twelve tables:

**product** (PK: `product_id`) — one row per product. Columns: `product_id VARCHAR(10)`, `category VARCHAR(30)`, `base_price DECIMAL(10,2)`, `base_demand INT`. This is the central reference table; most other application tables carry a foreign key to it.

**customer** (PK: `customer_id`) — one row per customer. Columns: `customer_id VARCHAR(10)` only. Acts as the FK anchor for `sales` and `customer_rfm_segment`.

**calendar** (PK: `date`) — one row per calendar date. Columns: `date DATE`, `year`, `month`, `weekday`, `weekday_name`, `is_weekend`, `seasonal_factor DECIMAL(6,4)`, `weekday_factor DECIMAL(6,4)`, `combined_factor DECIMAL(6,4)`, `festival_flag TINYINT(1)`. Provides pre-computed temporal features to avoid repeated calculation.

**price** (PK: `product_id, date`; FK → `product`, `calendar`) — daily price observations per product. Columns: `price DECIMAL(10,2)`, `is_promo TINYINT(1)`, `discount_pct DECIMAL(6,4)`.

**stock** (PK: `product_id, date`; FK → `product`, `calendar`) — daily stock observations. Columns: `stock_level INT`, `units_restocked INT`, `stockout_flag TINYINT(1)`.

**sales** (PK: `sale_id`; FK → `customer`, `product`, `calendar`) — transactional fact table. Columns: `sale_id INT`, `customer_id`, `product_id`, `date`, `units_sold INT`, `price_at_sale DECIMAL(10,2)`, `discount_pct DECIMAL(6,4)`, `revenue DECIMAL(12,2)`. Indexed on `(product_id, date)`, `customer_id`, and `date` for query performance.

**customer_rfm_segment** (PK: `customer_id`; FK → `customer`) — RFM scores and K-Means assignment per customer. Columns: `recency_days INT`, `frequency INT`, `monetary DECIMAL(14,2)`, `cluster_id INT`, `segment_label VARCHAR(20)`, `assigned_at DATETIME`.

**segment_summary** (PK: `segment_label`) — aggregate statistics per segment. Columns: `customer_count INT`, `share_pct DECIMAL(6,2)`, mean and median of recency, frequency, and monetary, `total_revenue DECIMAL(16,2)`, `revenue_share_pct DECIMAL(6,2)`, `assigned_at DATETIME`.

**product_elasticity** (PK: `product_id`; FK → `product`) — OLS elasticity estimates. Columns: `elasticity DECIMAL(8,4)`, `std_error`, `ci_low`, `ci_high`, `r_squared DECIMAL(6,4)`, `n_obs INT`, `reliable_flag TINYINT(1)`, `unreliable_reasons VARCHAR(100)`, `estimated_at DATETIME`.

**pricing_candidates** (PK: `product_id, step`; FK → `product`) — intermediate grid of candidate prices. Columns: `candidate_price DECIMAL(10,2)`, `change_pct DECIMAL(8,4)`, `unit_cost DECIMAL(10,4)`, `margin_pct DECIMAL(8,4)`, `is_current TINYINT(1)`, `passes_all TINYINT(1)`, `failed_reasons VARCHAR(100)`.

**pricing_recommendation** (PK: `product_id`; FK → `product`) — the winning recommendation per product. Columns: `current_price`, `recommended_price`, `change_pct`, `elasticity`, `baseline_demand`, `expected_demand`, `available_stock INT`, `current_revenue`, `expected_revenue`, `revenue_change_pct DECIMAL(8,4)`, `unit_cost`, `margin_pct`, `expected_profit`, `stock_limited TINYINT(1)`, `binding_constraint VARCHAR(30)`, `reason_codes VARCHAR(100)`, `model_type VARCHAR(30)`, `forecast_week VARCHAR(10)`, `generated_at DATETIME`.

**llm_explanation** (PK: `explanation_id`; UNIQUE on `entity_type, entity_id`) — one explanation record per entity. Columns: `entity_type VARCHAR(10)`, `entity_id VARCHAR(20)`, `explanation_text VARCHAR(1000)`, `source VARCHAR(10)`, `payload_json TEXT`, `payload_hash CHAR(64)`, `model_name VARCHAR(60)`, `guardrail_status VARCHAR(10)`, `rejection_reason VARCHAR(255)`, `attempts INT`, `generated_at DATETIME`.

### Ground-truth schema: `revenue_management_gt`

**gt_product_elasticity** (PK: `product_id`) — the true elasticity value used during data generation. Columns: `product_id VARCHAR(10)`, `true_elasticity DECIMAL(8,4)`.

**gt_customer_segment** (PK: `customer_id`) — the true segment assignment used during data generation. Columns: `customer_id VARCHAR(10)`, `true_segment VARCHAR(20)`, `purchase_rate DECIMAL(5,3)`, `basket_mean DECIMAL(8,2)`, `basket_std DECIMAL(8,2)`.

### Key relationships

`product` is the central reference entity. `sales` joins all three dimension tables (`product`, `customer`, `calendar`), making it the primary fact table. `product_elasticity`, `pricing_candidates`, and `pricing_recommendation` all have a one-to-one or one-to-many relationship with `product`. `customer_rfm_segment` has a one-to-one relationship with `customer`. `segment_summary` is keyed on the segment label, which is a categorical value shared with `customer_rfm_segment`. `llm_explanation` is keyed on `(entity_type, entity_id)`, which resolves to either a `product_id` (for pricing explanations) or a `segment_label` (for segment explanations).

The design decision to isolate ground truth in a separate schema (`revenue_management_gt`) ensures that application code cannot accidentally read true elasticity or true segment labels. Because the two schemas have no shared foreign keys, any query that joins across them is an explicit, deliberate act rather than an incidental result of normal ORM traversal.

## 4.4 API Design Summary

All endpoints are read-only GET requests served at base URL `http://localhost:5000`. All responses are JSON. Error responses share the uniform shape `{"error": {"status": <code>, "message": "<text>"}}`. Endpoints are organised into five resource groups via Flask blueprints.

| Group | Method | Path | Description |
|---|---|---|---|
| **Health** | GET | `/api/health` | Returns `{"status": "ok"}` to confirm the server is running |
| **Products** | GET | `/api/products` | Returns all 50 products; optional `?category=` filter |
| **Forecast** | GET | `/api/forecast/metrics` | Returns model comparison metadata (both models, metrics, selected model, training/test date ranges) |
| **Forecast** | GET | `/api/forecast/<product_id>` | Returns the weekly demand series for one product (12 history rows + 8 test rows) |
| **Forecast** | GET | `/api/forecast/<product_id>/explanation` | Always returns HTTP 200 with `explanation_available: false` (forecast explanations not supported) |
| **Segments** | GET | `/api/segments` | Returns segment summary: n_clusters, silhouette_score, total_customers, and per-segment statistics |
| **Segments** | GET | `/api/segments/customers` | Paginated list of all customers with RFM values and segment labels; optional `?segment=` filter |
| **Segments** | GET | `/api/customers/<customer_id>/segment` | Returns RFM values and segment label for one customer |
| **Segments** | GET | `/api/segments/<segment_label>/explanation` | Returns the LLM explanation for a segment profile |
| **Pricing** | GET | `/api/pricing/<product_id>` | Returns the pricing recommendation for one product (always HTTP 200; 404 only if product not in DB) |
| **Pricing** | GET | `/api/pricing/recommendations` | Paginated list of recommendations for all 50 products; optional `?category=` filter |
| **Explanations** | GET | `/api/pricing/<product_id>/explanation` | Returns the LLM explanation for a product's pricing recommendation |

The `binding_constraint` field in pricing responses can take the values `MAX_CHANGE`, `MARGIN`, `PRICE_RANGE`, `ELASTICITY_UNRELIABLE`, `STOCK`, `NO_FEASIBLE_PRICE`, and `TIE_TOLERANCE`. The last value, `TIE_TOLERANCE`, is not yet listed in `api.md` (KI-01): seven products (P013, P015, P016, P018, P021, P022, P030) return this value, and a Phase 13 contract test now guards the behaviour, but the documentation has not been updated.

One field, `revenue_change_abs` (the absolute £ revenue change), is computed by the API layer as `expected_revenue − current_revenue` rather than stored in the `pricing_recommendation` table (KI-07).

## 4.5 Dashboard Design

The Angular SPA is organised around three lazy-loaded routes, each corresponding to one analytical domain.

**`/forecast` — Forecast View.** Presents demand-forecasting results for any selected product. A product sidebar (with category chip filters) allows product selection. The main panel contains a Chart.js line chart displaying 12 weeks of training history followed by the 8-week test window, with separate series for actual and predicted units. Below the chart, three metric tiles show MAPE, RMSE, and MAE for the selected product. A model comparison table shows the aggregate metrics for both XGBoost and Linear Regression. A weekly data table lists the raw values.

**`/segments` — Segments View.** Presents customer segmentation results. Three stat tiles at the top show total customers, number of clusters (k=4), and silhouette score. A segment summary table shows the four segments with bar-chart visualisations of relative size and revenue share. A Chart.js doughnut chart shows revenue share across segments. Below, a customer lookup field and a paginated, filterable customer table allow exploration of individual RFM values and segment assignments.

**`/pricing` — Pricing View.** Presents pricing recommendations. A product sidebar with category chip filters allows product selection. The recommendation card shows current and recommended prices, a direction tag (INCREASE/DECREASE/KEEP), revenue change tiles with currency symbol and directional arrow, a Chart.js bar chart comparing current and expected weekly revenue, the elasticity estimate, applicable constraints, and reason codes. An explanation panel below the card displays the LLM explanation in one of four states: loading, available, unavailable, or error. A paginated recommendations table shows all 50 products.

**Key architectural decisions in the dashboard:**

- *Standalone Angular components.* All components use `standalone: true` and declare their own `imports[]`, which eliminates the need for `NgModule` declarations and makes each component self-contained.
- *Signal-based state management.* State is managed via Angular 21's `signal()`, `computed()`, and `effect()` primitives rather than `BehaviorSubject` or `async` pipes.
- *Stale-response guard.* `PricingComponent` maintains separate `recToken` and `expToken` counters. A subscriber writes to signals only when its captured token still matches the current counter. This prevents stale data appearing when the user switches products rapidly.
- *Explanation timeout.* `EXPLANATION_TIMEOUT_MS = 35 000` (35 seconds, approximately 5 seconds above the backend LLM timeout). A `timer()` observable races against the HTTP call; if the state is still `loading` when the timer fires, the panel transitions to an error state with a Retry button.
- *Chart.js registered once.* `ChartWrapperComponent` registers all used Chart.js components on first import to avoid duplicate registration errors. The chart types used are: line (forecast history and test window), doughnut (segment revenue share), and bar (pricing recommendation).

All 76 frontend specs across 10 spec files pass with zero failures (source: `docs/frontend.md`).

## 4.6 Technology Choices and Justification

| Technology | Choice | Justification |
|---|---|---|
| Language | Python 3.11 | Broad ML ecosystem; supported by scikit-learn, XGBoost, statsmodels, and Flask. (Python 3.13 is explicitly not supported due to NumPy 1.26 incompatibility.) |
| ML framework | scikit-learn + XGBoost | scikit-learn provides the preprocessing, Ridge regression baseline, and K-Means clustering. XGBoost is the primary forecasting model, chosen for its strong tabular performance without requiring deep-learning infrastructure. |
| Database | MySQL 8.0 | Relational integrity enforces referential consistency between products, customers, sales, and downstream result tables. The two-schema design (application + ground truth) is straightforward to implement in MySQL. |
| API framework | Flask | Lightweight, requires no ORM or migration tooling for a read-only API, and maps naturally to Blueprint-based route organisation. |
| Frontend framework | Angular 21 | Provides typed templates, dependency injection, and a mature HTTP client. The standalone component model and signal-based reactivity (introduced in recent Angular versions) reduce boilerplate compared with older NgModule patterns. |
| UI charting | Chart.js | Small bundle footprint; supports the three required chart types (line, doughnut, bar) without a large framework dependency. |
| Statistical modelling | statsmodels OLS | Provides coefficient standard errors and confidence intervals for the log-log elasticity regression, which are needed for the `reliable_flag` decision. scikit-learn's OLS does not expose these diagnostics. |
| LLM integration | Configurable provider via environment variable | Avoids hard-coding a specific LLM provider. The provider (e.g. Gemini) is resolved at runtime from `data-pipeline/.env`, so the system can be tested without an API key (using the `mock` source path). |

## 4.7 Key Design Decisions

**XGBoost as primary forecasting model with Linear Regression as baseline.** Training both models and comparing them on a held-out test set (2024-11-04 to 2024-12-23, 8 weeks) allows the team to measure the improvement that XGBoost provides over a simpler model. XGBoost achieved RMSE 21.1903 against the baseline's 24.2629 — a 12.7% improvement. The comparison also guards against the case where the added complexity of a tree ensemble provides no benefit.

**Synthetic data with hidden ground truth.** Because the dataset is generated programmatically, the true per-product elasticity and true per-customer segment are known. Storing them in a separate, isolated schema (`revenue_management_gt`) that application code cannot read creates a controlled evaluation environment: the team can measure how closely the models recover the structure that was deliberately embedded in the data. This would not be possible with real retail data, where the true elasticity and true segment are unknown.

**LLM explains only, never computes.** The LLM receives a structured JSON payload of pre-validated numbers and is asked only to narrate what the payload already says. Guardrails (`guardrails.py`) extract all numbers from the LLM response and verify each against the payload; any number not present in the payload triggers rejection and a fallback template sentence is returned. This design (REQ-20 to REQ-22) prevents the LLM from introducing incorrect figures into the user interface.

**No deep learning.** A neural forecasting model (e.g. LSTM or Temporal Fusion Transformer) was identified as out of scope. It would require additional infrastructure (GPU or extended CPU training time, a different ML framework), and the dataset size (7 300 training observations) is modest. The tabular structure of the feature set (lag features, calendar variables, price) suits gradient boosting well.

**No reinforcement learning for pricing.** Reinforcement learning for dynamic pricing (for example, contextual bandits or a Markov decision process) was reviewed in the literature but excluded from this implementation. The current one-shot grid search is simpler, fully deterministic and reproducible, and does not require an online feedback loop or a simulated environment. RL pricing is documented as a direction for future work.

**Pricing as a one-shot grid search.** The optimiser generates 31 candidate prices per product (±15% in 1% steps), filters by business constraints, evaluates expected revenue under the estimated elasticity, and selects the maximum. This approach is deterministic: the same pipeline inputs always produce the same recommendation. It is also transparent: the `binding_constraint` and `reason_codes` fields explain exactly why each recommendation was made.
