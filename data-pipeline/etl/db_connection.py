from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (
    os.path.join(_HERE, "..", ".env"),
    os.path.join(_HERE, "..", "..", ".env"),
):
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break


def _build_url(db_name: str) -> str:
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
    name = db_name or os.getenv("DB_NAME", "revenue_management")
    engine = create_engine(
        _build_url(name),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return engine


@lru_cache(maxsize=None)
def get_gt_engine() -> Engine:
    name = os.getenv("DB_GT_NAME", "revenue_management_gt")
    return get_engine(db_name=name)


def test_connection(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"  Connection test failed: {exc}")
        return False
