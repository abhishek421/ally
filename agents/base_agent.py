from typing import Dict, Any, List, Optional, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from tools.database_tools import get_database_tools
from tools.schema_tools import get_schema_tools


class AgentState(TypedDict):
    """State shared between agents"""
    messages: List[Dict[str, str]]
    user_query: str
    intent: str
    sql_query: str
    query_result: str
    final_response: str
    error: str
    tools_used: List[str]


class BaseAgent:
    """Base class for all agents"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
    
    def run(self, state: AgentState) -> AgentState:
        """Run the agent - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement run method")
    
    def _log_message(self, state: AgentState, role: str, content: str) -> None:
        """Helper method to log messages to state"""
        state["messages"].append({
            "role": role,
            "content": content
        })
    
    def _set_error(self, state: AgentState, error: str) -> None:
        """Helper method to set error in state"""
        state["error"] = error
