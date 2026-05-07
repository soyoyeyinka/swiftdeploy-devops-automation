import os
import time
import random
from datetime import datetime, timezone
from collections import defaultdict
from flask import Flask, jsonify, request, Response, g

app = Flask(__name__)

START_TIME = time.time()

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
MODE = os.getenv("MODE", "stable")
APP_PORT = int(os.getenv("APP_PORT", "3000"))

chaos_state = {
    "mode": "recover",
    "duration": 0,
    "error_rate": 0.0
}

REQUEST_TOTAL = defaultdict(int)
REQUEST_DURATION_BUCKETS = [
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0
]
REQUEST_DURATION_HISTOGRAM = defaultdict(lambda: defaultdict(int))
REQUEST_DURATION_SUM = defaultdict(float)
REQUEST_DURATION_COUNT = defaultdict(int)


def normalise_path(path):
    if path == "/":
        return "/"
    if path.startswith("/chaos"):
        return "/chaos"
    if path.startswith("/healthz"):
        return "/healthz"
    if path.startswith("/metrics"):
        return "/metrics"
    return path


def chaos_code():
    if chaos_state["mode"] == "slow":
        return 1
    if chaos_state["mode"] == "error":
        return 2
    return 0


def app_mode_value():
    return 1 if MODE == "canary" else 0


@app.before_request
def start_timer():
    g.start_time = time.time()


@app.after_request
def record_metrics_and_headers(response):
    duration = time.time() - getattr(g, "start_time", time.time())
    path = normalise_path(request.path)
    method = request.method
    status_code = str(response.status_code)

    label_key = (method, path, status_code)
    REQUEST_TOTAL[label_key] += 1

    histogram_key = (method, path)
    REQUEST_DURATION_SUM[histogram_key] += duration
    REQUEST_DURATION_COUNT[histogram_key] += 1

    for bucket in REQUEST_DURATION_BUCKETS:
        if duration <= bucket:
            REQUEST_DURATION_HISTOGRAM[histogram_key][bucket] += 1

    if MODE == "canary":
        response.headers["X-Mode"] = "canary"

    return response


@app.route("/", methods=["GET"])
def index():
    chaos_response = apply_chaos_if_enabled()
    if chaos_response:
        return chaos_response

    return jsonify({
        "message": "Welcome to SwiftDeploy API",
        "mode": MODE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    uptime = round(time.time() - START_TIME, 2)

    return jsonify({
        "status": "ok",
        "mode": MODE,
        "version": APP_VERSION,
        "uptime_seconds": uptime
    }), 200


@app.route("/chaos", methods=["POST"])
def chaos():
    if MODE != "canary":
        return jsonify({
            "error": "chaos endpoint is only active in canary mode",
            "mode": MODE
        }), 403

    data = request.get_json(silent=True) or {}
    requested_mode = data.get("mode")

    if requested_mode == "slow":
        duration = int(data.get("duration", 1))
        chaos_state["mode"] = "slow"
        chaos_state["duration"] = duration
        chaos_state["error_rate"] = 0.0

        return jsonify({
            "message": "slow chaos mode enabled",
            "duration": duration
        }), 200

    if requested_mode == "error":
        rate = float(data.get("rate", 0.5))
        rate = max(0.0, min(rate, 1.0))

        chaos_state["mode"] = "error"
        chaos_state["duration"] = 0
        chaos_state["error_rate"] = rate

        return jsonify({
            "message": "error chaos mode enabled",
            "rate": rate
        }), 200

    if requested_mode == "recover":
        chaos_state["mode"] = "recover"
        chaos_state["duration"] = 0
        chaos_state["error_rate"] = 0.0

        return jsonify({
            "message": "chaos mode disabled"
        }), 200

    return jsonify({
        "error": "invalid chaos mode",
        "allowed_modes": ["slow", "error", "recover"]
    }), 400


@app.route("/metrics", methods=["GET"])
def metrics():
    lines = []

    lines.append("# HELP http_requests_total Total number of HTTP requests.")
    lines.append("# TYPE http_requests_total counter")

    for (method, path, status_code), count in sorted(REQUEST_TOTAL.items()):
        lines.append(
            f'http_requests_total{{method="{method}",path="{path}",status_code="{status_code}"}} {count}'
        )

    lines.append("")
    lines.append("# HELP http_request_duration_seconds HTTP request duration in seconds.")
    lines.append("# TYPE http_request_duration_seconds histogram")

    for (method, path), bucket_counts in sorted(REQUEST_DURATION_HISTOGRAM.items()):
        running_count = 0

        for bucket in REQUEST_DURATION_BUCKETS:
            running_count = bucket_counts.get(bucket, 0)
            lines.append(
                f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bucket}"}} {running_count}'
            )

        total_count = REQUEST_DURATION_COUNT[(method, path)]
        total_sum = REQUEST_DURATION_SUM[(method, path)]

        lines.append(
            f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {total_count}'
        )
        lines.append(
            f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total_sum}'
        )
        lines.append(
            f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {total_count}'
        )

    uptime = round(time.time() - START_TIME, 2)

    lines.append("")
    lines.append("# HELP app_uptime_seconds Application uptime in seconds.")
    lines.append("# TYPE app_uptime_seconds gauge")
    lines.append(f"app_uptime_seconds {uptime}")

    lines.append("")
    lines.append("# HELP app_mode Current app mode. 0 means stable, 1 means canary.")
    lines.append("# TYPE app_mode gauge")
    lines.append(f"app_mode {app_mode_value()}")

    lines.append("")
    lines.append("# HELP chaos_active Current chaos state. 0 means none, 1 means slow, 2 means error.")
    lines.append("# TYPE chaos_active gauge")
    lines.append(f"chaos_active {chaos_code()}")

    return Response("\n".join(lines) + "\n", mimetype="text/plain")


def apply_chaos_if_enabled():
    if MODE != "canary":
        return None

    if chaos_state["mode"] == "slow":
        time.sleep(chaos_state["duration"])

    if chaos_state["mode"] == "error":
        if random.random() < chaos_state["error_rate"]:
            return jsonify({
                "error": "simulated canary error",
                "mode": MODE
            }), 500

    return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
