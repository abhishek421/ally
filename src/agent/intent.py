"""Intent classification for dynamic tool selection.

Classifies user messages into tool categories using keyword/pattern matching.
This allows the agent to load only relevant tools for each request,
reducing token usage by 45-55%.

See: DYNAMIC_TOOL_SELECTION_PLAN.md for full design rationale.
"""

import re
import logging
from src.tools import ToolCategory

logger = logging.getLogger(__name__)


# Keyword patterns mapped to tool categories
# READ is not listed here because it's always included via ALWAYS_INCLUDE
INTENT_PATTERNS: dict[ToolCategory, list[str]] = {
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
        r"\badd\s+(?:to\s+group|to\s+company)\b",
    ],
    ToolCategory.NOTES: [
        r"\bnote\b",
        r"\bnotes\b",
        r"\bjot\b",
        r"\bmemo\b",
        r"\bwrite\s+(?:a\s+)?(?:note|memo)\b",
        r"\bannotate\b",
    ],
    ToolCategory.REMINDERS: [
        r"\bremind\b",
        r"\breminder\b",
        r"\breminders\b",
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
        r"\blook\s*up\b",
        r"\bwhat\s+(?:is|are|does)\b.*\b(?:industry|market|funding|revenue)\b",
    ],
    ToolCategory.CONTEXT: [
        r"\binstructions?\b",
        r"\bguidelines?\b",
        r"\bworkspace\s+(?:rules|settings)\b",
    ],
}


def classify_intent(message: str) -> list[ToolCategory]:
    """Classify user message into tool categories using keyword matching.

    Returns list of matched categories. Falls back to [READ] if no
    specific intent is detected (user is probably asking a question).

    Note: READ is always included via ALWAYS_INCLUDE in the tool registry,
    so it doesn't need to be matched here.

    Args:
        message: The user's message text

    Returns:
        List of matched ToolCategory values
    """
    message_lower = message.lower().strip()
    matched = set()

    for category, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                matched.add(category)
                break

    # Fallback: if nothing matched, it's likely a read/general query
    if not matched:
        return [ToolCategory.READ]

    return list(matched)
