# Revenue Management — AI-Powered Demand Forecasting & Dynamic Pricing

Final-year undergraduate project. One pipeline that **forecasts demand**, **segments customers**, **estimates price elasticity**, **recommends a revenue-maximising price** per product, and has an **LLM explain each result in plain English**. Results are served through a Flask API to an Angular dashboard, with MySQL as the shared data layer.

Every number is produced by a classical, inspectable model (Linear Regression, XGBoost, K-Means, log-log OLS). The LLM only rephrases validated results and is checked by guardrails so it cannot invent numbers.

Because public retail data has neither controlled price changes nor known "right answers", the project generates its own **synthetic dataset with hidden ground truth** (`true_elasticity` per product, `true_segment` per customer). The models never see these values; they are used only to measure how close the models get.

---

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Monorepo setup | ✅ |
| 1a / 1b | Synthetic dataset (products, customers, calendar / prices, sales, stock) | ✅ |
| 2a / 2b | ETL cleaning / MySQL schema + load (Phase 3 folded into 2b) | ✅ |
| 4 | Weekly feature table (lags, calendar, price) | ✅ |
| 5 | Demand forecasting — Linear Regression vs XGBoost | ✅ |
| 6 | Customer segmentation — RFM + K-Means | ✅ |
| 7 | Price elasticity — per-product log-log regression | ✅ |
| 8a / 8b | Pricing — candidate prices + rules / revenue-maximising price | ✅ |
| 9 | LLM explanation layer — Gemini + guardrails + fallback | ✅ |
| 10a / 10b | Flask API — forecasts & segments / pricing & explanations | ⏳ next |
| 11a / 11b | Angular dashboard | ⏳ |
| 12 – 14 | Integration, full evaluation (+ optional M5 check), documentation | ⏳ |

Headline results so far are in [`docs/results.md`](docs/results.md).

---

## Repository structure

```
revenue-management-project/
├── data-pipeline/                 Python: data, ETL, features, models, pricing, LLM layer
│   ├── data_generation/           Phase 1 — synthetic dataset (fixed seed, reproducible)
│   ├── etl/                       Phase 2 — cleaning, validation, MySQL connection + loader
│   ├── features/                  Phase 4 — weekly feature table
│   ├── models/                    Phase 5 — demand forecasting (+ saved model in artifacts/)
│   ├── segmentation/              Phase 6 — RFM, K-Means, labeling, validation
│   ├── pricing/                   Phase 7 elasticity · Phase 8a candidates · Phase 8b optimiser
│   ├── explanations/              Phase 9 — payloads, prompts, LLM client, guardrails, fallback
│   ├── tests/                     pytest suite (no database needed)
│   ├── data/                      generated data and model outputs (see "Data files" below)
│   ├── requirements.txt
│   └── .env.example
├── backend/                       Flask REST API (health check now; endpoints in Phase 10)
├── frontend/                      Angular dashboard (scaffold now; views in Phase 11)
├── database/schema.sql            Full MySQL schema, incl. the ground-truth holdout schema
├── docs/                          Results and project documentation
├── .env.example                   Reference list of every environment variable
├── CONTRIBUTING.md                Git workflow for the team
└── README.md
```

---

## Setup

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | **3.10 – 3.12** | numpy 1.26.4 (pinned) has no Python 3.13 wheels |
| MySQL | 8.0+ | |
| Node.js | 22 LTS | frontend only |
| Angular CLI | 21+ | `npm install -g @angular/cli` |

### 1. Python pipeline

```bash
cd data-pipeline
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate         # macOS / Linux
pip install -r requirements.txt

copy .env.example .env             # Windows   (cp on macOS / Linux)
# then fill in DB_USER, DB_PASSWORD (and LLM_API_KEY if using Gemini)
```

### 2. MySQL schema (first time only)

```bash
mysql -u <user> -p < database/schema.sql
```

⚠️ `schema.sql` **drops and recreates** both schemas. Run it once on a fresh setup, not on a populated database. The Phase 6–9 tables also create themselves (`CREATE TABLE IF NOT EXISTS`), so you never need to re-run it for them.

### 3. Backend (Flask)

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py                      # GET http://localhost:5000/api/health → {"status": "ok"}
```

### 4. Frontend (Angular)

```bash
cd frontend
npm install --legacy-peer-deps     # npm 10.9.x peer-dependency resolver bug with vitest
ng serve                           # http://localhost:4200
```

---

## Running the pipeline

All commands run from `data-pipeline/` with the venv active. Every step is deterministic (fixed seeds), so re-running gives the same numbers.

| # | Phase | Command | Reads → writes |
|---|---|---|---|
| 1 | 1a | `python -m data_generation.generate_base_tables` | → `data/raw/` product, customer, calendar |
| 2 | 1b | `python -m data_generation.generate_transactional_tables` | → `data/raw/` price, sales, stock |
| 3 | 2a | `python -m etl.clean_tables` | `data/raw/` → `data/cleaned/` |
| 4 | 2b | `python -m etl.load_to_mysql` | `data/cleaned/` → MySQL (app + ground-truth schemas) |
| 5 | 4 | `python -m features.build_feature_table` | MySQL → `forecast_features` (table + CSV) |
| 6 | 5 | `python -m models.train_forecasting_models` | features → `models/artifacts/` |
| 7 | 7 | `python -m pricing.estimate_elasticity` | MySQL → `product_elasticity` |
| 8 | 6 | `python -m segmentation.run_segmentation` | MySQL → `customer_rfm_segment`, `segment_summary` |
| 9 | 8a | `python -m pricing.build_candidates` | → `pricing_candidates` |
| 10 | 8b | `python -m pricing.run_pricing` | → `pricing_recommendation` |
| 11 | 9 | `python -m explanations.generate_explanations` | → `llm_explanation` |

Steps 1–3 take a few minutes (1.3 M sales rows). Phase 6 is independent of 7/8 and can run at any point after step 4.

**Tests** (no MySQL needed):

```bash
pytest tests -v
```

### Data files

`data/raw/` and `data/cleaned/` are **not in git** (about 120 MB, and fully reproducible from the seed). After cloning, run steps 1–4 above. The small model outputs (`data/features/`, `data/elasticity/`, `data/segmentation/`, `data/pricing/pricing_candidates.csv`) and the trained model in `models/artifacts/` are committed for review.

Re-running a phase rewrites its output CSV with a new timestamp column, even though the numbers come out identical. Don't commit those changes: `git checkout -- data-pipeline/data`.

---

## Environment variables

Put these in `data-pipeline/.env` (pipeline) and `backend/.env` (API). Never commit a real `.env`.

| Variable | Used by | Purpose |
|---|---|---|
| `DB_HOST`, `DB_PORT` | pipeline, backend | MySQL server (default `localhost:3306`) |
| `DB_NAME` | pipeline, backend | application schema (`revenue_management`) |
| `DB_GT_NAME` | pipeline (validation only) | ground-truth schema (`revenue_management_gt`) |
| `DB_USER`, `DB_PASSWORD` | pipeline, backend | MySQL credentials |
| `LLM_PROVIDER` | pipeline (Phase 9) | `mock` (offline, default) or `gemini` |
| `LLM_MODEL` | pipeline (Phase 9) | Gemini model name |
| `LLM_API_KEY` | pipeline (Phase 9) | Gemini API key (only when `LLM_PROVIDER=gemini`) |
| `FLASK_DEBUG`, `FLASK_PORT` | backend | Flask settings |

---

## Key design decisions

- **Ground truth is physically separated.** `true_elasticity` and `true_segment` live in a separate MySQL schema (`revenue_management_gt`). Only the `validate_*.py` files read it, and tests fail if any other module references it.
- **Elasticity uses the list price, with a promotion control**, at weekly grain. That matches how the generator creates demand and avoids bias from zero-sales days.
- **Segmentation drops recency from clustering by a documented rule.** Every customer bought recently, so recency carries no signal in this dataset. It is still computed, saved and reported.
- **Pricing demand = forecast × (price ratio)^elasticity.** XGBoost is not swept over price directly because tree models are step-shaped and can't extrapolate. With a revenue objective and constant elasticity, the best price usually sits at a rule limit (raise inelastic products, cut elastic ones), so every recommendation records which rule stopped it.
- **Unit cost is assumed.** The data has no cost column, so cost = base price × a per-category ratio (`pricing/pricing_config.py`). All margin figures depend on this assumption.
- **The LLM explains and never computes.** Numbers are pre-formatted, every output is checked for numbers not in the input, and a template fallback guarantees an explanation for every item.

---

## Team

Three-person undergraduate team. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the Git workflow.
