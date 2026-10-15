"""
Centralised error handling.

Every error response in the API has the same shape:

    {
        "error": {
            "status":  <HTTP status code as int>,
            "message": <human-readable description>
        }
    }

Register the handlers with register_error_handlers(app) in app.py.
"""

from __future__ import annotations

from flask import Flask, jsonify


def error_response(status: int, message: str):
    """Build a standard error JSON response."""
    resp = jsonify({"error": {"status": status, "message": message}})
    resp.status_code = status
    return resp


def register_error_handlers(app: Flask) -> None:
    """Attach 400, 404, and 500 handlers to *app*."""

    @app.errorhandler(400)
    def bad_request(exc):
        msg = exc.description if hasattr(exc, "description") else str(exc)
        return error_response(400, msg or "Bad request.")

    @app.errorhandler(404)
    def not_found(exc):
        msg = exc.description if hasattr(exc, "description") else str(exc)
        return error_response(404, msg or "Resource not found.")

    @app.errorhandler(500)
    def internal_error(exc):
        # Never expose internal details to the client
        app.logger.exception("Unhandled exception: %s", exc)
        return error_response(500, "An unexpected server error occurred.")
