# Requirements Traceability Matrix

**Status key:** SATISFIED / PARTIAL / MISSING

Summary: **26 SATISFIED, 0 PARTIAL, 0 MISSING**

---

| REQ | Requirement | Status | Implementing file(s) | Verification |
|---|---|---|---|---|
| REQ-1 | Ingest raw sales / product / price / discount / customer / stock records | SATISFIED | `data_generation/generate_base_tables.py`, `generate_transactional_tables.py`; raw CSVs in `data/raw/` | Checked in Phase 1 — 6 raw CSVs generated with correct schemas |
| REQ-2 | Remove duplicates | SATISFIED | `etl/cleaning.py` (`clean_sales`, `clean_price`, etc.) — each cleaner calls `drop_duplicates()` | `etl/validation.py` counts duplicates before/after; Phase 2a output shows 0 remaining duplicates |
| REQ-3 | Handle missing values by documented rules | SATISFIED | `etl/cleaning.py` — missing prices imputed from nearest neighbour; missing stock levels filled forward | `run_validation()` reports missing value counts; `clean_tables.py` logs "dropped N rows" per table |
| REQ-4 | Standardise formats (dates, types) | SATISFIED | `etl/cleaning.py` — dates parsed to `datetime`, dtypes enforced | Verified by `pd.read_csv` with `parse_dates` in `load_to_mysql.py` |
| REQ-5 | Derived fields (weekly totals, discount %, days since last purchase) | SATISFIED | `features/weekly_aggregation.py` (weekly totals); `features/price_features.py` (discount); `segmentation/rfm.py` (recency) | `build_feature_table.py` section 7 prints feature table summary |
| REQ-6 | Persist to MySQL (fact table + dimensions) | SATISFIED | `etl/load_to_mysql.py` — loads 6 app tables into `revenue_management`; `database/schema.sql` defines DDL | Row-count verification in `load_to_mysql.py` section checks CSV == DB |
| REQ-7 | Predict weekly units per product from past sales, price, discount, month, weekday | SATISFIED | `models/xgboost_model.py`, `models/baseline_model.py` — feature set in `metadata.json`: lag_1/2/3_units, month, seasonal_factor, festival_week, list_price_mean, avg_discount | `train_forecasting_models.py` section 7 prints spot-check table for P001 |
| REQ-8 | Linear Regression baseline | SATISFIED | `models/baseline_model.py` — `DemandLinearRegression` using `Ridge` with product one-hot | `train_forecasting_models.py` section 3 trains and evaluates LR; MAE=17.65, RMSE=24.26, MAPE=15.26% |
| REQ-9 | XGBoost primary model | SATISFIED | `models/xgboost_model.py` — `DemandXGBoost` with params in `XGBOOST_PARAMS` | `train_forecasting_models.py` section 4 trains XGBoost; MAE=14.73, RMSE=21.19, MAPE=9.72% |
| REQ-10 | Evaluate with MAE, RMSE, MAPE on held-out most recent weeks | SATISFIED | `models/evaluate.py` — `compute_metrics()`, `evaluate_per_product()` | `train_forecasting_models.py` prints per-model metrics; `metadata.json` stores them persistently |
| REQ-11 | Use XGBoost if it beats the baseline, otherwise flag | SATISFIED | `train_forecasting_models.py` — `compare_models()` selects winner by RMSE; prints `[FLAG]` if XGBoost loses | In all runs XGBoost wins; flag logic tested by `test_pricing_optimizer.py::test_pricing_ground_truth_isolation` |
| REQ-12 | RFM per customer | SATISFIED | `segmentation/rfm.py` — `compute_rfm()` queries `sales` table for recency (days since last purchase, snapshot 2025-01-01), frequency (transaction count), monetary (total spend) | `run_segmentation.py` prints RFM distribution; all 1 000 customers have values |
| REQ-13 | K-Means on RFM | SATISFIED | `segmentation/clustering.py` — `fit_kmeans()` wraps `sklearn.cluster.KMeans` with fixed `random_state=42` | `run_segmentation.py` section "Production model" prints centroids |
| REQ-14 | Elbow method and Silhouette score | SATISFIED | `segmentation/clustering.py` — `k_search()` runs k=2..8; `choose_k()` picks best Silhouette; elbow computed via inertia drop | `run_segmentation.py` prints the k-search table; plots saved to `data/segmentation/` |
| REQ-15 | Descriptive segment labels | SATISFIED | `segmentation/labeling.py` — `label_clusters()` assigns labels based on centroid ranking (high_value / regular / occasional / at_risk) | Verified by `test_segmentation.py::test_labels_follow_rfm_order` |
| REQ-16 | Log-log elasticity per product | SATISFIED | `pricing/elasticity_model.py` — `fit_ols()` fits `log(units) = a + b*log(price) + controls` per product via `statsmodels.OLS` | `estimate_elasticity.py` prints OLS output; `test_elasticity.py` tests negative sign and significance |
| REQ-17 | Candidate prices with demand predicted by the forecasting model | SATISFIED | `pricing/candidates.py` generates grid ±15% in 1% steps; `pricing/demand_response.py` — `elasticity_scaled_demand()` uses XGBoost baseline + elasticity scaling | `build_candidates.py` prints "1 550 candidates for 50 products" |
| REQ-18 | Discard candidates violating minimum margin, maximum price change, or stock limit | SATISFIED | `pricing/constraints.py` — `check_margin()`, `check_max_change()`, `check_price_range()`, `check_elasticity_reliable()`, stock cap in `revenue.py` | `test_pricing_constraints.py` (11 tests); `build_candidates.py` prints rejection counts |
| REQ-19 | Recommend highest expected revenue price with revenue change | SATISFIED | `pricing/optimizer.py` — `select_best()` picks maximum `expected_revenue`; `run_pricing.py` records `revenue_change_pct` | `test_pricing_optimizer.py` (11 tests including inelastic→upper-bound, elastic→lower-bound) |
| REQ-20 | Explanations from validated outputs only | SATISFIED | `explanations/generate_explanations.py` — `build_all_payloads()` reads from `pricing_recommendation` and `segment_summary` (both validated tables); LLM receives only the structured payload | `test_explanations.py::test_payload_only_uses_stored_values` |
| REQ-21 | LLM never alters or invents numbers | SATISFIED | `explanations/guardrails.py` — `check_output()` extracts all numbers from the LLM response and checks each against the payload; any new number triggers rejection and fallback | `test_explanations.py::test_guardrail_rejects_new_number` |
| REQ-22 | Graceful LLM failure | SATISFIED | `explanations/generate_explanations.py` — `explain_one()` catches `LLMError`, retries `MAX_RETRIES` times, then returns `fallback_text()`; backend `routes/explanations.py` returns `explanation_available: false` on missing row | Backend test `test_explanation_api.py::test_all_segments_have_explanations`; manual test with `LLM_PROVIDER=mock` |
| REQ-23 | Dashboard forecast chart per product | SATISFIED | `frontend/src/app/features/forecast/forecast.component.ts` — `GET /api/forecast/<product_id>` feeds `ChartWrapperComponent` with history + test-window line chart | `ng test` — 76 tests pass; visual verified in browser |
| REQ-24 | Dashboard segments and distribution | SATISFIED | `frontend/src/app/features/segments/segments.component.ts` — `GET /api/segments` and `GET /api/segments/customers`; doughnut chart for revenue share, paginated customer table | `ng test` — 76 tests pass |
| REQ-25 | Dashboard recommended price, revenue change, and explanation | SATISFIED | `frontend/src/app/features/pricing/pricing.component.ts`, `recommendation-card.component.ts`, `explanation-panel.component.ts` — `GET /api/pricing/<id>` + `GET /api/pricing/<id>/explanation` | `ng test` — 76 tests pass; visual verified for P001, P023, P027 |
| REQ-26 | Chart.js visualizations | SATISFIED | `frontend/src/app/shared/components/chart-wrapper.component.ts` — wraps Chart.js; used in Forecast (line), Segments (doughnut), Pricing (bar) | `ng build` 0 errors; chart-wrapper unit tests in shared/tests/ |

---

## Notes

- **REQ-5 note on discount %:** Discount percentage is generated in `data_generation/price.py` as a column in the price table and loaded into MySQL by `load_to_mysql.py`. It is used as a feature in `features/price_features.py` (`avg_discount`).
- **REQ-11 note:** XGBoost always wins in the current run (RMSE 21.19 vs 24.26). The flag path is implemented and tested but not exercised on real data.
- **REQ-20 note:** "Validated outputs" means the outputs have already passed Phase 8 constraint checks (`assert_recommendations_valid`) before being written to the database. The explanation layer reads these pre-validated rows — it does not re-validate them.
