"""FastAPI application entrypoint: app instance, CORS, and route registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assessments import router as assessments_router
from app.api.health import router as health_router
from app.api.sample_apps import router as sample_apps_router
from app.core.config import settings
from app.core.observability import configure_langsmith
from app.db.init_db import init_db
from app.graph.checkpointer import get_checkpointer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Turn LangSmith tracing on/off from settings before anything runs a graph.
    # In tests and the offline evaluation settings.langsmith_tracing is already
    # False, so this only ever disables it there.
    configure_langsmith()

    # Create schema on boot so a fresh `docker compose up` is enough. A failure
    # here must not kill the app — /health reports database status instead.
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("db_init_failed", extra={"error_class": type(exc).__name__})

    # Run the checkpointer's setup() now, while nothing else holds a database
    # transaction. Its migrations include CREATE INDEX CONCURRENTLY, which blocks
    # until every concurrent transaction finishes — if setup() is deferred to the
    # first assessment request, it deadlocks against that same request's open
    # session. get_checkpointer() is cached, so the request path reuses this.
    try:
        get_checkpointer()
    except Exception as exc:  # noqa: BLE001
        logger.warning("checkpointer_setup_failed", extra={"error_class": type(exc).__name__})

    yield


app = FastAPI(
    lifespan=lifespan,
    title="Enterprise Modernization Multi-Agent System",
    description=(
        "Technical demonstration of a safe, stateful multi-agent workflow for "
        "legacy-application modernization assessment."
    ),
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(health_router)  # bare /health alias
app.include_router(sample_apps_router, prefix="/api/v1")
app.include_router(assessments_router, prefix="/api/v1")
