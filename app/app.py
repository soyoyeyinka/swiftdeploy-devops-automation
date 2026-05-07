import os
import time
import random
from datetime import datetime, timezone
from flask import Flask, jsonify, request

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


@app.after_request
def add_mode_header(response):
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
