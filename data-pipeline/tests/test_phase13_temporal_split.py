"""Phase 13 — Item 10: temporal split no-overlap test.

Confirms ``time_split()`` on the real ``forecast_features.csv`` never
overlaps train and test dates, and that the resulting split matches the
metadata recorded by Phase 5.  No DB access — reads the feature CSV only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def test_time_split_no_overlap():
    from models.data_split import load_features, time_split, TEST_WEEKS

    df = load_features()
    split = time_split(df, TEST_WEEKS)
    assert split.train_end < split.test_start, (
        f"LEAKAGE: train_end={split.train_end} >= test_start={split.test_start}"
    )


def test_time_split_matches_metadata():
    from models.data_split import load_features, time_split, TEST_WEEKS

    meta_path = PIPELINE_ROOT / "models" / "artifacts" / "metadata.json"
    with open(meta_path) as f:
        meta = json.load(f)

    df = load_features()
    split = time_split(df, TEST_WEEKS)
    assert split.test_start == meta["test_start"], (
        f"test_start mismatch: split={split.test_start} meta={meta['test_start']}"
    )
    assert split.test_end == meta["test_end"], (
        f"test_end mismatch: split={split.test_end} meta={meta['test_end']}"
    )
    assert split.n_train == meta["n_train"], (
        f"n_train mismatch: split={split.n_train} meta={meta['n_train']}"
    )
    assert split.n_test == meta["n_test"], (
        f"n_test mismatch: split={split.n_test} meta={meta['n_test']}"
    )
