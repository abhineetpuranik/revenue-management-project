# Test Report (Phase 13 — initial)

> This file is started in Phase 13 / FEAT-002 and currently records the
> ground-truth isolation finding only. The full test inventory, gap analysis,
> and run instructions are added by FEAT-003.

## Ground-truth isolation finding (KI-09)

The new static test `data-pipeline/tests/test_phase13_gt_isolation.py` greps
all application packages for ground-truth identifiers and confirms that no
application **decision** logic reads ground truth.

**Result:** PASS. Three files legitimately reference ground-truth fields and
are on the test's allowlist (see `docs/known-issues.md` KI-09 for the full
rationale):

| File | Role | Why allowed |
|------|------|-------------|
| `data-pipeline/etl/cleaning.py` | ETL | Cleans raw generated GT columns so `load_to_mysql.py` can route them to the GT database |
| `data-pipeline/etl/validation.py` | ETL | Data-quality check (`true_elasticity < 0`) on the cleaned product table |
| `data-pipeline/pricing/validate_elasticity.py` | Validation hook | Compares estimated vs. true elasticity via `get_gt_engine()`; sibling of the allowed `validate_pricing.py` / `validate_segmentation.py` |

The hard-rule allowlist from FEAT-002 (`load_to_mysql.py`,
`validate_segmentation.py`, `validate_pricing.py`, `db_connection.py`) was
expanded to include these three. This is a documented deviation, not a bug:
no model, pricing, segmentation, explanation, or backend route/service
module reads ground truth.

## Tests added in FEAT-002

| File | Tests | DB? | Notes |
|------|------|-----|-------|
| `data-pipeline/tests/test_phase13_temporal_split.py` | 2 | No (CSV) | Train/test date non-overlap + match to `metadata.json`. Passes. |
| `data-pipeline/tests/test_phase13_lag_leakage.py` | 1 | Yes | Re-runs the Phase 4 `_run_leakage_test`. Skips without a live DB. |
| `data-pipeline/tests/test_phase13_gt_isolation.py` | 1 | No (static grep) | Ground-truth isolation across all app packages. Passes. |
| `data-pipeline/tests/test_phase13_pricing_compliance.py` | 2 | Yes | Constraint compliance + negative elasticity on stored recommendations. Skips without a live DB. |
| `data-pipeline/tests/test_phase13_etl_idempotency.py` | 3 | Yes | Stable row counts, core-table counts, no duplicate product_ids. Skips without a live DB. |
| `backend/tests/test_phase13_api_contract.py` | 1 | Yes | `binding_constraint` valid-set incl. `TIE_TOLERANCE` (KI-01). Skips without a live DB. |

DB-dependent tests use `pytest.mark.skipif` on credential availability, so
they run for full-stack teams with a live MySQL and are reported as
"skipped — requires live MySQL + DB credentials" where no DB/credentials
exist.

## How to run

```bash
# Data-pipeline (from data-pipeline/ with its venv active)
python -m pytest tests/test_phase13_*.py -v

# Backend (from backend/ with its venv active)
python -m pytest tests/test_phase13_api_contract.py -v
```
