from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base_agent import BaseAgent, AgentState


class QueryUnderstandingAgent(BaseAgent):
    """Agent responsible for understanding user queries and determining intent"""
    
    def __init__(self, llm):
        super().__init__(llm)
        self.system_prompt = """You are a query understanding agent. Your job is to analyze user queries and determine their intent.

Your tasks:
1. Understand what the user is asking for
2. Identify the intent (e.g., "get top companies", "count people", "find specific data")
3. Extract key entities and parameters
4. Determine if schema information is needed

Respond with a clear intent description that will help other agents understand what to do.

Examples:
- "What are top 5 newly added companies?" -> Intent: "get_top_newest_companies", count: 5
- "How many people work in Engineering?" -> Intent: "count_people_by_department", department: "Engineering"
- "Show me companies in Technology industry" -> Intent: "filter_companies_by_industry", industry: "Technology"
"""

    def run(self, state: AgentState) -> AgentState:
        """Process the user query and determine intent"""
        try:
            user_query = state["user_query"]
            
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"User query: {user_query}\n\nDetermine the intent and extract key information.")
            ]
            
            response = self.llm.invoke(messages)
            intent = response.content.strip()
            
            # Update state
            state["intent"] = intent
            self._log_message(state, "assistant", f"Intent identified: {intent}")
            
            return state
            
        except Exception as e:
            self._set_error(state, f"Query understanding failed: {str(e)}")
            return state
