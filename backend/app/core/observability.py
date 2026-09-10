"""Wire the LangSmith settings into the variables LangChain actually reads.

`settings` (app.core.config) is the single source of truth for tracing
configuration. LangChain's client discovers tracing from a fixed set of
environment variable names, not from our Settings object, so this module copies
the resolved settings into those names once, at application startup. Nothing
else in the app should touch LangSmith configuration.

Tests and the offline evaluation set ``LANGSMITH_TRACING=false`` in the
environment *before* ``settings`` is constructed, so ``settings.langsmith_tracing``
is already ``False`` for them and this only ever writes ``"false"``. It mirrors
the settings; it can never override an opt-out.
"""

import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Propagate ``settings.langsmith_*`` into the ``LANGSMITH_*`` environment.

    Idempotent. Safe to call when tracing is disabled — it writes ``"false"`` and
    leaves the credentials untouched.
    """
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
