"""Configuration module for AI Analyst RAG system"""

from config.config_manager import ConfigManager, get_config_manager as get_cm, set_config_manager as set_cm
from config.settings import get_agent_config, set_config_manager

__all__ = [
    'ConfigManager',
    'get_config_manager',
    'set_config_manager',
    'get_agent_config',
]

# Re-export for convenience
get_config_manager = get_cm
