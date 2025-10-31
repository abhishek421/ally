"""
Configuration Manager for LLM settings
Handles loading from database, inheritance, and fallback logic
"""
import os
import logging
from typing import Optional, Dict
from database.prisma_client import prisma_client
from config.models.llm_config import (
    GlobalLLMConfigModel,
    AgentLLMConfigModel,
    LLMConfig
)

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages LLM configuration with database-backed settings and inheritance.
    
    Configuration resolution priority (highest to lowest):
    1. DB agent-specific config (if provider/model set)
    2. DB global config
    3. Env agent-specific vars (AGENT_PROVIDER, AGENT_MODEL)
    4. Env global vars (GLOBAL_LLM_PROVIDER, GLOBAL_LLM_MODEL)

    API keys are always sourced from environment variables.

    Note: Hardcoded defaults have been removed. Configuration must be
    provided via database or environment variables.
    """
    
    def __init__(self):
        self._global_config: Optional[GlobalLLMConfigModel] = None
        self._agent_configs: Dict[str, AgentLLMConfigModel] = {}
        self._db_available: bool = False
        self._initialized: bool = False
    
    async def initialize(self) -> None:
        """
        Initialize ConfigManager by loading configs from database.
        Falls back to env vars if DB is unavailable.
        """
        if self._initialized:
            logger.debug("ConfigManager already initialized")
            return
        
        try:
            # Try to connect to database
            await prisma_client.connect()
            self._db_available = True
            
            # Load global config
            await self._load_global_config()
            
            # Load agent configs
            await self._load_agent_configs()
            
            logger.info("ConfigManager initialized successfully from database")
            
        except Exception as e:
            logger.warning(f"Failed to load config from database, falling back to env vars: {e}")
            self._db_available = False
            # Will fall back to env vars when get_agent_config is called
        
        self._initialized = True
    
    async def _load_global_config(self) -> None:
        """Load global LLM config from database"""
        try:
            client = await prisma_client.get_client()
            
            # Get the first enabled global config (should only be one)
            result = await client.globalllmconfig.find_first(
                where={"enabled": True},
                order={"updatedAt": "desc"}
            )
            
            if result:
                self._global_config = GlobalLLMConfigModel(
                    id=result.id,
                    provider=result.provider,
                    model=result.model,
                    enabled=result.enabled,
                    version=result.version,
                    createdAt=result.createdAt,
                    updatedAt=result.updatedAt
                )
                logger.info(f"Loaded global LLM config: {self._global_config.provider}/{self._global_config.model}")
            else:
                logger.warning("No global LLM config found in database")
                
        except Exception as e:
            logger.error(f"Error loading global config from database: {e}")
            raise
    
    async def _load_agent_configs(self) -> None:
        """Load all agent-specific configs from database"""
        try:
            client = await prisma_client.get_client()
            
            results = await client.agentllmconfig.find_many(
                where={"enabled": True}
            )
            
            for result in results:
                config = AgentLLMConfigModel(
                    id=result.id,
                    agentName=result.agentName,
                    provider=result.provider,
                    model=result.model,
                    enabled=result.enabled,
                    version=result.version,
                    createdAt=result.createdAt,
                    updatedAt=result.updatedAt
                )
                self._agent_configs[result.agentName] = config
                logger.debug(f"Loaded config for agent '{result.agentName}': {config.provider or 'inherit'}/{config.model or 'inherit'}")
            
            logger.info(f"Loaded {len(self._agent_configs)} agent configs from database")
            
        except Exception as e:
            logger.error(f"Error loading agent configs from database: {e}")
            raise
    
    def get_agent_config_sync(self, agent_name: str) -> LLMConfig:
        """
        Get resolved LLM configuration for an agent.

        Resolution priority:
        1. DB agent config (if provider/model set)
        2. DB global config
        3. Env agent vars
        4. Env global vars

        Args:
            agent_name: Name of the agent (e.g., 'query_optimizer')

        Returns:
            LLMConfig with resolved provider, model, and api_key

        Raises:
            ValueError: If provider or model cannot be determined from any source
        """
        provider: Optional[str] = None
        model: Optional[str] = None
        source: str = "none"

        # Step 1: Check agent-specific DB config
        if self._db_available and agent_name in self._agent_configs:
            agent_config = self._agent_configs[agent_name]
            if agent_config.provider is not None:
                provider = agent_config.provider
                model = agent_config.model or (self._global_config.model if self._global_config else None)
                source = "db_agent"
                logger.debug(f"Using agent-specific DB config for '{agent_name}'")

        # Step 2: Check global DB config
        if provider is None and self._global_config:
            provider = self._global_config.provider
            model = self._global_config.model
            source = "db_global"
            logger.debug(f"Using global DB config for '{agent_name}'")

        # Step 3: Fall back to env vars (agent-specific)
        if provider is None:
            prefix = agent_name.upper()
            provider = os.getenv(f"{prefix}_PROVIDER")
            if provider:
                model = os.getenv(f"{prefix}_MODEL")
                source = "env_agent"
                logger.debug(f"Using agent-specific env vars for '{agent_name}'")

        # Step 4: Fall back to env vars (global)
        if provider is None:
            provider = os.getenv("GLOBAL_LLM_PROVIDER")
            if provider:
                model = os.getenv("GLOBAL_LLM_MODEL")
                source = "env_global"
                logger.debug(f"Using global env vars for '{agent_name}'")

        # Raise error if provider/model not configured
        if provider is None:
            raise ValueError(
                f"Provider not configured for agent '{agent_name}'. "
                f"Please set configuration via database or environment variables "
                f"(e.g., {agent_name.upper()}_PROVIDER or GLOBAL_LLM_PROVIDER)."
            )

        if model is None:
            raise ValueError(
                f"Model not configured for agent '{agent_name}'. "
                f"Please set configuration via database or environment variables "
                f"(e.g., {agent_name.upper()}_MODEL or GLOBAL_LLM_MODEL)."
            )
        
        # Get API key from environment (always from env)
        api_key = self._get_api_key_for_provider(provider)
        
        config = LLMConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            source=source,
            agent_name=agent_name
        )
        
        logger.info(f"Resolved config for '{agent_name}': {provider}/{model} (source: {source})")
        return config
    
    async def get_agent_config(self, agent_name: str) -> LLMConfig:
        """
        Async alias for get_agent_config_sync (for consistency).
        Actually just calls the sync version since configs are cached.
        """
        return self.get_agent_config_sync(agent_name)
    
    def _get_api_key_for_provider(self, provider: str) -> str:
        """
        Get API key for a provider from environment variables.
        
        Args:
            provider: Provider name (openai, anthropic, gemini)
            
        Returns:
            API key string, empty if not found
        """
        provider_lower = provider.lower()
        
        key_mapping = {
OPENAI_API_KEY=REDACTED
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GOOGLE_API_KEY"
        }
        
        env_key = key_mapping.get(provider_lower, "")
        if env_key:
            api_key = os.getenv(env_key, "")
            if not api_key:
                logger.warning(f"API key not found in env for provider '{provider}' (expected {env_key})")
            return api_key
        
        logger.warning(f"Unknown provider '{provider}', no API key mapping")
        return ""
    
    def reload(self) -> None:
        """
        Reload configurations from database.
        Useful when configs are updated and need to be refreshed.
        """
        logger.info("Reloading configurations from database")
        self._global_config = None
        self._agent_configs.clear()
        self._initialized = False
    
    @property
    def db_available(self) -> bool:
        """Check if database is available"""
        return self._db_available
    
    @property
    def global_config(self) -> Optional[GlobalLLMConfigModel]:
        """Get the loaded global config"""
        return self._global_config


# Global singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get the global ConfigManager instance.
    Creates it if it doesn't exist (but doesn't initialize - call initialize() explicitly).
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def set_config_manager(manager: ConfigManager) -> None:
    """Set the global ConfigManager instance (useful for testing)"""
    global _config_manager
    _config_manager = manager

