"""Detector precision — the rules must separate real violations from correct patterns."""

import pytest

from app.graph.fake_agents import _has_hardcoded_secret, _logs_pii


@pytest.mark.parametrize(
    "line",
    [
        'PAYMENT_GATEWAY_API_KEY = "DEMO_KEY_SHOULD_BE_IN_KEY_VAULT"',
        "SECRET_TOKEN = 'abc123'",
        'db_password = "hunter2"',
    ],
)
def test_flags_literal_credential_assignments(line):
    assert _has_hardcoded_secret(line)


@pytest.mark.parametrize(
    "line",
    [
        # Reading a credential from the environment is the prescribed pattern.
        'WAREHOUSE_API_KEY = os.environ.get("WAREHOUSE_API_KEY")',
        'TOKEN = os.getenv("TOKEN")',
        'DATABASE_HOST = "legacy-orders-db.internal"',
        "LOG_LEVEL = 'INFO'",
    ],
)
def test_does_not_flag_correct_or_unrelated_patterns(line):
    assert not _has_hardcoded_secret(line)


@pytest.mark.parametrize(
    "line",
    [
        'logger.info("Looked up customer record: %s", row)',
        'logger.info("user email is %s", email)',
        'logging.debug("record", record)',
    ],
)
def test_flags_log_calls_carrying_pii(line):
    assert _logs_pii(line)


@pytest.mark.parametrize(
    "line",
    [
        # Logs a lookup key and a boolean — the prescribed pattern.
        'logger.info("item_lookup", extra={"sku": sku, "found": row is not None})',
        'logger.info("started", extra={"service": SERVICE_NAME})',
        # The word appears, but not in a logging call.
        "row = cursor.fetchone()",
    ],
)
def test_does_not_flag_safe_or_non_logging_lines(line):
    assert not _logs_pii(line)


def test_clean_sample_app_produces_no_risk_findings(ingested, db_session):
    """The clean fixture must come back low-risk, or demo path 1 has no path."""
    from app.graph.fake_agents import fake_risk_findings
    from app.tools.repository_evidence import RepositoryEvidenceTool

    evidence = RepositoryEvidenceTool(db_session).search(
        "hard-coded secret credential PII logging authentication authorization SQL injection",
        sample_app_id="modern_inventory_service",
    )
    assert evidence, "no evidence retrieved for the clean sample app"
    assert fake_risk_findings(evidence) == []
