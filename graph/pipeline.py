"""
LangGraph pipeline orchestration for AI Analyst
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.query_optimizer import QueryOptimizerAgent
from agents.models import NextAction


class AgentState(TypedDict):
    """State that flows between agents"""
    user_query: str
    workspace_id: str
    user_id: str
    context_messages: List[Dict[str, Any]]
    optimized_query: str
    extracted_data: dict
    validation_result: Optional[dict]
    retry_count: int
    needs_clarification: bool
    clarification_question: Optional[str]
    final_response: dict


class AnalystPipeline:
    """Main pipeline orchestrating agents with validation loop"""

    MAX_RETRIES = 2  # Maximum refinement attempts

    def __init__(self, enable_reactive: bool = True, enable_orchestrator: bool = False):
        """
        Initialize pipeline

        Args:
            enable_reactive: Use ReActiveDataExtractor (True) or legacy DataExtractor (False)
            enable_orchestrator: Use OrchestratorAgent for intelligent coordination (default: False)
        """
        self.enable_reactive = enable_reactive
        self.enable_orchestrator = enable_orchestrator

        if enable_orchestrator:
            # New orchestrator-based pipeline
            from agents.orchestrator import OrchestratorAgent
            self.orchestrator = OrchestratorAgent()
        else:
            # Legacy graph-based pipeline
            self.graph = self._build_graph()
            self.memory = MemorySaver()
            self.query_optimizer = QueryOptimizerAgent()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph pipeline with validation loop"""
        workflow = StateGraph(AgentState)

        # Add nodes for each agent
        workflow.add_node("query_optimizer", self._query_optimizer_node)
        workflow.add_node("data_extractor", self._data_extractor_node)
        workflow.add_node("result_validator", self._result_validator_node)
        workflow.add_node("response_formatter", self._response_formatter_node)

        # Define the flow with conditional routing
        workflow.set_entry_point("query_optimizer")
        workflow.add_edge("query_optimizer", "data_extractor")

        # After data extraction, always validate
        workflow.add_edge("data_extractor", "result_validator")

        # Conditional routing from validator
        workflow.add_conditional_edges(
            "result_validator",
            self._route_from_validator,
            {
                "complete": "response_formatter",
                "refine": "data_extractor",
                "clarify": END
            }
        )

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
        """DataExtractorAgent: Extracts data using tools (reactive or legacy)"""
        if self.enable_reactive:
            # Use new ReActiveDataExtractor with Think-Act-Observe-Reflect loop
            from agents.reactive_data_extractor import ReActiveDataExtractor

            extractor = ReActiveDataExtractor()

            # Get refinement feedback from previous validation (if any)
            refinement_feedback = None
            if state.get('validation_result'):
                validation = state['validation_result']
                refinement_feedback = {
                    "issues": validation.get('heuristic_issues', []),
                    "recommendations": validation.get('recommendations', []),
                    "semantic_analysis": validation.get('semantic_analysis'),
                    "confidence_score": validation.get('confidence_score', 0.0)
                }

            result = await extractor.extract(
                optimized_query=state['optimized_query'],
                workspace_id=state['workspace_id'],
                user_id=state['user_id'],
                refinement_feedback=refinement_feedback,
                context_messages=state.get('context_messages', [])
            )

            # Convert ExtractionResult to dict
            extracted_data = result.data
            extracted_data['_reasoning_traces'] = [
                trace.dict() for trace in result.reasoning_traces
            ]
            extracted_data['_observations'] = [
                obs.dict() for obs in result.observations
            ]
            extracted_data['_confidence_scores'] = result.confidence_scores
            extracted_data['_final_confidence'] = result.final_confidence
            extracted_data['_total_iterations'] = result.total_iterations
            extracted_data['_metadata'] = result.metadata

            # Check if clarification is needed
            if result.needs_clarification:
                return {
                    "extracted_data": extracted_data,
                    "needs_clarification": True,
                    "clarification_question": result.clarification_question
                }

            return {"extracted_data": extracted_data}

        else:
            # Use legacy DataExtractorAgent
            from agents.data_extractor import DataExtractorAgent

            data_extractor = DataExtractorAgent()
            extracted = await data_extractor.extract(
                optimized_query=state['optimized_query'],
                workspace_id=state['workspace_id'],
                user_id=state['user_id'],
                context_messages=state.get('context_messages', [])
            )
            return {"extracted_data": extracted}
    
    async def _result_validator_node(self, state: AgentState) -> AgentState:
        """ResultValidator: Validates extraction results and determines next action"""
        from agents.result_validator import ResultValidator

        # Skip validation if clarification is already needed
        if state.get('needs_clarification', False):
            return {
                "validation_result": {
                    "is_sufficient": False,
                    "confidence_score": 0.0,
                    "next_action": "clarify"
                }
            }

        validator = ResultValidator()

        # Extract reasoning traces for validation
        reasoning_traces = None
        extracted_data = state['extracted_data']
        if '_reasoning_traces' in extracted_data:
            reasoning_traces = extracted_data['_reasoning_traces']

        # Run validation
        validation_result = await validator.validate(
            original_query=state['user_query'],
            optimized_query=state['optimized_query'],
            extracted_data=extracted_data,
            reasoning_traces=reasoning_traces,
            enable_semantic=self.enable_reactive  # Only semantic validation in reactive mode
        )

        # Convert ValidationResult to dict
        validation_dict = {
            "is_sufficient": validation_result.is_sufficient,
            "confidence_score": validation_result.confidence_score,
            "heuristic_issues": [issue.dict() for issue in validation_result.heuristic_issues],
            "semantic_analysis": validation_result.semantic_analysis.dict() if validation_result.semantic_analysis else None,
            "recommendations": validation_result.recommendations,
            "next_action": validation_result.next_action if isinstance(validation_result.next_action, str) else validation_result.next_action.value,
            "metadata": validation_result.metadata
        }

        return {"validation_result": validation_dict}

    def _route_from_validator(self, state: AgentState) -> str:
        """
        Route based on validation result

        Returns:
            "complete": Proceed to response formatting
            "refine": Retry data extraction with feedback
            "clarify": End pipeline, needs user clarification
        """
        validation = state.get('validation_result', {})
        next_action = validation.get('next_action', 'complete')

        # If clarification is needed, end immediately
        if state.get('needs_clarification', False) or next_action == NextAction.CLARIFY.value:
            return "clarify"

        # Check retry limit
        retry_count = state.get('retry_count', 0)
        if retry_count >= self.MAX_RETRIES:
            # Max retries reached, accept what we have
            return "complete"

        # If validation suggests refinement and we haven't hit retry limit
        if next_action == NextAction.REFINE.value:
            # Increment retry count
            state['retry_count'] = retry_count + 1
            return "refine"

        # Default: complete and format response
        return "complete"

    def _response_formatter_node(self, state: AgentState) -> AgentState:
        """ResponseFormatterAgent: Formats response in markdown format with raw data"""
        from agents.response_formatter import ResponseFormatterAgent

        response_formatter = ResponseFormatterAgent()
        formatted_response = response_formatter.format(
            optimized_query=state['optimized_query'],
            extracted_data=state['extracted_data']
        )

        # Add validation metadata to response
        if state.get('validation_result'):
            validation = state['validation_result']
            formatted_response['_validation'] = {
                "confidence_score": validation.get('confidence_score'),
                "is_sufficient": validation.get('is_sufficient'),
                "retry_count": state.get('retry_count', 0)
            }

        return {"final_response": formatted_response}
    
    async def run(self, user_query: str, workspace_id: str, user_id: str, context_messages: List[Dict[str, Any]] = None) -> dict:
        """
        Run the pipeline with a user query, workspace_id, user_id, and optional context

        Returns:
            dict: Final response or clarification request
        """
        if self.enable_orchestrator:
            # Use orchestrator-based pipeline
            result = await self.orchestrator.orchestrate(
                user_query=user_query,
                workspace_id=workspace_id,
                user_id=user_id,
                context_messages=context_messages
            )

            # Convert OrchestrationResult to dict for compatibility
            return self._convert_orchestration_result(result)

        else:
            # Use legacy graph-based pipeline
            initial_state = {
                "user_query": user_query,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "context_messages": context_messages or [],
                "optimized_query": "",
                "extracted_data": {},
                "validation_result": None,
                "retry_count": 0,
                "needs_clarification": False,
                "clarification_question": None,
                "final_response": {}
            }

            result = await self.graph.ainvoke(initial_state)

            # Check if clarification is needed
            if result.get('needs_clarification', False):
                return {
                    "status": "needs_clarification",
                    "clarification_question": result.get('clarification_question'),
                    "partial_data": result.get('extracted_data', {}),
                    "validation": result.get('validation_result')
                }

            return result['final_response']

    def _convert_orchestration_result(self, result) -> dict:
        """
        Convert OrchestrationResult to dict format compatible with API

        Args:
            result: OrchestrationResult from orchestrator

        Returns:
            Dict compatible with existing API format
        """
        # Check for clarification
        if result.needs_clarification:
            return {
                "status": "needs_clarification",
                "clarification_question": result.clarification_question,
                "partial_data": result.data,
                "metadata": {
                    "orchestration": {
                        "query_analysis": result.query_analysis.dict(),
                        "execution_plan": result.execution_plan.dict(),
                        "agents_executed": [agent.dict() for agent in result.agents_executed],
                        "total_time_ms": result.total_time_ms
                    }
                }
            }

        # Success case
        response = result.data.copy() if isinstance(result.data, dict) else {"data": result.data}

        # Add orchestration metadata
        response["_orchestration"] = {
            "query_analysis": result.query_analysis.dict(),
            "execution_plan": {
                "strategy": result.execution_plan.extractor_strategy.value,
                "validation_level": result.execution_plan.validation_level.value,
                "reasoning": result.execution_plan.reasoning
            },
            "agents_executed": [
                {
                    "name": agent.agent_name,
                    "duration_ms": agent.duration_ms,
                    "success": agent.success
                }
                for agent in result.agents_executed
            ],
            "total_time_ms": result.total_time_ms,
            "confidence_score": result.confidence_score,
            "retry_count": result.retry_count
        }

        return response


# Main entry point
def create_pipeline(enable_reactive: bool = True, enable_orchestrator: bool = True):
    """
    Factory function to create and return the pipeline

    Args:
        enable_reactive: Use ReActiveDataExtractor (True) or legacy DataExtractor (False)
        enable_orchestrator: Use OrchestratorAgent for intelligent coordination (default: True)

    Returns:
        AnalystPipeline instance

    Note:
        When enable_orchestrator=True (default):
        - Orchestrator analyzes query complexity before execution
        - Routes meta queries for instant responses
        - Automatically selects best extractor (static vs reactive)
        - Conditionally runs optimization and validation
        - Provides detailed execution metadata
        - Breaks the sequential pipeline for optimal performance
    """
    return AnalystPipeline(enable_reactive=enable_reactive, enable_orchestrator=enable_orchestrator)

