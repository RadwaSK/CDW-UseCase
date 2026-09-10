"""Centralized application settings, read once from the environment.

No module should read os.environ directly — import `settings` from here.
Env vars always win over the .env file, so conftest.py can force test-only
values (USE_FAKE_EMBEDDINGS, etc.) without touching .env itself.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str

    llm_provider: str = "azure_openai"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    openai_api_key: str = ""
    openai_chat_model: str = ""
    openai_embedding_model: str = ""

    # LangSmith tracing config. This is the single source of truth; app.core.
    # observability.configure_langsmith() copies it into the LANGSMITH_* env vars
    # that LangChain reads, once at startup. Disabled by default and forced off
    # in tests and the offline evaluation.
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "multi-agent-repo-reviewer"
    langsmith_endpoint: str = ""

    use_fake_embeddings: bool = False
    use_fake_llm: bool = False
    embedding_dimension: int = 1536
    sample_data_dir: str = "sample_data"
    retrieval_top_k: int = 6
    max_revisions: int = 1

    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
