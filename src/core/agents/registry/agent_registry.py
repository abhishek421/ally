"""
AgentRegistry - Dynamic agent management and lazy loading

This registry manages all available agents and provides them on-demand.
Agents are only instantiated when first used to minimize initialization overhead.
"""
import logging
from typing import Dict, Any, Optional, Callable
from src.infrastructure.llm.base import LLMProvider


class AgentRegistry:
    """
    Registry for managing agent instances with lazy loading

    Provides:
    - Lazy instantiation (agents created on first use)
    - Singleton pattern (one instance per agent type)
    - Dependency injection (shared LLM provider)
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize the registry

        Args:
            llm_provider: Shared LLM provider for all agents
        """
        self._logger = logging.getLogger(__name__)
        self.llm_provider = llm_provider

        # Lazy-loaded agent instances
        self._agents: Dict[str, Any] = {}

        # Agent factory functions (imports deferred until needed)
        self._factories: Dict[str, Callable] = {
            "data_extractor": self._create_data_extractor,
            "result_validator": self._create_result_validator,
        }

        self._logger.debug("AgentRegistry initialized")

    def get(self, agent_name: str) -> Any:
        """
        Get an agent instance (creates if doesn't exist)

        Args:
            agent_name: Name of the agent (e.g., "query_optimizer")

        Returns:
            Agent instance

        Raises:
            ValueError: If agent name is not registered
        """
        if agent_name not in self._factories:
            available = ", ".join(self._factories.keys())
            raise ValueError(f"Unknown agent: {agent_name}. Available: {available}")

        # Return cached instance if exists
        if agent_name in self._agents:
            return self._agents[agent_name]

        # Create new instance
        self._logger.debug(f"Creating agent: {agent_name}")
        agent = self._factories[agent_name]()
        self._agents[agent_name] = agent

        return agent

    def has(self, agent_name: str) -> bool:
        """Check if agent is registered"""
        return agent_name in self._factories

    def list_agents(self) -> list[str]:
        """List all registered agent names"""
        return list(self._factories.keys())

    # Factory methods (imports deferred)

    def _create_data_extractor(self):
        """Create DataExtractorAgent"""
        from src.core.agents.extraction.data_extractor import DataExtractorAgent
        return DataExtractorAgent(self.llm_provider)

    def _create_result_validator(self):
        """Create ResultValidator"""
        from src.core.agents.validation.result_validator import ResultValidator
        return ResultValidator(self.llm_provider)

    def clear(self):
        """Clear all cached agent instances"""
        self._agents.clear()
        self._logger.debug("Agent cache cleared")
