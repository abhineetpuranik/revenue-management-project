"""Phase 13 — Item 15: API documented-keys contract (KI-01).

The pricing ``binding_constraint`` field can take the value ``TIE_TOLERANCE``
which ``api.md`` omits (see KI-01).  This test asserts that every
``binding_constraint`` value returned by the recommendations endpoint belongs
to the known-valid set, including ``TIE_TOLERANCE``.  Requires the Flask app
and DB (uses the shared ``client`` fixture from conftest.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parent.parent)
_PIPELINE = str(Path(__file__).resolve().parent.parent.parent / "data-pipeline")
for p in (_BACKEND, _PIPELINE):
    if p not in sys.path:
        sys.path.insert(0, p)


def _db_ready() -> bool:
    """True when DB credentials are available (env, backend/.env, or
    data-pipeline/.env).  The Flask app (via the ``client`` fixture) needs a
    live MySQL to build responses, so the test skips cleanly where no
    DB/credentials exist and runs for full-stack teams."""
    from dotenv import load_dotenv

    here = Path(__file__).resolve()
    for env in (here.parent.parent / ".env",                 # backend/.env
                here.parent.parent.parent / "data-pipeline" / ".env"):
        load_dotenv(env)
    return bool(os.getenv("DB_USER") and os.getenv("DB_PASSWORD"))


NEEDS_DB = pytest.mark.skipif(
    not _db_ready(), reason="requires live MySQL + DB credentials"
)


def get_json(client, url):
    resp = client.get(url)
    return resp, resp.get_json()


@NEEDS_DB
def test_binding_constraint_includes_tie_tolerance(client):
    """KI-01: TIE_TOLERANCE is a valid binding_constraint value even though
    api.md omits it."""
    _, data = get_json(client, "/api/pricing/recommendations?page_size=200")
    constraints = {r["binding_constraint"] for r in data["recommendations"]}
    # Known-valid binding_constraint values produced by the pricing optimizer.
    valid = {
        "MAX_CHANGE", "MARGIN", "PRICE_RANGE", "ELASTICITY_UNRELIABLE", "STOCK",
        "NO_FEASIBLE_PRICE", "TIE_TOLERANCE",
    }
    unexpected = constraints - valid
    assert not unexpected, f"Unexpected binding_constraint values: {unexpected}"
