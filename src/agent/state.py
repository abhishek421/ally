"""Agent state schema for LangGraph."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


def limit_messages(all_messages: list, new_messages: list) -> list:
    """Reducer to add messages or replace history.
    """
    # 1. Check for replacement sentinel in new messages
    if new_messages and len(new_messages) > 0:
        for i, msg in enumerate(new_messages):
            if hasattr(msg, "content") and msg.content == "__REPLACE_HISTORY__":
                # Replace: only take what's after the sentinel
                # AND filter out any non-message crud (but allow valid dicts)
                return [m for m in new_messages[i+1:] if hasattr(m, "content") or (isinstance(m, dict) and "content" in m)]
        
    # 2. Standard addition — let add_messages handle dict-to-Message conversion.
    # Only filter out items that are neither Message objects nor valid dicts.
    def _is_message(m):
        """Return True for LangChain Message objects or dict-format messages."""
        if hasattr(m, "content"):
            return True
        if isinstance(m, dict) and "content" in m:
            return True
        return False

    clean_all = [m for m in all_messages if _is_message(m)]
    clean_new = [m for m in new_messages if _is_message(m)]

    return add_messages(clean_all, clean_new)


class AgentState(TypedDict):
    """State schema for the Ally agent.
    
    This uses a custom limit_messages reducer to properly handle message
    accumulation while preventing history from ballooning.
    """
    
    # Messages accumulate using the limit_messages reducer
    messages: Annotated[list, limit_messages]
    
    # Required by create_react_agent
    remaining_steps: int
    
    # Workspace context
    workspace_id: str
    
    # User context
    user_id: str
    
    # Auth token for GraphQL calls
    auth_token: str

