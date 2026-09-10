"""LangSmith wiring: settings is the source of truth, and tests never trace.

The suite must not emit LangSmith traces — it would add a network call per graph
node to an otherwise offline run. conftest.py pins the flag off before any
import; these tests confirm it stuck and that configure_langsmith() only ever
mirrors settings, never re-enables tracing.
"""

import os

import pytest
from langsmith import utils as ls_utils

from app.core import config
from app.core.observability import configure_langsmith

_LANGSMITH_VARS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
)


@pytest.fixture(autouse=True)
def _restore_langsmith_env():
    """configure_langsmith() writes os.environ directly; put it back after each test."""
    saved = {k: os.environ.get(k) for k in _LANGSMITH_VARS}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    ls_utils.get_env_var.cache_clear()


def test_tracing_is_disabled_for_the_test_suite():
    assert os.environ.get("LANGSMITH_TRACING") == "false"
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"


def test_langsmith_client_reports_tracing_disabled():
    ls_utils.get_env_var.cache_clear()
    assert ls_utils.tracing_is_enabled() is False


def test_settings_langsmith_tracing_is_false_under_test():
    assert config.settings.langsmith_tracing is False


def test_configure_langsmith_mirrors_settings_and_cannot_enable_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")  # pretend something turned it on
    configure_langsmith()  # settings.langsmith_tracing is still False under test
    assert os.environ["LANGSMITH_TRACING"] == "false"

    ls_utils.get_env_var.cache_clear()
    assert ls_utils.tracing_is_enabled() is False


def test_configure_langsmith_does_not_clobber_langchain_defaults_with_blanks(monkeypatch):
    """An unset endpoint must not overwrite LangChain's default with an empty string."""
    monkeypatch.setattr(config.settings, "langsmith_endpoint", "", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    configure_langsmith()
    assert "LANGSMITH_ENDPOINT" not in os.environ


def test_configure_langsmith_propagates_a_set_endpoint(monkeypatch):
    url = "https://example.test"
    monkeypatch.setattr(config.settings, "langsmith_endpoint", url, raising=False)
    configure_langsmith()
    assert os.environ["LANGSMITH_ENDPOINT"] == url
