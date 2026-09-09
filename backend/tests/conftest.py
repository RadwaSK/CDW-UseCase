"""Test-run guarantees, applied before app imports (see app/core/config.py)."""

import os

# Tests never call a real embedding model, whatever .env says — protects the
# Azure credit budget and keeps runs deterministic and offline.
os.environ["USE_FAKE_EMBEDDINGS"] = "true"

# Refuse to run against anything that isn't clearly a test database, so a .env
# pointed at real data can't be mutated by a test run.
_db_url = os.environ.get("DATABASE_URL", "")
if "test" not in _db_url.lower() and os.environ.get("TEST_DB", "false").lower() != "true":
    raise RuntimeError(
        f"DATABASE_URL does not look like a test database: {_db_url!r}. "
        "Include 'test' in the database name, or set TEST_DB=true to allow it."
    )
