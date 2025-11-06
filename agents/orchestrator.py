"""
OrchestratorAgent - Central decision-making agent that coordinates all other agents

This agent is responsible for:
1. Analyzing query complexity and intent
2. Deciding execution strategy (which agents, validation level, retries)
3. Coordinating agent execution
4. Evaluating results and determining next actions

Architecture:
    User Query
        ↓
    ORCHESTRATOR
        ↓
    ├─ Phase 1: ANALYZE → Query complexity, intent, clarity
    ├─ Phase 2: PLAN → Decide which agents and strategy
    ├─ Phase 3: COORDINATE → Execute agents with adaptive retry
    └─ Phase 4: CONTROL → Evaluate results, accept/refine/clarify
"""
import logging
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from adapters.llm_provider import LLMProvider
from agents.models import (
    QueryComplexity,
    QueryIntent,
    ExtractorStrategy,
    ValidationLevel,
    QueryAnalysis,
    ExecutionPlan,
    AgentExecution,
    OrchestrationResult,
    NextAction
)


class OrchestratorAgent:
    """
    Central orchestrator that intelligently coordinates all agents

    Key Features:
    - Analyzes query complexity before execution
    - Selects optimal extractor (static vs reactive)
    - Skips unnecessary steps (optimization, validation)
    - Adaptive retry with feedback
    - Cost and latency optimization
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize OrchestratorAgent

        Args:
            llm_provider: LLM provider for analysis and planning (optional)
        """
        self._logger = logging.getLogger(__name__)

        # Set LLM provider
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from adapters.provider_factory import LLMProviderFactory
            from config.settings import DATA_EXTRACTOR_CONFIG
            self.llm_provider = LLMProviderFactory.create(DATA_EXTRACTOR_CONFIG)

        # Lazy-loaded agents (created on first use)
        self._query_optimizer = None
        self._static_extractor = None
        self._reactive_extractor = None
        self._validator = None
        self._formatter = None

        # Strategy statistics (for learning)
        self.strategy_stats = {
            "static": {"success": 0, "total": 0, "avg_time_ms": 0},
            "reactive": {"success": 0, "total": 0, "avg_time_ms": 0}
        }

        self._logger.debug("OrchestratorAgent initialized")

    async def orchestrate(
        self,
        user_query: str,
        workspace_id: str,
        user_id: str,
        context_messages: Optional[List[Dict]] = None
    ) -> OrchestrationResult:
        """
        Main entry point - orchestrates entire query execution

        Flow:
        0. PRE-ROUTE: Fast-path for meta queries (help, greetings)
        1. ANALYZE: Assess query complexity, intent, clarity
        2. PLAN: Create execution strategy
        3. COORDINATE: Execute agents with adaptive retry
        4. CONTROL: Evaluate and finalize results

        Args:
            user_query: Raw user query
            workspace_id: Workspace identifier
            user_id: User identifier
            context_messages: Optional conversation context

        Returns:
            OrchestrationResult with data and execution metadata
        """
        self._logger.info("=" * 60)
        self._logger.info("ORCHESTRATOR: Starting orchestration")
        self._logger.info(f"Query: {user_query}")
        self._logger.info("=" * 60)

        start_time = time.time()
        agents_executed = []

        try:
            # Phase 0: PRE-ROUTE - Fast-path for meta queries
            from agents.query_router import QueryRouter
            router = QueryRouter()
            fast_response = router.route(user_query)

            if fast_response:
                # Meta query detected - return instant response
                total_time_ms = int((time.time() - start_time) * 1000)
                self._logger.info(f"FAST-PATH: Meta query handled in {total_time_ms}ms")

                return OrchestrationResult(
                    success=True,
                    data=fast_response,
                    query_analysis=QueryAnalysis(
                        complexity=QueryComplexity.SIMPLE,
                        intent=QueryIntent.META,
                        entities_mentioned=[],
                        filters_detected=[],
                        clarity_score=1.0,
                        requires_optimization=False,
                        estimated_steps=0,
                        reasoning="Meta query - instant response"
                    ),
                    execution_plan=ExecutionPlan(
                        should_optimize_query=False,
                        extractor_strategy=ExtractorStrategy.STATIC,
                        validation_level=ValidationLevel.NONE,
                        max_retries=0,
                        confidence_threshold=1.0,
                        reasoning="Meta query fast-path",
                        estimated_cost="zero"
                    ),
                    agents_executed=[],
                    total_time_ms=total_time_ms,
                    confidence_score=1.0,
                    retry_count=0,
                    needs_clarification=False
                )

            # Phase 1: ANALYZE QUERY
            self._logger.info("Phase 1: ANALYZE - Assessing query...")
            analysis = await self._analyze_query(user_query, context_messages)
            self._logger.info(
                f"Analysis complete: complexity={analysis.complexity.value}, "
                f"intent={analysis.intent.value}, clarity={analysis.clarity_score:.2f}"
            )

            # Phase 2: CREATE EXECUTION PLAN
            self._logger.info("Phase 2: PLAN - Creating execution strategy...")
            execution_plan = await self._create_execution_plan(analysis)
            self._logger.info(
                f"Plan: strategy={execution_plan.extractor_strategy.value}, "
                f"validation={execution_plan.validation_level.value}, "
                f"optimize={execution_plan.should_optimize_query}"
            )
            self._logger.info(f"Reasoning: {execution_plan.reasoning}")

            # Phase 3: COORDINATE EXECUTION
            self._logger.info("Phase 3: COORDINATE - Executing agents...")
            result = await self._execute_plan(
                execution_plan,
                analysis,
                user_query,
                workspace_id,
                user_id,
                context_messages,
                agents_executed
            )

            # Phase 4: EVALUATE AND FINALIZE
            self._logger.info("Phase 4: CONTROL - Finalizing results...")
            final_result = await self._evaluate_and_finalize(
                result,
                analysis,
                execution_plan,
                agents_executed,
                start_time
            )

            elapsed_ms = int((time.time() - start_time) * 1000)
            self._logger.info("=" * 60)
            self._logger.info(
                f"ORCHESTRATOR: Complete - success={final_result.success}, "
                f"confidence={final_result.confidence_score:.2f}, "
                f"time={elapsed_ms}ms"
            )
            self._logger.info("=" * 60)

            return final_result

        except Exception as e:
            self._logger.exception(f"Orchestration failed: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Return error result
            return OrchestrationResult(
                success=False,
                data={"_error": str(e)},
                query_analysis=QueryAnalysis(
                    complexity=QueryComplexity.SIMPLE,
                    intent=QueryIntent.SEARCH,
                    clarity_score=0.0,
                    requires_optimization=False,
                    estimated_steps=1,
                    reasoning=f"Error during orchestration: {e}"
                ),
                execution_plan=ExecutionPlan(
                    should_optimize_query=False,
                    extractor_strategy=ExtractorStrategy.STATIC,
                    validation_level=ValidationLevel.NONE,
                    reasoning="Error occurred before plan could be created"
                ),
                agents_executed=agents_executed,
                total_time_ms=elapsed_ms,
                confidence_score=0.0,
                metadata={"error": str(e), "error_type": type(e).__name__}
            )

    async def _analyze_query(
        self,
        user_query: str,
        context_messages: Optional[List[Dict]]
    ) -> QueryAnalysis:
        """
        Phase 1: ANALYZE

        Analyzes query to determine:
        - Complexity level (simple/medium/complex)
        - Intent (search/count/analytics/etc.)
        - Entities mentioned
        - Clarity score (how unambiguous)
        - Whether optimization is needed

        Args:
            user_query: Raw user query
            context_messages: Optional conversation context

        Returns:
            QueryAnalysis object
        """
        self._logger.debug("Analyzing query with LLM...")

        try:
            # Import prompt
            from prompts.orchestrator_prompts import ORCHESTRATOR_ANALYZE_PROMPT

            # Format context
            context_str = "No previous context"
            if context_messages and len(context_messages) > 0:
                context_str = json.dumps(context_messages[-3:], indent=2)  # Last 3 messages

            # Format prompt
            prompt = ORCHESTRATOR_ANALYZE_PROMPT.format(
                user_query=user_query,
                context=context_str
            )

            # Call LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a query analysis expert. Analyze queries to determine complexity and execution strategy."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            llm_response = self.llm_provider.chat(messages, temperature=0.1)
            self._logger.debug(f"LLM analysis received: {len(llm_response)} chars")

            # Parse JSON response
            json_text = self._extract_json_from_response(llm_response)
            parsed = json.loads(json_text)

            # Convert to QueryAnalysis model
            analysis = QueryAnalysis(
                complexity=QueryComplexity(parsed["complexity"]),
                intent=QueryIntent(parsed["intent"]),
                entities_mentioned=parsed.get("entities_mentioned", []),
                filters_detected=parsed.get("filters_detected", []),
                clarity_score=parsed.get("clarity_score", 0.5),
                requires_optimization=parsed.get("requires_optimization", True),
                estimated_steps=parsed.get("estimated_steps", 1),
                reasoning=parsed.get("reasoning", "No reasoning provided")
            )

            self._logger.debug(f"Analysis complete: {analysis.dict()}")
            return analysis

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self._logger.warning(f"Failed to parse LLM analysis: {e}, falling back to heuristic")

            # Fallback to heuristic analysis
            return self._heuristic_analysis(user_query)

    def _heuristic_analysis(self, user_query: str) -> QueryAnalysis:
        """
        Fallback heuristic analysis when LLM fails

        Args:
            user_query: User query

        Returns:
            QueryAnalysis based on simple rules
        """
        query_lower = user_query.lower()

        # Detect complexity
        complexity = QueryComplexity.SIMPLE
        complexity_score = 0

        # Count complexity indicators
        # Note: Don't count "and" in simple entity lists like "companies, people, and interactions"
        # Only count if used in actual filter conditions
        has_filter_and = False
        if ' where ' in query_lower or ' with ' in query_lower or ' that ' in query_lower:
            # These suggest actual filtering conditions
            if ' and ' in query_lower or ' or ' in query_lower:
                complexity_score += 1
                has_filter_and = True

        # Count temporal filters
        if any(word in query_lower for word in ['last week', 'last month', 'yesterday', 'before', 'after']):
            complexity_score += 1

        # Count aggregation operations
        if any(word in query_lower for word in ['aggregate', 'sum', 'average', 'group by', 'total']):
            complexity_score += 2

        if complexity_score >= 3:
            complexity = QueryComplexity.COMPLEX
        elif complexity_score >= 1:
            complexity = QueryComplexity.MEDIUM

        # Detect intent
        intent = QueryIntent.SEARCH

        # Simple list queries (find X, show X, get X)
        if any(word in query_lower for word in ['find', 'show', 'get', 'list']):
            # Check if it's just "find X" without filters
            words = query_lower.split()
            if len(words) <= 3 and complexity_score == 0:
                intent = QueryIntent.LIST
                complexity = QueryComplexity.SIMPLE  # Force simple for basic list queries

        if any(word in query_lower for word in ['how many', 'count', 'number of']):
            intent = QueryIntent.COUNT
        elif any(word in query_lower for word in ['list all', 'show all', 'get all']):
            intent = QueryIntent.LIST
        elif any(word in query_lower for word in ['sum', 'total', 'average', 'aggregate']):
            intent = QueryIntent.ANALYTICS

        # Detect entities
        entities = []
        if 'compan' in query_lower:
            entities.append("company")
        if 'people' in query_lower or 'person' in query_lower or 'contact' in query_lower:
            entities.append("people")
        if 'email' in query_lower:
            entities.append("email")
        if 'interaction' in query_lower or 'meeting' in query_lower:
            entities.append("interaction")

        # Estimate clarity
        clarity_score = 0.7  # Default medium clarity

        # Count queries with clear entities are very clear
        if intent == QueryIntent.COUNT and len(entities) > 0:
            clarity_score = 0.9  # Count queries are explicit about what they want
        # Simple queries with clear entities are very clear
        elif len(entities) > 0 and len(query_lower.split()) <= 3 and complexity_score == 0:
            clarity_score = 0.95  # Very clear and simple
        elif len(user_query.split()) < 5:
            clarity_score = 0.6  # Short queries might be ambiguous

        if any(word in query_lower for word in ['that', 'this', 'those', 'them']) and len(entities) == 0:
            clarity_score = 0.3  # References without entities are ambiguous

        # Simple queries don't need optimization
        requires_optimization = complexity != QueryComplexity.SIMPLE or clarity_score < 0.8

        return QueryAnalysis(
            complexity=complexity,
            intent=intent,
            entities_mentioned=entities,
            filters_detected=[],
            clarity_score=clarity_score,
            requires_optimization=requires_optimization,
            estimated_steps=1 if complexity == QueryComplexity.SIMPLE else 2,
            reasoning=f"Heuristic analysis: complexity={complexity.value}, intent={intent.value}, clarity={clarity_score:.2f}"
        )

    async def _create_execution_plan(
        self,
        analysis: QueryAnalysis
    ) -> ExecutionPlan:
        """
        Phase 2: PLAN

        Creates execution strategy based on query analysis

        Decision Logic:
        - SIMPLE + high clarity → fast path (static, no validation)
        - MEDIUM → standard path (static, heuristic validation)
        - COMPLEX or low clarity → adaptive path (reactive, semantic validation)

        Args:
            analysis: Query analysis from Phase 1

        Returns:
            ExecutionPlan object
        """
        # This will be implemented in the next step
        # For now, return a reasonable default plan
        self._logger.debug("Execution planning not yet implemented, using rule-based plan")

        complexity = analysis.complexity
        clarity = analysis.clarity_score

        # Decision tree - optimized for performance
        if complexity == QueryComplexity.SIMPLE and clarity > 0.8:
            # FAST PATH: Simple and clear queries
            # Examples: "find companies", "show people", "list emails"
            # Strategy: Direct tool call, no optimization, no validation
            return ExecutionPlan(
                should_optimize_query=False,  # Skip query optimization LLM call
                extractor_strategy=ExtractorStrategy.STATIC,  # Direct tool execution
                validation_level=ValidationLevel.NONE,  # Skip validation
                max_retries=0,  # No retries
                confidence_threshold=0.6,  # Lower threshold since no validation
                reasoning=f"FAST PATH: Simple & clear (clarity={clarity:.2f}) - direct execution, no optimization/validation",
                estimated_cost="low"
            )

        elif complexity == QueryComplexity.SIMPLE and clarity > 0.6:
            # LIGHT PATH: Simple but slightly ambiguous
            # Strategy: Quick optimization, static extraction, skip validation
            return ExecutionPlan(
                should_optimize_query=True,  # Light optimization to clarify
                extractor_strategy=ExtractorStrategy.STATIC,
                validation_level=ValidationLevel.NONE,
                max_retries=0,
                confidence_threshold=0.7,
                reasoning=f"LIGHT PATH: Simple but moderate clarity ({clarity:.2f}) - quick optimization, no validation",
                estimated_cost="low-medium"
            )

        elif complexity == QueryComplexity.COMPLEX or clarity < 0.5:
            # ADAPTIVE PATH: Complex or ambiguous queries
            # Strategy: Full optimization, reactive loops, semantic validation
            return ExecutionPlan(
                should_optimize_query=True,
                extractor_strategy=ExtractorStrategy.REACTIVE,
                validation_level=ValidationLevel.SEMANTIC,
                max_retries=2,
                confidence_threshold=0.8,
                reasoning=f"ADAPTIVE PATH: {'Complex' if complexity == QueryComplexity.COMPLEX else 'Ambiguous'} (clarity={clarity:.2f}) - full pipeline",
                estimated_cost="high"
            )

        else:
            # STANDARD PATH: Medium complexity with good clarity
            # Strategy: Optimization + static extraction + light validation
            return ExecutionPlan(
                should_optimize_query=True,
                extractor_strategy=ExtractorStrategy.STATIC,
                validation_level=ValidationLevel.HEURISTIC,  # Fast validation only
                max_retries=1,
                confidence_threshold=0.7,
                reasoning=f"STANDARD PATH: Medium complexity (clarity={clarity:.2f}) - standard pipeline",
                estimated_cost="medium"
            )

    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        analysis: QueryAnalysis,
        user_query: str,
        workspace_id: str,
        user_id: str,
        context_messages: Optional[List[Dict]],
        agents_executed: List[AgentExecution]
    ) -> Dict[str, Any]:
        """
        Phase 3: COORDINATE

        Executes agents according to plan with adaptive retry

        Flow:
        1. Query Optimization (conditional)
        2. Data Extraction (strategy-based)
        3. Result Validation (conditional)
        4. Retry loop with feedback

        Args:
            plan: Execution plan
            analysis: Query analysis
            user_query: Raw user query
            workspace_id: Workspace ID
            user_id: User ID
            context_messages: Context messages
            agents_executed: List to track executed agents

        Returns:
            Dictionary with execution results
        """
        optimized_query = user_query
        extraction_result = None
        validation_result = None
        retry_count = 0

        # Step 1: Query Optimization (conditional)
        if plan.should_optimize_query:
            self._logger.info("Step 1: Running QueryOptimizer...")
            optimized_query = await self._run_query_optimizer(
                user_query,
                context_messages,
                agents_executed
            )
            self._logger.info(f"Optimized query: {optimized_query[:100]}...")
        else:
            self._logger.info("Step 1: Skipping QueryOptimizer (not needed)")

        # Step 2-4: Extraction + Validation Loop with Retry
        while retry_count <= plan.max_retries:
            if retry_count > 0:
                self._logger.info(f"Retry attempt {retry_count}/{plan.max_retries}")

            # Step 2: Data Extraction
            self._logger.info(f"Step 2: Running {plan.extractor_strategy.value} extractor...")
            extraction_result = await self._run_extractor(
                plan.extractor_strategy,
                optimized_query,
                workspace_id,
                user_id,
                validation_result,  # Pass validation feedback for refinement
                agents_executed
            )

            # Check for clarification request
            if extraction_result.get("needs_clarification"):
                self._logger.info("Extraction requires clarification")
                return {
                    "status": "needs_clarification",
                    "extraction_result": extraction_result,
                    "validation_result": None,
                    "retry_count": retry_count
                }

            # Step 3: Result Validation (conditional)
            if plan.validation_level != ValidationLevel.NONE:
                self._logger.info(f"Step 3: Running {plan.validation_level.value} validation...")
                validation_result = await self._run_validator(
                    user_query,
                    optimized_query,
                    extraction_result,
                    plan.validation_level,
                    agents_executed
                )

                self._logger.info(
                    f"Validation: confidence={validation_result['confidence_score']:.2f}, "
                    f"sufficient={validation_result['is_sufficient']}"
                )

                # Check if results meet confidence threshold
                if validation_result["confidence_score"] >= plan.confidence_threshold:
                    self._logger.info("✓ Confidence threshold met, accepting results")
                    break

                # Check next action
                next_action = validation_result.get("next_action")
                if next_action == NextAction.CLARIFY.value:
                    self._logger.info("Validation recommends clarification")
                    return {
                        "status": "needs_clarification",
                        "extraction_result": extraction_result,
                        "validation_result": validation_result,
                        "retry_count": retry_count
                    }

                if next_action != NextAction.REFINE.value:
                    self._logger.info("Validation suggests accepting results")
                    break

                self._logger.info("Validation suggests refinement")
            else:
                self._logger.info("Step 3: Skipping validation (not needed)")
                # No validation, accept results
                break

            retry_count += 1

        # Check if we hit max retries
        if retry_count > plan.max_retries:
            self._logger.warning(f"Max retries ({plan.max_retries}) reached, accepting best result")

        return {
            "status": "complete",
            "extraction_result": extraction_result,
            "validation_result": validation_result,
            "retry_count": retry_count
        }

    async def _run_query_optimizer(
        self,
        user_query: str,
        context_messages: Optional[List[Dict]],
        agents_executed: List[AgentExecution]
    ) -> str:
        """
        Run QueryOptimizerAgent

        Args:
            user_query: Raw user query
            context_messages: Context messages
            agents_executed: List to track execution

        Returns:
            Optimized query string
        """
        agent_start = time.time()

        try:
            # Lazy-load query optimizer
            if self._query_optimizer is None:
                from agents.query_optimizer import QueryOptimizerAgent
                self._query_optimizer = QueryOptimizerAgent()

            # Run optimizer
            optimized = self._query_optimizer.optimize(
                user_query=user_query,
                context_messages=context_messages or []
            )

            duration_ms = int((time.time() - agent_start) * 1000)

            # Track execution
            agents_executed.append(AgentExecution(
                agent_name="QueryOptimizer",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=True,
                result_summary=f"Optimized: {optimized[:50]}..."
            ))

            return optimized

        except Exception as e:
            duration_ms = int((time.time() - agent_start) * 1000)
            self._logger.error(f"QueryOptimizer failed: {e}")

            # Track failure
            agents_executed.append(AgentExecution(
                agent_name="QueryOptimizer",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            ))

            # Return original query on error
            return user_query

    async def _run_extractor(
        self,
        strategy: ExtractorStrategy,
        optimized_query: str,
        workspace_id: str,
        user_id: str,
        refinement_feedback: Optional[Dict],
        agents_executed: List[AgentExecution]
    ) -> Dict[str, Any]:
        """
        Run data extractor (static or reactive)

        Args:
            strategy: Extractor strategy
            optimized_query: Optimized query
            workspace_id: Workspace ID
            user_id: User ID
            refinement_feedback: Validation feedback for refinement
            agents_executed: List to track execution

        Returns:
            Extraction result dictionary
        """
        agent_start = time.time()

        try:
            if strategy == ExtractorStrategy.REACTIVE:
                # Use ReActiveDataExtractor
                if self._reactive_extractor is None:
                    from agents.reactive_data_extractor import ReActiveDataExtractor
                    self._reactive_extractor = ReActiveDataExtractor(self.llm_provider)

                result = await self._reactive_extractor.extract(
                    optimized_query=optimized_query,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    refinement_feedback=refinement_feedback
                )

                duration_ms = int((time.time() - agent_start) * 1000)

                # Convert ExtractionResult to dict
                extraction_dict = {
                    **result.data,
                    "_reasoning_traces": [trace.dict() for trace in result.reasoning_traces],
                    "_observations": [obs.dict() for obs in result.observations],
                    "_confidence_scores": result.confidence_scores,
                    "_final_confidence": result.final_confidence,
                    "_total_iterations": result.total_iterations,
                    "_metadata": result.metadata,
                    "needs_clarification": result.needs_clarification,
                    "clarification_question": result.clarification_question
                }

                # Track execution
                agents_executed.append(AgentExecution(
                    agent_name="ReActiveDataExtractor",
                    completed_at=datetime.now(),
                    duration_ms=duration_ms,
                    success=result.success,
                    result_summary=f"Iterations: {result.total_iterations}, Confidence: {result.final_confidence:.2f}"
                ))

                # Update strategy stats
                self._update_strategy_stats("reactive", result.success, duration_ms)

                return extraction_dict

            else:  # STATIC
                # Use DataExtractorAgent
                if self._static_extractor is None:
                    from agents.data_extractor import DataExtractorAgent
                    self._static_extractor = DataExtractorAgent(self.llm_provider)

                result = await self._static_extractor.extract(
                    optimized_query=optimized_query,
                    workspace_id=workspace_id,
                    user_id=user_id
                )

                duration_ms = int((time.time() - agent_start) * 1000)

                # Track execution
                has_data = any(
                    len(v) > 0 if isinstance(v, list) else v is not None
                    for k, v in result.items()
                    if not k.startswith("_")
                )

                agents_executed.append(AgentExecution(
                    agent_name="DataExtractor",
                    completed_at=datetime.now(),
                    duration_ms=duration_ms,
                    success=has_data,
                    result_summary=f"Data keys: {', '.join([k for k in result.keys() if not k.startswith('_')])}"
                ))

                # Update strategy stats
                self._update_strategy_stats("static", has_data, duration_ms)

                return result

        except Exception as e:
            duration_ms = int((time.time() - agent_start) * 1000)
            self._logger.error(f"Extractor failed: {e}")

            # Track failure
            agent_name = "ReActiveDataExtractor" if strategy == ExtractorStrategy.REACTIVE else "DataExtractor"
            agents_executed.append(AgentExecution(
                agent_name=agent_name,
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            ))

            return {
                "_error": str(e),
                "_error_type": type(e).__name__
            }

    async def _run_validator(
        self,
        user_query: str,
        optimized_query: str,
        extraction_result: Dict[str, Any],
        validation_level: ValidationLevel,
        agents_executed: List[AgentExecution]
    ) -> Dict[str, Any]:
        """
        Run ResultValidator

        Args:
            user_query: Original user query
            optimized_query: Optimized query
            extraction_result: Extraction results
            validation_level: Validation level
            agents_executed: List to track execution

        Returns:
            Validation result dictionary
        """
        agent_start = time.time()

        try:
            # Lazy-load validator
            if self._validator is None:
                from agents.result_validator import ResultValidator
                self._validator = ResultValidator(self.llm_provider)

            # Extract reasoning traces if present
            reasoning_traces = extraction_result.get("_reasoning_traces")

            # Run validation
            enable_semantic = (validation_level == ValidationLevel.SEMANTIC)
            result = await self._validator.validate(
                original_query=user_query,
                optimized_query=optimized_query,
                extracted_data=extraction_result,
                reasoning_traces=reasoning_traces,
                enable_semantic=enable_semantic
            )

            duration_ms = int((time.time() - agent_start) * 1000)

            # Convert to dict
            validation_dict = {
                "is_sufficient": result.is_sufficient,
                "confidence_score": result.confidence_score,
                "heuristic_issues": [issue.dict() for issue in result.heuristic_issues],
                "semantic_analysis": result.semantic_analysis.dict() if result.semantic_analysis else None,
                "recommendations": result.recommendations,
                "next_action": result.next_action.value,
                "metadata": result.metadata
            }

            # Track execution
            agents_executed.append(AgentExecution(
                agent_name="ResultValidator",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=True,
                result_summary=f"Confidence: {result.confidence_score:.2f}, Action: {result.next_action.value}"
            ))

            return validation_dict

        except Exception as e:
            duration_ms = int((time.time() - agent_start) * 1000)
            self._logger.error(f"Validator failed: {e}")

            # Track failure
            agents_executed.append(AgentExecution(
                agent_name="ResultValidator",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            ))

            # Return permissive validation on error
            return {
                "is_sufficient": True,
                "confidence_score": 0.5,
                "heuristic_issues": [],
                "semantic_analysis": None,
                "recommendations": [f"Validation failed: {e}"],
                "next_action": NextAction.COMPLETE.value,
                "metadata": {"error": str(e)}
            }

    async def _evaluate_and_finalize(
        self,
        result: Dict[str, Any],
        analysis: QueryAnalysis,
        plan: ExecutionPlan,
        agents_executed: List[AgentExecution],
        start_time: float
    ) -> OrchestrationResult:
        """
        Phase 4: CONTROL

        Evaluates results and creates final response

        Flow:
        1. Check for clarification needs
        2. Format response
        3. Calculate final confidence
        4. Package orchestration result

        Args:
            result: Execution results from Phase 3
            analysis: Query analysis
            plan: Execution plan
            agents_executed: List of executed agents
            start_time: Start timestamp

        Returns:
            OrchestrationResult
        """
        elapsed_ms = int((time.time() - start_time) * 1000)
        status = result.get("status")
        extraction_result = result.get("extraction_result", {})
        validation_result = result.get("validation_result")
        retry_count = result.get("retry_count", 0)

        # Handle clarification request
        if status == "needs_clarification":
            self._logger.info("Finalizing with clarification request")

            clarification_question = extraction_result.get("clarification_question")
            if not clarification_question and validation_result:
                # Try to get clarification from validation
                clarification_question = "Could you provide more details about what you're looking for?"

            return OrchestrationResult(
                success=False,
                data=extraction_result,
                query_analysis=analysis,
                execution_plan=plan,
                agents_executed=agents_executed,
                total_time_ms=elapsed_ms,
                confidence_score=0.0,
                retry_count=retry_count,
                needs_clarification=True,
                clarification_question=clarification_question,
                metadata={
                    "status": "needs_clarification",
                    "validation_result": validation_result
                }
            )

        # Format response
        self._logger.info("Formatting final response...")
        formatted_data = await self._run_response_formatter(
            extraction_result,
            agents_executed
        )

        # Calculate final confidence
        final_confidence = 0.5  # Default
        if validation_result:
            final_confidence = validation_result.get("confidence_score", 0.5)
        elif extraction_result.get("_final_confidence"):
            final_confidence = extraction_result["_final_confidence"]

        # Determine success
        has_data = any(
            len(v) > 0 if isinstance(v, list) else v is not None
            for k, v in extraction_result.items()
            if not k.startswith("_") and k not in ["needs_clarification", "clarification_question"]
        )

        success = has_data and final_confidence >= 0.3  # Very lenient threshold

        # Package metadata
        metadata = {
            "retry_count": retry_count,
            "has_data": has_data,
            "agents_count": len(agents_executed),
            "strategy_used": plan.extractor_strategy.value,
            "validation_level": plan.validation_level.value
        }

        if validation_result:
            metadata["validation"] = {
                "is_sufficient": validation_result.get("is_sufficient"),
                "next_action": validation_result.get("next_action"),
                "recommendations": validation_result.get("recommendations", [])[:3]
            }

        self._logger.info(
            f"Finalization complete: success={success}, confidence={final_confidence:.2f}"
        )

        return OrchestrationResult(
            success=success,
            data=formatted_data,
            query_analysis=analysis,
            execution_plan=plan,
            agents_executed=agents_executed,
            total_time_ms=elapsed_ms,
            confidence_score=final_confidence,
            retry_count=retry_count,
            needs_clarification=False,
            metadata=metadata
        )

    async def _run_response_formatter(
        self,
        extraction_result: Dict[str, Any],
        agents_executed: List[AgentExecution]
    ) -> Dict[str, Any]:
        """
        Run ResponseFormatterAgent

        Args:
            extraction_result: Extraction results
            agents_executed: List to track execution

        Returns:
            Formatted response dictionary
        """
        agent_start = time.time()

        try:
            # Lazy-load formatter
            if self._formatter is None:
                from agents.response_formatter import ResponseFormatterAgent
                self._formatter = ResponseFormatterAgent()

            # Get optimized query from extraction metadata
            optimized_query = extraction_result.get("_metadata", {}).get("optimized_query", "")
            if not optimized_query:
                # Fallback: try to reconstruct from available data
                optimized_query = "Data retrieval query"

            # Format response
            formatted = self._formatter.format(
                optimized_query=optimized_query,
                extracted_data=extraction_result
            )

            duration_ms = int((time.time() - agent_start) * 1000)

            # Track execution
            agents_executed.append(AgentExecution(
                agent_name="ResponseFormatter",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=True,
                result_summary="Response formatted"
            ))

            return formatted

        except Exception as e:
            duration_ms = int((time.time() - agent_start) * 1000)
            self._logger.error(f"ResponseFormatter failed: {e}")

            # Track failure
            agents_executed.append(AgentExecution(
                agent_name="ResponseFormatter",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            ))

            # Return extraction result as-is on error
            return extraction_result

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response (might be wrapped in code blocks)

        Args:
            response: Raw LLM response

        Returns:
            Extracted JSON string
        """
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```"):
            start_idx = response.find("\n") + 1
            end_idx = response.rfind("```")
            if end_idx > start_idx:
                response = response[start_idx:end_idx].strip()

        # If response doesn't start with {, try to find the JSON object
        if not response.startswith("{"):
            start_idx = response.find("{")
            if start_idx >= 0:
                response = response[start_idx:]

        return response

    def _update_strategy_stats(
        self,
        strategy: str,
        success: bool,
        duration_ms: int
    ):
        """
        Update strategy statistics for learning

        Args:
            strategy: Strategy used (static/reactive)
            success: Whether execution succeeded
            duration_ms: Execution duration
        """
        if strategy not in self.strategy_stats:
            return

        stats = self.strategy_stats[strategy]
        stats["total"] += 1

        if success:
            stats["success"] += 1

        # Update rolling average time
        if stats["avg_time_ms"] == 0:
            stats["avg_time_ms"] = duration_ms
        else:
            stats["avg_time_ms"] = int(
                (stats["avg_time_ms"] * (stats["total"] - 1) + duration_ms) / stats["total"]
            )

    def get_strategy_success_rate(self, strategy: str) -> float:
        """
        Get historical success rate for a strategy

        Args:
            strategy: Strategy name

        Returns:
            Success rate (0.0-1.0)
        """
        if strategy not in self.strategy_stats:
            return 0.5

        stats = self.strategy_stats[strategy]
        if stats["total"] == 0:
            return 0.5

        return stats["success"] / stats["total"]
