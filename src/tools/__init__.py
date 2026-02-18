"""Tools module for Ally AI agent.

Includes a ToolCategory registry for intent-based dynamic tool selection.
See DYNAMIC_TOOL_SELECTION_PLAN.md for full design rationale.
"""

import logging
from enum import Enum
from typing import Callable

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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Category Registry
# ---------------------------------------------------------------------------

class ToolCategory(str, Enum):
    """Categories for grouping tools by user intent."""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    RESEARCH = "research"
    CONTEXT = "context"
    NOTES = "notes"
    REMINDERS = "reminders"


# Registry mapping categories to their tool getter functions
TOOL_REGISTRY: dict[ToolCategory, Callable] = {
    ToolCategory.READ: get_read_tools,
    ToolCategory.CREATE: get_create_tools,
    ToolCategory.UPDATE: get_update_tools,
    ToolCategory.RESEARCH: get_research_tools,
    ToolCategory.CONTEXT: get_context_tools,
    ToolCategory.NOTES: get_note_tools,
    ToolCategory.REMINDERS: get_reminder_tools,
}

# Tools that should ALWAYS be included (resolvers are needed for almost everything)
ALWAYS_INCLUDE = {ToolCategory.READ}


def get_tools_for_categories(
    context: ToolContext,
    categories: list[ToolCategory],
) -> list:
    """Load only the tools for the specified categories.

    Always includes the ALWAYS_INCLUDE categories (READ) in addition
    to whatever categories the intent classifier returns.

    Args:
        context: Tool context with auth and workspace info
        categories: List of ToolCategory values from intent classification

    Returns:
        List of tool functions for the selected categories
    """
    all_categories = set(categories) | ALWAYS_INCLUDE

    tools = []
    for category in all_categories:
        getter = TOOL_REGISTRY[category]
        cat_tools = getter(context)
        tools.extend(cat_tools)
        logger.info(f"   📦 {category.value}: {len(cat_tools)} tools loaded")

    logger.info(
        f"🔧 Total tools loaded: {len(tools)} "
        f"(categories: {[c.value for c in all_categories]})"
    )
    return tools


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
    "ToolCategory",
    "TOOL_REGISTRY",
    "ALWAYS_INCLUDE",
    "get_all_tools",
    "get_tools_for_categories",
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
