from typing import Dict, Any, List, Optional, TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import os

from agents.base_agent import AgentState
from agents.query_agent import QueryUnderstandingAgent
from agents.sql_agent import SQLGeneratorAgent
from agents.executor_agent import DatabaseExecutorAgent
from agents.formatter_agent import ResponseFormatterAgent


class MultiAgentChatbot:
    """Main chatbot class that orchestrates the multi-agent system"""
    
openai_api_key="REDACTED"
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
openai_api_key="REDACTED"
            temperature=0.1
        )
        
        # Initialize agents
        self.query_agent = QueryUnderstandingAgent(self.llm)
        self.sql_agent = SQLGeneratorAgent(self.llm)
        self.executor_agent = DatabaseExecutorAgent()
        self.formatter_agent = ResponseFormatterAgent(self.llm)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("query_understanding", self.query_agent.run)
        workflow.add_node("sql_generation", self.sql_agent.run)
        workflow.add_node("query_execution", self.executor_agent.run)
        workflow.add_node("response_formatting", self.formatter_agent.run)
        
        # Define the flow
        workflow.set_entry_point("query_understanding")
        workflow.add_edge("query_understanding", "sql_generation")
        workflow.add_edge("sql_generation", "query_execution")
        workflow.add_edge("query_execution", "response_formatting")
        workflow.add_edge("response_formatting", END)
        
        return workflow.compile()
    
    def chat(self, user_query: str) -> str:
        """Process a user query through the multi-agent system"""
        try:
            # Initialize state
            initial_state = AgentState(
                messages=[],
                user_query=user_query,
                intent="",
                sql_query="",
                query_result="",
                final_response="",
                error="",
                tools_used=[]
            )
            
            # Run the workflow
            result = self.graph.invoke(initial_state)
            
            # Check for errors
            if result["error"]:
                return f"I encountered an error: {result['error']}"
            
            return result["final_response"]
            
        except Exception as e:
            return f"I encountered an error processing your query: {str(e)}"
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the conversation history"""
        return []


def create_chatbot() -> MultiAgentChatbot:
    """Create a new chatbot instance"""
OPENAI_API_KEY=REDACTED
openai_api_key="REDACTED"
OPENAI_API_KEY=REDACTED
    
openai_api_key="REDACTED"
