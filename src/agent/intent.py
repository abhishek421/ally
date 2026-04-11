"""Intent classification for dynamic tool selection.

Primary: LLM-based classifier (LITE tier, ~200 tokens in / ~50 out).
Fallback: regex pattern matching (used when LLM call fails or times out).

READ (resolver tools) and MEMORY are always loaded via ALWAYS_INCLUDE.
Entity-type sub-categories (COMPANIES, PEOPLE, GROUPS, EMAIL, COLUMNS) are
loaded only when the query mentions those entity types.

Token impact per category loaded:
  READ (resolvers): ~80 tokens   — always loaded
  MEMORY:           ~150 tokens  — always loaded
  COMPANIES:        ~300 tokens
  PEOPLE:           ~300 tokens
  GROUPS:           ~220 tokens
  EMAIL:            ~800 tokens
  COLUMNS:          ~660 tokens
  DEALS:            ~120 tokens
  CREATE:           ~260 tokens
  UPDATE:           ~750 tokens
"""

import json
import re
import logging
import asyncio
from src.tools import ToolCategory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM classifier prompt
# ---------------------------------------------------------------------------

_CLASSIFIER_SYSTEM = """You are an intent classifier for a CRM AI agent.
Classify the user message into zero or more tool categories by returning a valid JSON array.

Available categories:
- "companies"  → queries about companies, businesses, organizations, startups, clients
- "people"     → queries about contacts, people, founders, CEOs, employees
- "groups"     → queries about groups, lists, pipelines, folders, views
- "email"      → email, messages, drafts, sending, threads, templates
- "columns"    → custom fields, status, stage, priority, revenue, column values; any ranked/sorted/filtered query
- "deals"      → deals, opportunities, contracts
- "create"     → creating new entities (company, person, note, group, deal, reminder)
- "update"     → updating, editing, deleting, renaming, moving, attaching, assigning, linking
- "notes"      → notes, memos, annotations
- "reminders"  → reminders, follow-ups, deadlines, schedules, upcoming tasks
- "research"   → web search, external info lookup
- "context"    → workspace instructions, rules, guidelines
- "memory"     → saving or recalling facts/preferences about entities

Rules:
- Return ONLY a valid JSON array of strings. No explanation. No markdown.
- Include "columns" for any analytical query (highest, lowest, best, ranked, sorted, filtered, over $X).
- Include "update" for delete, remove, rename, move, attach, unlink, assign operations.
- Fallback when unclear: ["companies", "people"]

Examples:
"who is John Smith?" → ["people"]
"list all companies" → ["companies"]
"add Acme to the enterprise group" → ["companies", "groups", "update"]
"which company has highest revenue?" → ["companies", "columns"]
"create a note for Sarah about the meeting" → ["people", "notes", "create"]
"send an email to john@acme.com" → ["email"]
"remind me to call Lisa on Friday" → ["people", "reminders", "create"]
"delete the deal named Q2 expansion" → ["deals", "update"]
"what do I have coming up this week?" → ["reminders"]"""

_VALID_CATEGORIES = {c.value for c in ToolCategory}

# Module-level LLM cache to avoid re-initializing on every call
_classifier_llm = None
_classifier_llm_lock = asyncio.Lock()


async def _get_classifier_llm():
    """Return a cached LITE-tier LLM instance for classification."""
    global _classifier_llm
    if _classifier_llm is not None:
        return _classifier_llm

    async with _classifier_llm_lock:
        if _classifier_llm is not None:
            return _classifier_llm

        try:
            from src.config import get_settings
            settings = get_settings()

            # Use LITE tier if routing is enabled, else fall back to default
            if settings.enable_model_routing:
                provider = settings.lite_provider
                model = settings.lite_model
            else:
                provider = settings.llm_provider
                model = settings.llm_model

            if provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                _classifier_llm = ChatAnthropic(
                    model=model,
                    api_key=settings.anthropic_api_key,
                    temperature=0.0,
                    max_tokens=64,
                )
            elif provider == "gemini":
                from langchain_google_genai import ChatGoogleGenerativeAI
                _classifier_llm = ChatGoogleGenerativeAI(
                    model=model,
                    api_key=settings.google_api_key,
                    temperature=0.0,
                )
            else:  # openai (default)
                from langchain_openai import ChatOpenAI
                _classifier_llm = ChatOpenAI(
                    model=model,
                    api_key=settings.openai_api_key,
                    temperature=0.0,
                    max_tokens=64,
                )

            logger.info(f"🤖 Intent classifier LLM: {provider}/{model}")
        except Exception as e:
            logger.warning(f"Could not initialize classifier LLM: {e}")
            _classifier_llm = None

    return _classifier_llm


async def _llm_classify(message: str) -> list[ToolCategory]:
    """Call LITE-tier LLM to classify intent. Returns empty list on failure."""
    llm = await _get_classifier_llm()
    if llm is None:
        raise RuntimeError("Classifier LLM not available")

    from langchain_core.messages import HumanMessage, SystemMessage

    response = await asyncio.wait_for(
        llm.ainvoke([
            SystemMessage(content=_CLASSIFIER_SYSTEM),
            HumanMessage(content=message),
        ]),
        timeout=3.0,
    )

    raw = response.content.strip()
    # Strip markdown fences if model added them
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n")

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got: {type(parsed)}")

    categories = []
    for item in parsed:
        if isinstance(item, str) and item in _VALID_CATEGORIES:
            categories.append(ToolCategory(item))

    return categories


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
    ToolCategory.DEALS: [
        r"\bdeal\b",
        r"\bdeals\b",
        r"\bopportunity\b",
        r"\bopportunities\b",
        r"\bcontract\b",
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
        r"\bdelete\b",
        r"\bset\s+(?:status|stage|priority)\b",
        r"\bassign\b",
        r"\bunlink\b",
        r"\badd\s+(?:to\s+group|to\s+company)\b",
        r"\battach\b",
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
        r"\bsearch\s+(?:the\s+|on\s+|)?(?:web|internet|online)\b",
        r"\bsearch\s+online\b",
        r"\bfind\s+(?:out|info|information)\b",
        r"\blook\s*up\b",
        r"\bwhat\s+(?:is|are|does)\b.*\b(?:industry|market|funding|revenue)\b",
        r"\bweb\s+search\b",
        r"\bsearch\s+for\b",
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

# Analytical/ranking patterns — when these appear alongside an entity type,
# also load COLUMNS so filter/sort tools and column resolvers are available.
# Examples: "which company has highest revenue", "sort people by deal size",
#           "find contacts added this week", "best performing deal"
_ANALYTICAL_PATTERNS = [
    r"\bbest\b",
    r"\bworst\b",
    r"\bhighest\b",
    r"\blowest\b",
    r"\bmost\b",
    r"\bleast\b",
    r"\branked?\b",
    r"\bsorte?d?\s+by\b",
    r"\bfilter(?:ed)?\s+by\b",
    r"\bover\s+\$?\d",
    r"\bunder\s+\$?\d",
    r"\bmore\s+than\b",
    r"\bless\s+than\b",
    r"\bgreater\s+than\b",
    r"\bperform(?:ing|ance|ed)?\b",
    r"\btop\s+\d+\b",
    r"\bbottom\s+\d+\b",
    r"\bthis\s+week\b",
    r"\bthis\s+month\b",
    r"\bthis\s+year\b",
    r"\blast\s+\d+\s+(?:days?|weeks?|months?)\b",
    r"\brecent(?:ly)?\b",
    r"\bnew(?:est)?\b",
    r"\blatest\b",
    r"\bold(?:est)?\b",
]


def _regex_classify(message: str) -> list[ToolCategory]:
    """Fallback regex-based intent classification.

    Returns list of matched categories. The fallback when nothing entity-specific
    is detected is [COMPANIES, PEOPLE] — the most common read query targets.
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

    # When an analytical/ranking pattern is present alongside an entity type,
    # load COLUMNS so resolve_column_by_name and filter/sort tools are available.
    _entity_types = {ToolCategory.COMPANIES, ToolCategory.PEOPLE, ToolCategory.DEALS}
    if matched & _entity_types:
        if any(re.search(p, message_lower) for p in _ANALYTICAL_PATTERNS):
            matched.add(ToolCategory.COLUMNS)

    # Fallback: if no entity type was detected, default to the two most common
    # entity types so the agent can answer general CRM questions.
    if not matched:
        return [ToolCategory.COMPANIES, ToolCategory.PEOPLE]

    return list(matched)


async def classify_intent(message: str) -> list[ToolCategory]:
    """Classify user message into tool categories.

    Primary: LLM-based classifier (LITE tier, ~200 tokens in / ~50 out, ~3ms).
    Fallback: regex pattern matching (zero cost, always succeeds).

    The greeting fast-path in graph.py fires BEFORE this function, so greetings
    never reach here. ALWAYS_INCLUDE (READ + MEMORY) are added by the caller.

    Args:
        message: The user's message text.

    Returns:
        List of matched ToolCategory values.
    """
    try:
        categories = await _llm_classify(message)
        if categories:
            logger.info(f"🤖 LLM intent: {[c.value for c in categories]}")
            return categories
        # Empty list from LLM = uncertain — fall through to regex
        logger.info("🤖 LLM returned empty intent, falling back to regex")
    except asyncio.TimeoutError:
        logger.warning("⏱ Intent classifier timed out (>3s), using regex fallback")
    except Exception as e:
        logger.warning(f"⚠ Intent classifier error ({type(e).__name__}), using regex fallback")

    result = _regex_classify(message)
    logger.info(f"📋 Regex intent: {[c.value for c in result]}")
    return result
