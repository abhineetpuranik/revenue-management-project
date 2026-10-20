# AI-Powered Demand Forecasting and Dynamic Pricing

A final-year undergraduate project that forecasts weekly product demand, segments customers by behaviour, and recommends revenue-maximising prices — all explained in plain English by an LLM. A Flask REST API serves the results; an Angular dashboard displays them.

```
50 products  •  1 000 customers  •  3 years of daily sales  •  ~1.3 M transaction rows
XGBoost MAPE 9.7%  •  Segmentation ARI 1.0  •  Revenue uplift +7.9%
```

---

## Architecture (text diagram)

```
Synthetic dataset        ETL             Feature           Forecasting
generator          →  clean +   →   engineering    →   LR baseline +
(data_generation/)    load MySQL    (features/)         XGBoost  (models/)
                        ↓                                     ↓
                   MySQL                             model artifact
                   revenue_management         (models/artifacts/)
                        ↓                                     ↓
               Elasticity ←→ Segmentation ←→ Pricing ←→ Explanations
               (pricing/)    (segmentation/)  (pricing/) (explanations/)
                        ↓
                   Flask API  (backend/)
                        ↓
                 Angular dashboard  (frontend/)
```

---

## Quick start (30 seconds)

If you have already run the pipeline and have a populated database, or have restored the demo dump:

```bash
# Terminal 1 — start the backend
cd backend
python app.py
# -> http://localhost:5000/api/health  ->  {"status": "ok"}

# Terminal 2 — start the frontend
cd frontend
npm install
npx ng serve
# -> http://localhost:4200
```

---

## Full setup from scratch

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10 – 3.12 | 3.13 not supported (numpy 1.26 incompatibility) |
| MySQL | 8.0 | Server must be running before loading data |
| Node.js | 22 LTS | For the Angular frontend |
| mysqldump | 8.0 | For demo backups (ships with MySQL) |

### Step 1 — Clone and create the database schema

```bash
git clone <repo-url>
cd "Revenue Management"

# Create both schemas (drops any existing revenue_management databases)
mysql -u root -p < database/schema.sql
```

### Step 2 — Data-pipeline environment

```bash
cd data-pipeline

# Create and activate a virtual environment
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

# Copy and fill in credentials
copy .env.example .env     # Windows
cp .env.example .env       # macOS / Linux
```

Open `data-pipeline/.env` and set at minimum:
```
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
```

### Step 3 — Run the pipeline

From `data-pipeline/` with the venv active, either use the runner:

```bash
cd ..
python scripts/run_pipeline.py           # all 11 stages
python scripts/run_pipeline.py --list    # see what stages exist
python scripts/run_pipeline.py --from train_model  # resume from a stage
```

Or run stages manually (all commands from `data-pipeline/`):

```bash
python -m data_generation.generate_base_tables
python -m data_generation.generate_transactional_tables   # ~2 minutes
python -m etl.clean_tables
python -m etl.load_to_mysql
python -m features.build_feature_table
python -m models.train_forecasting_models
python -m pricing.estimate_elasticity
python -m segmentation.run_segmentation
python -m pricing.build_candidates
python -m pricing.run_pricing
python -m explanations.generate_explanations
```

**Total time (approximate):** ~8–12 minutes on a modern laptop.  
Every stage is deterministic — running the pipeline twice produces identical output.

### Step 4 — Backend environment

```bash
cd backend
python -m venv venv

.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
copy .env.example .env    # Windows
cp .env.example .env      # macOS / Linux
```

Fill in the same `DB_USER` and `DB_PASSWORD` as the data pipeline.

Start the backend:
```bash
python app.py
# Confirm: curl http://localhost:5000/api/health  ->  {"status": "ok"}
```

### Step 5 — Frontend

```bash
cd frontend
npm install      # add --legacy-peer-deps if npm < 11
npx ng serve
# Open: http://localhost:4200
```

---

## Demo from a dump (fastest)

If a teammate has already run the pipeline, you can restore their database directly:

```bash
# Download revenue_management.sql.gz and revenue_management_gt.sql.gz
# from shared storage (link in demo/README.md) and place in demo/
mysql -u root -p < database/schema.sql
python demo/restore_demo.py
# Then start the backend and frontend as above
```

---

## Running the tests

```bash
# Data-pipeline tests (no MySQL needed)
cd data-pipeline
pytest tests/ -v              # 56 tests, ~4 seconds

# Backend tests (no MySQL needed)
cd backend
pytest tests/ -v              # 86 tests, ~3 seconds

# Frontend tests
cd frontend
npx ng test --watch=false     # 76 tests, ~11 seconds

# Frontend build
npx ng build --configuration development
```

---

## Verification script

Run after the pipeline and while the backend is running:

```bash
python scripts/verify_system.py
```

Expected output: `PASS=46  FAIL=0  SKIP=0`

If the backend is not running, D/F/G-api/H/I checks are skipped automatically.

---

## Folder structure

```
Revenue Management/
├── data-pipeline/              Python pipeline (all ML work)
│   ├── data_generation/        Synthetic dataset generator
│   ├── etl/                    Cleaning, validation, MySQL loading
│   ├── features/               Weekly feature table builder
│   ├── models/                 Demand forecasting (LR + XGBoost)
│   │   └── artifacts/          Saved model + metadata.json (committed)
│   ├── segmentation/           RFM computation + K-Means clustering
│   ├── pricing/                Elasticity estimation + pricing optimiser
│   ├── explanations/           LLM explanation layer
│   ├── tests/                  Unit + integration tests (56 total)
│   ├── data/
│   │   ├── raw/                gitignored — regenerated by pipeline
│   │   ├── cleaned/            gitignored — regenerated by pipeline
│   │   ├── features/           forecast_features.csv (committed)
│   │   ├── elasticity/         product_elasticity.csv (committed)
│   │   ├── segmentation/       customer_segments.csv, plots (committed)
│   │   ├── pricing/            pricing_candidates.csv (committed)
│   │   │                       pricing_recommendation.csv (gitignored)
│   │   └── explanations/       gitignored — regenerated by Phase 9
│   └── requirements.txt
├── backend/                    Flask REST API (86 tests)
├── frontend/                   Angular + Chart.js dashboard (76 tests)
├── database/
│   └── schema.sql              MySQL DDL (run once to create schemas)
├── scripts/
│   ├── run_pipeline.py         Cross-platform pipeline runner
│   └── verify_system.py        End-to-end read-only verification
├── demo/
│   ├── dump_demo.py            Create compressed DB dumps
│   ├── restore_demo.py         Restore dumps for demo
│   └── README.md               Demo procedure + shared storage link
└── docs/
    ├── api.md                  REST API reference
    ├── frontend.md             Angular architecture and components
    ├── results.md              Detailed metrics from every phase
    ├── demo-script.md          10-minute demo walkthrough
    ├── viva-guide.md           Module-by-module viva preparation
    ├── traceability.md         SRS requirement traceability matrix
    └── known-issues.md         Issues found but not fixed in Phase 12
```

---

## Environment variables

All variables go in `data-pipeline/.env` (pipeline + backend reads it via config.py fallback).  
A separate `backend/.env` overrides backend-specific settings.

| Variable | Default | Used by | Purpose |
|---|---|---|---|
| `DB_HOST` | `localhost` | pipeline, backend | MySQL host |
| `DB_PORT` | `3306` | pipeline, backend | MySQL port |
| `DB_NAME` | `revenue_management` | pipeline, backend | Application database |
| `DB_GT_NAME` | `revenue_management_gt` | pipeline only | Ground-truth database (evaluation only) |
| `DB_USER` | — | pipeline, backend | MySQL username (**required**) |
| `DB_PASSWORD` | — | pipeline, backend | MySQL password (**required**) |
| `LLM_PROVIDER` | `mock` | pipeline only | `mock` (no key) or `gemini` |
| `LLM_MODEL` | `gemini-3.5-flash` | pipeline only | Gemini model name |
| `LLM_API_KEY` | — | pipeline only | Gemini API key (only if `LLM_PROVIDER=gemini`) |
| `FLASK_DEBUG` | `false` | backend | Flask debug mode |
| `FLASK_PORT` | `5000` | backend | Flask listening port |
| `CORS_ORIGINS` | `http://localhost:4200` | backend | Allowed Angular origin(s) |
| `FORECAST_HISTORY_WEEKS` | `12` | backend | History weeks returned with test predictions |

---

## Key results

| Metric | Value |
|---|---|
| Demand forecast MAPE (XGBoost) | 9.7% |
| LR baseline MAPE | 15.3% |
| XGBoost improvement over LR (RMSE) | 12.7% |
| Elasticity MAE vs. true values | 0.062 |
| Elasticity correct sign | 100% (50/50 products) |
| Segmentation accuracy vs. true labels (ARI) | 1.0 |
| Expected weekly revenue uplift from pricing | +7.9% |
| Pricing decisions matching true-elasticity direction | 48/50 products |

Full metrics per phase are in [`docs/results.md`](docs/results.md).

---

## How the ground-truth separation works

The generator assigns every product a `true_elasticity` and every customer a `true_segment`. These go into `revenue_management_gt` — a completely separate MySQL schema. The ML models only connect to `revenue_management`. Validation scripts connect to `revenue_management_gt` after training, but never feed those values back into the models. Unit tests (`test_ground_truth_isolation`, `test_pricing_ground_truth_isolation`) enforce this at the code level.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` in pipeline | Confirm the venv is active: `data-pipeline/venv/Scripts/Activate.ps1` |
| `Access denied for user` (MySQL) | Check `DB_USER` / `DB_PASSWORD` in `data-pipeline/.env` |
| `Table doesn't exist` | Run `mysql -u root -p < database/schema.sql` first |
| Backend 404 on every endpoint | Run the full pipeline before starting the backend |
| `npm install` peer-dependency errors | Add `--legacy-peer-deps` flag |
| Frontend shows "OFFLINE" health badge | The backend is not running; start with `python app.py` in `backend/` |
| Explanation panel always shows "unavailable" | Expected if `LLM_PROVIDER=mock`; set to `gemini` and add `LLM_API_KEY` |
| `verify_system.py` FAIL on check E | Confirm the venv is active when running the script |

---

## Design decisions

**Why synthetic data?** Public retail datasets don't vary prices in a controlled way. Without known true elasticities there is no way to verify Phase 7.

**Why XGBoost?** Published benchmarks confirm tree-based models outperform neural networks on tabular data at this scale (~7 700 training rows). XGBoost is also interpretable via feature importance.

**Why is recency dropped from clustering?** All customers in the 3-year dataset bought recently (max gap 23 days). Recency is noise, not signal. The code detects this automatically.

**Why does pricing use elasticity scaling rather than XGBoost directly?** XGBoost was trained on narrow historical price ranges. Querying it at prices outside that range is extrapolation with no reliable signal. Elasticity scaling is economically grounded and explicitly designed for this purpose.

**Why can the LLM only explain?** To prevent hallucination. The guardrail checks every number in the output against the input payload. If a new number appears, the output is rejected and replaced with a template.

---

## Project phases

| Phase | Description | Status |
|---|---|---|
| 0 | Repo setup | Done |
| 1 | Synthetic dataset generation | Done |
| 2 | ETL | Done |
| 4 | Feature engineering | Done |
| 5 | Demand forecasting | Done |
| 6 | Customer segmentation | Done |
| 7 | Price elasticity | Done |
| 8 | Pricing optimisation | Done |
| 9 | LLM explanation layer | Done |
| 10 | Flask REST API | Done |
| 11 | Angular dashboard | Done |
| 12 | Integration and demo readiness | Done |
| 13–14 | Evaluation report and final submission | Planned |
