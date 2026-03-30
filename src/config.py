"""Configuration settings for the Ally AI service."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the absolute path to the .env file (in the ally project root)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration (single-model fallback when routing is disabled)
    llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
openai_api_key="REDACTED"
    anthropic_api_key: str = ""
    google_api_key: str = ""
    llm_model: str = "gpt-4o"

    # Multi-Model Routing
    # Set enable_model_routing=True to route queries to different models by complexity.
    # Set to False to use single llm_provider/llm_model for everything (original behavior).
    enable_model_routing: bool = False

    # Tier 1 — LITE: greetings, simple lookups, chitchat
    lite_provider: Literal["openai", "anthropic", "gemini"] = "gemini"
    lite_model: str = "gemini-2.0-flash-lite"

    # Tier 2 — STANDARD: CRM operations, summaries, data questions
    standard_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    standard_model: str = "gpt-4o-mini"

    # Tier 3 — POWER: deep analysis, research, multi-step reasoning
    power_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    power_model: str = "gpt-4o"

    # Research / Web Search
PERPLEXITY_API_KEY=REDACTED

    # Backend GraphQL
    backend_graphql_url: str = "http://localhost:3000/graphql"

    # Database
    DATABASE_URL_ALLY: str = "postgresql://postgres:postgres@localhost:5432/allyos"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # AWS Cognito (for JWT validation)
    aws_cognito_region: str = ""
    aws_cognito_user_pool_id: str = ""
    aws_cognito_client_id: str = ""

    # GraphQL Client Configuration
    graphql_connect_timeout: float = 10.0   # seconds to establish TCP connection
    graphql_request_timeout: float = 30.0   # seconds per query/mutation

    # Token / Context Configuration
    default_context_window: int = 128000
    context_warning_threshold: float = 0.7   # 70% — emit warning
    context_limit_threshold: float = 0.8     # 80% — block further requests
    model_context_windows: dict[str, int] = {
        # OpenAI
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        # Anthropic
        "claude-3-5-sonnet": 200000,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        # Google Gemini
        "gemini-1.5-pro": 2000000,
        "gemini-1.5-flash": 1000000,
        "gemini-2.0-flash": 1048576,
        "gemini-2.0-flash-lite": 1048576,
        "gemini-2.5-pro": 1048576,
        "gemini-2.5-flash": 1048576,
    }

    @property
    def is_openai(self) -> bool:
        """Check if using OpenAI provider."""
        return self.llm_provider == "openai"

    @property
    def is_anthropic(self) -> bool:
        """Check if using Anthropic provider."""
        return self.llm_provider == "anthropic"

    @property
    def is_gemini(self) -> bool:
        """Check if using Google Gemini provider."""
        return self.llm_provider == "gemini"

    @property
    def api_key(self) -> str:
        """Get the API key for the configured provider."""
        if self.is_openai:
openai_api_key="REDACTED"
        if self.is_gemini:
            return self.google_api_key
        return self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

