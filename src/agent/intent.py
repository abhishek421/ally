"""Hybrid intent classification for dynamic tool selection.

Classifies user messages into tool categories to load only relevant tools
per request, reducing token usage by ~60-65%.

Uses a two-tier approach:
  1. Rule-based keyword matching (fast, zero-cost, handles ~80% of queries)
  2. LLM fallback via get_mini_llm() (for ambiguous queries when enabled)

See: DYNAMIC_TOOL_SELECTION_PLAN.md for full design rationale.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field

from src.tools import ToolCategory

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result of intent classification."""

    categories: list[ToolCategory]
    confidence: float  # 0.0 - 1.0
    source: str  # "rules" | "llm" | "fallback"
    matched_patterns: dict = field(default_factory=dict)  # {category_value: pattern}
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Keyword patterns mapped to tool categories.
# ALWAYS_INCLUDE categories (CORE, SEARCH, CONTEXT, MEMORY) are loaded
# regardless of classification — only additional categories are matched here.
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[ToolCategory, list[str]] = {
    ToolCategory.DETAILS: [
        r"\bdetails?\b",
        r"\bfull\s+info\b",
        r"\bprofile\b",
        r"\beverything\s+about\b",
        r"\btell\s+me\s+(?:about|more)\b",
        r"\binfo\s+(?:on|about)\b",
        r"\bwhat\s+(?:do\s+(?:we|you)\s+know|can\s+you\s+tell\s+me)\b",
        r"\bwho\s+is\b",
        r"\bhistory\b",
    ],
    ToolCategory.PIPELINE: [
        r"\bpipeline\b",
        r"\bstage\b",
        r"\bcolumns?\b",
        r"\bkanban\b",
        r"\bboard\b",
        r"\bfilter\s+by\s+status\b",
        r"\bwhat\s+(?:are|is)\s+(?:the\s+)?status",
        r"\bstatus\b",
        r"\bleads?\b",
        r"\bqualified\b",
        r"\bwon\b",
        r"\blost\b",
        r"\bfunnel\b",
        r"\bdeals?\b",
    ],
    ToolCategory.EMAIL: [
        r"\bemails?\b",
        r"\bmail\b",
        r"\bdraft\b",
        r"\bsend\b",
        r"\btemplates?\b",
        r"\bthread\b",
        r"\binteractions?\b",
        r"\breply\b",
        r"\bcompose\b",
        r"\binbox\b",
        r"\bcc\b",
        r"\bbcc\b",
        r"\bsubject\b",
        r"\bforward\b",
    ],
    ToolCategory.CREATE: [
        r"\bcreate\b",
        r"\badd\s+(?:a\s+)?(?:new\s+)?(?:company|person|contact|group|view)\b",
        r"\bmake\s+(?:a\s+)?(?:new\s+)?\b",
        r"\bset\s*up\b",
        r"\bnew\s+(?:company|person|contact|group)\b",
    ],
    ToolCategory.UPDATE: [
        r"\bupdate\b",
        r"\bchange\b",
        r"\bmodify\b",
        r"\bedit\b",
        r"\brename\b",
        r"\bmove\b",
        r"\bremove\b",
        r"\bdelete\s+(?:from|company|person)\b",
        r"\bset\s+(?:status|stage|priority)\b",
        r"\bassign\b",
        r"\bunlink\b",
        r"\badd\s+(?:\w+\s+)?(?:to\s+group|to\s+company)\b",
    ],
    ToolCategory.NOTES: [
        r"\bnotes?\b",
        r"\bjot\b",
        r"\bmemo\b",
        r"\bwrite\s+(?:a\s+)?(?:note|memo)\b",
        r"\bannotate\b",
    ],
    ToolCategory.REMINDERS: [
        r"\bremind(?:er|ers)?\b",
        r"\bschedule\b",
        r"\bdue\s+date\b",
        r"\bfollow\s*up\b",
        r"\balarm\b",
        r"\bdeadline\b",
    ],
    ToolCategory.RESEARCH: [
        r"\bresearch\b",
        r"\bsearch\s+(?:the\s+)?(?:web|internet|online)\b",
        r"\bfind\s+(?:out|info|information)\b",
        r"\bwhat\s+(?:is|are|does)\b.*\b(?:industry|market|funding|revenue|competitor)\b",
        r"\blook\s*up\s+(?:online|on\s+the\s+web)\b",
    ],
}


# Co-occurrence rules: when a category is selected, auto-include dependencies.
CO_OCCURRENCE: dict[ToolCategory, list[ToolCategory]] = {
    ToolCategory.UPDATE: [ToolCategory.PIPELINE],  # status updates often need pipeline tools
    ToolCategory.EMAIL: [ToolCategory.DETAILS],  # emailing needs contact details
}


# LLM classification prompt (kept minimal for speed and cost).
_LLM_CLASSIFICATION_PROMPT = """Classify this CRM assistant query into tool categories.
Return ONLY a JSON array of matching category names. Do not include "core", "search", "context", or "memory" — those are always loaded.

Valid categories: details, pipeline, email, create, update, notes, reminders, research

Examples:
- "list all companies" → []
- "create a company called Acme" → ["create"]
- "send an email to John" → ["email"]
- "update John's status and add a note" → ["update", "notes"]
- "what's Acme's pipeline status?" → ["pipeline", "details"]
- "hey!" → []

Query: "{message}"
{context_line}
Categories:"""


def _classify_rules(message: str) -> IntentResult:
    """Classify using rule-based keyword matching.

    Returns:
        IntentResult with categories, confidence, and matched patterns.
    """
    start = time.time()
    message_lower = message.lower().strip()
    matched: dict[ToolCategory, str] = {}

    for category, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                matched[category] = pattern
                break

    categories = list(matched.keys())
    latency_ms = (time.time() - start) * 1000

    # Confidence heuristic
    if len(categories) == 0:
        confidence = 0.0  # No match — may need LLM fallback
    elif len(categories) <= 2:
        confidence = 0.85  # Clear intent
    else:
        confidence = 0.70  # Multi-intent — higher chance of misclassification

    return IntentResult(
        categories=categories,
        confidence=confidence,
        source="rules",
        matched_patterns={cat.value: pat for cat, pat in matched.items()},
        latency_ms=latency_ms,
    )


async def _classify_llm(message: str, context_summary: str | None = None) -> IntentResult:
    """Classify using a fast/cheap LLM call.

    Uses the cached mini LLM (gpt-4o-mini / claude-haiku / gemini-flash).
    """
    from src.agent.graph import get_mini_llm

    start = time.time()

    context_line = ""
    if context_summary:
        context_line = f'Recent context: "{context_summary}"'

    prompt = _LLM_CLASSIFICATION_PROMPT.format(
        message=message[:200],  # truncate long messages
        context_line=context_line,
    )

    try:
        llm = get_mini_llm()
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        # Parse JSON array from response
        # Handle cases where LLM wraps in markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        raw_categories = json.loads(content)
        categories = []
        for name in raw_categories:
            try:
                categories.append(ToolCategory(name))
            except ValueError:
                logger.warning(f"LLM returned unknown category: {name}")

        latency_ms = (time.time() - start) * 1000
        return IntentResult(
            categories=categories,
            confidence=0.75,  # LLM is generally reliable but not perfect
            source="llm",
            latency_ms=latency_ms,
        )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        logger.warning(f"LLM intent classification failed ({latency_ms:.0f}ms): {e}")
        return IntentResult(
            categories=[],
            confidence=0.0,
            source="fallback",
            latency_ms=latency_ms,
        )


def _extract_history_context(conversation_history: list | None) -> tuple[list[ToolCategory], str | None]:
    """Extract tool categories and context from recent conversation history.

    Scans the last few messages for tool names and maps them back to categories.

    Returns:
        Tuple of (categories from history, summary of last user messages)
    """
    if not conversation_history:
        return [], None

    from src.tools import get_tool_to_category

    tool_to_category = get_tool_to_category()
    history_categories: set[ToolCategory] = set()
    recent_user_messages: list[str] = []

    # Scan last 6 messages (3 turns) for tool usage and user messages
    recent = conversation_history[-6:]
    for msg in recent:
        # Extract tool names from ToolMessage objects
        msg_name = getattr(msg, "name", None)
        if msg_name and msg_name in tool_to_category:
            history_categories.add(tool_to_category[msg_name])

        # Collect recent user messages for LLM context
        msg_type = getattr(msg, "type", None)
        if msg_type == "human":
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content:
                recent_user_messages.append(content[:100])

    context_summary = " | ".join(recent_user_messages[-2:]) if recent_user_messages else None
    return list(history_categories), context_summary


def _apply_co_occurrence(categories: list[ToolCategory]) -> list[ToolCategory]:
    """Expand categories with co-occurrence dependencies."""
    expanded = set(categories)
    for cat in categories:
        if cat in CO_OCCURRENCE:
            expanded.update(CO_OCCURRENCE[cat])
    return list(expanded)


async def classify_intent(
    message: str,
    conversation_history: list | None = None,
    settings=None,
) -> IntentResult:
    """Classify user message into tool categories.

    Uses a hybrid approach:
    1. Rule-based keyword matching (fast path, ~0.1ms)
    2. LLM fallback for ambiguous queries (when enabled, ~200-500ms)
    3. Multi-turn context from conversation history

    Args:
        message: The user's current message
        conversation_history: Recent messages from the conversation checkpoint
        settings: App settings (for feature flags). Auto-loaded if None.

    Returns:
        IntentResult with categories, confidence, and metadata
    """
    if settings is None:
        from src.config import get_settings
        settings = get_settings()

    start = time.time()

    # Step 1: Rule-based classification on current message
    result = _classify_rules(message)

    # Step 2: LLM fallback if rules produced low confidence and LLM is enabled
    if result.confidence < settings.intent_confidence_threshold and settings.intent_llm_fallback_enabled:
        history_categories, context_summary = _extract_history_context(conversation_history)
        llm_result = await _classify_llm(message, context_summary)

        if llm_result.confidence > result.confidence:
            result = llm_result

    # Step 3: Enrich with multi-turn context
    history_categories, _ = _extract_history_context(conversation_history)
    if history_categories:
        merged = set(result.categories) | set(history_categories)
        result.categories = list(merged)
        logger.debug(f"   📜 Added history categories: {[c.value for c in history_categories]}")

    # Step 4: Apply co-occurrence rules
    result.categories = _apply_co_occurrence(result.categories)

    # Final timing
    result.latency_ms = (time.time() - start) * 1000

    # Log classification result
    cat_names = [c.value for c in result.categories] if result.categories else ["(ALWAYS_INCLUDE only)"]
    logger.info(
        f"🎯 INTENT: {cat_names} "
        f"confidence={result.confidence:.2f} source={result.source} "
        f"latency={result.latency_ms:.1f}ms"
    )

    return result
