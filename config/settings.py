# Application settings and configuration
import os
from dotenv import load_dotenv
from prompts import QUERY_OPTIMIZER_TEMPLATE

# Load variables from a .env file if present
load_dotenv()

# Prompt templates (imported from prompts module)
QUERY_OPTIMIZATION_TEMPLATE = QUERY_OPTIMIZER_TEMPLATE

# ============================================================================
# Per-Agent LLM Configuration
# Each agent can have its own provider and model configuration
# ============================================================================

def _get_agent_config(agent_name: str, default_provider: str = "openai", default_model: str = "gpt-4") -> dict:
    """
    Get configuration for a specific agent from environment variables
    
    Args:
        agent_name: Name of the agent (e.g., 'query_optimizer')
        default_provider: Default provider if not specified
        default_model: Default model if not specified
    
    Returns:
        Dictionary with provider configuration
    """
    prefix = agent_name.upper()
    
    provider = os.getenv(f"{prefix}_PROVIDER", default_provider)
    model = os.getenv(f"{prefix}_MODEL", default_model)
    
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

# QueryOptimizerAgent Configuration
QUERY_OPTIMIZER_CONFIG = _get_agent_config(
    "QUERY_OPTIMIZER", 
    default_provider="openai", 
    default_model="gpt-4"
)

# DataExtractorAgent Configuration
DATA_EXTRACTOR_CONFIG = _get_agent_config(
    "DATA_EXTRACTOR",
    default_provider="openai",
    default_model="gpt-4"
)

# ResponseFormatterAgent Configuration
RESPONSE_FORMATTER_CONFIG = _get_agent_config(
    "RESPONSE_FORMATTER",
    default_provider="openai",
    default_model="gpt-3.5-turbo"
)

# Legacy support (for backward compatibility)
OPENAI_API_KEY=REDACTED
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")

