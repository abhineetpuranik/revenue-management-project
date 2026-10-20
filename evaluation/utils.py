"""Shared helpers for all evaluation scripts.

This module is the only place that knows where the pipeline root is and how to
reach the application databases.  Every evaluation script imports from here
instead of hard-coding paths or duplicating sys.path manipulation.

Hard rules enforced here:
- Database engines are obtained from the application's own db_connection module
  (read-only by convention — evaluation scripts only ever issue SELECT statements).
- Ground-truth reads go through get_gt_engine().
- No evaluation output lands inside data-pipeline/ or backend/.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_RANDOM_SEED: int = 42

# Absolute path to the data-pipeline package (parent of etl/, models/, etc.)
PIPELINE_ROOT: Path = Path(__file__).resolve().parent.parent / "data-pipeline"

# All evaluation outputs go here
RESULTS_DIR: Path = Path(__file__).resolve().parent / "results"


# ---------------------------------------------------------------------------
# sys.path bootstrap  (called lazily when a DB or pipeline import is needed)
# ---------------------------------------------------------------------------

def _ensure_pipeline_on_path() -> None:
    """Insert PIPELINE_ROOT into sys.path if not already present."""
    root_str = str(PIPELINE_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


# ---------------------------------------------------------------------------
# Database engine accessors
# ---------------------------------------------------------------------------

def get_engine():
    """Return an SQLAlchemy Engine for the main application database.

    SELECT-only by convention — no DDL or DML in evaluation scripts.
    """
    _ensure_pipeline_on_path()
    from etl.db_connection import get_engine as _get_engine  # noqa: PLC0415
    return _get_engine()


def get_gt_engine():
    """Return an SQLAlchemy Engine for the ground-truth database.

    Ground-truth columns (true_elasticity, true_segment) must ONLY be read
    through this engine inside evaluation scripts.
    """
    _ensure_pipeline_on_path()
    from etl.db_connection import get_gt_engine as _get_gt_engine  # noqa: PLC0415
    return _get_gt_engine()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def ensure_results_dir() -> Path:
    """Create RESULTS_DIR if it does not exist; return it."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def save_fig(fig, name: str) -> Path:
    """Save a matplotlib Figure to RESULTS_DIR/<name>.png and close it."""
    import matplotlib  # noqa: PLC0415
    ensure_results_dir()
    path = RESULTS_DIR / name
    if not name.endswith(".png"):
        path = RESULTS_DIR / (name + ".png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    matplotlib.pyplot.close(fig)
    logger.info("Saved figure: %s", path)
    return path


def save_json(data: dict | list, name: str) -> Path:
    """Serialise *data* to RESULTS_DIR/<name>.json."""
    ensure_results_dir()
    path = RESULTS_DIR / name
    if not name.endswith(".json"):
        path = RESULTS_DIR / (name + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=_json_default)
    logger.info("Saved JSON: %s", path)
    return path


def save_csv(df: pd.DataFrame, name: str) -> Path:
    """Save a DataFrame to RESULTS_DIR/<name>.csv."""
    ensure_results_dir()
    path = RESULTS_DIR / name
    if not name.endswith(".csv"):
        path = RESULTS_DIR / (name + ".csv")
    df.to_csv(path, index=False)
    logger.info("Saved CSV: %s", path)
    return path


def _json_default(obj):
    """JSON serialiser for numpy / pandas types."""
    import numpy as np  # noqa: PLC0415
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


# ---------------------------------------------------------------------------
# Metadata loader
# ---------------------------------------------------------------------------

def load_metadata() -> dict:
    """Load data-pipeline/models/artifacts/metadata.json and return it."""
    meta_path = PIPELINE_ROOT / "models" / "artifacts" / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"metadata.json not found at {meta_path}.\n"
            "Run Phase 5 (models/train_forecasting_models.py) first."
        )
    with open(meta_path, encoding="utf-8") as fh:
        return json.load(fh)
