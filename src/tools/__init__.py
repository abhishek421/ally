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
    get_resolver_tools,
    get_company_read_tools,
    get_people_read_tools,
    get_group_read_tools,
    get_email_tools,
    get_column_tools,
)
from src.tools.create_tools import get_create_tools
from src.tools.update_tools import get_update_tools
from src.tools.deal_tools import get_deal_tools
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

class ToolCategory(str, Enum):
    """Categories for grouping tools by user intent."""
    # Core — always loaded (resolvers + memory)
    READ = "read"           # resolve_entity, get_current_page, list_workspace_members (3 tools)
    MEMORY = "memory"       # get/save/update/delete object memories (4 tools)
    # Entity read sub-categories — loaded based on which entity the query mentions
    COMPANIES = "companies" # find/list/get/query company tools (5 tools)
    PEOPLE = "people"       # find/list/get/query people tools (5 tools)
    GROUPS = "groups"       # list/get/search group tools (3 tools)
    EMAIL = "email"         # email read + compose tools (6 tools)
    COLUMNS = "columns"     # column/pipeline/status tools (5 tools)
    DEALS = "deals"         # list/get/create/update/delete deal tools (7 tools)
    # Write categories
    CREATE = "create"
    UPDATE = "update"
    NOTES = "notes"
    REMINDERS = "reminders"
    # Utility
    RESEARCH = "research"
    CONTEXT = "context"


# Registry mapping categories to their tool getter functions.
# Every tool getter MUST be registered here — this is the single source of truth
# for dynamic tool selection. Adding a new category = add it here + intent.py.
TOOL_REGISTRY: dict[ToolCategory, Callable] = {
    # Core (always included)
    ToolCategory.READ: get_resolver_tools,      # just 4 resolver tools
    ToolCategory.MEMORY: get_memory_tools,
    # Entity read sub-categories
    ToolCategory.COMPANIES: get_company_read_tools,
    ToolCategory.PEOPLE: get_people_read_tools,
    ToolCategory.GROUPS: get_group_read_tools,
    ToolCategory.EMAIL: get_email_tools,
    ToolCategory.COLUMNS: get_column_tools,
    ToolCategory.DEALS: get_deal_tools,
    # Write categories
    ToolCategory.CREATE: get_create_tools,
    ToolCategory.UPDATE: get_update_tools,
    ToolCategory.NOTES: get_note_tools,
    ToolCategory.REMINDERS: get_reminder_tools,
    # Utility
    ToolCategory.RESEARCH: get_research_tools,
    ToolCategory.CONTEXT: get_context_tools,
}

# Categories that are always loaded regardless of intent classification.
# READ: the 4 core resolver tools (resolve_company/person/group, get_current_page).
# MEMORY: entity memory recall is consulted before acting on any entity.
ALWAYS_INCLUDE = {ToolCategory.READ, ToolCategory.MEMORY}


def get_tools_for_categories(
    categories: list[ToolCategory],
) -> list:
    """Load only the tools for the specified categories.

    Passing a non-empty list merges categories with ALWAYS_INCLUDE so
    resolvers and memory tools are always available for CRM operations.

    Passing an empty list (`[]`) is a special case — it means "no tools at all"
    and bypasses ALWAYS_INCLUDE. Used for pure chitchat/greeting turns where
    loading tool schemas would waste thousands of input tokens.

    Args:
        categories: List of ToolCategory values from intent classification.
            Pass [] to load zero tools (greeting/chitchat optimisation).

    Returns:
        List of tool functions for the selected categories
    """
    # Empty list = explicit "no tools" (greeting fast-path, bypasses ALWAYS_INCLUDE)
    if not categories:
        logger.info("🔧 No tools loaded (chitchat/greeting fast-path)")
        return []

    all_categories = set(categories) | ALWAYS_INCLUDE

    tools = []
    for category in all_categories:
        getter = TOOL_REGISTRY[category]
        cat_tools = getter()
        tools.extend(cat_tools)
        logger.info(f"   📦 {category.value}: {len(cat_tools)} tools loaded")

    logger.info(
        f"🔧 Total tools loaded: {len(tools)} "
        f"(categories: {[c.value for c in all_categories]})"
    )
    return tools


def get_all_tools() -> list:
    """Get all available tools for the agent.

    Derived from TOOL_REGISTRY so it stays in sync automatically
    when new categories are added.

    Returns:
        List of all tool functions
    """
    tools = []
    for getter in TOOL_REGISTRY.values():
        tools.extend(getter())
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
