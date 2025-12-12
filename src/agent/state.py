"""Agent state schema for LangGraph."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State schema for the Ally agent.
    
    This uses the add_messages annotation to properly handle message
    accumulation across conversation turns.
    """
    
    # Messages accumulate using the add_messages reducer
    messages: Annotated[list, add_messages]
    
    # Workspace context
    workspace_id: str
    
    # User context
    user_id: str
    
    # Auth token for GraphQL calls
    auth_token: str

