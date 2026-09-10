"""Pytest fixtures.

Import order matters here: _enforce_test_environment() must run before any
app.* import, since importing app.core.config instantiates Settings from
whatever is currently in os.environ (see app/core/config.py).
"""

import os

import pytest


def _enforce_test_environment() -> None:
    """Force fake embeddings and refuse a non-test DATABASE_URL."""
    # Tests never call a real model, whatever .env says — protects the Azure
    # credit budget and keeps runs deterministic and offline.
    os.environ["USE_FAKE_EMBEDDINGS"] = "true"
    os.environ["USE_FAKE_LLM"] = "true"

    # Refuse to run against anything that isn't clearly a test database, so a
    # .env pointed at real data can't be mutated by a test run.
    db_url = os.environ.get("DATABASE_URL", "")
    if "test" not in db_url.lower() and os.environ.get("TEST_DB", "false").lower() != "true":
        raise RuntimeError(
            f"DATABASE_URL does not look like a test database: {db_url!r}. "
            "Include 'test' in the database name, or set TEST_DB=true to allow it."
        )


_enforce_test_environment()

# Only safe to import app.* below this point — see module docstring.
from app.db.init_db import init_db  # noqa: E402
from app.db.models import Assessment  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _initialized_db():
    """Create extension + tables once per test session, before any DB access."""
    init_db()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_assessments(db_session):
    """Assessments (and their cascaded artifacts/trace/tickets) reset per test.

    document_chunks is intentionally left alone — ingestion is idempotent and
    session-scoped fixtures reuse it across tests instead of re-embedding.
    """
    yield
    db_session.query(Assessment).delete()
    db_session.commit()


@pytest.fixture
def assessment_record(db_session):
    """A real assessments row, so trace events can satisfy their foreign key."""
    assessment = Assessment(
        sample_app_id="legacy_order_service",
        objective="Prepare the order service for cloud deployment while protecting customer PII.",
        status="pending",
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)
    return assessment.id


@pytest.fixture(scope="session")
def ingested(_initialized_db):
    """Run ingestion once per test session; chunk/retrieval tests depend on this."""
    from app.services.ingestion import ingest_all

    return ingest_all()
