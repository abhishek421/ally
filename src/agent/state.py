"""Agent state schema for LangGraph."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


def limit_messages(all_messages: list, new_messages: list) -> list:
    """Reducer to add messages and limit the total history.
    
    Keeps only the last 20 messages to prevent token bloat in long conversations.
    """
    combined = add_messages(all_messages, new_messages)
    return combined[-20:]  # Keep last 20 messages


class AgentState(TypedDict):
    """State schema for the Ally agent.
    
    This uses a custom limit_messages reducer to properly handle message
    accumulation while preventing history from ballooning.
    """
    
    # Messages accumulate using the limit_messages reducer
    messages: Annotated[list, limit_messages]
    
    # Workspace context
    workspace_id: str
    
    # User context
    user_id: str
    
    # Auth token for GraphQL calls
    auth_token: str

