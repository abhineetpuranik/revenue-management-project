"""
Database connection module.

Provides a SQLAlchemy engine built from environment variables so that no
credentials are ever hard-coded.  Both the application schema
(revenue_management) and the ground-truth schema (revenue_management_gt)
are supported — callers pass the desired DB name explicitly.

Environment variables (set in .env or shell before running):
    DB_HOST      — MySQL server host      (default: localhost)
    DB_PORT      — MySQL server port      (default: 3306)
    DB_NAME      — application schema     (default: revenue_management)
    DB_GT_NAME   — ground-truth schema    (default: revenue_management_gt)
    DB_USER      — MySQL username
    DB_PASSWORD  — MySQL password

Usage
-----
    from etl.db_connection import get_engine, get_gt_engine

    engine = get_engine()          # connects to revenue_management
    gt_engine = get_gt_engine()    # connects to revenue_management_gt

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Load .env from data-pipeline/ or repo root (whichever exists first)
_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (
    os.path.join(_HERE, "..", ".env"),         # data-pipeline/.env
    os.path.join(_HERE, "..", "..", ".env"),   # repo root .env
):
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break


def _build_url(db_name: str) -> str:
    """Construct a mysql+mysqlconnector:// URL from environment variables."""
    host     = os.getenv("DB_HOST",     "localhost")
    port     = int(os.getenv("DB_PORT", "3306"))
    user     = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    if not user or not password:
        raise EnvironmentError(
            "DB_USER and DB_PASSWORD must be set in the environment or a .env file.\n"
            "Copy .env.example to .env and fill in your MySQL credentials."
        )

    return (
        f"mysql+mysqlconnector://{user}:{password}"
        f"@{host}:{port}/{db_name}"
        "?charset=utf8mb4"
    )


@lru_cache(maxsize=None)
def get_engine(db_name: str | None = None) -> Engine:
    """
    Return a cached SQLAlchemy Engine for the application schema.

    Parameters
    ----------
    db_name : str | None
        Override the database name (defaults to DB_NAME env var, then
        'revenue_management').
    """
    name = db_name or os.getenv("DB_NAME", "revenue_management")
    engine = create_engine(
        _build_url(name),
        pool_pre_ping=True,   # silently reconnect if the connection drops
        pool_size=5,
        max_overflow=10,
    )
    return engine


@lru_cache(maxsize=None)
def get_gt_engine() -> Engine:
    """
    Return a cached SQLAlchemy Engine for the ground-truth holdout schema.

    This engine should only be used by Phase 6 / Phase 7 evaluation scripts.
    Application code and model-training code must use get_engine() instead.
    """
    name = os.getenv("DB_GT_NAME", "revenue_management_gt")
    return get_engine(db_name=name)


def test_connection(engine: Engine) -> bool:
    """Attempt a trivial query; return True on success, False on failure."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Connection test failed: {exc}")
        return False
