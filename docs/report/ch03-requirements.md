# Chapter 3 — Requirements Analysis

## 3.1 User Classes

Three user classes interact with the system:

1. **Retail Manager.** Views the Angular dashboard, reads LLM-generated plain-English explanations of pricing recommendations and customer segment profiles, and acts on the recommended prices. The Retail Manager does not run scripts or interact directly with the database.

2. **Data Analyst.** Runs the pipeline scripts (data generation, ETL, feature engineering, model training, segmentation, elasticity estimation, pricing optimisation, explanation generation) from the command line, reads evaluation output in `evaluation/results/`, and interprets the metrics produced by each module.

3. **System Administrator.** Deploys the MySQL database (schema in `database/schema.sql`), starts the Flask backend and Angular frontend servers, manages database credentials in `data-pipeline/.env`, and ensures the runtime dependencies (Python 3.10–3.12, Node.js 22 LTS) are correctly installed.

## 3.2 Functional Requirements

All 26 functional requirements are SATISFIED (source: `/docs/traceability.md`). The table below summarises each requirement, grouped by feature area. Requirement texts are taken verbatim or summarised to ≤25 words from the traceability matrix; REQ numbers are exact.

### Data Pipeline (REQ-1 to REQ-6)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-1 | Ingest raw sales, product, price, discount, customer, and stock records. | SATISFIED |
| REQ-2 | Remove duplicate rows from all ingested tables. | SATISFIED |
| REQ-3 | Handle missing values by documented rules (e.g., nearest-neighbour price imputation, forward-fill for stock). | SATISFIED |
| REQ-4 | Standardise formats: dates to `datetime`, column types enforced. | SATISFIED |
| REQ-5 | Derive weekly totals, discount percentage, and days since last purchase as engineered features. | SATISFIED |
| REQ-6 | Persist cleaned and transformed data to MySQL (fact table and dimensions). | SATISFIED |

### Demand Forecasting (REQ-7 to REQ-11)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-7 | Predict weekly units per product from past sales, price, discount, month, and weekday features. | SATISFIED |
| REQ-8 | Implement a Linear Regression baseline model for demand forecasting. | SATISFIED |
| REQ-9 | Implement XGBoost as the primary demand forecasting model. | SATISFIED |
| REQ-10 | Evaluate both models with MAE, RMSE, and MAPE on the held-out most recent weeks. | SATISFIED |
| REQ-11 | Select XGBoost if it beats the baseline on RMSE; otherwise flag the result. | SATISFIED |

### Customer Segmentation (REQ-12 to REQ-15)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-12 | Compute RFM (Recency, Frequency, Monetary) values per customer from the sales table. | SATISFIED |
| REQ-13 | Apply K-Means clustering to the RFM features to segment customers. | SATISFIED |
| REQ-14 | Use the elbow method and silhouette score to select the number of clusters k. | SATISFIED |
| REQ-15 | Assign descriptive labels (high_value, regular, occasional, at_risk) to clusters based on centroid ranking. | SATISFIED |

### Price Elasticity (REQ-16)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-16 | Estimate per-product price elasticity using log-log OLS regression with controls for promotions, seasonality, and festivals. | SATISFIED |

### Pricing Optimisation (REQ-17 to REQ-19)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-17 | Generate candidate prices using demand predicted by the forecasting model. | SATISFIED |
| REQ-18 | Discard candidates violating minimum margin, maximum price change, stock limit, or price range constraints. | SATISFIED |
| REQ-19 | Recommend the candidate price with highest expected revenue; record the revenue change. | SATISFIED |

### LLM Explanation Layer (REQ-20 to REQ-22)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-20 | Generate explanations only from validated pipeline outputs; LLM receives only the structured payload. | SATISFIED |
| REQ-21 | LLM must never alter or introduce numbers not present in the payload; violations trigger fallback. | SATISFIED |
| REQ-22 | Handle LLM failure gracefully: retry, then return a pre-written fallback; never crash. | SATISFIED |

### Dashboard (REQ-23 to REQ-26)

| REQ | Requirement (summarised ≤25 words) | Status |
|---|---|---|
| REQ-23 | Display a forecast chart per product in the dashboard. | SATISFIED |
| REQ-24 | Display customer segment distribution and segment summaries in the dashboard. | SATISFIED |
| REQ-25 | Display the recommended price, expected revenue change, and LLM explanation in the dashboard. | SATISFIED |
| REQ-26 | Implement all dashboard charts using Chart.js. | SATISFIED |

## 3.3 Non-Functional Requirements

| ID | Non-Functional Requirement |
|---|---|
| NFR-1 | **Reproducibility.** Fixed random seeds (`RANDOM_SEED = 42` in `data_generation/config.py`; `RANDOM_STATE = 42` in `segmentation/clustering.py`) are applied in all stochastic steps so that results are reproducible across runs on the same machine. |
| NFR-2 | **Determinism.** Running the pipeline twice on the same machine produces identical rows in the MySQL application database. |
| NFR-3 | **API response time.** All GET endpoints must respond in under 500 ms. This requirement is validated by the backend test suite using a mock database fixture; actual database latency under production load has not been formally measured. |
| NFR-4 | **Test coverage.** All 26 functional requirements have at least one automated test (228 tests total across data-pipeline, backend, and frontend suites; source: `docs/test-report.md`). |
| NFR-5 | **Ground-truth isolation.** No application module reads the ground-truth database (`revenue_management_gt`). The evaluation layer is the only code that accesses ground-truth tables, and it does so in a read-only, evaluation-time-only context. |

## 3.4 Constraints

- **Python version.** Python 3.10–3.12 is required. Python 3.13 is not supported due to a NumPy 1.26 incompatibility (source: `README.md`).
- **Database.** MySQL 8.0. The schema is defined in `database/schema.sql`.
- **Frontend runtime.** Node.js 22 LTS. Angular CLI must be invoked via `npx ng` on a fresh clone (KI-08; source: `docs/known-issues.md`).
- **Deployment.** Single-machine deployment only. No distributed infrastructure, cloud services, or containerisation is required or provided.
- **Data.** Synthetic data only. No real customer personally identifiable information (PII) is used or stored.

## 3.5 Traceability Summary

All 26 functional requirements are recorded as SATISFIED in `/docs/traceability.md`. The traceability matrix maps each requirement to its implementing file(s) and to its verification evidence (automated test names, script output, and Phase 13 evaluation results where available).

The Phase 13 evaluation run could not re-measure several metrics due to environment constraints (absent database credentials and a missing XGBoost native library on the evaluation machine). These are environment-blocked re-measurements, not requirement failures: every metric that could be computed was consistent with its requirement, and the unmet measurement gaps are documented as KI-10 in `/docs/known-issues.md`. No REQ changed status as a result of the Phase 13 run.
