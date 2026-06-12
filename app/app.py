import os
import random

from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics


app = Flask(__name__)
PrometheusMetrics(app)

ERR = float(os.getenv("ERROR_RATE", "0"))
VER = os.getenv("VERSION", "v1")


@app.get("/")
def index():
    if random.random() < ERR:
        return jsonify(error="injected", version=VER), 500
    return jsonify(ok=True, version=VER)


@app.get("/healthz")
def healthz():
    return "ok", 200


@app.route('/bad-health')
def bad_health():
    """Simulates a bad health check that causes the app to exit."""
    print("Received request to /bad-health, simulating failure...")
    sys.exit(1)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
