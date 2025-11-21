"""Tool registry for managing available tools."""

from typing import Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing and accessing tools."""

    def __init__(self):
        """Initialize empty tool registry."""
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """List all registered tools.

        Returns:
            List of all registered tools
        """
        return list(self._tools.values())

    def get_tool_descriptions(self) -> List[Dict[str, any]]:
        """Get descriptions of all tools for LLM context.

        Returns:
            List of tool descriptions
        """
        return [tool.to_dict() for tool in self._tools.values()]

    def execute_tool(self, name: str, **kwargs: any) -> any:
        """Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
        """
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in registry")

        logger.info(f"Executing tool: {name}", parameters=kwargs)
        try:
            result = tool.execute(**kwargs)
            logger.info(f"Tool '{name}' executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool '{name}' execution failed", error=str(e), exc_info=True)
            raise


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry instance.

    Returns:
        ToolRegistry instance
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry

