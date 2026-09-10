"""HTTP endpoints for the synthetic modern inventory service.

Authorization is enforced on every state-changing endpoint, and liveness and
readiness probes are exposed for the platform.
"""

from functools import wraps

from flask import Flask, g, jsonify, request

from auth import verify_bearer_token
from repository import adjust_quantity, find_item_by_sku

app = Flask(__name__)


def requires_role(role: str):
    """Enforce authentication and role-based authorization before the handler runs."""

    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            principal = verify_bearer_token(request.headers.get("Authorization"))
            if principal is None:
                return jsonify({"error": "unauthorized"}), 401
            if role not in principal["roles"]:
                return jsonify({"error": "forbidden"}), 403
            g.principal = principal
            return handler(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/health/live", methods=["GET"])
def liveness():
    return jsonify({"status": "ok"})


@app.route("/health/ready", methods=["GET"])
def readiness():
    try:
        find_item_by_sku("__probe__")
    except Exception:
        return jsonify({"status": "degraded", "database": "unavailable"}), 503
    return jsonify({"status": "ok", "database": "ok"})


@app.route("/items/<sku>", methods=["GET"])
@requires_role("inventory.read")
def get_item(sku: str):
    row = find_item_by_sku(sku)
    if row is None:
        return jsonify({"error": "item not found"}), 404
    return jsonify({"sku": row[0], "name": row[1], "quantity": row[2]})


@app.route("/items/<sku>/adjust", methods=["POST"])
@requires_role("inventory.write")
def adjust_item(sku: str):
    payload = request.get_json(silent=True) or {}
    delta = payload.get("delta")
    if not isinstance(delta, int):
        return jsonify({"error": "delta must be an integer"}), 400

    adjust_quantity(sku, delta)
    return jsonify({"sku": sku, "adjusted_by": delta}), 200
