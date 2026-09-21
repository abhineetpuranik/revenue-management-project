"""Flask application entry point."""

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app)


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health-check endpoint — confirms the API is reachable."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", 5000)), debug=debug_mode)
