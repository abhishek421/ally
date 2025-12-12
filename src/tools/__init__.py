"""Tools module for Ally AI agent."""

from src.tools.base import BaseTool, ToolContext
from src.tools.read_tools import get_read_tools
from src.tools.create_tools import get_create_tools
from src.tools.update_tools import get_update_tools


def get_all_tools(context: ToolContext) -> list:
    """Get all available tools for the agent.
    
    Args:
        context: Tool context with auth and workspace info
        
    Returns:
        List of all tool functions
    """
    tools = []
    tools.extend(get_read_tools(context))
    tools.extend(get_create_tools(context))
    tools.extend(get_update_tools(context))
    return tools


__all__ = [
    "BaseTool",
    "ToolContext",
    "get_all_tools",
    "get_read_tools",
    "get_create_tools",
    "get_update_tools",
]

