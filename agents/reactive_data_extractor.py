"""
ReActiveDataExtractor - Reactive data extraction using ReAct pattern

This agent implements the Think-Act-Observe-Reflect loop for dynamic,
adaptive tool execution.

Flow:
1. INITIALIZE - Set goals and success criteria
2. LOOP (max 5 iterations):
   - THINK: Decide next action
   - ACT: Execute tool
   - OBSERVE: Analyze result
   - REFLECT: Assess progress
3. RETURN - Final results with reasoning traces
"""
import logging
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from adapters.llm_provider import LLMProvider
from tools.tool_factory import ToolFactory
from tools.base_tool import QueryType, ToolResult

from agents.models import (
    ExecutionState,
    ReasoningTrace,
    Observation,
    Reflection,
    ToolSpec,
    ToolCall,
    DecisionType,
    ExtractionResult
)
from agents.utils import (
    count_results,
    summarize_tool_result,
    summarize_collected_data,
    format_observations_for_prompt
)
from prompts.reactive_execution_prompts import (
    INITIAL_PLANNING_PROMPT,
    THINK_PROMPT,
    OBSERVE_PROMPT,
    REFLECT_PROMPT
)


class ReActiveDataExtractor:
    """
    Reactive data extractor using ReAct (Reasoning + Acting) pattern

    Key Differences from Static DataExtractor:
    1. Plans ONE step at a time (not all upfront)
    2. Observes results before next decision
    3. Can refine strategy based on observations
    4. Maintains reasoning traces
    5. Has early stopping when sufficient
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize ReActiveDataExtractor

        Args:
            llm_provider: LLM provider instance (optional)
        """
        self._logger = logging.getLogger(__name__)

        # Set LLM provider
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from adapters.provider_factory import LLMProviderFactory
            from config.settings import DATA_EXTRACTOR_CONFIG
            self.llm_provider = LLMProviderFactory.create(DATA_EXTRACTOR_CONFIG)

        self._logger.debug("ReActiveDataExtractor initialized")

    async def extract(
        self,
        optimized_query: str,
        workspace_id: str,
        user_id: str,
        refinement_feedback: Optional[Dict] = None,
        max_iterations: int = 5
    ) -> ExtractionResult:
        """
        Main entry point - reactive extraction loop

        Args:
            optimized_query: Optimized query from QueryOptimizer
            workspace_id: Workspace identifier
            user_id: User identifier
            refinement_feedback: Optional feedback from validator for refinement
            max_iterations: Maximum iterations (default: 5)

        Returns:
            ExtractionResult with data and metadata
        """
        self._logger.info("Starting reactive data extraction")
        self._logger.debug(f"Query: {optimized_query}")
        self._logger.debug(f"Max iterations: {max_iterations}")

        start_time = time.time()

        try:
            # Phase 1: Strategic Planning
            state = await self._initialize_state(
                optimized_query,
                workspace_id,
                user_id,
                refinement_feedback,
                max_iterations
            )
            self._logger.info(f"Initialized state: intent={state.original_intent}")

            # Phase 2: Reactive Execution Loop
            while state.should_continue and state.iteration < state.max_iterations:
                self._logger.info(f"=== Iteration {state.iteration + 1}/{state.max_iterations} ===")

                # THINK: Decide next action
                thought = await self._think(state)
                state.reasoning_traces.append(thought)
                self._logger.info(f"THINK: {thought.decision} (confidence: {thought.confidence:.2f})")

                if thought.decision == DecisionType.SUFFICIENT:
                    self._logger.info("SUFFICIENT - Have enough data, stopping")
                    break

                elif thought.decision == DecisionType.EXECUTE_TOOL:
                    if not thought.tool_spec:
                        self._logger.error("EXECUTE_TOOL decision but no tool_spec provided")
                        break

                    # ACT: Execute the tool
                    self._logger.info(f"ACT: Executing {thought.tool_spec.tool}")
                    tool_call = await self._act(thought.tool_spec, state)
                    state.tool_calls.append(tool_call)

                    # OBSERVE: Analyze the result
                    self._logger.info(f"OBSERVE: Analyzing result")
                    observation = await self._observe(tool_call, state)
                    state.observations.append(observation)
                    self._logger.info(
                        f"Observed: {observation.result_count} results, "
                        f"confidence={observation.confidence_score:.2f}"
                    )

                    # Update collected data
                    self._update_collected_data(state, tool_call, observation)

                    # REFLECT: Should we continue?
                    self._logger.info(f"REFLECT: Assessing progress")
                    reflection = await self._reflect(state)
                    state.should_continue = reflection.should_continue
                    self._logger.info(
                        f"Progress: {reflection.progress_assessment}, "
                        f"continue={reflection.should_continue}"
                    )

                elif thought.decision == DecisionType.CLARIFY:
                    self._logger.info(f"CLARIFY - Need user input: {thought.clarification_question}")
                    # Return early with clarification request
                    return self._create_clarification_result(state, thought)

                state.iteration += 1

            # Phase 3: Create final result
            elapsed_ms = int((time.time() - start_time) * 1000)
            self._logger.info(
                f"Extraction complete: {state.iteration} iterations, {elapsed_ms}ms"
            )

            return self._create_extraction_result(state, elapsed_ms)

        except Exception as e:
            self._logger.exception(f"Error in reactive extraction: {e}")
            # Return error result
            return ExtractionResult(
                data={"_error": str(e)},
                reasoning_traces=[],
                observations=[],
                confidence_scores={},
                total_iterations=0,
                final_confidence=0.0,
                success=False,
                metadata={"error": str(e)}
            )

    async def _initialize_state(
        self,
        optimized_query: str,
        workspace_id: str,
        user_id: str,
        refinement_feedback: Optional[Dict],
        max_iterations: int
    ) -> ExecutionState:
        """
        Phase 1: Strategic Planning

        - Parse optimized query
        - Determine success criteria
        - Set initial strategy

        Args:
            optimized_query: Optimized query
            workspace_id: Workspace ID
            user_id: User ID
            refinement_feedback: Optional refinement feedback
            max_iterations: Max iterations

        Returns:
            Initialized ExecutionState
        """
        self._logger.debug("Initializing execution state")

        # Format prompt
        prompt = INITIAL_PLANNING_PROMPT.format(
            optimized_query=optimized_query
        )

        # Call LLM for strategic planning
        messages = [
            {
                "role": "system",
                "content": "You are a strategic planner for data extraction. Analyze queries and set success criteria."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        try:
            llm_response = self.llm_provider.chat(messages, temperature=0.2)
            json_text = self._extract_json_from_response(llm_response)
            plan = json.loads(json_text)

            self._logger.debug(f"Strategic plan: {plan}")

        except (json.JSONDecodeError, Exception) as e:
            self._logger.warning(f"Failed to parse strategic plan: {e}, using defaults")
            # Fallback to basic plan
            plan = {
                "intent": "search",
                "primary_entity": "unknown",
                "entities_mentioned": [],
                "success_criteria": {
                    "min_results": 1,
                    "required_fields": [],
                    "answer_type": "list"
                },
                "initial_strategy": "Execute basic search",
                "potential_challenges": [],
                "expected_tools": []
            }

        # Create execution state
        state = ExecutionState(
            query=optimized_query,
            workspace_id=workspace_id,
            user_id=user_id,
            success_criteria=plan.get("success_criteria", {}),
            original_intent=plan.get("intent", "search"),
            max_iterations=max_iterations,
            refinement_feedback=refinement_feedback
        )

        return state

    async def _think(self, state: ExecutionState) -> ReasoningTrace:
        """
        THINK phase: Decide next action based on current state

        Key Decision Points:
        1. Do I have sufficient data?
        2. What tool should I use next?
        3. What parameters should I use?
        4. Should I refine my search?

        Args:
            state: Current execution state

        Returns:
            ReasoningTrace with decision
        """
        # Prepare context for LLM
        recent_observations = format_observations_for_prompt(
            state.observations[-3:] if len(state.observations) > 3 else state.observations
        )

        recent_reasoning = json.dumps(
            [
                {
                    "iteration": t.iteration,
                    "decision": t.decision,
                    "reasoning": t.reasoning[:100]  # Truncate
                }
                for t in state.reasoning_traces[-2:]
            ],
            indent=2
        ) if state.reasoning_traces else "None yet"

        tools_executed = [tc.tool_name for tc in state.tool_calls]
        data_summary = summarize_collected_data(state.collected_data)

        # Add refinement feedback if present
        refinement_context = ""
        if state.refinement_feedback:
            refinement_context = f"""
REFINEMENT FEEDBACK (from previous attempt):
Issues: {json.dumps(state.refinement_feedback.get('issues', []), indent=2)}
Recommendations: {json.dumps(state.refinement_feedback.get('recommendations', []), indent=2)}
"""

        # Format prompt
        prompt = THINK_PROMPT.format(
            query=state.query,
            success_criteria=json.dumps(state.success_criteria, indent=2),
            iteration=state.iteration,
            max_iterations=state.max_iterations,
            collected_data_keys=list(state.collected_data.keys()),
            confidence_scores=json.dumps(state.confidence_scores, indent=2),
            recent_observations=recent_observations,
            recent_reasoning=recent_reasoning,
            tools_executed=tools_executed,
            data_summary=data_summary,
            refinement_feedback=refinement_context
        )

        # Call LLM
        messages = [
            {
                "role": "system",
                "content": "You are a tactical decision maker. Decide the next action based on current state."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        try:
            llm_response = self.llm_provider.chat(messages, temperature=0.2)
            json_text = self._extract_json_from_response(llm_response)
            decision_data = json.loads(json_text)

            # Parse decision
            decision_type = DecisionType(decision_data["decision"])

            # Create tool spec if needed
            tool_spec = None
            if decision_type == DecisionType.EXECUTE_TOOL and "tool_spec" in decision_data:
                tool_spec_data = decision_data["tool_spec"]
                tool_spec = ToolSpec(
                    tool=tool_spec_data["tool"],
                    query_type=tool_spec_data["query_type"],
                    params=tool_spec_data.get("params", {}),
                    expected_outcome=tool_spec_data.get("expected_outcome", ""),
                    fallback_plan=tool_spec_data.get("fallback_plan")
                )

            reasoning_trace = ReasoningTrace(
                iteration=state.iteration,
                decision=decision_type,
                reasoning=decision_data.get("reasoning", "No reasoning provided"),
                confidence=decision_data.get("confidence", 0.5),
                tool_spec=tool_spec,
                clarification_question=decision_data.get("clarification_question"),
                clarification_reason=decision_data.get("clarification_reason")
            )

            return reasoning_trace

        except (json.JSONDecodeError, KeyError, Exception) as e:
            self._logger.error(f"Failed to parse THINK response: {e}")
            # Fallback: try to execute a basic tool or stop
            if state.iteration == 0:
                # First iteration - execute a basic search
                return ReasoningTrace(
                    iteration=state.iteration,
                    decision=DecisionType.EXECUTE_TOOL,
                    reasoning="Fallback: Execute basic search on first iteration",
                    confidence=0.3,
                    tool_spec=ToolSpec(
                        tool="company",
                        query_type="list",
                        params={"limit": 10},
                        expected_outcome="Get some initial data"
                    )
                )
            else:
                # Later iterations - just stop
                return ReasoningTrace(
                    iteration=state.iteration,
                    decision=DecisionType.SUFFICIENT,
                    reasoning="Fallback: Stopping due to parsing error",
                    confidence=0.3
                )

    async def _act(self, tool_spec: ToolSpec, state: ExecutionState) -> ToolCall:
        """
        ACT phase: Execute the tool

        Args:
            tool_spec: Tool specification
            state: Current execution state

        Returns:
            ToolCall with result
        """
        start_time = time.time()

        try:
            # Resolve parameters from previous results
            resolved_params = self._resolve_parameters_from_state(
                tool_spec.params,
                state
            )

            self._logger.debug(
                f"Executing {tool_spec.tool}.{tool_spec.query_type} "
                f"with params: {resolved_params}"
            )

            # Create tool instance
            tool = ToolFactory.create_tool(
                tool_spec.tool,
                state.workspace_id,
                state.user_id
            )

            # Execute tool
            query_type = QueryType(tool_spec.query_type.lower())
            result = await tool.execute(query_type, **resolved_params)

            execution_time = int((time.time() - start_time) * 1000)
            self._logger.debug(
                f"Tool execution completed in {execution_time}ms, "
                f"success={result.success}"
            )

            return ToolCall(
                tool_name=tool_spec.tool,
                query_type=tool_spec.query_type,
                params=resolved_params,
                result=result,
                expected_outcome=tool_spec.expected_outcome
            )

        except Exception as e:
            self._logger.error(f"Error executing tool {tool_spec.tool}: {e}")
            # Return failed tool call
            return ToolCall(
                tool_name=tool_spec.tool,
                query_type=tool_spec.query_type,
                params=tool_spec.params,
                result=ToolResult(
                    success=False,
                    error=str(e),
                    execution_time_ms=int((time.time() - start_time) * 1000)
                ),
                expected_outcome=tool_spec.expected_outcome
            )

    def _resolve_parameters_from_state(
        self,
        params: Dict[str, Any],
        state: ExecutionState
    ) -> Dict[str, Any]:
        """
        Resolve parameter placeholders from previous tool results

        Placeholder format: <field_name_from_previous_call>

        Args:
            params: Parameters that may contain placeholders
            state: Current execution state

        Returns:
            Resolved parameters
        """
        resolved = {}

        for key, value in params.items():
            # Check if value is a placeholder
            if isinstance(value, str) and value.startswith('<') and value.endswith('>'):
                placeholder = value[1:-1]  # Remove < >

                # Extract value from previous results
                extracted_value = self._extract_value_from_state(placeholder, state)

                if extracted_value is not None:
                    resolved[key] = extracted_value
                    self._logger.debug(
                        f"Resolved placeholder '{value}' -> '{extracted_value}'"
                    )
                else:
                    self._logger.warning(
                        f"Could not resolve placeholder '{value}', skipping parameter"
                    )
                    # Don't include unresolved parameters
                    continue
            else:
                resolved[key] = value

        return resolved

    def _extract_value_from_state(
        self,
        placeholder: str,
        state: ExecutionState
    ) -> Optional[str]:
        """
        Extract value from previous tool results based on placeholder

        Args:
            placeholder: Placeholder string (without < >)
            state: Current execution state

        Returns:
            Extracted value or None
        """
        import re

        # Parse placeholder to extract field name
        match = re.match(r'^(.+?)_from_previous_call$', placeholder)
        if match:
            field_name = match.group(1)
        else:
            field_name = placeholder

        # Search through collected data
        for key, value in state.collected_data.items():
            if key.startswith('_'):
                continue

            # Check if it's a list of items
            if isinstance(value, list) and len(value) > 0:
                first_item = value[0]
                if isinstance(first_item, dict):
                    if field_name in first_item:
                        return str(first_item[field_name])
                    elif 'id' in first_item and field_name.endswith('_id'):
                        return str(first_item['id'])

            # Check if it's a single dict
            elif isinstance(value, dict):
                if field_name in value:
                    return str(value[field_name])

        return None

    async def _observe(self, tool_call: ToolCall, state: ExecutionState) -> Observation:
        """
        OBSERVE phase: Analyze what we learned from tool execution

        Args:
            tool_call: Tool call that was executed
            state: Current execution state

        Returns:
            Observation with learnings
        """
        result = tool_call.result

        # Basic observation from result
        observation = Observation(
            tool=tool_call.tool_name,
            success=result.success,
            result_count=count_results(result) if result.success else 0,
            confidence_score=self._score_tool_result(result)
        )

        # If tool failed, return early
        if not result.success:
            observation.data_quality_issues.append(f"Tool failed: {result.error}")
            return observation

        # If no results, return early
        if observation.result_count == 0:
            observation.still_missing.append(f"No {tool_call.tool_name} data found")
            return observation

        # LLM-based observation for successful results
        try:
            result_summary = summarize_tool_result(result, max_items=3)

            prompt = OBSERVE_PROMPT.format(
                query=state.query,
                expected_outcome=tool_call.expected_outcome or "Get data",
                tool_name=tool_call.tool_name,
                query_type=tool_call.query_type,
                params=json.dumps(tool_call.params, default=str),
                result_summary=result_summary
            )

            messages = [
                {
                    "role": "system",
                    "content": "You are analyzing tool execution results. Extract key learnings."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            llm_response = self.llm_provider.chat(messages, temperature=0.1)
            json_text = self._extract_json_from_response(llm_response)
            llm_observation = json.loads(json_text)

            # Update observation with LLM insights
            observation.learned = llm_observation.get("learned", [])
            observation.relevance = llm_observation.get("relevance_to_query", 0.5)
            observation.still_missing = llm_observation.get("still_missing", [])
            observation.new_questions = llm_observation.get("new_questions", [])
            observation.data_quality_issues.extend(
                llm_observation.get("data_quality_issues", [])
            )

        except (json.JSONDecodeError, Exception) as e:
            self._logger.warning(f"Failed to get LLM observation: {e}")
            # Basic observation is already set

        return observation

    def _score_tool_result(self, result: ToolResult) -> float:
        """
        Score confidence in tool result

        Args:
            result: ToolResult object

        Returns:
            Confidence score 0.0-1.0
        """
        if not result.success:
            return 0.1

        if not result.data:
            return 0.2

        count = count_results(result)
        if count == 0:
            return 0.3
        elif count > 100:
            return 0.7
        elif count > 50:
            return 0.85
        else:
            return 0.9

    def _update_collected_data(
        self,
        state: ExecutionState,
        tool_call: ToolCall,
        observation: Observation
    ):
        """
        Update collected data from tool result

        Args:
            state: Execution state to update
            tool_call: Tool call that was executed
            observation: Observation from the call
        """
        if not tool_call.result or not tool_call.result.success:
            return

        # Update confidence scores
        state.confidence_scores[tool_call.tool_name] = observation.confidence_score

        # Extract data from result
        data = tool_call.result.data
        if not data:
            return

        # Add to collected data based on tool type
        tool_name = tool_call.tool_name
        if isinstance(data, dict):
            # Check for common data keys
            for key in ['companies', 'people', 'emails', 'interactions', 'groups']:
                if key in data and isinstance(data[key], list):
                    if key not in state.collected_data:
                        state.collected_data[key] = []
                    state.collected_data[key].extend(data[key])

            # Single entity result
            if 'id' in data and tool_name not in ['workspace']:
                key = tool_name if tool_name.endswith('s') else f"{tool_name}s"
                if key not in state.collected_data:
                    state.collected_data[key] = []
                state.collected_data[key].append(data)

    async def _reflect(self, state: ExecutionState) -> Reflection:
        """
        REFLECT phase: Should we continue execution?

        Args:
            state: Current execution state

        Returns:
            Reflection with continue decision
        """
        recent_observations = format_observations_for_prompt(
            state.observations[-2:] if len(state.observations) > 2 else state.observations
        )

        prompt = REFLECT_PROMPT.format(
            query=state.query,
            success_criteria=json.dumps(state.success_criteria, indent=2),
            iteration=state.iteration,
            max_iterations=state.max_iterations,
            tool_count=len(state.tool_calls),
            data_keys=list(state.collected_data.keys()),
            recent_observations=recent_observations,
            confidence_scores=json.dumps(state.confidence_scores, indent=2)
        )

        messages = [
            {
                "role": "system",
                "content": "You are reflecting on progress. Decide if we should continue or stop."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        try:
            llm_response = self.llm_provider.chat(messages, temperature=0.1)
            json_text = self._extract_json_from_response(llm_response)
            reflection_data = json.loads(json_text)

            return Reflection(
                should_continue=reflection_data.get("should_continue", False),
                reason=reflection_data.get("reason", "No reason provided"),
                progress_assessment=reflection_data.get("progress_assessment", "ok"),
                recommendations=reflection_data.get("next_recommendations", [])
            )

        except (json.JSONDecodeError, Exception) as e:
            self._logger.warning(f"Failed to parse REFLECT response: {e}")
            # Fallback: continue if not at max iterations
            return Reflection(
                should_continue=(state.iteration + 1) < state.max_iterations,
                reason="Fallback: Continue until max iterations",
                progress_assessment="ok",
                recommendations=[]
            )

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response"""
        response = response.strip()

        if response.startswith("```"):
            start_idx = response.find("\n") + 1
            end_idx = response.rfind("```")
            if end_idx > start_idx:
                response = response[start_idx:end_idx].strip()

        if not response.startswith("{"):
            start_idx = response.find("{")
            if start_idx >= 0:
                response = response[start_idx:]

        return response

    def _create_clarification_result(
        self,
        state: ExecutionState,
        thought: ReasoningTrace
    ) -> ExtractionResult:
        """
        Create result requesting user clarification

        Args:
            state: Current execution state
            thought: Reasoning trace with clarification request

        Returns:
            ExtractionResult with clarification request
        """
        return ExtractionResult(
            data=state.collected_data,
            reasoning_traces=state.reasoning_traces,
            observations=state.observations,
            confidence_scores=state.confidence_scores,
            total_iterations=state.iteration,
            final_confidence=0.0,
            success=False,
            needs_clarification=True,
            clarification_question=thought.clarification_question,
            metadata={
                "reason": "needs_clarification",
                "clarification_reason": thought.clarification_reason
            }
        )

    def _create_extraction_result(
        self,
        state: ExecutionState,
        elapsed_ms: int
    ) -> ExtractionResult:
        """
        Create final extraction result

        Args:
            state: Final execution state
            elapsed_ms: Total execution time

        Returns:
            ExtractionResult with all data and metadata
        """
        # Calculate final confidence
        if state.confidence_scores:
            final_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
        else:
            final_confidence = 0.0

        # Check if successful
        has_data = bool(state.collected_data and any(
            len(v) > 0 if isinstance(v, list) else v is not None
            for k, v in state.collected_data.items()
            if not k.startswith('_')
        ))

        return ExtractionResult(
            data=state.collected_data,
            reasoning_traces=state.reasoning_traces,
            observations=state.observations,
            confidence_scores=state.confidence_scores,
            total_iterations=state.iteration,
            final_confidence=final_confidence,
            success=has_data,
            needs_clarification=False,
            metadata={
                "execution_time_ms": elapsed_ms,
                "tools_executed": len(state.tool_calls),
                "max_iterations_reached": state.iteration >= state.max_iterations
            }
        )
