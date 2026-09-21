# Revenue Management — AI-Powered Demand Forecasting & Dynamic Pricing

A final-year undergraduate project that combines machine learning, a REST API, and an interactive dashboard to help retail businesses forecast demand and optimise pricing dynamically.

---

## Repository Structure

```
Revenue Management/
├── data-pipeline/          # Python: dataset generation, ETL, feature engineering, ML models, pricing
│   ├── data_generation/    # Synthetic data generation
│   ├── etl/                # Extract, Transform, Load
│   ├── features/           # Feature engineering
│   ├── models/             # Demand forecasting & customer segmentation models
│   ├── pricing/            # Price elasticity & dynamic pricing optimisation
│   └── requirements.txt
│
├── backend/                # Flask REST API exposing model outputs & LLM explanations
│   ├── app.py
│   └── requirements.txt
│
├── frontend/               # Angular dashboard (Chart.js visualisations)
│   ├── src/
│   └── package.json
│
├── database/               # MySQL schema files and migration scripts
│   └── schema.sql
│
├── docs/                   # Project documentation
│
├── .env.example            # Reference list of all environment variables
├── .gitignore
├── CONTRIBUTING.md
└── README.md
```

---

## Environment Setup

### Prerequisites

| Tool | Version used | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 22 LTS | [nodejs.org](https://nodejs.org/) |
| Angular CLI | 21+ | `npm install -g @angular/cli` |
| MySQL | 8.0+ | [dev.mysql.com](https://dev.mysql.com/downloads/) |
| Git | Any recent | [git-scm.com](https://git-scm.com/) |

---

### 1. Python — data-pipeline

```bash
cd data-pipeline

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Deactivate when done:**
```bash
deactivate
```

---

### 2. Flask — backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux

# Run the development server
python app.py
```

The API will be available at `http://localhost:5000`.  
Health check: `GET http://localhost:5000/api/health` → `{"status": "ok"}`

---

### 3. Angular — frontend

```bash
cd frontend

# Install dependencies
# Note: --legacy-peer-deps is required due to an npm 10.9.x resolver bug with vitest peer deps
npm install --legacy-peer-deps

# Start the development server
ng serve
```

The app will be available at `http://localhost:4200`.

---

### Environment Variables

Copy `.env.example` (repo root) to `.env` and fill in real values, **or** copy the per-service `.env.example` into the service folder. Never commit a real `.env` file.

| Variable | Used by | Description |
|---|---|---|
| `DB_HOST` | data-pipeline, backend | MySQL host |
| `DB_PORT` | data-pipeline, backend | MySQL port (default 3306) |
| `DB_NAME` | data-pipeline, backend | Database name |
| `DB_USER` | data-pipeline, backend | MySQL username |
| `DB_PASSWORD` | data-pipeline, backend | MySQL password |
| `FLASK_DEBUG` | backend | Enable Flask debug mode (true/false) |
| `FLASK_PORT` | backend | Port the API listens on (default 5000) |
| `LLM_API_KEY` | backend | API key for LLM explanation generation (Phase 3+) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML pipeline | Python 3.12, pandas, numpy, scikit-learn, XGBoost |
| Database | MySQL 8.0 |
| API | Flask 3, Flask-CORS, python-dotenv |
| Frontend | Angular 21, TypeScript, Chart.js (Phase 2+) |

---

## Project Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Project setup & monorepo skeleton | ✅ Complete |
| 1 | Dataset generation & ETL | Planned |
| 2 | ML models (forecasting & segmentation) | Planned |
| 3 | Flask API + LLM explanations | Planned |
| 4 | Angular dashboard | Planned |

---

## Contributors

Three-person undergraduate team — see `CONTRIBUTING.md` for the Git workflow.
