"""
Backend configuration — all settings read from environment variables.

Copy backend/.env.example to backend/.env and fill in values before
running the app.  Nothing is hardcoded here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env, then fall back to the repo-root .env
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE / ".env", _HERE.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break


class Config:
    # ── Flask ─────────────────────────────────────────────────────────────
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT:  int  = int(os.getenv("FLASK_PORT", "5000"))

    # ── CORS ──────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins, e.g.
    #   CORS_ORIGINS=http://localhost:4200,http://localhost:4201
    # Defaults to the Angular dev server.
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",")
        if o.strip()
    ]

    # ── MySQL ─────────────────────────────────────────────────────────────
    DB_HOST:     str = os.getenv("DB_HOST",     "localhost")
    DB_PORT:     int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME:     str = os.getenv("DB_NAME",     "revenue_management")
    DB_USER:     str = os.getenv("DB_USER",     "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # ── Data-pipeline root (for PYTHONPATH and artifact paths) ────────────
    # Resolved relative to this file: backend/ → repo root → data-pipeline/
    PIPELINE_ROOT: Path = _HERE.parent / "data-pipeline"

    # ── Phase 5 model artifact ────────────────────────────────────────────
    MODEL_ARTIFACT_PATH: Path = (
        Path(os.getenv("MODEL_ARTIFACT_PATH", ""))
        if os.getenv("MODEL_ARTIFACT_PATH")
        else PIPELINE_ROOT / "models" / "artifacts" / "production_model.joblib"
    )
    MODEL_METADATA_PATH: Path = (
        Path(os.getenv("MODEL_METADATA_PATH", ""))
        if os.getenv("MODEL_METADATA_PATH")
        else PIPELINE_ROOT / "models" / "artifacts" / "metadata.json"
    )

    # ── Forecast endpoint ─────────────────────────────────────────────────
    # Number of training weeks to return as history context alongside the
    # test-window predictions.
    FORECAST_HISTORY_WEEKS: int = int(os.getenv("FORECAST_HISTORY_WEEKS", "12"))

    # ── Pagination ────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "50"))
    MAX_PAGE_SIZE:     int = int(os.getenv("MAX_PAGE_SIZE",     "200"))
