"""Logic for compressing conversation history via summarization."""

import logging
import re
from typing import List

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
    trim_messages,
)
from langchain_openai import ChatOpenAI

from src.config import get_settings

logger = logging.getLogger(__name__)


def _estimate_message_tokens(msg: BaseMessage) -> int:
    """Fast heuristic token estimate (~4 chars per token for English text)."""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return len(content) // 4
    return len(str(content)) // 4


def _summarize_tool_result(content: str) -> str:
    """Create a one-line summary of a tool result for compression."""
    if not content:
        return "empty"
    lower = content.lower()
    if "could not find" in lower or "no matches" in lower or "not found" in lower:
        return "not found"
    count_match = re.search(r"found\s+(\d+)", lower)
    if count_match:
        return f"found {count_match.group(1)} results"
    if any(w in lower for w in ["success", "created", "updated", "added", "removed"]):
        return "success"
    # Preserve entity IDs mentioned
    ids = re.findall(r"ID:\s*([a-f0-9-]+)", content)
    if ids:
        return f"IDs: {', '.join(ids[:3])}"
    return content[:50] + "..."


def _format_old_messages(old_messages: List[BaseMessage]) -> str:
    """Format old messages for summarization with tool-aware collapsing.

    Tool call/result pairs are collapsed into one-liners instead of
    including full verbose results. This dramatically reduces the
    summarization input size.
    """
    chat_history = ""
    for m in old_messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            # Collapse tool calls to one-liners
            for tc in m.tool_calls:
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                # Only show key args, skip verbose ones
                brief_args = {k: v for k, v in args.items() if isinstance(v, (str, int, bool)) and len(str(v)) < 50}
                chat_history += f"[Called {name}({brief_args})]\n"
        elif isinstance(m, ToolMessage):
            tool_name = getattr(m, "name", "unknown")
            summary = _summarize_tool_result(getattr(m, "content", ""))
            chat_history += f"[{tool_name} → {summary}]\n"
        elif isinstance(m, HumanMessage):
            chat_history += f"User: {m.content}\n"
        elif isinstance(m, AIMessage):
            # Text response — truncate long ones
            content = getattr(m, "content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            chat_history += f"Ally: {content}\n"
        elif isinstance(m, SystemMessage):
            content = getattr(m, "content", "")
            chat_history += f"System: {content[:100]}\n"
    return chat_history


def compress_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Compress conversation history if it exceeds the configured threshold.

    Uses both message count AND token estimation to decide when to compress.
    Keeps the most recent messages verbatim and summarizes the older ones
    with tool-aware collapsing for efficient summarization.

    Also repairs broken history by pruning AIMessages with missing ToolMessages.
    """
    # PARANOID CLEANUP: Remove anything that isn't a BaseMessage
    messages = [m for m in messages if hasattr(m, "content") or (isinstance(m, dict) and "content" in m)]

    settings = get_settings()
    original_len = len(messages)

    # REPAIR BROKEN HISTORY
    # LangGraph requires that every tool_call in an AIMessage MUST have a corresponding ToolMessage.
    repaired_messages = []
    i = 0
    while i < len(messages):
        msg = messages[i]

        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tool_call_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}

            # Look ahead for following ToolMessages
            j = i + 1
            found_ids = set()
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                found_ids.add(messages[j].tool_call_id)
                j += 1

            if not tool_call_ids.issubset(found_ids):
                logger.warning(
                    f"⚠️ Pruning broken AIMessage (turn {i}) - tool_calls {tool_call_ids} "
                    f"missing matching ToolMessages (found {found_ids})"
                )
                i = j
                continue

        repaired_messages.append(msg)
        i += 1

    messages = repaired_messages

    if not settings.compression_enabled:
        if len(messages) < original_len:
            return [SystemMessage(content="__REPLACE_HISTORY__")] + messages
        return messages

    recent_count = settings.compression_recent_count

    # Check both message count AND token budget
    total_tokens = sum(_estimate_message_tokens(m) for m in messages)
    under_message_limit = len(messages) <= recent_count
    under_token_limit = total_tokens <= settings.compression_token_threshold

    if under_message_limit and under_token_limit:
        if len(messages) < original_len:
            return [SystemMessage(content="__REPLACE_HISTORY__")] + messages
        return messages

    logger.info(
        f"💾 Compressing: {len(messages)} messages, ~{total_tokens} tokens "
        f"→ summary + last {recent_count}"
    )

    # Split into old (to be summarized) and recent (to keep verbatim).
    # CRITICAL: The split must not orphan ToolMessages — every ToolMessage
    # needs its preceding AIMessage(tool_calls). Walk backward from the
    # candidate split point to find a clean boundary.
    split_idx = max(0, len(messages) - recent_count)

    # If the split lands on a ToolMessage, walk backward to include
    # the AIMessage that triggered it.
    while split_idx > 0 and isinstance(messages[split_idx], ToolMessage):
        split_idx -= 1

    recent_messages = messages[split_idx:]
    old_messages = messages[:split_idx]

    if old_messages:
        try:
            summarizer = ChatOpenAI(model="gpt-4o-mini", temperature=0)

            # Use tool-aware formatting for efficient summarization
            chat_history = _format_old_messages(old_messages)

            summary_prompt = f"""Summarize this CRM conversation history concisely.
CRITICAL: Preserve ALL entity IDs (UUIDs) — the agent needs these for follow-up operations.
Focus on: entity IDs & names, actions completed, user preferences.

History:
{chat_history}

Concise Summary (preserve all IDs):"""

            summary_response = summarizer.invoke([HumanMessage(content=summary_prompt)])
            summary_text = summary_response.content

            summary_msg = SystemMessage(
                content=f"PREVIOUS CONVERSATION SUMMARY:\n{summary_text}\n\nUse this context for entity IDs and preferences mentioned earlier."
            )

            return [SystemMessage(content="__REPLACE_HISTORY__"), summary_msg] + recent_messages

        except Exception as e:
            logger.error(f"Failed to compress messages: {e}")
            return [SystemMessage(content="__REPLACE_HISTORY__")] + messages

    return messages
