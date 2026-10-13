# Revenue Management: Demand Forecasting and Dynamic Pricing

Final year project. The system forecasts weekly demand, segments customers, estimates price elasticity per product and recommends a price for each product. An LLM turns the results into short explanations for the dashboard. Backend is Flask, frontend is Angular with Chart.js, and data is stored in MySQL.

We use a generated dataset because public retail data does not have controlled price changes or known answers to check against. The generator stores the true elasticity of each product and the true segment of each customer in a separate schema (`revenue_management_gt`). The models never read it. It is only used to check results.

## Progress

| Phase | Work | Status |
|---|---|---|
| 0 | Project setup | Done |
| 1 | Dataset generation | Done |
| 2 | ETL and MySQL schema | Done |
| 4 | Feature table | Done |
| 5 | Demand forecasting (Linear Regression, XGBoost) | Done |
| 6 | Customer segmentation (RFM, K-Means) | Done |
| 7 | Price elasticity | Done |
| 8 | Pricing optimisation | Done |
| 9 | LLM explanations | Done |
| 10 | Flask API | Next |
| 11 | Angular dashboard | |
| 12-14 | Integration, testing, documentation | |

Results are in [docs/results.md](docs/results.md).

## Folders

```
data-pipeline/
  data_generation/   synthetic dataset
  etl/               cleaning, validation, MySQL loading
  features/          weekly feature table
  models/            demand forecasting
  segmentation/      RFM and K-Means
  pricing/           elasticity, price candidates, optimiser
  explanations/      LLM explanations
  tests/
  data/              generated data and outputs
backend/             Flask API
frontend/            Angular app
database/schema.sql  MySQL schema
docs/
```

## Setup

You need Python 3.10 to 3.12 (numpy 1.26 does not install on 3.13), MySQL 8, Node 22 and Angular CLI.

Pipeline:

```bash
cd data-pipeline
python -m venv venv
.\venv\Scripts\Activate.ps1      # Windows
source venv/bin/activate         # Mac/Linux
pip install -r requirements.txt
copy .env.example .env           # then fill in your MySQL details
```

Database (first time only, it drops and recreates both schemas):

```bash
mysql -u <user> -p < database/schema.sql
```

Backend:

```bash
cd backend
python -m venv venv
pip install -r requirements.txt
copy .env.example .env
python app.py                    # http://localhost:5000/api/health
```

Frontend:

```bash
cd frontend
npm install --legacy-peer-deps
ng serve                         # http://localhost:4200
```

## Running the pipeline

Run from `data-pipeline/`, in this order:

```bash
python -m data_generation.generate_base_tables
python -m data_generation.generate_transactional_tables
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

The first three steps take a few minutes. Everything uses a fixed seed, so results are the same on every machine.

Tests do not need MySQL:

```bash
pytest tests -v
```

`data/raw` and `data/cleaned` are not in git because they are large and can be regenerated with the first three commands.

## Environment variables

| Variable | Used in | |
|---|---|---|
| DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD | pipeline, backend | MySQL connection |
| DB_GT_NAME | pipeline | ground truth schema, only used for validation |
| LLM_PROVIDER | pipeline | `mock` (no key needed) or `gemini` |
| LLM_MODEL, LLM_API_KEY | pipeline | Gemini model and key |
| FLASK_DEBUG, FLASK_PORT | backend | |

## Notes on the approach

- Elasticity is estimated per product with a log-log regression on weekly sales. We use the list price and control for promotions, because that is how demand is generated.
- Recency is left out of the clustering. Every customer bought something in the last few weeks, so it does not separate anyone in this dataset.
- For pricing, demand at a new price is the forecast at the current price scaled by the elasticity. Each recommendation records which rule limited it (max change, margin, price range or stock).
- There is no cost data, so unit cost is assumed as a share of base price per category (`pricing/pricing_config.py`).
- The LLM only rewrites numbers it is given. Any output with a number that is not in the input is rejected and a template sentence is used instead.

## Team

Three students. See [CONTRIBUTING.md](CONTRIBUTING.md) for how we use Git.
