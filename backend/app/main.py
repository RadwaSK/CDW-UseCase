"""FastAPI application entrypoint: app instance, CORS, and route registration."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Enterprise Modernization Multi-Agent System",
    description=(
        "Technical demonstration of a safe, stateful multi-agent workflow for "
        "legacy-application modernization made-up use case. Not an official CDW product."
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
app.include_router(health_router)
