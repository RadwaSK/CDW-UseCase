"""Centralized application settings, read once from the environment.

No module should read os.environ directly — import `settings` from here.
Env vars always win over the .env file (pydantic-settings' own priority
order), so conftest.py can load .env.test and it overrides .env untouched.
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

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "cdw-usecase"
    langsmith_endpoint: str = ""

    use_fake_embeddings: bool = False
    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
