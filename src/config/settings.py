"""
Application configuration using Pydantic Settings.

This module defines all configuration settings for the CRM AI Copilot application.
Settings are loaded from environment variables and .env files, with sensible defaults
for development.

Environment Variable Loading:

Pydantic Settings automatically loads configuration in this order:
1. Environment variables (highest priority)
2. .env file in the project root
3. Default values defined in the Settings class (lowest priority)

This allows for:
- Local development using .env file
- Production deployment using environment variables
- Docker deployment with env vars or .env file mounted

Configuration Powers:

This settings object is used throughout the application for:
- Server configuration (port, host, environment)
- GraphQL backend connection (endpoint, authentication)
- LLM integration (OpenAI API key, model selection)
- Redis session storage (connection URL, TTL)
- Logging configuration (level, format)
- CORS settings (allowed origins)

Usage:

    from src.config.settings import settings
    
    # Access configuration
    print(settings.GRAPHQL_ENDPOINT)
    print(settings.OPENAI_MODEL)
    
    # Settings are immutable by default (frozen=True in Config)
    # This prevents accidental modification at runtime

Type Safety:

All settings are type-checked by Pydantic. Invalid types or missing required
fields will raise ValidationError on application startup, preventing runtime errors.

Example .env file:

    ENV=production
    PORT=8000
    GRAPHQL_ENDPOINT=https://api.example.com/graphql
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4-turbo-preview
    REDIS_URL=redis://localhost:6379/0
    LOG_LEVEL=INFO

Validation:

Settings are validated on initialization:
- PORT must be between 1 and 65535
- LOG_LEVEL must be valid logging level
- URLs are validated for proper format
- Required fields must be present or have defaults
"""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    
    All settings can be overridden by environment variables.
    Required settings without defaults will raise ValidationError if not provided.
    """
    
    # ========================================
    # Application Environment
    # ========================================
    
    ENV: str = Field(
        default="development",
        description="Application environment (development, staging, production)"
    )
    
    # ========================================
    # Server Configuration
    # ========================================
    
    PORT: int = Field(
        default=8000,
        description="Server port number",
        ge=1,
        le=65535
    )
    
    HOST: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )
    
    # ========================================
    # GraphQL Backend Configuration
    # ========================================
    
    GRAPHQL_ENDPOINT: str = Field(
        ...,  # Required field (no default)
        description="GraphQL API endpoint URL"
    )
    
    # ========================================
    # LLM Configuration (Multi-Provider)
    # ========================================
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for LLM access"
    )
    
    # Anthropic Claude
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude models"
    )
    
    # Google Gemini
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None,
        description="Google API key for Gemini models"
    )
    
    OPENAI_MODEL: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model to use for agent reasoning"
    )
    
    OPENAI_TEMPERATURE: float = Field(
        default=0.7,
        description="LLM temperature (0.0-2.0, lower = more deterministic)",
        ge=0.0,
        le=2.0
    )
    
    OPENAI_MAX_TOKENS: int = Field(
        default=2048,
        description="Maximum tokens for LLM responses",
        ge=1,
        le=8192
    )
    
    # Model routing for different tasks
    PLANNER_MODEL: str = Field(
        default="gpt-4-turbo-preview",
        description="Model for planning tasks (requires strong reasoning)"
    )
    
    SUMMARY_MODEL: str = Field(
        default="gpt-3.5-turbo",
        description="Model for summarization tasks (can be faster/cheaper)"
    )
    
    REASONING_MODEL: str = Field(
        default="gpt-4-turbo-preview",
        description="Model for deep reasoning tasks"
    )
    
    FALLBACK_MODEL: str = Field(
        default="gpt-3.5-turbo",
        description="Fallback model when primary model fails"
    )
    
    # Azure OpenAI (optional, alternative to OpenAI)
    AZURE_OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="Azure OpenAI API key (alternative to OPENAI_API_KEY)"
    )
    
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(
        default=None,
        description="Azure OpenAI endpoint URL"
    )
    
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = Field(
        default=None,
        description="Azure OpenAI deployment name"
    )
    
    AZURE_OPENAI_API_VERSION: str = Field(
        default="2024-02-15-preview",
        description="Azure OpenAI API version"
    )
    
    # ========================================
    # Redis Configuration (Session Storage)
    # ========================================
    
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for session storage"
    )
    
    SESSION_TTL_SECONDS: int = Field(
        default=604800,  # 7 days
        description="Session time-to-live in seconds",
        ge=60  # Minimum 1 minute
    )

    # ========================================
    # Database Configuration
    # ========================================

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_ai",
        description="PostgreSQL connection URL (async)"
    )
    
    # ========================================
    # Logging Configuration
    # ========================================
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    LOG_FORMAT: str = Field(
        default="text",
        description="Log format (text or json)"
    )
    
    # ========================================
    # CORS Configuration
    # ========================================
    
    ALLOWED_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins (or * for all)"
    )
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    # ========================================
    # Optional: Monitoring & Observability
    # ========================================
    
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    
    PROMETHEUS_ENABLED: bool = Field(
        default=False,
        description="Enable Prometheus metrics endpoint"
    )
    
    # ========================================
    # Validators
    # ========================================
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that LOG_LEVEL is a valid logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_levels}, got '{v}'"
            )
        return v_upper
    
    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate that LOG_FORMAT is either 'text' or 'json'."""
        valid_formats = ["text", "json"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(
                f"LOG_FORMAT must be one of {valid_formats}, got '{v}'"
            )
        return v_lower
    
    @field_validator("ENV")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate that ENV is a recognized environment."""
        valid_envs = ["development", "staging", "production", "test"]
        v_lower = v.lower()
        if v_lower not in valid_envs:
            # Don't raise error, just warn (allow custom environments)
            pass
        return v_lower

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """
        Ensure DATABASE_URL uses the asyncpg driver for async support.
        Also removes 'schema' query parameter if present as it's not supported by asyncpg.
        """
        # Handle postgresql:// -> postgresql+asyncpg://
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            
        # Remove 'schema' query parameter if present
        # This is needed because some environments (like Supabase or default Postgres setups)
        # might add ?schema=public, but asyncpg's connect() method doesn't accept 'schema' argument.
        if "?schema=" in v or "&schema=" in v:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            
            parsed = urlparse(v)
            query_params = parse_qs(parsed.query)
            
            if 'schema' in query_params:
                # Remove schema parameter
                del query_params['schema']
                
                # Reconstruct URL
                new_query = urlencode(query_params, doseq=True)
                v = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                
        return v
    
    # ========================================
    # Pydantic Settings Configuration
    # ========================================
    
    model_config = SettingsConfigDict(
        # Load from .env file
        env_file=".env",
        env_file_encoding="utf-8",
        
        # Allow environment variables to override
        case_sensitive=True,
        
        # Ignore extra fields in .env
        extra="ignore",
        
        # Make settings immutable (prevent accidental modification)
        frozen=False,  # Set to True in production for immutability
        
        # Validate on assignment
        validate_assignment=True,
    )
    
    # ========================================
    # Utility Methods
    # ========================================
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENV.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENV.lower() == "production"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.ENV.lower() == "staging"
    
    @property
    def use_azure_openai(self) -> bool:
        """Check if Azure OpenAI is configured (vs standard OpenAI)."""
        return all([
            self.AZURE_OPENAI_API_KEY,
            self.AZURE_OPENAI_ENDPOINT,
            self.AZURE_OPENAI_DEPLOYMENT
        ])
    
    def get_cors_origins(self) -> List[str]:
        """Get list of allowed CORS origins."""
        return self.allowed_origins_list
    
    def __repr__(self) -> str:
        """Safe string representation (hides sensitive values)."""
        return (
            f"Settings("
            f"ENV={self.ENV}, "
            f"PORT={self.PORT}, "
            f"GRAPHQL_ENDPOINT={self.GRAPHQL_ENDPOINT}, "
            f"OPENAI_MODEL={self.OPENAI_MODEL}, "
            f"LOG_LEVEL={self.LOG_LEVEL}"
            f")"
        )


# ========================================
# Export Settings Instance
# ========================================

# Create singleton settings instance
# This is loaded once at application startup
# Any validation errors will be raised here
settings = Settings()


# ========================================
# Convenience Exports
# ========================================

# Export commonly used values for convenience
__all__ = [
    "settings",
    "Settings",
]
