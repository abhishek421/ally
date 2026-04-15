"""Intent classification for dynamic tool selection.

LLM-based classifier (LITE tier, ~200 tokens in / ~50 out).
On failure, falls back to the safe default: [COMPANIES, PEOPLE].

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
- Include "update" + entity type when changing a status, stage, priority, or column value.
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
"what do I have coming up this week?" → ["reminders"]
"move John to the Qualified stage" → ["people", "columns", "update"]
"what are the pipeline stages for Leads?" → ["groups", "columns"]"""

_VALID_CATEGORIES = {c.value for c in ToolCategory}

_DEFAULT_CATEGORIES = [ToolCategory.COMPANIES, ToolCategory.PEOPLE]

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
openai_api_key="REDACTED"
                    temperature=0.0,
                    max_tokens=64,
                )

            logger.info(f"🤖 Intent classifier LLM: {provider}/{model}")
        except Exception as e:
            logger.warning(f"Could not initialize classifier LLM: {e}")
            _classifier_llm = None

    return _classifier_llm


async def _llm_classify(message: str) -> list[ToolCategory]:
    """Call LITE-tier LLM to classify intent. Raises on failure."""
    llm = await _get_classifier_llm()
    if llm is None:
        raise RuntimeError("Classifier LLM not available")

    from langchain_core.messages import HumanMessage, SystemMessage

    response = await asyncio.wait_for(
        llm.ainvoke([
            SystemMessage(content=_CLASSIFIER_SYSTEM),
            HumanMessage(content=message),
        ]),
        timeout=5.0,
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


async def classify_intent(message: str) -> list[ToolCategory]:
    """Classify user message into tool categories using LLM.

    Uses LITE-tier LLM. On timeout or error, falls back to the safe
    default [COMPANIES, PEOPLE] so the agent can still answer general
    CRM questions without crashing.

    The greeting fast-path in graph.py fires BEFORE this function, so
    greetings never reach here. ALWAYS_INCLUDE (READ + MEMORY) are added
    by the caller.

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
        # LLM returned empty array — treat as uncertain, use default
        logger.info("🤖 LLM returned empty intent, using default categories")
        return _DEFAULT_CATEGORIES
    except asyncio.TimeoutError:
        logger.warning("⏱ Intent classifier timed out (>5s), using default categories")
    except Exception as e:
        logger.warning(f"⚠ Intent classifier error ({type(e).__name__}: {e}), using default categories")

    return _DEFAULT_CATEGORIES
