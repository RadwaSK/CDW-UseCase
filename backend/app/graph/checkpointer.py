"""Postgres checkpointer so a paused graph can resume with the same state.

LangGraph owns these tables and creates them via its own setup() — they are
deliberately outside app/db/models.py and init_db().
"""

import logging
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Our own Pydantic state models must be explicitly allow-listed for msgpack, or
# LangGraph warns now and refuses to deserialize them in a future version.
_ALLOWED_MSGPACK_MODULES = (
    ("app.models.evidence", "EvidenceReference"),
    ("app.models.evidence", "RetrievedEvidence"),
    ("app.models.findings", "ArchitectureFinding"),
    ("app.models.findings", "RiskFinding"),
    ("app.models.plan", "ModernizationOption"),
    ("app.models.plan", "ModernizationPlan"),
    ("app.models.plan", "RoadmapPhase"),
    ("app.models.review", "RemovedClaim"),
    ("app.models.review", "ReviewDecision"),
    ("app.models.report", "ApprovalRecord"),
    ("app.models.report", "AssessmentReport"),
    ("app.models.report", "RiskRegisterEntry"),
    ("app.models.report", "ScopeSummary"),
)


def _psycopg_dsn() -> str:
    """SQLAlchemy URL -> plain libpq DSN (psycopg doesn't accept the +driver form)."""
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_checkpointer() -> PostgresSaver:
    """Process-wide checkpointer. setup() is idempotent, like init_db()."""
    pool = ConnectionPool(
        conninfo=_psycopg_dsn(),
        max_size=5,
        open=True,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )
    saver = PostgresSaver(
        pool, serde=JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES)
    )
    saver.setup()
    logger.info("checkpointer_ready")
    return saver
