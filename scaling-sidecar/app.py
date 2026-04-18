"""
Scaling Sidecar — Exposes Docker Compose scaling operations over HTTP.

This lightweight Flask service runs alongside the Sentinel stack with
the Docker socket mounted. The orchestrator calls it to scale the
demo-backend service up/down without requiring Docker-in-Docker.

Endpoints:
  POST /scale    — Scale a service to N replicas
  GET  /replicas — Get current replica counts
  GET  /health   — Health check
"""

import json
import os
import subprocess
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

COMPOSE_DIR = os.environ.get("COMPOSE_DIR", "/workspace")
COMPOSE_PROJECT = os.environ.get("COMPOSE_PROJECT", "sentinel")


def _run_compose(*args, timeout=30):
    """Run a docker compose command and return (returncode, stdout, stderr)."""
    cmd = ["docker", "compose", "-f", f"{COMPOSE_DIR}/docker-compose.yml"]
    if COMPOSE_PROJECT:
        cmd.extend(["-p", COMPOSE_PROJECT])
    cmd.extend(args)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout, result.stderr


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "scaling-sidecar"})


@app.route("/scale", methods=["POST"])
def scale():
    """Scale a service to the desired replica count.

    Body: {"service": "demo-backend", "replicas": 3}
    Returns: {"status": "ok", "service": ..., "desired": ..., "elapsed_ms": ...}
    """
    data = request.get_json(force=True)
    service = data.get("service", "demo-backend")
    replicas = int(data.get("replicas", 1))

    # Safety bounds
    replicas = max(1, min(replicas, 10))

    app.logger.info(f"Scaling {service} to {replicas} replicas")
    start = time.time()

    rc, stdout, stderr = _run_compose(
        "up", "-d", "--scale", f"{service}={replicas}", "--no-recreate", service
    )

    elapsed_ms = int((time.time() - start) * 1000)

    if rc != 0:
        app.logger.error(f"Scale failed: {stderr}")
        return jsonify({
            "status": "error",
            "service": service,
            "desired": replicas,
            "error": stderr.strip(),
            "elapsed_ms": elapsed_ms,
        }), 500

    return jsonify({
        "status": "ok",
        "service": service,
        "desired": replicas,
        "elapsed_ms": elapsed_ms,
    })


@app.route("/replicas", methods=["GET"])
def replicas():
    """Get current replica status for all services or a specific service.

    Query: ?service=demo-backend (optional)
    Returns: {"demo-backend": {"desired": 3, "running": 2}}
    """
    target_service = request.args.get("service")

    rc, stdout, stderr = _run_compose("ps", "--format", "json")
    if rc != 0:
        return jsonify({"error": stderr.strip()}), 500

    # Parse docker compose ps JSON output (one JSON object per line)
    services = {}
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            svc_name = entry.get("Service", "")
            state = entry.get("State", "").lower()

            if svc_name not in services:
                services[svc_name] = {"total": 0, "running": 0}
            services[svc_name]["total"] += 1
            if state == "running":
                services[svc_name]["running"] += 1
        except json.JSONDecodeError:
            continue

    if target_service:
        info = services.get(target_service, {"total": 0, "running": 0})
        return jsonify({target_service: info})

    return jsonify(services)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)
