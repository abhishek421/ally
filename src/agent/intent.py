"""Intent classification for dynamic tool selection.

Classifies user messages into tool categories using keyword/pattern matching.
This allows the agent to load only the relevant tool subset per request.

READ (resolver tools) and MEMORY are always loaded via ALWAYS_INCLUDE.
Entity-type sub-categories (COMPANIES, PEOPLE, GROUPS, EMAIL, COLUMNS) are
loaded only when the query mentions those entity types.

Token impact per category loaded:
  READ (resolvers): ~160 tokens  — always loaded
  MEMORY:           ~110 tokens  — always loaded
  COMPANIES:        ~360 tokens
  PEOPLE:           ~360 tokens
  GROUPS:           ~220 tokens
  EMAIL:            ~930 tokens
  COLUMNS:          ~660 tokens
  CREATE:           ~260 tokens
  UPDATE:           ~750 tokens
"""

import re
import logging
from src.tools import ToolCategory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[ToolCategory, list[str]] = {
    # --- Entity type detection (drives which READ sub-category loads) ---
    ToolCategory.COMPANIES: [
        r"\bcompan(?:y|ies)\b",
        r"\bbusiness(?:es)?\b",
        r"\bfirm\b",
        r"\borganization\b",
        r"\bstartup\b",
        r"\bclient\b",
    ],
    ToolCategory.PEOPLE: [
        r"\bperson\b",
        r"\bpeople\b",
        r"\bcontact\b",
        r"\bcontacts\b",
        r"\bsomeone\b",
        r"\bwho\b",
        r"\bfounder\b",
        r"\bceo\b",
        r"\bemployee\b",
    ],
    ToolCategory.GROUPS: [
        r"\bgroup\b",
        r"\bgroups\b",
        r"\blist\b",
        r"\bpipeline\b",
        r"\bfolder\b",
        r"\bcollection\b",
        r"\bview\b",
    ],
    ToolCategory.EMAIL: [
        r"\bemail\b",
        r"\bemails\b",
        r"\bmessage\b",
        r"\bdraft\b",
        r"\bsend\b",
        r"\bthread\b",
        r"\binbox\b",
        r"\btemplate\b",
    ],
    ToolCategory.COLUMNS: [
        r"\bstatus\b",
        r"\bpriority\b",
        r"\bcolumn\b",
        r"\bstage\b",
        r"\bfield\b",
        r"\boption\b",
    ],
    # --- Write operations ---
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
    ToolCategory.MEMORY: [
        r"\bremember\b",
        r"\bforget\b",
        r"\bprefer(?:ence|s)?\b",
        r"\bsave\s+(?:a\s+)?(?:note|memory|fact)\b",
        r"\bwhat\s+(?:do\s+)?(?:i|we)\s+know\s+about\b",
    ],
}

# When UPDATE is detected and these column keywords are present, also load COLUMNS
_COLUMN_WITH_UPDATE_PATTERNS = [
    r"\bstatus\b", r"\bpriority\b", r"\bcolumn\b", r"\bstage\b", r"\bfield\b",
]


def classify_intent(message: str) -> list[ToolCategory]:
    """Classify user message into tool categories using keyword matching.

    Returns list of matched categories. The fallback when nothing entity-specific
    is detected is [COMPANIES, PEOPLE] — the most common read query targets.

    READ (resolvers) and MEMORY are always added via ALWAYS_INCLUDE; they don't
    need to appear here.

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

    # When UPDATE is matched without an entity type, include both COMPANIES and PEOPLE
    # so the agent can resolve whichever entity is mentioned in the message.
    if ToolCategory.UPDATE in matched and not (
        ToolCategory.COMPANIES in matched or ToolCategory.PEOPLE in matched
    ):
        matched.add(ToolCategory.COMPANIES)
        matched.add(ToolCategory.PEOPLE)

    # When UPDATE is matched with column-related keywords, also load COLUMNS tools.
    if ToolCategory.UPDATE in matched:
        if any(re.search(p, message_lower) for p in _COLUMN_WITH_UPDATE_PATTERNS):
            matched.add(ToolCategory.COLUMNS)

    # Fallback: if no entity type was detected, default to the two most common
    # entity types so the agent can answer general CRM questions.
    if not matched:
        return [ToolCategory.COMPANIES, ToolCategory.PEOPLE]

    return list(matched)
