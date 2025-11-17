"""Application configuration management."""

from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "LangGraph Orchestration"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # API Keys
openai_api_key="REDACTED"
    google_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # LLM Configuration
    llm_model: str = "gpt-4.1-nano"
    summary_model: str = "gpt-4o-mini"
    llm_context_limit: int = 128000
    context_threshold_percentage: int = 70

    # Tokenizer Configuration
    tokenizer_type: str = "tiktoken"

    # Storage Configuration
    storage_type: str = "langgraph"

    # Conversation Configuration
    conversation_id: Optional[str] = None

    # Node Configuration
    query_builder_timeout: int = 30

    # Graph Configuration
    max_iterations: int = 100


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

