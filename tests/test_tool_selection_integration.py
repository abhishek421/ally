"""Integration tests for intent-based dynamic tool selection.

Tests the full flow: message → classify → get_tools_for_categories → verify tools.
"""

import pytest
from unittest.mock import MagicMock

from src.agent.intent import classify_intent
from src.tools import (
    ToolCategory,
    ALWAYS_INCLUDE,
    get_tools_for_categories,
    get_all_tools,
)


def _get_tool_names(tools: list) -> set[str]:
    """Extract tool names from a tools list."""
    return {getattr(t, "name", str(t)) for t in tools}


class TestAlwaysInclude:
    """Verify ALWAYS_INCLUDE tools are present in every filtered set."""

    def test_always_include_categories(self):
        """ALWAYS_INCLUDE should contain CORE, SEARCH, CONTEXT, MEMORY."""
        assert ToolCategory.CORE in ALWAYS_INCLUDE
        assert ToolCategory.SEARCH in ALWAYS_INCLUDE
        assert ToolCategory.CONTEXT in ALWAYS_INCLUDE
        assert ToolCategory.MEMORY in ALWAYS_INCLUDE

    def test_always_include_with_empty_categories(self):
        """Even with no categories, ALWAYS_INCLUDE tools should be loaded."""
        tools = get_tools_for_categories([])
        assert len(tools) > 0
        names = _get_tool_names(tools)
        # CORE tools should always be present
        assert "resolve_entity_name" in names or "search_and_get_entity" in names

    def test_always_include_with_create(self):
        """CREATE + ALWAYS_INCLUDE should have more tools than ALWAYS_INCLUDE alone."""
        base_tools = get_tools_for_categories([])
        create_tools = get_tools_for_categories([ToolCategory.CREATE])
        assert len(create_tools) > len(base_tools)


class TestToolFiltering:
    """Test that filtered tool sets contain expected tools and exclude others."""

    def test_create_has_create_tools(self):
        tools = get_tools_for_categories([ToolCategory.CREATE])
        names = _get_tool_names(tools)
        assert "create_company" in names or "create_entity" in names

    def test_email_has_email_tools(self):
        tools = get_tools_for_categories([ToolCategory.EMAIL])
        names = _get_tool_names(tools)
        # Should have at least one email-related tool
        email_tools = [n for n in names if "email" in n.lower() or "draft" in n.lower() or "send" in n.lower()]
        assert len(email_tools) > 0

    def test_notes_has_note_tools(self):
        tools = get_tools_for_categories([ToolCategory.NOTES])
        names = _get_tool_names(tools)
        note_tools = [n for n in names if "note" in n.lower()]
        assert len(note_tools) > 0

    def test_filtered_is_subset_of_all(self):
        """Filtered tools should be a subset of all tools."""
        all_tools = get_all_tools()
        all_names = _get_tool_names(all_tools)

        for category in [ToolCategory.CREATE, ToolCategory.UPDATE, ToolCategory.NOTES]:
            filtered = get_tools_for_categories([category])
            filtered_names = _get_tool_names(filtered)
            assert filtered_names.issubset(all_names), (
                f"Category {category.value} has tools not in all_tools: "
                f"{filtered_names - all_names}"
            )

    def test_filtered_fewer_than_all(self):
        """Filtered tools should be fewer than all tools (the whole point)."""
        all_count = len(get_all_tools())
        for category in [ToolCategory.CREATE, ToolCategory.NOTES, ToolCategory.REMINDERS]:
            filtered = get_tools_for_categories([category])
            assert len(filtered) < all_count, (
                f"Category {category.value}: {len(filtered)} tools is not less than {all_count}"
            )

    def test_no_duplicates(self):
        """get_tools_for_categories should deduplicate tools."""
        # Load categories with overlapping tools
        tools = get_tools_for_categories([ToolCategory.CREATE, ToolCategory.UPDATE])
        names = [getattr(t, "name", str(t)) for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tools found: {[n for n in names if names.count(n) > 1]}"


class TestEndToEndFlow:
    """Test the full classify → filter → verify flow."""

    @pytest.mark.asyncio
    async def test_create_query_flow(self):
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        result = await classify_intent("create a new company called Acme", settings=settings)
        tools = get_tools_for_categories(result.categories)
        names = _get_tool_names(tools)

        # Should have create tools
        assert "create_company" in names or "create_entity" in names
        # Should still have ALWAYS_INCLUDE tools
        assert "resolve_entity_name" in names or "search_and_get_entity" in names

    @pytest.mark.asyncio
    async def test_greeting_flow(self):
        """Greeting should load only ALWAYS_INCLUDE tools."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        result = await classify_intent("hey!", settings=settings)
        tools = get_tools_for_categories(result.categories)
        all_tools = get_all_tools()

        # Should have significantly fewer tools than all
        assert len(tools) < len(all_tools)

    @pytest.mark.asyncio
    async def test_token_savings(self):
        """Verify that filtering produces meaningful token savings."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        all_count = len(get_all_tools())

        for query in ["create a company", "add a note", "set a reminder", "hey"]:
            result = await classify_intent(query, settings=settings)
            filtered = get_tools_for_categories(result.categories)
            savings_pct = (1 - len(filtered) / all_count) * 100
            assert savings_pct > 20, (
                f"Query '{query}': only {savings_pct:.0f}% savings "
                f"({len(filtered)}/{all_count} tools)"
            )
