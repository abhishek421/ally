"""Logic for compressing conversation history via summarization."""

import logging
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

def compress_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Compress conversation history if it exceeds the configured threshold.
    
    Keeps the most recent messages verbatim and summarizes the older ones.
    Also repairs broken history by pruning trailing AIMessages with missing tools.
    """
    # PARANOID CLEANUP: Remove anything that isn't a BaseMessage (e.g. leftover dicts from failed attempts)
    messages = [m for m in messages if hasattr(m, "content") and not isinstance(m, dict)]
    
    settings = get_settings()
    original_len = len(messages)
    
    # REPAIR BROKEN HISTORY
    # LangGraph requires that every tool_call in an AIMessage MUST have a corresponding ToolMessage.
    # We prune any AIMessage that has dangling tool calls to avoid history validation errors.
    repaired_messages = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        
        # If it's an AIMessage with tool calls, verify all of them are answered
        if isinstance(msg, AIMessage) and msg.tool_calls:
            tool_call_ids = {tc.get('id') for tc in msg.tool_calls if tc.get('id')}
            
            # Look ahead for following ToolMessages
            j = i + 1
            found_ids = set()
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                found_ids.add(messages[j].tool_call_id)
                j += 1
            
            # If any tool_call_id from the AI message is missing a ToolMessage,
            # this turn is "broken" and must be pruned to satisfy LangGraph invariants.
            if not tool_call_ids.issubset(found_ids):
                logger.warning(
                    f"⚠️ Pruning broken AIMessage (turn {i}) - tool_calls {tool_call_ids} "
                    f"missing matching ToolMessages (found {found_ids})"
                )
                # Skip the AIMessage AND any partial ToolMessages that followed it
                i = j 
                continue
        
        repaired_messages.append(msg)
        i += 1
    
    messages = repaired_messages
    
    if not settings.compression_enabled:
        # If history was repaired, we still need to signal a replacement
        if len(messages) < original_len:
            return [SystemMessage(content="__REPLACE_HISTORY__")] + messages
        return messages
        
    recent_count = settings.compression_recent_count
    
    # If history is short and wasn't repaired, no replacement needed
    if len(messages) <= recent_count:
        if len(messages) < original_len:
            return [SystemMessage(content="__REPLACE_HISTORY__")] + messages
        return messages
        
    logger.info(f"💾 Compressing conversation: {len(messages)} messages -> summary + last {recent_count}")
    
    # Split into old (to be summarized) and recent (to keep verbatim)
    recent_messages = messages[-recent_count:]
    old_messages = messages[:-recent_count]
    
    if old_messages:
        try:
            summarizer = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            
            chat_history = ""
            for m in old_messages:
                role = "User" if isinstance(m, HumanMessage) else "Ally"
                if isinstance(m, SystemMessage): role = "System/Summary"
                chat_history += f"{role}: {getattr(m, 'content', str(m))}\n"
                
            summary_prompt = f"""Summarize the following CRM conversation history concisely. 
Focus on:
1. Entities mentioned (people, companies, groups).
2. Actions already taken.
3. User preferences or specific instructions given.

History:
{chat_history}

Concise Summary:"""
            
            summary_response = summarizer.invoke([HumanMessage(content=summary_prompt)])
            summary_text = summary_response.content
            
            summary_msg = SystemMessage(
                content=f"PREVIOUS CONVERSATION SUMMARY:\n{summary_text}\n\nUse this context for entity IDs and preferences mentioned earlier."
            )
            
            # Prepend sentinel + summary + recent
            return [SystemMessage(content="__REPLACE_HISTORY__"), summary_msg] + recent_messages
            
        except Exception as e:
            logger.error(f"Failed to compress messages: {e}")
            # If compression failed but history was repaired/cleaned, still return repaired list with sentinel
            return [SystemMessage(content="__REPLACE_HISTORY__")] + messages
            
    return messages
