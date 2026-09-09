"""Health endpoint: reports application liveness and database reachability."""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        logger.warning("database_health_check_failed", extra={"error_class": type(exc).__name__})
        db_status = "unavailable"

    return {
        "status": "ok",
        "database": db_status,
    }
