"""
Database access helper for the backend.

Re-uses the data-pipeline's db_connection module so there is one connection
implementation in the project, not two.  The pipeline root is added to
sys.path here (once, at import time) so every other backend module can
import from data-pipeline packages without repeating the path manipulation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from config import Config

# ── PYTHONPATH: make data-pipeline importable ─────────────────────────────
_PIPELINE_ROOT = str(Config.PIPELINE_ROOT)
if _PIPELINE_ROOT not in sys.path:
    sys.path.insert(0, _PIPELINE_ROOT)

# Now safe to import from the pipeline
from etl.db_connection import get_engine  # noqa: E402  (import after sys.path)


def get_db():
    """Return the SQLAlchemy engine for revenue_management.

    The engine is cached by get_engine() so this is cheap to call.
    """
    return get_engine(Config.DB_NAME)
