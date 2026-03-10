"""Tools module for Ally AI agent.

Includes a ToolCategory registry for intent-based dynamic tool selection.
See DYNAMIC_TOOL_SELECTION_PLAN.md for full design rationale.
"""

import logging
from enum import Enum
from typing import Callable

from src.tools.base import BaseTool, ToolContext
from src.tools.read_tools import (
    get_read_tools,
    get_core_tools,
    get_search_tools,
    get_details_tools,
    get_pipeline_tools,
    get_email_tools,
)
from src.tools.create_tools import get_create_tools
from src.tools.update_tools import get_update_tools
from src.tools.research_tools import get_research_tools
from src.tools.context_tools import get_context_tools
from src.tools.reminder_tools import get_reminder_tools
from src.tools.note_tools import get_note_tools
from src.tools.memory_tools import get_memory_tools
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

class ToolCategory(Enum):
    """Categories of tools for intent classification."""
    READ = "read"           # All read tools combined (fallback)
    CORE = "core"           # Resolvers + composite lookups (always loaded)
    SEARCH = "search"       # Entity listing and searching
    DETAILS = "details"     # Full entity detail fetches
    PIPELINE = "pipeline"   # Pipeline status, columns, column options
    EMAIL = "email"         # Email interactions, templates, drafting
    CREATE = "create"       # Entity creation
    UPDATE = "update"       # Entity updates, deletes
    RESEARCH = "research"   # Web search via Perplexity
    CONTEXT = "context"     # Workspace/entity instructions
    REMINDERS = "reminders" # Reminder CRUD
    NOTES = "notes"         # Note CRUD
    MEMORY = "memory"       # Long-term entity memory


# Registry mapping categories to their tool getter functions
TOOL_REGISTRY: dict[ToolCategory, Callable] = {
    ToolCategory.READ: get_read_tools,
    ToolCategory.CORE: get_core_tools,
    ToolCategory.SEARCH: get_search_tools,
    ToolCategory.DETAILS: get_details_tools,
    ToolCategory.PIPELINE: get_pipeline_tools,
    ToolCategory.EMAIL: get_email_tools,
    ToolCategory.CREATE: get_create_tools,
    ToolCategory.UPDATE: get_update_tools,
    ToolCategory.RESEARCH: get_research_tools,
    ToolCategory.CONTEXT: get_context_tools,
    ToolCategory.NOTES: get_note_tools,
    ToolCategory.REMINDERS: get_reminder_tools,
    ToolCategory.MEMORY: get_memory_tools,
}

# Tools loaded on every request regardless of intent.
# CORE (6 tools): resolvers + composite lookups + page awareness
# CONTEXT (1 tool): entity-specific instructions
ALWAYS_INCLUDE = {ToolCategory.CORE, ToolCategory.CONTEXT}

# Categories safe to route to gpt-4o-mini (simple queries)
SIMPLE_CATEGORIES = {ToolCategory.CORE, ToolCategory.SEARCH, ToolCategory.CONTEXT}


def get_tools_for_categories(
    categories: list[ToolCategory],
) -> list:
    """Load only the tools for the specified categories.

    Always includes the ALWAYS_INCLUDE categories in addition
    to whatever categories the intent classifier returns.

    Args:
        categories: List of ToolCategory values from intent classification

    Returns:
        List of tool functions for the selected categories
    """
    all_categories = set(categories) | ALWAYS_INCLUDE

    tools = []
    seen_names = set()  # Deduplicate tools that appear in multiple categories
    for category in all_categories:
        getter = TOOL_REGISTRY[category]
        cat_tools = getter()
        new_tools = [t for t in cat_tools if t.name not in seen_names]
        seen_names.update(t.name for t in new_tools)
        tools.extend(new_tools)
        logger.info(f"   📦 {category.value}: {len(new_tools)} tools loaded")

    logger.info(
        f"🔧 Total tools loaded: {len(tools)} "
        f"(categories: {[c.value for c in all_categories]})"
    )
    return tools


def get_all_tools() -> list:
    """Get all available tools for the agent.

    Returns:
        List of all tool functions
    """
    tools = []
    tools.extend(get_read_tools())
    tools.extend(get_create_tools())
    tools.extend(get_update_tools())
    tools.extend(get_research_tools())
    tools.extend(get_context_tools())
    tools.extend(get_reminder_tools())
    tools.extend(get_note_tools())
    tools.extend(get_memory_tools())
    return tools


__all__ = [
    "BaseTool",
    "ToolContext",
    "ToolCategory",
    "TOOL_REGISTRY",
    "ALWAYS_INCLUDE",
    "SIMPLE_CATEGORIES",
    "get_all_tools",
    "get_tools_for_categories",
    "get_read_tools",
    "get_core_tools",
    "get_search_tools",
    "get_details_tools",
    "get_pipeline_tools",
    "get_email_tools",
    "get_create_tools",
    "get_update_tools",
    "get_research_tools",
    "get_context_tools",
    "get_reminder_tools",
    "get_note_tools",
    "get_memory_tools",
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

