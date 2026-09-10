"""Configuration for the synthetic modern inventory service.

Every secret is read from the environment at runtime and injected from a managed
vault by the deployment platform — nothing sensitive is committed here.
"""

import os

# Sourced from Azure Key Vault via the platform's secret injection; absent here by design.
WAREHOUSE_API_KEY = os.environ.get("WAREHOUSE_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

SERVICE_NAME = "modern-inventory-service"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "json"
DEBUG = False
