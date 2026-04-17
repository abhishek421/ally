"""Greeting detection for fast-path routing.

All non-greeting requests go to STANDARD tier with all tools loaded.
Greetings are detected here (regex, <1ms) and routed to LITE with zero tools.
"""

import re
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Model tiers."""
    LITE = "lite"           # Greetings — short chitchat prompt, 0 tools
    STANDARD = "standard"   # Everything else — full prompt, all tools


GREETING_PATTERNS = [
    r"^(hi|hey|hello|howdy|sup|yo|hola|good\s+(morning|afternoon|evening))[\s!?.]*$",
    r"^(thanks|thank\s*you|thx|ty|ok|okay|got\s*it|cool|nice|great|awesome|sure)[\s!?.]*$",
    r"^(bye|goodbye|see\s*ya|later|good\s*night|take\s*care)[\s!?.]*$",
    r"^(what\s+can\s+you\s+do|help|who\s+are\s+you|what\s+are\s+you)[\s?]*$",
    r"^(yes|no|yep|nope|yeah|nah)[\s!?.]*$",
    r"^[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f900-\U0001f9ff]+$",  # emoji-only
]


def is_greeting(message: str) -> bool:
    """Check if the message is a simple greeting or acknowledgement.

    Public — used by stream_agent to skip tool loading entirely for chitchat.
    Short messages (under 8 words) that match greeting patterns.
    """
    msg = message.lower().strip()
    if len(msg.split()) > 8:
        return False
    return any(re.match(p, msg) for p in GREETING_PATTERNS)


# Keep private alias so existing internal references keep working
_is_greeting = is_greeting
