# Viva Guide

All numbers in this document are taken directly from the system output.
Lines marked **VERIFY** indicate something that should be confirmed by running the relevant script.

---

## 1. Architecture overview

```
[Synthetic dataset generator]
        |
   data/raw/*.csv  (6 files)
        |
[ETL — clean + validate]
        |
   data/cleaned/*.csv
        |
[MySQL loader]  ->  revenue_management (app tables)
                ->  revenue_management_gt (ground truth, sealed)
        |
[Feature builder]  ->  forecast_features table (7 750 rows)
        |
[Forecasting trainer]  ->  models/artifacts/production_model.joblib
                       ->  models/artifacts/metadata.json
        |
[Elasticity estimator]  ->  product_elasticity table (50 rows)
        |
[Segmentation runner]   ->  customer_rfm_segment (1 000 rows)
                        ->  segment_summary (4 rows)
        |
[Pricing pipeline]      ->  pricing_candidates (1 550 rows)
                        ->  pricing_recommendation (50 rows)
        |
[LLM explanation layer] ->  llm_explanation (54 rows: 50 pricing + 4 segment)
        |
[Flask API]  <->  Angular dashboard
```

---

## 2. Data-flow trace: one number end-to-end

**Trace:** the `expected_revenue` figure of £1 447.54 shown for P001 in the dashboard.

1. **Raw data** — `data_generation/sales.py` generates a daily sales row for P001 on each calendar day. The `generate_sales()` function applies demand scaling: `demand × seasonal_factor × weekday_factor × elasticity_factor × promo_uplift`. With `RANDOM_SEED=42`, the same sequence is produced every run.

2. **ETL** — `etl/cleaning.py` `clean_sales()` removes duplicate `sale_id` values and validates that `revenue = units_sold × price_at_sale`. The cleaned row for P001 lands in `data/cleaned/sales.csv`.

3. **MySQL load** — `etl/load_to_mysql.py` inserts the row into the `sales` table in `revenue_management`. Ground-truth columns (`true_elasticity` etc.) go to `revenue_management_gt` only.

4. **Feature builder** — `features/weekly_aggregation.py` aggregates daily rows to one row per (product_id, iso_year, iso_week): sum of `units_sold`, mean of `price_at_sale`, count of `promo_days`. `features/lag_features.py` adds `lag_1_units`, `lag_2_units`, `lag_3_units` from the three preceding weeks.

5. **Forecasting** — `models/xgboost_model.py` `predict()` takes the P001 feature row for 2025-W01 as input. The XGBoost model outputs a raw demand value. `pricing/demand_response.py` `baseline_forecast()` calls `model.predict()` to get `baseline_demand = 409.79` units.

6. **Pricing** — `pricing/demand_response.py` `elasticity_scaled_demand()` computes `demand(p) = 409.79 × (3.77 / 3.28)^(−0.4676) = 383.96`. `pricing/revenue.py` `score_candidates()` computes `expected_revenue = 383.96 × 3.77 = £1 447.54`. (Stored with 2 decimal places after `round(d, 2)`.)

7. **API** — `backend/routes/pricing.py` reads the `pricing_recommendation` row and adds `revenue_change_abs = 1447.54 − 1344.12 = 103.42`.

8. **Dashboard** — `frontend/src/app/features/pricing/recommendation-card.component.ts` renders `£1447.54` from `expected_revenue` received in the HTTP response.

The number passes through 7 layers without modification — the dashboard strictly displays what the API returns.

---

## 3. Module-by-module reference

### 3.1 Dataset generation

**Purpose:** Create a reproducible synthetic retail dataset with controlled ground truth.

**Inputs:** `data_generation/config.py` parameters only (no external data).

**Outputs:** 6 CSV files in `data/raw/`: `product.csv` (50 rows), `customer.csv` (1 000 rows), `calendar.csv` (1 096 rows), `price.csv` (54 800 rows), `sales.csv` (~1.3 million rows), `stock.csv` (54 800 rows).

**Key files:** `generate_base_tables.py`, `generate_transactional_tables.py`, `config.py`, `sales.py`, `price.py`, `stock.py`.

**Algorithm in plain English:**  
Products are created with a base price and a `true_elasticity` drawn from a category-specific distribution. Customers are assigned to one of four purchasing-behaviour segments. A 3-year calendar is generated with seasonal factors per month and per weekday. For each product-day, the price either changes (with 60% probability every 14 days) or stays the same. Sales are generated for each customer using a Poisson-like process: the probability of a purchase depends on the customer's `purchase_rate`, and the basket size depends on the product's `base_demand`, the current price, the true elasticity, the seasonal factor, and any promo uplift.

**Key parameters:**
- `RANDOM_SEED = 42` — makes every run identical
- `PRICE_CHANGE_INTERVAL_DAYS = 14`, `PRICE_CHANGE_PROB = 0.60`
- Elasticity anchors by category: Staples −0.5, Personal Care −1.0, Electronics −1.5, Clothing −1.8, Impulse −2.0

**Known limitation:** The demand model is a simplified multiplicative function. Real retail data has autocorrelation and competitor effects not present here.

**Likely examiner questions:**

Q1: *Why use synthetic data instead of a public dataset like M5?*  
A: M5 does not contain controlled price changes with known true elasticities. Without knowing the true elasticity, we cannot validate whether our Phase 7 estimates are correct. The synthetic dataset lets us measure accuracy against ground truth.

Q2: *How do you know the synthetic data is realistic?*  
A: The generator embeds real seasonal patterns (Christmas uplift 30%, summer lower), real purchase-frequency differences across segments, and elasticity values consistent with published retail research (Staples −0.5 to −0.6, Electronics −1.5 to −2.0).

Q3: *What if someone queries the wrong database?*  
A: The `revenue_management_gt` schema has no foreign keys to `revenue_management`. The ML code only calls `get_engine()` which connects to `DB_NAME = revenue_management`. There are explicit tests (`test_ground_truth_isolation`, `test_pricing_ground_truth_isolation`) that search for any import or reference to `revenue_management_gt` in the modelling code.

---

### 3.2 ETL

**Purpose:** Clean, validate, and load the raw CSVs into MySQL.

**Inputs:** 6 CSV files in `data/raw/`.

**Outputs:** 6 cleaned CSVs in `data/cleaned/`; 6 app tables + 2 GT tables in MySQL.

**Key files:** `etl/cleaning.py`, `etl/validation.py`, `etl/load_to_mysql.py`, `etl/db_connection.py`.

**Algorithm:** Each raw table goes through a cleaner function that: (1) drops duplicate rows by primary key, (2) handles missing values (forward-fill for stock levels, nearest-price for gaps), (3) enforces column types, (4) validates domain constraints (e.g. `revenue = units × price`). The loader uses `TRUNCATE` + `to_sql(if_exists='append')` so it is idempotent.

**Key parameters:** `APP_COLUMNS` dict in `load_to_mysql.py` — defines exactly which columns enter the application schema. Ground-truth columns (`true_elasticity`, `true_segment`) are routed to `revenue_management_gt` only.

**Known limitation:** The cleaning rules are hardcoded and domain-specific. They would need updating for a different dataset.

**Likely examiner questions:**

Q1: *How do you ensure ground truth never leaks into the application tables?*  
A: The `APP_COLUMNS` dict in `load_to_mysql.py` explicitly lists every column for each table. `true_elasticity` and `true_segment` are not in any `APP_COLUMNS` entry. After loading, `load_to_mysql.py` runs a SQL query on `INFORMATION_SCHEMA.COLUMNS` to verify no `true_*` column exists in `revenue_management` (section "Ground-truth isolation check").

Q2: *What happens if you run the loader twice?*  
A: `TRUNCATE TABLE` before each insert makes it idempotent. The same data is loaded, producing identical results.

---

### 3.3 Feature engineering

**Purpose:** Transform daily transaction rows into a weekly supervised-learning dataset.

**Inputs:** `sales`, `price`, `calendar` tables in MySQL.

**Outputs:** `forecast_features` table (7 750 rows = 50 products × ~155 weeks, minus the first 3 weeks per product that lack lag history); `data/features/forecast_features.csv`.

**Key files:** `features/build_feature_table.py`, `features/weekly_aggregation.py`, `features/lag_features.py`, `features/calendar_features.py`, `features/price_features.py`.

**Features produced (14 total):** `lag_1_units`, `lag_2_units`, `lag_3_units`, `month`, `month_sin`, `month_cos`, `seasonal_factor_mean`, `festival_week`, `list_price_mean`, `price_change_pct`, `avg_discount_price`, `promo_days`, `avg_price`, `avg_discount`.

**Leakage prevention:** The lag features are strictly backward-looking — `lag_1_units` for week W is the actual sales of week W−1. The leakage test in `build_feature_table.py` confirms this for a 5-product sample. The test-train split in Phase 5 is time-based, so no future information leaks.

**Known limitation:** Only 3 lags are used. A longer lag window might capture monthly seasonality more precisely.

**Likely examiner questions:**

Q1: *Why is `price_change_pct` NULL for the first valid week?*  
A: There is no previous week to compare against for the very first price-valid week per product. The null is retained in the CSV and filled with `fillna(0)` before model training — a zero price change is the correct fallback.

Q2: *Why use week-of-year features as sin/cos transforms (`month_sin`, `month_cos`)?*  
A: To preserve the circular nature of the calendar — December and January should be "close" to each other. A linear month feature (1–12) would make December and January as far apart as possible.

---

### 3.4 Demand forecasting

**Purpose:** Train a demand model that predicts weekly units sold per product.

**Inputs:** `forecast_features` table. Train/test split: weeks up to 2024-10-28 (train), 2024-11-04 to 2024-12-23 (test). Split is time-based, never random.

**Outputs:** `models/artifacts/production_model.joblib`, `models/artifacts/metadata.json`.

**Key files:** `models/train_forecasting_models.py`, `models/xgboost_model.py`, `models/baseline_model.py`, `models/evaluate.py`, `models/data_split.py`.

**Results (from metadata.json, run 2026-10-08):**

| Model | MAE | RMSE | MAPE |
|---|---|---|---|
| Linear Regression | 17.65 | 24.26 | 15.26% |
| XGBoost | 14.73 | 21.19 | 9.72% |

XGBoost wins on RMSE by 12.7%. It is saved as the production model.

**Algorithm:** XGBoost adds product ID as an integer feature (encoded via `product_id_map_`), concatenated with the 14 feature columns. This allows the model to learn product-specific demand levels. Linear Regression uses one-hot product encoding via Ridge regression.

**Key parameters (XGBoost):** `n_estimators=300`, `max_depth=5`, `learning_rate=0.05`, `subsample=0.8`, `random_state=42`.

**Known limitation:** No hyperparameter search was performed; the parameters are manually chosen. A grid search might improve MAPE further.

**Likely examiner questions:**

Q1: *Why XGBoost rather than a neural network or LSTM?*  
A: 7 750 training rows is too few for a neural network to outperform gradient boosting on tabular data. Published benchmarks (Grinsztajn et al. 2022) confirm tree-based models consistently beat neural networks on datasets of this scale.

Q2: *Why is MAPE 9.7% and not lower?*  
A: The dataset has genuine stochastic noise — demand is simulated as a Poisson-like process. A MAPE of ~10% on weekly data is consistent with published retail forecasting benchmarks.

Q3: *Why not use the test-set split for training as well, to improve accuracy?*  
A: The test set must remain unseen to give an honest estimate of real-world performance. Reusing it would inflate the MAPE metric.

---

### 3.5 Customer segmentation

**Purpose:** Group customers into 4 behavioural segments based on Recency, Frequency, and Monetary value.

**Inputs:** `sales` and `customer` tables in MySQL. Snapshot date: 2025-01-01 (day after the last sales date).

**Outputs:** `customer_rfm_segment` table (1 000 rows); `segment_summary` table (4 rows); `data/segmentation/customer_segments.csv`.

**Key files:** `segmentation/run_segmentation.py`, `segmentation/rfm.py`, `segmentation/clustering.py`, `segmentation/labeling.py`.

**Results:**

| Segment | Customers | Revenue share |
|---|---|---|
| high_value | 160 (16%) | 40.1% |
| regular | 346 (34.6%) | 43.4% |
| occasional | 293 (29.3%) | 12.8% |
| at_risk | 201 (20.1%) | 3.8% |

Silhouette score = 0.857. Ground-truth ARI = 1.0 (perfect match).

**Why recency is excluded from clustering:** All 1 000 customers purchased within the last 23 days of the dataset. Recency has near-zero variance, so it adds noise rather than signal. The code detects this automatically in `clustering.py` `recency_is_informative()` and logs `[FLAG]` if recency is excluded.

**Known limitation:** K=4 is fixed. The elbow and Silhouette agree on k=4 for this dataset, but a different dataset might call for more clusters.

**Likely examiner questions:**

Q1: *Why K-Means rather than DBSCAN or hierarchical clustering?*  
A: K-Means is interpretable (centroids have business meaning), scales to 1 000 customers without issue, and the business requirement is exactly 4 segments (high-value, regular, occasional, at-risk).

Q2: *How do you choose k=4?*  
A: The Silhouette score peaks at k=4 (0.857). The elbow plot also shows a bend at k=4. Both methods agree.

Q3: *What does ARI 1.0 mean and why is it suspicious?*  
A: ARI = 1.0 means the K-Means clusters match the true segments perfectly. This is expected for a synthetic dataset where the four segments have non-overlapping purchase-rate distributions (high_value rate=0.4, at_risk rate=0.03). In real data, ARI of 0.6–0.8 would be a good result.

---

### 3.6 Price elasticity

**Purpose:** Estimate how sensitive each product's demand is to price changes.

**Inputs:** Daily `sales` and `price` tables, aggregated to weekly.

**Outputs:** `product_elasticity` table (50 rows); `data/elasticity/product_elasticity.csv`.

**Key files:** `pricing/estimate_elasticity.py`, `pricing/elasticity_model.py`, `pricing/elasticity_data.py`.

**Model:** Log-log OLS: `log(units_sold) = a + b × log(price) + c × promo_days + d × festival_week + ε`. The coefficient `b` is the elasticity estimate.

**Results summary:**
- All 50 products have negative elasticity (correct direction: 100%)
- Mean absolute error vs true values: 0.062 (from `docs/results.md`)
- Elasticity range: −0.41 (P010, Staples) to −2.54 (P042, Impulse)
- All 50 products have `reliable_flag = 1`

**Likely examiner questions:**

Q1: *Why log-log rather than a level regression?*  
A: The log-log model gives a constant elasticity coefficient directly. The level model (`units = a + b × price`) would give a coefficient with units of "units per £", which varies by price level and is harder to interpret or compare across products.

Q2: *What makes an elasticity estimate "unreliable"?*  
A: `pricing/constraints.py` `check_elasticity_reliable()` flags a product as unreliable if the confidence interval spans zero (sign uncertainty) or if the R² is below 0.3. All 50 products pass these checks in the current data.

Q3: *The true elasticity for P001 is stored in `revenue_management_gt`. What is it, and how close are you?*  
A: VERIFY by running: `SELECT true_elasticity FROM revenue_management_gt.gt_product_elasticity WHERE product_id='P001'`. The estimated value is −0.4676. The mean absolute error across all products is 0.062.

---

### 3.7 Pricing optimisation

**Purpose:** For each product, find the price that maximises expected weekly revenue subject to business constraints.

**Inputs:** `product_elasticity`, `pricing_candidates`, `forecast_features` (for next-week features), `sales`/`stock` tables; `production_model.joblib`.

**Outputs:** `pricing_candidates` table (1 550 rows = 50 products × 31 price steps); `pricing_recommendation` table (50 rows).

**Key files:** `pricing/run_pricing.py`, `pricing/build_candidates.py`, `pricing/candidates.py`, `pricing/constraints.py`, `pricing/optimizer.py`, `pricing/revenue.py`, `pricing/pricing_config.py`.

**Algorithm:**
1. Generate a grid of 31 candidate prices per product: current price ±15% in 1% steps.
2. For each candidate, apply four constraints: minimum margin (≥10%), maximum price change (≤15%), price must stay within the product's historical price range, elasticity must be reliable.
3. For each passing candidate, compute `expected_demand = baseline_demand × (p/p0)^elasticity` and `expected_revenue = expected_demand × p`.
4. Select the candidate with the highest `expected_revenue`. Tie-break: smallest price change.

**Key parameters (from `pricing_config.py`):**
- `MIN_MARGIN_PCT = 0.10` (10%)
- `MAX_PRICE_CHANGE_PCT = 0.15` (15%)
- `PRICE_STEP_PCT = 0.01` (1%)
- Unit cost = `base_price × COST_RATIO[category]` (Staples 70%, Electronics 75%, Clothing 45%)

**Results summary:**
- 34 products recommended a price RAISE, 13 a CUT, 3 held at current (PRICE_RANGE binding)
- Expected total weekly revenue: +7.9%
- 48/50 decisions match the true-elasticity optimum direction

**Likely examiner questions:**

Q1: *Why use elasticity scaling rather than asking XGBoost directly for each candidate price?*  
A: XGBoost was trained on historical prices within a narrow range. Asking it to predict at prices outside that range would be extrapolation — the model has no reliable signal there. Elasticity scaling is an economic model that is explicitly justified for this purpose. Both methods are actually computed (see `run_pricing.py` "Diagnostic" section) and the mean gap between them is printed.

Q2: *Why is the margin constraint 10%?*  
A: It is a business parameter, not derived from data. It reflects a typical retail minimum margin floor. It is hardcoded in `pricing_config.py` and should be made configurable for a production system.

Q3: *What is `TIE_TOLERANCE` in the binding constraint?*  
A: When two candidate prices produce revenues within 0.001 of each other, the tie-break rule (smallest price change) is applied. The `binding_constraint` is set to `TIE_TOLERANCE` to indicate the recommendation was driven by the tie-break, not a hard constraint. (Note: this is not documented in `docs/api.md` — see known-issues.md KI-01.)

---

### 3.8 LLM explanation layer

**Purpose:** Generate a one-sentence natural-language explanation for each pricing recommendation and each customer segment.

**Inputs:** `pricing_recommendation` and `segment_summary` tables.

**Outputs:** `llm_explanation` table (54 rows: 50 pricing + 4 segment); `data/explanations/llm_explanations.csv`.

**Key files:** `explanations/generate_explanations.py`, `explanations/guardrails.py`, `explanations/payloads.py`, `explanations/prompts.py`, `explanations/fallback.py`, `explanations/llm_client.py`.

**Algorithm:**
1. Build a structured payload dict from the recommendation (e.g. `{"action": "raise", "price_change": "14.9%", ...}`).
2. Send the payload + a system prompt to the LLM (Gemini or mock).
3. Run guardrail check: extract all numbers from the LLM output and verify each one appears in the payload. Any new number triggers rejection.
4. On rejection, retry up to `MAX_RETRIES` times. After all retries fail, use a template fallback sentence.

**Why this design?** The guardrail prevents the LLM from inventing or mis-stating numbers. This is the core safety requirement (REQ-21). The fallback ensures the system always produces an explanation without needing the API key.

**Known limitation:** The guardrail is string-based, not semantic. "7.0%" and "7%" are treated as the same number; "£57.70" and "57.70" must both appear in the payload or the check fails. This led to many fallbacks in the current run (source = "fallback" for 38 of 54 explanations).

**Likely examiner questions:**

Q1: *What stops the LLM from making up numbers?*  
A: `guardrails.py` `check_output()` extracts every decimal number from the LLM text and checks it against the payload dict. If any number in the text does not appear in the payload, the explanation is rejected and re-tried. The system prompt also explicitly instructs the LLM to only use numbers from the payload.

Q2: *What is the difference between "llm", "fallback", and "mock"?*  
A: `llm` = a genuine LLM response that passed the guardrail check. `fallback` = all retries failed the guardrail; a template sentence was used instead. `mock` = `LLM_PROVIDER=mock` in `.env`, meaning no API call was made and a canned response was returned.

Q3: *Why not run explanations as part of the main pipeline?*  
A: Explanations require either an API key (cost and latency) or a mock. They are not needed for the core analytical outputs and can be regenerated independently without rerunning the whole pipeline.

---

### 3.9 Flask API

**Purpose:** Serve all pipeline outputs as a REST API consumed by the Angular dashboard.

**Inputs:** MySQL `revenue_management` database tables.

**Outputs:** JSON responses on `http://localhost:5000`.

**Key files:** `backend/app.py`, `backend/config.py`, `backend/db.py`, `backend/routes/forecast.py`, `backend/routes/segments.py`, `backend/routes/pricing.py`, `backend/routes/explanations.py`.

**All endpoints (from `docs/api.md`):**
- `GET /api/health`
- `GET /api/products[?category=...]`
- `GET /api/forecast/metrics`
- `GET /api/forecast/<product_id>`
- `GET /api/segments`
- `GET /api/segments/customers[?segment=...&page=...&page_size=...]`
- `GET /api/customers/<customer_id>/segment`
- `GET /api/pricing/<product_id>`
- `GET /api/pricing/recommendations[?category=...&page=...&page_size=...]`
- `GET /api/pricing/<product_id>/explanation`
- `GET /api/segments/<segment_label>/explanation`

**Likely examiner questions:**

Q1: *How does the API serve forecast predictions without rerunning the model?*  
A: The model artifact (`production_model.joblib`) is loaded once at startup in `app.py`. The `forecast` blueprint's `GET /api/forecast/<product_id>` endpoint reads the feature rows for the test window from the `forecast_features` table and calls `model.predict()` on those rows. The model is in memory for the lifetime of the server process.

Q2: *Why is `revenue_change_abs` not in the database?*  
A: It is a derived field: `expected_revenue - current_revenue`. Computing it server-side avoids storing a value that is redundant with the two stored values. See known-issues.md KI-07.

---

### 3.10 Angular dashboard

**Purpose:** Display all pipeline outputs in an interactive browser UI.

**Key files:** All under `frontend/src/app/`.

**Architecture:** Angular 21, standalone components, signals for state, lazy-loaded routes. No state-management library. All HTTP goes through `ApiService` (`core/api.service.ts`).

**Views:** Forecast (`/forecast`), Segments (`/segments`), Pricing (`/pricing`).

**Likely examiner questions:**

Q1: *How do you prevent stale data from appearing when switching products quickly?*  
A: `pricing.component.ts` maintains separate `recToken` and `expToken` counters. Each product selection increments both counters. A subscriber only writes to the signal if its captured token still equals the current counter — older in-flight responses are silently discarded.

Q2: *How do you prevent the LLM explanation from blocking the price numbers?*  
A: The recommendation HTTP call and the explanation HTTP call are fired as separate subscriptions. The numbers render as soon as the recommendation response arrives, independently of the explanation response. The explanation panel shows a loading spinner until its own response arrives.

---

## 4. Decision log

| Decision | Why |
|---|---|
| **Synthetic data with hidden ground truth** | Public retail datasets (M5, Kaggle retail) have no controlled price variation or known true elasticities. Without ground truth we cannot validate elasticity estimation or measure segmentation accuracy. The synthetic approach is standard in simulation-based ML evaluation. |
| **XGBoost with Linear Regression baseline** | XGBoost is the dominant algorithm for tabular regression at this data scale (7 700 rows). Linear Regression is a meaningful baseline because it is the simplest interpretable model. A neural network would underfit on this dataset size. |
| **K-Means for segmentation** | Business requirement is 4 named segments. K-Means is interpretable (centroids are the "average customer" in each group), fast, and well-understood. DBSCAN would not produce exactly 4 clusters, and hierarchical clustering is harder to update incrementally. |
| **Log-log OLS for elasticity** | Standard econometric approach for price elasticity. The log-log form gives a constant-elasticity coefficient directly and is stable under log-normal demand noise. |
| **LLM explains only, never computes** | REQ-21: the LLM must not introduce new numbers. The guardrail enforces this strictly. If the LLM were allowed to re-derive numbers it might produce plausible but incorrect values, which a manager might act on. Restricting it to rephrasing numbers it is given prevents this. |
| **No deep learning or reinforcement learning** | The dataset is too small (1 000 customers, 50 products, 3 years) for deep learning to reliably outperform XGBoost. Reinforcement learning would require a live feedback loop that doesn't exist. Both are reasonable extensions for a production system. |

---

## 5. "Looks fine but hard to defend"

These are things an examiner is likely to probe.

**5.1 "Your silhouette score of 0.857 is suspiciously high."**  
It is high because the synthetic customer segments have non-overlapping purchase-rate distributions (0.40 vs 0.20 vs 0.07 vs 0.03). In real retail data the segments blur together. The ARI of 1.0 confirms this is a property of the dataset, not the algorithm.

**5.2 "You only use 3 lag features. What about seasonality lags (e.g. lag_52)?"**  
True. The data covers 3 years, which would allow a 52-week lag. We chose 3 lags to keep the model simple and explainable. The calendar features (month_sin/cos, seasonal_factor) partially substitute for seasonal lags.

**5.3 "The pricing decisions match the true elasticity 48/50 times. The two failures — what are they?"**  
The two exceptions are products whose current price already breaks the margin floor. The optimiser must raise the price to restore the margin, even though the true elasticity says cut. This is not a failure of estimation — it is the constraint overriding the signal. See `run_pricing.py` "Corner-solution check".

**5.4 "How do you know unit_cost = 70% of base_price for Staples is correct?"**  
We don't. There is no cost table in the dataset. The ratio is a calibrated assumption that produces realistic margin percentages for the category. In a real system, actual purchase order costs would replace this.

**5.5 "Your LLM fallback rate is high (38/54 explanations are fallbacks)."**  
The guardrail is strict: any number in the output that doesn't appear in the payload is rejected. The LLM frequently re-rounds or reformats numbers (e.g. "14.9%" becomes "15%"). The fallback template still produces a correct, readable explanation — it just loses the LLM's phrasing.

**5.6 "Why not deploy to AWS / use Docker?"**  
This is a final-year undergraduate project scoped for demonstration, not production. Containerisation and cloud deployment are Phase 14+ extensions. The architecture (Flask API, Angular SPA, MySQL) is standard and straightforward to containerise with docker-compose.
