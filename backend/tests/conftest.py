"""
Pytest configuration — provides a Flask test client fixture.

The fixture creates a fresh app instance per test session, injects a
real DB engine and the real production model (both loaded once), so tests
run against actual data.  This validates the full stack: SQL queries, model
predictions, and JSON serialisation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure backend/ is importable from tests/
_BACKEND = str(Path(__file__).resolve().parent.parent)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Also ensure data-pipeline/ is on the path (needed by services)
_PIPELINE = str(Path(__file__).resolve().parent.parent.parent / "data-pipeline")
if _PIPELINE not in sys.path:
    sys.path.insert(0, _PIPELINE)


@pytest.fixture(scope="session")
def app():
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()
