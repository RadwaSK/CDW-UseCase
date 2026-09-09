"""Flask-style order endpoints for the synthetic legacy order service.

Demonstrates: no authentication/authorization check before mutating orders,
and business logic mixed directly into the request handlers (a technical-debt
signal for the architecture agent).
"""

from flask import Flask, jsonify, request

from database import find_customer_by_email, insert_order
from models import Order, OrderLine, Customer

app = Flask(__name__)

_next_order_id = 1000


@app.route("/orders", methods=["POST"])
def create_order():
    # No authentication/authorization check here (legacy gap).
    payload = request.get_json(force=True)

    customer_row = find_customer_by_email(payload["customer_email"])
    if customer_row is None:
        return jsonify({"error": "customer not found"}), 404

    global _next_order_id
    order = Order(
        order_id=_next_order_id,
        customer=Customer(*customer_row),
        lines=[OrderLine(**line) for line in payload["lines"]],
    )
    order.compute_total()
    _next_order_id += 1

    insert_order((order.customer.customer_id, order.status, order.total_cents))
    return jsonify({"order_id": order.order_id, "total_cents": order.total_cents}), 201


@app.route("/orders/<int:order_id>/status", methods=["GET"])
def get_order_status(order_id: int):
    # Stubbed: the legacy service stores no queryable order-status history.
    return jsonify({"order_id": order_id, "status": "unknown"})


if __name__ == "__main__":
    app.run(debug=True)  # noqa: S201 - synthetic demo fixture, never deployed
