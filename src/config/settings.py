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
    query_processing_model: str = "gpt-4o"
    llm_context_limit: int = 128000
    llm_max_tokens: int = 4096  # Max tokens for response generation (configurable via LLM_MAX_TOKENS in .env)
    context_threshold_percentage: int = 70

    # Tokenizer Configuration
    tokenizer_type: str = "tiktoken"

    # Storage Configuration
    storage_type: str = "langgraph"

    # Conversation Configuration
    conversation_id: Optional[str] = None

    # Node Configuration
    query_builder_timeout: int = 30
    query_processing_timeout: int = 60
    max_react_iterations: int = 10
    enable_tools: bool = True
    tool_result_limit: int = 10000  # Character limit for tool outputs in context

    # Graph Configuration
    max_iterations: int = 100

    # Database Configuration
    database_url_ally: Optional[str] = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600  # Recycle connections after 1 hour
    db_pool_timeout: int = 30  # Wait 30s for connection from pool
    db_connect_timeout: int = 10  # Connection timeout in seconds
    db_echo: bool = False  # Log SQL queries (useful for debugging)

    # Workspace Configuration
    workspace_id: Optional[str] = None

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

