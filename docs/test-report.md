# Phase 13 — Test Report

This report inventories the automated test suites, documents the gaps filled
in Phase 13, lists remaining gaps, and gives the exact commands to run every
suite. Test counts are the number of `def test_` functions (Python) or `it(`
calls (Angular) counted in the repository; conftest/`__init__` files hold
shared fixtures only and are listed for completeness with a count of 0.

---

## 1. Test inventory

### Data-pipeline suite — `data-pipeline/tests/` (pytest)

| File | Scope | Test count | Framework | Command |
|---|---|---|---|---|
| `tests/test_elasticity.py` | OLS elasticity recovery, reliability flags, determinism, GT isolation | 7 | pytest | `cd data-pipeline && python -m pytest tests/test_elasticity.py -v` |
| `tests/test_explanations.py` | Guardrails (numbers/direction/length/jargon), payload builders, explain_one retry/fallback, API error, GT isolation | 17 | pytest | `cd data-pipeline && python -m pytest tests/test_explanations.py -v` |
| `tests/test_pricing_constraints.py` | Margin, max-change, price-range, elasticity-reliable, candidate grid, apply_constraints | 11 | pytest | `cd data-pipeline && python -m pytest tests/test_pricing_constraints.py -v` |
| `tests/test_pricing_optimizer.py` | Elasticity-scaled demand, revenue/stock cap, inelastic→upper/elastic→lower bound, binding constraint, tie-break, calendar, GT isolation | 13 | pytest | `cd data-pipeline && python -m pytest tests/test_pricing_optimizer.py -v` |
| `tests/test_segmentation.py` | Recency rule, clustering features, k-search, labels, determinism, GT isolation | 8 | pytest | `cd data-pipeline && python -m pytest tests/test_segmentation.py -v` |
| `tests/test_phase13_temporal_split.py` | (Phase 13) Time-split no-overlap + match to metadata | 2 | pytest | `cd data-pipeline && python -m pytest tests/test_phase13_temporal_split.py -v` |
| `tests/test_phase13_lag_leakage.py` | (Phase 13) Phase 4 lag-leakage check as a pytest | 1 | pytest | `cd data-pipeline && python -m pytest tests/test_phase13_lag_leakage.py -v` |
| `tests/test_phase13_gt_isolation.py` | (Phase 13) Ground-truth isolation across all app packages | 1 | pytest | `cd data-pipeline && python -m pytest tests/test_phase13_gt_isolation.py -v` |
| `tests/test_phase13_pricing_compliance.py` | (Phase 13) All stored recommendations satisfy constraints; all elasticities negative | 2 | pytest | `cd data-pipeline && python -m pytest tests/test_phase13_pricing_compliance.py -v` |
| `tests/test_phase13_etl_idempotency.py` | (Phase 13) Row-count stability, core table counts, no duplicate product_ids | 3 | pytest | `cd data-pipeline && python -m pytest tests/test_phase13_etl_idempotency.py -v` |
| `tests/conftest.py` | Shared fixtures | 0 | pytest | — |

**Data-pipeline subtotal: 65 test functions** across 10 test files.

### Backend suite — `backend/tests/` (pytest)

| File | Scope | Test count | Framework | Command |
|---|---|---|---|---|
| `tests/test_api.py` | Phase 10a endpoints: health, products, forecast/metrics, forecast/P001, segments, customer segment, GT isolation in responses, model loaded once | 39 | pytest | `cd backend && python -m pytest tests/test_api.py -v` |
| `tests/test_pricing_api.py` | Phase 10b pricing endpoints: single product, list pagination/filter, GT isolation | 24 | pytest | `cd backend && python -m pytest tests/test_pricing_api.py -v` |
| `tests/test_explanation_api.py` | Explanation endpoints: pricing, forecast (unsupported), segment, 404s, graceful failure, payload number consistency | 23 | pytest | `cd backend && python -m pytest tests/test_explanation_api.py -v` |
| `tests/test_phase13_api_contract.py` | (Phase 13) KI-01 contract: binding_constraint values valid incl. TIE_TOLERANCE | 1 | pytest | `cd backend && python -m pytest tests/test_phase13_api_contract.py -v` |
| `tests/conftest.py`, `tests/__init__.py` | Shared fixtures / package marker | 0 | pytest | — |

**Backend subtotal: 87 test functions** across 4 test files.

### Frontend suite — `frontend/src/` (Jasmine / Karma)

| File | Scope | Test count | Framework | Command |
|---|---|---|---|---|
| `app/app.spec.ts` | App bootstrap | — | Jasmine/Karma | `cd frontend && npx ng test --watch=false` |
| `app/core/tests/api.service.spec.ts` | API service | — | Jasmine/Karma | as above |
| `app/core/tests/api-pricing.service.spec.ts` | Pricing API service | — | Jasmine/Karma | as above |
| `app/features/pricing/pricing.component.spec.ts` | Pricing component | — | Jasmine/Karma | as above |
| `app/features/pricing/recommendation-card.spec.ts` | Recommendation card | — | Jasmine/Karma | as above |
| `app/features/pricing/recommendations-table.spec.ts` | Recommendations table | — | Jasmine/Karma | as above |
| `app/shared/tests/explanation-panel.spec.ts` | Explanation panel | — | Jasmine/Karma | as above |
| `app/shared/tests/loading-state.spec.ts` | Loading state | — | Jasmine/Karma | as above |
| `app/shared/tests/segment-color.spec.ts` | Segment colour pipe | — | Jasmine/Karma | as above |
| `app/shared/tests/stat-tile.spec.ts` | Stat tile | — | Jasmine/Karma | as above |

**Frontend subtotal: 76 `it()` specs across 10 spec files** (counted in the
repository). Framework: Jasmine run via Karma (`npx ng test`).

### Evaluation scripts — `evaluation/` (not pytest; standalone runner)

The six evaluation scripts are invoked through `evaluation/run_evaluation.py`
(areas: `forecasting`, `segmentation`, `elasticity`, `pricing`, `llm_layer`,
`system_performance`). They are **measure-only** scripts, not tests, and are
never imported by application code.

---

## 2. Gaps filled in Phase 13

Six new test files were added (no existing test or application file was
modified). They close the gaps identified in the Phase 13 test-gap analysis:

1. **`data-pipeline/tests/test_phase13_temporal_split.py`** (2 tests) —
   Gap: temporal split no-overlap was only an `assert` in source, not a
   pytest. Fills it: `test_time_split_no_overlap` asserts
   `split.train_end < split.test_start` on the real `forecast_features.csv`,
   and `test_time_split_matches_metadata` asserts the split dates/counts match
   `metadata.json`. CSV-only, runs without a DB.
2. **`data-pipeline/tests/test_phase13_lag_leakage.py`** (1 test) —
   Gap: the Phase 4 `_run_leakage_test` only ran during the pipeline, not as a
   pytest. Fills it: loads weekly aggregates and the feature CSV, calls
   `_run_leakage_test`, asserts it passes. Requires a live DB.
3. **`data-pipeline/tests/test_phase13_gt_isolation.py`** (1 test) —
   Gap: existing GT-isolation greps covered `pricing/`, `segmentation/`,
   `explanations/` but not `etl/`, `features/`, `models/`, or `backend/`.
   Fills it: greps all app packages for ground-truth identifiers and asserts
   no violations outside the documented allowlist. Static, runs without a DB.
4. **`data-pipeline/tests/test_phase13_pricing_compliance.py`** (2 tests) —
   Gap: constraint functions were unit-tested, but no pytest looped over all
   50 stored recommendations from the DB. Fills it:
   `test_all_stored_recommendations_satisfy_constraints` (zero margin/max-change
   violations) and `test_all_recommendations_have_negative_elasticity`.
   Requires a live DB.
5. **`data-pipeline/tests/test_phase13_etl_idempotency.py`** (3 tests) —
   Gap: no test for ETL idempotency. Fills it:
   `test_forecast_features_row_count_stable`, `test_core_table_row_counts_nonzero`
   (product=50, customer=1000, product_elasticity=50, customer_rfm_segment=1000),
   `test_no_duplicate_product_ids_in_pricing_recommendation`. Requires a live
   DB.
6. **`backend/tests/test_phase13_api_contract.py`** (1 test) —
   Gap (KI-01): `TIE_TOLERANCE` is a valid `binding_constraint` value that
   `api.md` omits. Fills it:
   `test_binding_constraint_includes_tie_tolerance` asserts every
   `binding_constraint` returned by `/api/pricing/recommendations` is in the
   known-valid set including `TIE_TOLERANCE`. Requires the Flask app + DB.

---

## 3. Remaining gaps

- **DB-dependent Phase 13 tests skip in environments without DB credentials.**
  `test_phase13_lag_leakage.py`, `test_phase13_pricing_compliance.py`,
  `test_phase13_etl_idempotency.py`, and `backend/test_phase13_api_contract.py`
  are marked `skipif(not DB credentials)`. They collect cleanly and run (and
  are expected to pass) for a full-stack team with the populated database; in
  the Phase 13 sandbox (no `data-pipeline/.env`) they skip with reason
  "requires live MySQL + DB credentials". The two CSV/static tests
  (`test_phase13_temporal_split.py`, `test_phase13_gt_isolation.py`) pass
  without a DB.
- **Full existing-suite regression run.** Phase 13 added files only (no
  existing test or application file changed), so no regression is introduced;
  a complete `pytest tests/ -v` pass across both suites was not executed in
  the Phase 13 sandbox because the sandbox venv lacks the full dependency set
  (xgboost native library, Flask, etc.) and the DB. This is an environment
  constraint, not a coverage gap.
- **Live LLM numeric consistency and latency** are covered by evaluation
  scripts (`evaluation/llm_layer_eval.py` with `--with-llm`), not by pytest,
  because they require a paid LLM API key. The guardrail *logic* is covered by
  `test_explanations.py`.
- **KI-09** documents that three ETL/validation files legitimately reference
  ground-truth fields and are on the `test_phase13_gt_isolation.py`
  allowlist; this is a documented exception, not an open gap.

---

## 4. How to run all tests

```bash
# Data-pipeline suite (requires data-pipeline/.env DB credentials for DB tests;
# CSV/static tests pass without)
cd /Users/kanishkbagzai/Revenue-Management-Project/revenue-management-project/data-pipeline
python -m pytest tests/ -v

# Backend suite (requires DB + model artifacts for most tests)
cd /Users/kanishkbagzai/Revenue-Management-Project/revenue-management-project/backend
python -m pytest tests/ -v

# Frontend suite (single-run; --watch=false avoids the Karma watcher)
cd /Users/kanishkbagzai/Revenue-Management-Project/revenue-management-project/frontend
npx ng test --watch=false

# Phase 13 evaluation scripts (measure-only; read-only DB; optional --with-llm)
cd /Users/kanishkbagzai/Revenue-Management-Project/revenue-management-project
python evaluation/run_evaluation.py --list
python evaluation/run_evaluation.py                       # all areas (LLM off)
python evaluation/run_evaluation.py --only forecasting    # one area
python evaluation/run_evaluation.py --with-llm            # enable paid LLM checks
```

Individual Phase 13 test files:

```bash
cd /Users/kanishkbagzai/Revenue-Management-Project/revenue-management-project/data-pipeline
python -m pytest tests/test_phase13_temporal_split.py tests/test_phase13_lag_leakage.py \
  tests/test_phase13_gt_isolation.py tests/test_phase13_pricing_compliance.py \
  tests/test_phase13_etl_idempotency.py -v

cd /Users/kanishkbagzai/Revenue-Management-Project/revenue-management-project/backend
python -m pytest tests/test_phase13_api_contract.py -v
```
