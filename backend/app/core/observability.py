"""Copy settings.langsmith_* into the LANGSMITH_* env vars LangChain reads, once
at startup. settings is the source of truth; nothing else touches LangSmith
config. Tests and the evaluation pin LANGSMITH_TRACING=false before settings is
built, so this can only ever mirror an opt-out, never override one."""

import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Propagate settings.langsmith_* into the environment. Idempotent."""
    enabled = settings.langsmith_tracing
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"

    # Only propagate values that are actually set: an empty setting must never
    # clobber a LangChain default (notably the public endpoint URL).
    for name, value in (
        ("LANGSMITH_API_KEY", settings.langsmith_api_key),
        ("LANGSMITH_PROJECT", settings.langsmith_project),
        ("LANGSMITH_ENDPOINT", settings.langsmith_endpoint),
    ):
        if value:
            os.environ[name] = value

    if enabled:
        logger.info("langsmith_tracing_enabled", extra={"project": settings.langsmith_project})
    else:
        logger.info("langsmith_tracing_disabled")
