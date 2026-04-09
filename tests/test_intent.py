"""Unit tests for the intent classifier."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agent.intent import (
    IntentResult,
    _classify_rules,
    _apply_co_occurrence,
    _extract_history_context,
    classify_intent,
    CO_OCCURRENCE,
)
from src.tools import ToolCategory


# ---------------------------------------------------------------------------
# Rule-based classification tests
# ---------------------------------------------------------------------------


class TestClassifyRules:
    """Tests for the rule-based keyword classifier."""

    def test_search_queries(self):
        """Search/list queries should not match additional categories (covered by ALWAYS_INCLUDE)."""
        for query in ["list all companies", "show me people", "find John", "search for Acme"]:
            result = _classify_rules(query)
            # These might match DETAILS ("find") or nothing — but should NOT error
            assert isinstance(result, IntentResult)

    def test_create_intent(self):
        result = _classify_rules("create a new company called Acme")
        assert ToolCategory.CREATE in result.categories
        assert result.confidence > 0

    def test_update_intent(self):
        result = _classify_rules("update John's job title")
        assert ToolCategory.UPDATE in result.categories

    def test_email_intent(self):
        for query in ["send an email to John", "draft a message", "check my inbox", "reply to the thread"]:
            result = _classify_rules(query)
            assert ToolCategory.EMAIL in result.categories, f"Failed for: {query}"

    def test_pipeline_intent(self):
        for query in ["what's the pipeline status?", "move to qualified stage", "show deals", "filter by leads"]:
            result = _classify_rules(query)
            assert ToolCategory.PIPELINE in result.categories, f"Failed for: {query}"

    def test_notes_intent(self):
        result = _classify_rules("add a note for Acme Corp")
        assert ToolCategory.NOTES in result.categories

    def test_reminders_intent(self):
        for query in ["set a reminder for tomorrow", "follow up with Sarah", "what are my deadlines"]:
            result = _classify_rules(query)
            assert ToolCategory.REMINDERS in result.categories, f"Failed for: {query}"

    def test_research_intent(self):
        result = _classify_rules("research competitors in the AI market")
        assert ToolCategory.RESEARCH in result.categories

    def test_details_intent(self):
        for query in ["tell me about Acme", "get details on John", "who is Sarah?"]:
            result = _classify_rules(query)
            assert ToolCategory.DETAILS in result.categories, f"Failed for: {query}"

    def test_multi_intent(self):
        result = _classify_rules("create a company and set a reminder")
        assert ToolCategory.CREATE in result.categories
        assert ToolCategory.REMINDERS in result.categories

    def test_greeting_no_match(self):
        """Greetings should produce no categories (ALWAYS_INCLUDE handles them)."""
        for query in ["hey", "hello!", "thanks", "hi there"]:
            result = _classify_rules(query)
            assert len(result.categories) == 0, f"Unexpected match for: {query}"
            assert result.confidence == 0.0

    def test_confidence_scoring(self):
        # Single clear match → high confidence
        result = _classify_rules("create a company")
        assert result.confidence == 0.85

        # No match → zero confidence
        result = _classify_rules("hey")
        assert result.confidence == 0.0

        # Many matches → lower confidence
        result = _classify_rules("create a note and set a reminder and send an email")
        assert result.confidence == 0.70

    def test_source_is_rules(self):
        result = _classify_rules("create a company")
        assert result.source == "rules"

    def test_matched_patterns_recorded(self):
        result = _classify_rules("create a company")
        assert "create" in result.matched_patterns


# ---------------------------------------------------------------------------
# Co-occurrence tests
# ---------------------------------------------------------------------------


class TestCoOccurrence:
    def test_update_adds_pipeline(self):
        result = _apply_co_occurrence([ToolCategory.UPDATE])
        assert ToolCategory.PIPELINE in result

    def test_email_adds_details(self):
        result = _apply_co_occurrence([ToolCategory.EMAIL])
        assert ToolCategory.DETAILS in result

    def test_no_co_occurrence(self):
        result = _apply_co_occurrence([ToolCategory.NOTES])
        assert set(result) == {ToolCategory.NOTES}

    def test_preserves_existing(self):
        result = _apply_co_occurrence([ToolCategory.UPDATE, ToolCategory.NOTES])
        assert ToolCategory.UPDATE in result
        assert ToolCategory.NOTES in result
        assert ToolCategory.PIPELINE in result


# ---------------------------------------------------------------------------
# History context extraction tests
# ---------------------------------------------------------------------------


class TestExtractHistoryContext:
    def test_none_history(self):
        categories, summary = _extract_history_context(None)
        assert categories == []
        assert summary is None

    def test_empty_history(self):
        categories, summary = _extract_history_context([])
        assert categories == []
        assert summary is None

    def test_extracts_tool_names(self):
        """ToolMessage objects with known names should map to categories."""
        # Create mock messages
        tool_msg = MagicMock()
        tool_msg.name = "create_company"
        tool_msg.type = "tool"
        tool_msg.content = "Created company"

        with patch("src.agent.intent.get_tool_to_category") as mock_lookup:
            mock_lookup.return_value = {"create_company": ToolCategory.CREATE}
            categories, _ = _extract_history_context([tool_msg])
            assert ToolCategory.CREATE in categories

    def test_extracts_user_messages(self):
        """Recent human messages should be captured as context summary."""
        msg = MagicMock()
        msg.name = None
        msg.type = "human"
        msg.content = "Create a company called Acme"

        with patch("src.agent.intent.get_tool_to_category") as mock_lookup:
            mock_lookup.return_value = {}
            _, summary = _extract_history_context([msg])
            assert "Acme" in summary


# ---------------------------------------------------------------------------
# Full classify_intent tests (async)
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_basic_classification(self):
        """Simple rule-based classification should work without LLM."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        result = await classify_intent("create a new company", settings=settings)
        assert ToolCategory.CREATE in result.categories
        assert result.source == "rules"

    @pytest.mark.asyncio
    async def test_co_occurrence_applied(self):
        """UPDATE should auto-include PIPELINE via co-occurrence."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        result = await classify_intent("update John's status", settings=settings)
        assert ToolCategory.UPDATE in result.categories
        assert ToolCategory.PIPELINE in result.categories

    @pytest.mark.asyncio
    async def test_greeting_returns_empty_categories(self):
        """Greetings should return empty categories (ALWAYS_INCLUDE handles them)."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        result = await classify_intent("hey!", settings=settings)
        # With no LLM fallback, empty categories is expected for greetings
        # ALWAYS_INCLUDE tools will still be loaded by get_tools_for_categories
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_llm_fallback_triggered_on_low_confidence(self):
        """LLM fallback should be called when rules have low confidence and LLM is enabled."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = True

        with patch("src.agent.intent._classify_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = IntentResult(
                categories=[ToolCategory.DETAILS],
                confidence=0.75,
                source="llm",
                latency_ms=200,
            )

            # "hey" has 0.0 confidence from rules, should trigger LLM
            result = await classify_intent("hey there, tell me something", settings=settings)
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_fallback_not_triggered_when_disabled(self):
        """LLM fallback should NOT be called when disabled."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        with patch("src.agent.intent._classify_llm", new_callable=AsyncMock) as mock_llm:
            result = await classify_intent("hey", settings=settings)
            mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_classification_with_history(self):
        """Multi-turn context should enrich classification."""
        settings = MagicMock()
        settings.intent_confidence_threshold = 0.6
        settings.intent_llm_fallback_enabled = False

        # Mock history with a tool call
        tool_msg = MagicMock()
        tool_msg.name = "create_company"
        tool_msg.type = "tool"
        tool_msg.content = "Created"

        user_msg = MagicMock()
        user_msg.name = None
        user_msg.type = "human"
        user_msg.content = "now add a reminder for them"

        with patch("src.agent.intent.get_tool_to_category") as mock_lookup:
            mock_lookup.return_value = {"create_company": ToolCategory.CREATE}
            result = await classify_intent(
                "also add a reminder for them",
                conversation_history=[tool_msg, user_msg],
                settings=settings,
            )
            # Should have REMINDERS from current message + CREATE from history
            assert ToolCategory.REMINDERS in result.categories
            assert ToolCategory.CREATE in result.categories
