"""Base tool interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Tool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name/identifier.

        Returns:
            Tool name
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description explaining what it does.

        Returns:
            Tool description
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Tool parameters schema (JSON Schema format).

        Returns:
            Dictionary describing parameter schema
        """
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary representation.

        Returns:
            Dictionary with tool metadata
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

