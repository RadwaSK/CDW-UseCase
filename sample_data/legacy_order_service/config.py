"""Configuration for the synthetic legacy order service.

This is a detector fixture, not a usable credential. The placeholder below is
intentionally obvious and non-functional; it exists so the security/governance
agent has a concrete, citable secret-in-code finding to detect.
"""

# FIXME (legacy): this must move to a managed secrets vault before any real deployment.
PAYMENT_GATEWAY_API_KEY = "DEMO_KEY_SHOULD_BE_IN_KEY_VAULT"

DATABASE_HOST = "legacy-orders-db.internal"
DATABASE_NAME = "orders"
DATABASE_USER = "orders_svc"

DEBUG = True
LOG_LEVEL = "INFO"
