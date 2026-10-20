"""Phase 13 — Item 11: lag-feature leakage check.

Re-runs the Phase 4 ``_run_leakage_test`` as a proper pytest so the
backward-looking property of the lag features is asserted against the real
weekly aggregates and the stored feature table.  Requires DB access.
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
    """True when DB credentials are available (env or data-pipeline/.env).

    Lets the test run for full-stack teams with a live MySQL, and skip
    cleanly (reported as "skipped — needs DB") where no DB/credentials exist.
    """
    from dotenv import load_dotenv

    load_dotenv(PIPELINE_ROOT / ".env")
    return bool(os.getenv("DB_USER") and os.getenv("DB_PASSWORD"))


NEEDS_DB = pytest.mark.skipif(
    not _db_ready(), reason="requires live MySQL + DB credentials"
)


@NEEDS_DB
def test_lag_features_no_leakage():
    from dotenv import load_dotenv

    from etl.db_connection import get_engine
    from features.build_feature_table import _run_leakage_test
    from features.weekly_aggregation import load_weekly_aggregates
    from models.data_split import load_features

    load_dotenv(PIPELINE_ROOT / ".env")
    engine = get_engine()
    df_weekly = load_weekly_aggregates(engine)
    df_features = load_features()
    all_pass = _run_leakage_test(df_features, df_weekly)
    assert all_pass, "Leakage test failed — lag features reference future data"
