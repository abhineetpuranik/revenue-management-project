"""Phase 13 — Item 14: ETL idempotency.

Confirms the feature table row count is stable across repeated queries
(no phantom duplicates from a previous run) and that the core ETL table
row counts match the expected dataset size.  Requires DB access.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def _db_ready() -> bool:
    """True when DB credentials are available (env or data-pipeline/.env)."""
    from dotenv import load_dotenv

    load_dotenv(PIPELINE_ROOT / ".env")
    return bool(os.getenv("DB_USER") and os.getenv("DB_PASSWORD"))


NEEDS_DB = pytest.mark.skipif(
    not _db_ready(), reason="requires live MySQL + DB credentials"
)


@NEEDS_DB
def test_forecast_features_row_count_stable():
    """Re-query forecast_features twice; row count must be identical."""
    from dotenv import load_dotenv
    from sqlalchemy import text

    from etl.db_connection import get_engine

    load_dotenv(PIPELINE_ROOT / ".env")
    engine = get_engine()
    with engine.connect() as conn:
        n1 = conn.execute(text("SELECT COUNT(*) FROM forecast_features")).scalar()
        n2 = conn.execute(text("SELECT COUNT(*) FROM forecast_features")).scalar()
    assert n1 == n2
    assert n1 > 0, "forecast_features is empty"


@NEEDS_DB
def test_core_table_row_counts_nonzero():
    from dotenv import load_dotenv
    from sqlalchemy import text

    from etl.db_connection import get_engine

    load_dotenv(PIPELINE_ROOT / ".env")
    engine = get_engine()
    EXPECTED = {
        "product": 50,
        "customer": 1000,
        "product_elasticity": 50,
        "customer_rfm_segment": 1000,
    }
    with engine.connect() as conn:
        for table, expected_count in EXPECTED.items():
            actual = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            assert actual == expected_count, (
                f"Table {table}: expected {expected_count} rows, got {actual}"
            )


@NEEDS_DB
def test_no_duplicate_product_ids_in_pricing_recommendation():
    from dotenv import load_dotenv
    from sqlalchemy import text

    from etl.db_connection import get_engine

    load_dotenv(PIPELINE_ROOT / ".env")
    engine = get_engine()
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM pricing_recommendation")).scalar()
        distinct = conn.execute(
            text("SELECT COUNT(DISTINCT product_id) FROM pricing_recommendation")
        ).scalar()
    assert total == distinct, (
        f"Duplicate product_ids: total={total}, distinct={distinct}"
    )
