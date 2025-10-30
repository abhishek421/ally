# Application settings and configuration
import os
import logging
from dotenv import load_dotenv
from typing import Optional
from prompts import QUERY_OPTIMIZER_TEMPLATE, DATA_EXTRACTOR_TEMPLATE

# Load variables from a .env file if present
load_dotenv()

logger = logging.getLogger(__name__)

# Prompt templates (imported from prompts module)
QUERY_OPTIMIZATION_TEMPLATE = QUERY_OPTIMIZER_TEMPLATE
DATA_EXTRACTOR_PROMPT_TEMPLATE = DATA_EXTRACTOR_TEMPLATE

# ============================================================================
# LLM Configuration System
# Supports database-backed configs with inheritance and env fallback
# ============================================================================

# Global ConfigManager instance (initialized on startup)
_config_manager: Optional['ConfigManager'] = None


def _get_env_agent_config(agent_name: str, default_provider: str = "openai", default_model: str = "gpt-4") -> dict:
    """
    Get configuration for a specific agent from environment variables (fallback only).
    
    This function is used when ConfigManager is not available or as a fallback.
    
    Args:
        agent_name: Name of the agent (e.g., 'query_optimizer')
        default_provider: Default provider if not specified
        default_model: Default model if not specified
    
    Returns:
        Dictionary with provider configuration
    """
    prefix = agent_name.upper()
    
    # Check for global env vars first
    provider = os.getenv(f"{prefix}_PROVIDER") or os.getenv("GLOBAL_LLM_PROVIDER", default_provider)
    model = os.getenv(f"{prefix}_MODEL") or os.getenv("GLOBAL_LLM_MODEL", default_model)
    
    # Get API key based on provider
    if provider.lower() == 'openai':
OPENAI_API_KEY=REDACTED
    elif provider.lower() == 'anthropic':
        api_key = os.getenv(f"{prefix}_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
    elif provider.lower() == 'gemini':
        api_key = os.getenv(f"{prefix}_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    else:
        api_key = os.getenv(f"{prefix}_API_KEY", "")
    
    return {
        "provider": provider,
        "model": model,
        "api_key": api_key
    }


def get_agent_config(agent_name: str, default_provider: str = "openai", default_model: str = "gpt-4") -> dict:
    """
    Get configuration for a specific agent.
    
    Priority order:
    1. ConfigManager (DB-backed with inheritance)
    2. Environment variables (backward compatibility)
    3. Hardcoded defaults
    
    Args:
        agent_name: Name of the agent (e.g., 'query_optimizer')
        default_provider: Default provider if not specified
        default_model: Default model if not specified
    
    Returns:
        Dictionary with provider, model, and api_key
    """
    global _config_manager
    
    # Try ConfigManager first (if initialized)
    if _config_manager is not None and _config_manager._initialized:
        try:
            config = _config_manager.get_agent_config_sync(agent_name)
            return config.to_dict()
        except Exception as e:
            logger.warning(f"Failed to get config from ConfigManager for {agent_name}, falling back to env: {e}")
    
    # Fall back to env vars
    return _get_env_agent_config(agent_name, default_provider, default_model)


def set_config_manager(manager: 'ConfigManager') -> None:
    """Set the global ConfigManager instance (called during startup)"""
    global _config_manager
    _config_manager = manager


# ============================================================================
# Per-Agent Configurations
# These use ConfigManager when available, fall back to env vars
# ============================================================================

# QueryOptimizerAgent Configuration (initialized with env fallback, will be updated on startup)
QUERY_OPTIMIZER_CONFIG = _get_env_agent_config(
    "QUERY_OPTIMIZER", 
    default_provider="openai", 
    default_model="gpt-4"
)

# DataExtractorAgent Configuration
DATA_EXTRACTOR_CONFIG = _get_env_agent_config(
    "DATA_EXTRACTOR",
    default_provider="openai",
    default_model="gpt-4"
)

# ResponseFormatterAgent Configuration
RESPONSE_FORMATTER_CONFIG = _get_env_agent_config(
    "RESPONSE_FORMATTER",
    default_provider="openai",
    default_model="gpt-3.5-turbo"
)

# Legacy support (for backward compatibility)
OPENAI_API_KEY=REDACTED
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
