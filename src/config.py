"""Configuration settings for the Ally AI service."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    llm_model: str = "gpt-4o"

    # Research / Web Search
    perplexity_api_key: str = "REDACTED_PERPLEXITY_API_KEY"

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
            return self.openai_api_key
        if self.is_gemini:
            return self.google_api_key
        return self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

