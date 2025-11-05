"""
LangGraph pipeline orchestration for AI Analyst
"""
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.query_optimizer import QueryOptimizerAgent


class AgentState(TypedDict):
    """State that flows between agents"""
    user_query: str
    workspace_id: str
    user_id: str
    context_messages: List[Dict[str, Any]]
    optimized_query: str
    extracted_data: dict
    final_response: dict


class AnalystPipeline:
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
        """QueryOptimizerAgent: Converts user query to defined query with context"""
        optimized_query = self.query_optimizer.optimize(
            user_query=state['user_query'],
            context_messages=state.get('context_messages', [])
        )
        return {"optimized_query": optimized_query}
    
    async def _data_extractor_node(self, state: AgentState) -> AgentState:
        """DataExtractorAgent: Extracts data using multiple tools"""
        from agents.data_extractor import DataExtractorAgent

        data_extractor = DataExtractorAgent()
        extracted = await data_extractor.extract(
            optimized_query=state['optimized_query'],
            workspace_id=state['workspace_id'],
            user_id=state['user_id']
        )
        return {"extracted_data": extracted}
    
    def _response_formatter_node(self, state: AgentState) -> AgentState:
        """ResponseFormatterAgent: Formats response in markdown format with raw data"""
        from agents.response_formatter import ResponseFormatterAgent

        response_formatter = ResponseFormatterAgent()
        formatted_response = response_formatter.format(
            optimized_query=state['optimized_query'],
            extracted_data=state['extracted_data']
        )
        return {"final_response": formatted_response}
    
    async def run(self, user_query: str, workspace_id: str, user_id: str, context_messages: List[Dict[str, Any]] = None) -> dict:
        """Run the pipeline with a user query, workspace_id, user_id, and optional context"""
        initial_state = {
            "user_query": user_query,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "context_messages": context_messages or [],
            "optimized_query": "",
            "extracted_data": {},
            "final_response": {}
        }
        result = await self.graph.ainvoke(initial_state)
        return result['final_response']


# Main entry point
def create_pipeline():
    """Factory function to create and return the pipeline"""
    return AnalystPipeline()

