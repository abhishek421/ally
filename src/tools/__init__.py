"""Tools module for Ally AI agent."""

from src.tools.base import BaseTool, ToolContext
from src.tools.read_tools import get_read_tools
from src.tools.create_tools import get_create_tools
from src.tools.update_tools import get_update_tools
from src.tools.research_tools import get_research_tools
from src.tools.context_tools import get_context_tools
from src.tools.reminder_tools import get_reminder_tools
from src.tools.note_tools import get_note_tools
from src.tools.confirmation import (
    ConfirmationType,
    ConfirmationRequest,
    ConfirmationResponse,
    ConfirmationOption,
    request_confirmation,
    request_entity_selection,
    request_create_confirmation,
    request_update_confirmation,
    request_delete_confirmation,
)


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
    tools.extend(get_research_tools(context))
    tools.extend(get_context_tools(context))
    tools.extend(get_reminder_tools(context))
    tools.extend(get_note_tools(context))
    return tools


__all__ = [
    "BaseTool",
    "ToolContext",
    "get_all_tools",
    "get_read_tools",
    "get_create_tools",
    "get_update_tools",
    "get_research_tools",
    "get_context_tools",
    "get_reminder_tools",
    "get_note_tools",
    # Confirmation utilities
    "ConfirmationType",
    "ConfirmationRequest",
    "ConfirmationResponse",
    "ConfirmationOption",
    "request_confirmation",
    "request_entity_selection",
    "request_create_confirmation",
    "request_update_confirmation",
    "request_delete_confirmation",
]
