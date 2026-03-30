"""Multi-model router for cost-optimized query handling.

Routes queries to Lite/Standard/Power model tiers based on
heuristic complexity scoring. Zero-cost routing — no LLM call needed.

Typical savings: 60-70% vs running everything on a single expensive model.
"""

import re
import logging
from enum import Enum
from typing import Optional

from src.tools import ToolCategory

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Model tiers ordered by cost/capability."""
    LITE = "lite"           # Cheapest — greetings, simple lookups
    STANDARD = "standard"   # Balanced — CRM operations, summaries
    POWER = "power"         # Most capable — deep analysis, research


# ---------------------------------------------------------------------------
# Fast heuristic patterns
# ---------------------------------------------------------------------------

GREETING_PATTERNS = [
    r"^(hi|hey|hello|howdy|sup|yo|hola|good\s+(morning|afternoon|evening))[\s!?.]*$",
    r"^(thanks|thank\s*you|thx|ty|ok|okay|got\s*it|cool|nice|great|awesome|sure)[\s!?.]*$",
    r"^(bye|goodbye|see\s*ya|later|good\s*night|take\s*care)[\s!?.]*$",
    r"^(what\s+can\s+you\s+do|help|who\s+are\s+you|what\s+are\s+you)[\s?]*$",
    r"^(yes|no|yep|nope|yeah|nah)[\s!?.]*$",
    r"^[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f900-\U0001f9ff]+$",  # emoji-only
]

POWER_KEYWORDS = [
    r"\bsummar(ize|y|ise)\b",
    r"\banalyze\b",
    r"\banalysis\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bbreakdown\b",
    r"\binsights?\b",
    r"\btrends?\b",
    r"\bstrateg(y|ic|ies)\b",
    r"\brecommend(ation)?s?\b",
    r"\bprioritize\b",
    r"\bforecast\b",
    r"\bpredict\b",
    r"\bwhy\s+(did|is|are|do|does|was|were|has|have|should)\b",
    r"\bexplain\s+(why|how)\b",
    r"\bwhat\s+should\s+(i|we)\b",
    r"\bacross\s+all\b",
    r"\bbulk\b",
    r"\beveryone\b",
    r"\ball\s+(emails?|contacts?|companies|groups|people|notes?|reminders?)\b",
    r"\bevaluate\b",
    r"\bassess\b",
    r"\baudit\b",
    r"\breview\s+all\b",
    r"\boverall\b",
    r"\bperformance\b",
    r"\bopportunit(y|ies)\b",
    r"\brisk\b",
]

MULTI_ENTITY_PATTERN = r"\b(and|vs\.?|versus|compared?\s+to|between)\b"


# ---------------------------------------------------------------------------
# Classification functions
# ---------------------------------------------------------------------------

def _is_greeting(message: str) -> bool:
    """Check if the message is a simple greeting or acknowledgement."""
    msg = message.lower().strip()
    # Short messages (under 8 words) that match greeting patterns
    if len(msg.split()) > 8:
        return False
    return any(re.match(p, msg) for p in GREETING_PATTERNS)


def _count_power_signals(message: str) -> int:
    """Count how many power-tier keyword signals are present."""
    msg_lower = message.lower()
    return sum(1 for p in POWER_KEYWORDS if re.search(p, msg_lower))


def _complexity_score(message: str, categories: list[ToolCategory]) -> int:
    """Score the complexity of a query (0-15+ scale).

    Scoring:
        0       → greeting (force LITE)
        1-2     → simple query (LITE)
        3-6     → standard query (STANDARD)
        7+      → complex query (POWER)
    """
    score = 0
    msg_lower = message.lower()

    # --- Tool category complexity ---
    non_read = [c for c in categories if c != ToolCategory.READ]

    if len(non_read) == 0:
        score += 1  # read-only query
    elif len(non_read) == 1:
        score += 2  # single write category
    else:
        score += 4  # multi-category (e.g., create + update)

    # --- Write operations need more reasoning ---
    if ToolCategory.CREATE in categories:
        score += 2
    if ToolCategory.UPDATE in categories:
        score += 2

    # --- Research is always complex ---
    if ToolCategory.RESEARCH in categories:
        score += 3

    # --- Power keywords ---
    power_hits = _count_power_signals(message)
    score += min(power_hits * 2, 6)  # cap contribution at 6

    # --- Multi-entity comparison ---
    if re.search(MULTI_ENTITY_PATTERN, msg_lower):
        score += 2

    # --- Message length (longer = usually more complex) ---
    word_count = len(message.split())
    if word_count > 50:
        score += 3
    elif word_count > 30:
        score += 2
    elif word_count > 15:
        score += 1

    return score


def route_query(
    message: str,
    categories: Optional[list[ToolCategory]] = None,
) -> ModelTier:
    """Route a user message to the appropriate model tier.

    This runs BEFORE the LLM call — zero cost, <1ms.

    Args:
        message: The user's raw message text
        categories: Pre-classified intent categories (from classify_intent).
                    If None, will import and call classify_intent.

    Returns:
        ModelTier indicating which model should handle this query
    """
    # Step 1: Fast greeting/chitchat check
    if _is_greeting(message):
        logger.info("🎯 Router → LITE (greeting/chitchat)")
        return ModelTier.LITE

    # Step 2: Get intent categories if not provided
    if categories is None:
        from src.agent.intent import classify_intent
        categories = classify_intent(message)

    # Step 3: Complexity scoring
    score = _complexity_score(message, categories)

    # Step 4: Map score to tier
    if score <= 2:
        tier = ModelTier.LITE
    elif score <= 6:
        tier = ModelTier.STANDARD
    else:
        tier = ModelTier.POWER

    logger.info(
        f"🎯 Router → {tier.value.upper()} "
        f"(score={score}, categories={[c.value for c in categories]})"
    )
    return tier
