"""Intent classification for dynamic tool selection.

Classifies user messages into tool categories using keyword/pattern matching.
This allows the agent to load only relevant tools for each request,
reducing token usage significantly.

See: DYNAMIC_TOOL_SELECTION_PLAN.md for full design rationale.
"""

import re
import logging
from src.tools import ToolCategory

logger = logging.getLogger(__name__)


# Keyword patterns mapped to tool categories.
# CORE is always loaded via ALWAYS_INCLUDE — not matched here.
INTENT_PATTERNS: dict[ToolCategory, list[str]] = {
    ToolCategory.SEARCH: [
        r"\bfind\b",
        r"\bsearch\b",
        r"\blist\b",
        r"\bshow\s+me\b",
        r"\bwho\s+is\b",
        r"\bwhere\s+is\b",
        r"\bwhat\s+groups\b",
        r"\bwhat\s+companies\b",
        r"\bwhat\s+people\b",
        r"\blookup\b",
        r"\blook\s*up\b",
    ],
    ToolCategory.DETAILS: [
        r"\bdetails\b",
        r"\bfull\s+info\b",
        r"\bprofile\b",
        r"\beverything\s+about\b",
        r"\bhistory\b",
    ],
    ToolCategory.PIPELINE: [
        r"\bstatus\b",
        r"\bpipeline\b",
        r"\bstage\b",
        r"\bcolumn\b",
        r"\bcolumns\b",
        r"\bkanban\b",
        r"\bboard\b",
        r"\bfilter\s+by\s+status\b",
        r"\bwhat\s+(?:are|is)\s+(?:the\s+)?status",
    ],
    ToolCategory.EMAIL: [
        r"\bemail\b",
        r"\bemails\b",
        r"\bmail\b",
        r"\bdraft\b",
        r"\bsend\b",
        r"\btemplate\b",
        r"\btemplates\b",
        r"\bthread\b",
        r"\binteractions\b",
        r"\breply\b",
        r"\bcompose\b",
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
    ToolCategory.MEMORY: [
        r"\bremember\b",
        r"\bpreference\b",
        r"\bpreferences\b",
        r"\brecall\b",
        r"\bwhat\s+do\s+(?:you|I)\s+know\s+about\b",
    ],
}


def classify_intent(message: str) -> list[ToolCategory]:
    """Classify user message into tool categories using keyword matching.

    Returns list of matched categories. Returns empty list if no
    specific intent is detected (greetings, casual chat) — the
    ALWAYS_INCLUDE set (CORE + CONTEXT) handles those.

    Args:
        message: The user's message text

    Returns:
        List of matched ToolCategory values
    """
    message_lower = message.lower().strip()
    logger.info(f"🔍 Classifying intent for: '{message_lower}'")
    matched = set()

    for category, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                logger.debug(f"   ✅ Matched {category.value} via pattern: {pattern}")
                matched.add(category)
                break

    if matched:
        logger.info(f"   🎯 Result: {[c.value for c in matched]}")
    else:
        logger.info("   🎯 Result: [] (casual/greeting — CORE only)")

    return list(matched)

