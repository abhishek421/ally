"""
LangGraph pipeline orchestration for AI Analyst RAG
"""
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.query_optimizer import QueryOptimizerAgent


class AgentState(TypedDict):
    """State that flows between agents"""
    user_query: str
    optimized_query: str
    extracted_data: dict
    final_response: dict


class AnalystRAGPipeline:
    """Main pipeline orchestrating the three agents"""
    
    def __init__(self):
        self.graph = self._build_graph()
        self.memory = MemorySaver()
        self.query_optimizer = QueryOptimizerAgent()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph pipeline with three agents"""
        workflow = StateGraph(AgentState)
        
        # Add nodes for each agent
        workflow.add_node("query_optimizer", self._query_optimizer_node)
        workflow.add_node("data_extractor", self._data_extractor_node)
        workflow.add_node("response_formatter", self._response_formatter_node)
        
        # Define the flow: optimizer -> extractor -> formatter
        workflow.set_entry_point("query_optimizer")
        workflow.add_edge("query_optimizer", "data_extractor")
        workflow.add_edge("data_extractor", "response_formatter")
        workflow.add_edge("response_formatter", END)
        
        return workflow.compile()
    
    def _query_optimizer_node(self, state: AgentState) -> AgentState:
        """QueryOptimizerAgent: Converts user query to defined query"""
        optimized_query = self.query_optimizer.optimize(state['user_query'])
        return {"optimized_query": optimized_query}
    
    def _data_extractor_node(self, state: AgentState) -> AgentState:
        """DataExtractorAgent: Extracts data using multiple tools"""
        # TODO: Implement data extraction logic with tools
        extracted = {"data": "extracted data", "query": state['optimized_query']}
        return {"extracted_data": extracted}
    
    def _response_formatter_node(self, state: AgentState) -> AgentState:
        """ResponseFormatterAgent: Formats response in JSON format"""
        # TODO: Implement response formatting logic
        formatted = {
            "query": state['optimized_query'],
            "data": state['extracted_data'],
            "formatted_response": "JSON formatted response"
        }
        return {"final_response": formatted}
    
    def run(self, user_query: str) -> dict:
        """Run the pipeline with a user query"""
        initial_state = {
            "user_query": user_query,
            "optimized_query": "",
            "extracted_data": {},
            "final_response": {}
        }
        result = self.graph.invoke(initial_state)
        return result['final_response']


# Main entry point
def create_pipeline():
    """Factory function to create and return the pipeline"""
    return AnalystRAGPipeline()

