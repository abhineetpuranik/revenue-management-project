# AI-Powered Demand Forecasting and Dynamic Pricing

A final-year undergraduate project that helps retail businesses forecast weekly product demand and automatically recommend prices to maximise revenue. A Flask API serves the results, and an Angular dashboard displays them with short LLM-generated explanations.

---

## What the system does

1. **Generates a synthetic retail dataset** — 50 products, 1 000 customers, 3 years of daily sales (≈ 1.3 million transaction rows). A synthetic dataset is used because public retail datasets do not have controlled price changes or verified ground-truth answers. The generator embeds a known true elasticity per product and a known true segment per customer in a separate, sealed database schema (`revenue_management_gt`). The ML models never read this schema; it is only used to measure how accurate the results are.

2. **Cleans and loads the data** — an ETL pipeline checks for duplicates, missing values and referential integrity, then loads everything into MySQL.

3. **Builds a weekly feature table** — aggregates daily sales to one row per product per ISO week, adds 3-week demand lags, calendar signals (month, seasonality, festival flags) and price features. Lag features are strictly backward-looking — no future data leaks in.

4. **Forecasts weekly demand** — trains a Linear Regression baseline and an XGBoost model, picks the winner by test-set RMSE, and saves it to disk. The saved model is the single source of truth for demand predictions everywhere else in the system.

5. **Estimates price elasticity per product** — a log-log OLS regression (`log units = a + b·log price + controls`) gives a per-product elasticity coefficient that describes how sensitive demand is to price changes.

6. **Segments customers** — computes Recency / Frequency / Monetary (RFM) values per customer, clusters with K-Means (k chosen by Silhouette score), and assigns a label (high-value / regular / occasional / at-risk) based on each cluster's actual RFM profile.

7. **Recommends prices** — for each product, sweeps a grid of candidate prices (±15% in 1% steps), predicts demand at each using the XGBoost model scaled by elasticity, filters out candidates that break the margin, max-change, or price-range rules, and picks the one with the highest expected revenue.

8. **Generates natural-language explanations** — passes the structured pricing and segmentation results to an LLM (Gemini, or a mock for testing). The LLM can only use numbers it is given; any output containing a new number is rejected and replaced with a template sentence.

---

## Key results (run on the synthetic dataset)

| | |
|---|---|
| **Demand forecast MAPE (XGBoost)** | 9.7 % |
| **Elasticity MAE vs. true values** | 0.062 |
| **Elasticity correct sign** | 100 % of products |
| **Segmentation accuracy vs. true labels** | 100 % (ARI 1.0) |
| **Expected weekly revenue uplift from pricing** | +7.9 % |
| **Pricing decisions matching true-elasticity optimum (direction)** | 48 / 50 products |

Full metrics are in [`docs/results.md`](docs/results.md).

---

## Folder structure

```
Revenue Management/
├── data-pipeline/              Python pipeline (all ML work lives here)
│   ├── data_generation/        Synthetic dataset generator
│   ├── etl/                    Cleaning, validation, MySQL loading
│   ├── features/               Weekly feature table builder
│   ├── models/                 Demand forecasting (LR + XGBoost)
│   │   └── artifacts/          Saved production model + metadata.json
│   ├── segmentation/           RFM computation + K-Means clustering
│   ├── pricing/                Elasticity estimation + pricing optimiser
│   ├── explanations/           LLM explanation layer
│   ├── tests/                  Unit + integration tests (56 total)
│   ├── data/                   Generated data and outputs
│   │   ├── raw/                Raw CSVs from the generator
│   │   ├── cleaned/            Cleaned CSVs (ETL output)
│   │   ├── features/           forecast_features.csv
│   │   ├── elasticity/         product_elasticity.csv
│   │   ├── segmentation/       customer_segments.csv, plots
│   │   └── pricing/            pricing_candidates.csv
│   └── requirements.txt
│
├── backend/                    Flask REST API
├── frontend/                   Angular + Chart.js dashboard
├── database/
│   └── schema.sql              MySQL DDL (run once to create all tables)
└── docs/
    └── results.md              Detailed metrics from every phase
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10 – 3.12 | 3.13 not supported (numpy 1.26 incompatibility) |
| MySQL | 8.0 | Server must be running before loading data |
| Node.js | 22 LTS | For the Angular frontend |
| Angular CLI | 17+ | `npm install -g @angular/cli` |

---

## First-time setup

### 1. Python environment (data pipeline)

```bash
cd data-pipeline
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment variables

Copy the example file and fill in your MySQL credentials:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and set at minimum:

```
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
```

The other defaults (host `localhost`, port `3306`, database name `revenue_management`) are fine for a local install.

**LLM:** the default `LLM_PROVIDER=mock` runs the explanation layer without any API key. To use Gemini, set `LLM_PROVIDER=gemini` and add your key to `LLM_API_KEY`.

### 3. MySQL schema (run once)

This drops and recreates the `revenue_management` and `revenue_management_gt` schemas, so do not run it against a database you want to keep:

```bash
mysql -u root -p < database/schema.sql
```

### 4. Flask backend

```bash
cd backend
python -m venv venv
pip install -r requirements.txt

# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env

python app.py
# Health check: http://localhost:5000/api/health  →  {"status": "ok"}
```

### 5. Angular frontend

```bash
cd frontend
npm install --legacy-peer-deps   # --legacy-peer-deps needed due to a known npm 10.9.x resolver bug
ng serve
# Open: http://localhost:4200
```

---

## Running the full pipeline

All commands are run from inside `data-pipeline/` with the virtual environment active.

```bash
# Step 1  Generate the synthetic dataset (takes a few minutes)
python -m data_generation.generate_base_tables
python -m data_generation.generate_transactional_tables

# Step 2  Clean the data and load it into MySQL
python -m etl.clean_tables
python -m etl.load_to_mysql

# Step 3  Build the weekly feature table
python -m features.build_feature_table

# Step 4  Train the demand forecasting models and save the winner
python -m models.train_forecasting_models

# Step 5  Estimate price elasticity per product
python -m pricing.estimate_elasticity

# Step 6  Segment customers with RFM + K-Means
python -m segmentation.run_segmentation

# Step 7  Generate candidate prices and apply constraints
python -m pricing.build_candidates

# Step 8  Score candidates and produce recommendations
python -m pricing.run_pricing

# Step 9  Generate natural-language explanations
python -m explanations.generate_explanations
```

Every step is deterministic (fixed random seed throughout). Running the pipeline twice produces identical output.

---

## Running the tests

The tests do not need MySQL and run in about 5 seconds:

```bash
cd data-pipeline
pytest tests/ -v
```

56 tests covering segmentation, elasticity, pricing constraints, pricing optimiser, and LLM guardrails. All should pass.

---

## Environment variables reference

All variables go in `data-pipeline/.env`. The root `.env.example` is a reference copy.

| Variable | Default | Purpose |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_NAME` | `revenue_management` | Application database |
| `DB_GT_NAME` | `revenue_management_gt` | Ground-truth database (evaluation only) |
| `DB_USER` | — | MySQL username (required) |
| `DB_PASSWORD` | — | MySQL password (required) |
| `LLM_PROVIDER` | `mock` | `mock` (no key needed) or `gemini` |
| `LLM_MODEL` | `gemini-3.5-flash` | Gemini model name |
| `LLM_API_KEY` | — | Gemini API key (only needed if `LLM_PROVIDER=gemini`) |
| `FLASK_DEBUG` | `false` | Flask debug mode |
| `FLASK_PORT` | `5000` | Flask port |

---

## How the ground-truth separation works

The synthetic data generator assigns every product a `true_elasticity` and every customer a `true_segment`. These are stored in the `revenue_management_gt` MySQL schema, which is a completely separate database from the one the application reads.

- The demand forecasting, elasticity estimation, and segmentation models **only connect to `revenue_management`**. They cannot accidentally read ground-truth values.
- The validation scripts (run at the end of Phases 6, 7, 8) connect to `revenue_management_gt` to measure accuracy. They never feed those values back into the models.
- The unit tests include an explicit search for any import or reference to `revenue_management_gt` in the modelling code, which will fail if someone accidentally introduces a dependency.

---

## Design decisions worth knowing

**Why synthetic data?** Public retail datasets don't vary prices in a controlled way. Without known true elasticities, there's no way to check whether the Phase 7 estimation is actually correct.

**Why is recency dropped from clustering?** Every customer in the 3-year dataset purchased recently (max gap: 23 days). Recency adds noise rather than signal. The code detects this automatically and logs it.

**How does pricing use the demand model?** The XGBoost model predicts baseline demand at the current price. Demand at a candidate price is then scaled using the elasticity estimate: `demand(p) = d0 × (p / p0)^elasticity`. This combines the model's precision with the economic structure of elasticity.

**Why is unit cost estimated rather than loaded from data?** There is no cost table in the synthetic dataset. Unit cost is approximated as a fixed fraction of the product's base price, with the fraction set per category in `pricing/pricing_config.py`. All margin calculations use this estimate consistently.

**LLM number guardrail** — every number in the LLM's output is checked against the numbers in the input payload. A re-rounded number (e.g. "14%" instead of "13.9%") fails the check. This prevents the LLM from silently introducing inaccurate figures into what a manager reads.

---

## Project phases

| Phase | What it does | Status |
|---|---|---|
| 0 | Repo setup, folder structure, environments | Done |
| 1 | Synthetic dataset generation | Done |
| 2 | ETL — data cleaning and MySQL loading | Done |
| 4 | Feature engineering (weekly aggregation, lags, calendar, price) | Done |
| 5 | Demand forecasting (Linear Regression + XGBoost) | Done |
| 6 | Customer segmentation (RFM + K-Means) | Done |
| 7 | Price elasticity estimation | Done |
| 8 | Pricing optimisation | Done |
| 9 | LLM explanation layer | Done |
| 10 | Flask REST API | Next |
| 11 | Angular dashboard | Planned |
| 12–14 | Integration, testing, final documentation | Planned |

---

## Team

Three students. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the Git branching and pull request workflow.
