# Application settings and configuration
import os
import logging
from dotenv import load_dotenv
from typing import Optional
from src.shared.prompts.business_analyst_persona import (
    BUSINESS_ANALYST_PERSONA,
    BUSINESS_ANALYST_SYSTEM_CONTEXT
)
from src.shared.prompts.data_extractor_prompt import DATA_EXTRACTOR_TEMPLATE

# Load variables from a .env file if present
load_dotenv()

logger = logging.getLogger(__name__)

# Business Analyst Persona (core system context)
BUSINESS_ANALYST_PERSONA_PROMPT = BUSINESS_ANALYST_PERSONA
BUSINESS_ANALYST_SYSTEM_PROMPT = BUSINESS_ANALYST_SYSTEM_CONTEXT

# Prompt templates (imported from prompts module)
DATA_EXTRACTOR_PROMPT_TEMPLATE = DATA_EXTRACTOR_TEMPLATE

# ============================================================================
# LLM Configuration (ENV-only)
# Uses only environment variables with global and per-agent overrides
# ============================================================================


def _get_env_agent_config(agent_name: str, default_provider: Optional[str] = None, default_model: Optional[str] = None) -> dict:
    """
    Get configuration for a specific agent from environment variables (fallback only).

    This function is used when ConfigManager is not available or as a fallback.

    Args:
        agent_name: Name of the agent (e.g., 'query_optimizer')
        default_provider: Optional default provider if not specified
        default_model: Optional default model if not specified

    Returns:
        Dictionary with provider configuration

    Raises:
        ValueError: If provider or model cannot be determined from environment
    """
    prefix = agent_name.upper()

    # Check for global env vars first
    provider = os.getenv(f"{prefix}_PROVIDER") or os.getenv("GLOBAL_LLM_PROVIDER")
    model = os.getenv(f"{prefix}_MODEL") or os.getenv("GLOBAL_LLM_MODEL")

    # Use defaults only if provided
    if not provider and default_provider:
        provider = default_provider
    if not model and default_model:
        model = default_model

    # Raise error if still not set
    if not provider:
        raise ValueError(
            f"Provider not configured for {agent_name}. Please set {prefix}_PROVIDER or GLOBAL_LLM_PROVIDER environment variable."
        )
    if not model:
        raise ValueError(
            f"Model not configured for {agent_name}. Please set {prefix}_MODEL or GLOBAL_LLM_MODEL environment variable."
        )
    
    # Get API key based on provider
    if provider.lower() == 'openai':
        api_key = os.getenv(f"{prefix}_API_KEY", os.getenv("OPENAI_API_KEY", ""))
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


def get_agent_config(agent_name: str, default_provider: Optional[str] = None, default_model: Optional[str] = None) -> dict:
    """
    Get configuration for a specific agent.

    Priority order:
    1. Environment variables (agent-specific overrides)
    2. Global environment variables
    3. Optional defaults (if provided)

    Args:
        agent_name: Name of the agent (e.g., 'query_optimizer')
        default_provider: Optional default provider if not specified
        default_model: Optional default model if not specified

    Returns:
        Dictionary with provider, model, and api_key

    Raises:
        ValueError: If provider or model cannot be determined
    """
    return _get_env_agent_config(agent_name, default_provider, default_model)


def set_config_manager(manager: 'ConfigManager') -> None:
    """No-op retained for backward compatibility (DB config removed)."""
    return None


# ============================================================================
# Per-Agent Configurations
# These use ConfigManager when available, fall back to env vars
# ============================================================================

# QueryOptimizerAgent Configuration (initialized with env fallback, will be updated on startup)
QUERY_OPTIMIZER_CONFIG = _get_env_agent_config("QUERY_OPTIMIZER")

# DataExtractorAgent Configuration
DATA_EXTRACTOR_CONFIG = _get_env_agent_config("DATA_EXTRACTOR")

# ResponseFormatterAgent Configuration
RESPONSE_FORMATTER_CONFIG = _get_env_agent_config("RESPONSE_FORMATTER")

"""
Note: Configuration is ENV-only. Use per-agent configuration via
get_agent_config(...) with global and agent-level env overrides.
"""
