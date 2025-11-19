"""
OrchestratorAgent V2 - Intelligent Query Orchestrator

TRUE ORCHESTRATOR that:
1. Responds directly to queries that don't need agents
2. Conditionally uses agents based on actual requirements
3. Dynamically decides which agents and in what order
4. Optimizes for performance and cost

Architecture:
    User Query
        ↓
    DecisionEngine (analyzes query)
        ↓
    ├─ DIRECT: Respond immediately (no agents)
    ├─ SIMPLE: Use minimal agents (extractor only)
    └─ COMPLEX: Use full pipeline (optimizer → extractor → validator)
"""
import logging
import time
import json
from typing import Dict, Any, List, Optional, TypedDict, Literal, Union
from datetime import datetime
from uuid import uuid4

from langgraph.graph import StateGraph, END, START

from src.infrastructure.llm.base import LLMProvider
from src.core.agents.registry.agent_registry import AgentRegistry
from src.core.agents.orchestration.decision_engine import DecisionEngine, ExecutionDecision
from src.core.agents.registry.models import (
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
from src.application.services.conversation.conversation_state import ConversationState
from src.application.services.blocks.models import StreamEvent, BlockType, Block
from src.application.services.blocks.smart_table_formatter import get_smart_table_formatter


class AgentState(TypedDict):
    """State for the orchestration graph"""
    user_query: str
    workspace_id: str
    user_id: str
    access_token: Optional[str]
    context_messages: List[Dict]
    conversation_state: Optional[ConversationState]
    entity_mentions: List[Dict[str, Any]]
    
    # Internal execution state
    decision: Optional[ExecutionDecision]
    enriched_context: Optional[str]
    extraction_result: Dict[str, Any]
    validation_result: Any
    retry_count: int
    final_response: Dict[str, Any]
    agents_executed: List[AgentExecution]
    start_time: float


class OrchestratorAgent:
    """
    Intelligent orchestrator that conditionally uses agents based on query needs
    
    Key Features:
    - Direct responses for simple queries (no agent overhead)
    - Conditional agent usage (only what's needed)
    - Dynamic decision making (not a fixed pipeline)
    - Performance optimized (minimal LLM calls)
    - Cost aware (tracks and minimizes token usage)
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize OrchestratorAgent
        
        Args:
            llm_provider: LLM provider for agents (optional)
        """
        self._logger = logging.getLogger(__name__)

        # Set LLM provider
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from src.infrastructure.llm.factory import LLMProviderFactory
            from src.shared.config.settings import DATA_EXTRACTOR_CONFIG
            self.llm_provider = LLMProviderFactory.create(DATA_EXTRACTOR_CONFIG)

        # Initialize core components
        self.agent_registry = AgentRegistry(self.llm_provider)
        self.decision_engine = DecisionEngine()

        # Performance tracking
        self.stats = {
            "direct_responses": 0,
            "simple_executions": 0,
            "complex_executions": 0,
            "total_queries": 0,
            "avg_time_ms": 0
        }

        # Initialize Graph
        self.graph = self._build_graph()
        
        self._logger.info("OrchestratorAgent V2 (LangGraph) initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("decide_strategy", self.node_decide_strategy)
        workflow.add_node("handle_direct", self.node_handle_direct)
        workflow.add_node("enrich_context", self.node_enrich_context)
        workflow.add_node("extract_data", self.node_extract_data)
        workflow.add_node("validate_result", self.node_validate_result)
        workflow.add_node("generate_response", self.node_generate_response)
        
        # Add Edges
        workflow.add_edge(START, "decide_strategy")
        
        # Route based on decision
        workflow.add_conditional_edges(
            "decide_strategy",
            self._route_strategy,
            {
                "direct": "handle_direct",
                "simple": "enrich_context",
                "complex": "enrich_context"
            }
        )
        
        # Direct path -> Response
        workflow.add_edge("handle_direct", "generate_response")
        
        # Data path -> Enrichment -> Extraction
        workflow.add_edge("enrich_context", "extract_data")
        
        # After extraction -> Route based on strategy/result
        workflow.add_conditional_edges(
            "extract_data",
            self._route_after_extraction,
            {
                "simple": "generate_response",
                "complex": "validate_result",
                "clarify": "generate_response" # Pass through to response generation (which handles clarification status)
            }
        )
        
        # After validation -> Route based on outcome
        workflow.add_conditional_edges(
            "validate_result",
            self._route_after_validation,
            {
                "success": "generate_response",
                "retry": "extract_data",
                "clarify": "generate_response"
            }
        )
        
        # End
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()

    # =================================================================
    # Graph Nodes
    # =================================================================

    def node_decide_strategy(self, state: AgentState) -> Dict[str, Any]:
        """Node: Analyze query and decide execution strategy"""
        self._logger.info(f"DECIDE: Analyzing query: {state['user_query']}")
        
        decision = self.decision_engine.decide(
            query=state['user_query'],
            context_messages=state['context_messages'],
            is_first_message=(not state['context_messages'] or len(state['context_messages']) == 0)
        )
        
        self._logger.info(f"Decision: {decision.strategy.upper()}")
        self._logger.info(f"Agents needed: {decision.agents_needed}")
        
        return {"decision": decision}

    async def node_handle_direct(self, state: AgentState) -> Dict[str, Any]:
        """Node: Handle direct queries (meta/conversational)"""
        decision = state['decision']
        user_query = state['user_query']
        agents_executed = state['agents_executed']
        
        self._logger.info("DIRECT PATH: Handling without data extraction")
        
        # Handle meta queries
        if decision.meta_type:
            agent_start = time.time()
            response_text = self._generate_meta_response(decision.meta_type)
            duration_ms = int((time.time() - agent_start) * 1000)

            agents_executed.append(AgentExecution(
                agent_name="MetaResponse",
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=True,
                result_summary=f"Meta query handled: {decision.meta_type}"
            ))
            
            return {
                "final_response": {
                    "response": response_text,
                    "metadata": {"type": f"meta_{decision.meta_type}", "fast_path": True},
                    "_direct_response": True
                },
                "agents_executed": agents_executed
            }
            
        # Handle other direct queries
        agent_start = time.time()
        response_text = self._generate_direct_response(user_query)
        duration_ms = int((time.time() - agent_start) * 1000)

        agents_executed.append(AgentExecution(
            agent_name="DirectResponse",
            completed_at=datetime.now(),
            duration_ms=duration_ms,
            success=True,
            result_summary="Generated direct response"
        ))
        
        return {
            "final_response": {
                "response": response_text,
                "_direct_response": True
            },
            "agents_executed": agents_executed
        }

    async def node_enrich_context(self, state: AgentState) -> Dict[str, Any]:
        """Node: Enrich entity mentions with CRM data"""
        entity_mentions = state.get('entity_mentions')
        access_token = state.get('access_token')
        workspace_id = state['workspace_id']
        
        if not entity_mentions or not access_token:
            return {"enriched_context": None}
            
        try:
            from src.application.services.entity import get_enrichment_service
            enrichment_service = get_enrichment_service()

            self._logger.info(f"Enriching {len(entity_mentions)} entity mentions with CRM data...")
            enriched_entities = enrichment_service.enrich_entity_mentions(
                entity_mentions=entity_mentions,
                access_token=access_token,
                workspace_id=workspace_id
            )

            if enriched_entities:
                context = enrichment_service.format_enriched_entities_for_context(enriched_entities)
                self._logger.info(f"Enriched {len(enriched_entities)} entities with CRM data")
                return {"enriched_context": context}
            else:
                self._logger.warning("No entities could be enriched")
                return {"enriched_context": None}
                
        except Exception as e:
            self._logger.error(f"Entity enrichment failed: {e}", exc_info=True)
            return {"enriched_context": None}

    async def node_extract_data(self, state: AgentState) -> Dict[str, Any]:
        """Node: Run data extractor agent"""
        self._logger.info("EXECUTE: Running DataExtractor...")
        
        # Determine agents executed list (either existing or new)
        agents_executed = state.get('agents_executed', [])
        
        extraction_result = await self._run_agent(
            "data_extractor",
            lambda agent: agent.extract(
                optimized_query=state['user_query'],
                workspace_id=state['workspace_id'],
                user_id=state['user_id'],
                context_messages=state['context_messages'],
                entity_mentions=state['entity_mentions'],
                enriched_context=state['enriched_context']
            ),
            agents_executed,
            "Data extraction complete"
        )
        
        # Update conversation state
        if state['conversation_state'] and extraction_result:
            try:
                if hasattr(extraction_result, 'data'):
                    state['conversation_state'].update_from_results(extraction_result.data)
                else:
                    state['conversation_state'].update_from_results(extraction_result)
            except Exception as e:
                self._logger.warning(f"Failed to update conversation state: {e}")
        
        return {
            "extraction_result": extraction_result,
            "agents_executed": agents_executed
        }

    async def node_validate_result(self, state: AgentState) -> Dict[str, Any]:
        """Node: Validate extraction results (Complex path)"""
        self._logger.info("VALIDATE: Running ResultValidator...")
        
        retry_count = state.get('retry_count', 0)
        max_retries = state['decision'].max_retries
        
        if retry_count > max_retries:
            self._logger.info("Max retries reached, accepting current result")
            return {"validation_result": {"confidence_score": 0.5, "next_action": "ACCEPT"}}
            
        extracted_data = state['extraction_result']
        reasoning_traces = extracted_data.get("_reasoning_traces")
        agents_executed = state['agents_executed']
        
        validation_result = await self._run_agent(
            "result_validator",
            lambda agent: agent.validate(
                original_query=state['user_query'],
                optimized_query=state['user_query'],
                extracted_data=extracted_data,
                reasoning_traces=reasoning_traces,
                enable_semantic=True
            ),
            agents_executed,
            f"Validation complete (Attempt {retry_count + 1})"
        )
        
        return {
            "validation_result": validation_result,
            "agents_executed": agents_executed,
            "retry_count": retry_count + 1
        }

    async def node_generate_response(self, state: AgentState) -> Dict[str, Any]:
        """Node: Generate final response package"""
        decision = state['decision']
        
        # Case 1: Direct Response (already has final_response)
        if state.get('final_response') and state['final_response'].get('_direct_response'):
            return {}
            
        # Case 2: Clarification needed
        extraction_result = state.get('extraction_result', {})
        validation_result = state.get('validation_result')
        
        needs_clarification = False
        clarification_q = None
        
        if extraction_result.get("needs_clarification"):
            needs_clarification = True
            clarification_q = extraction_result.get("clarification_question")
        elif validation_result:
             next_action = validation_result.next_action if hasattr(validation_result, 'next_action') else validation_result.get('next_action')
             if next_action in ["CLARIFY", NextAction.CLARIFY.value]:
                 needs_clarification = True
                 clarification_q = "I need some clarification to answer your question."
        
        if needs_clarification:
            return {
                "final_response": {
                    "status": "needs_clarification",
                    "data": extraction_result,
                    "clarification_question": clarification_q,
                    "retry_count": state.get('retry_count', 0)
                }
            }
            
        # Case 3: Standard Data Response
        return {
            "final_response": {
                "status": "complete",
                "data": extraction_result,
                "validation": validation_result,
                "retry_count": state.get('retry_count', 0)
            }
        }

    # =================================================================
    # Edge Routing Logic
    # =================================================================

    def _route_strategy(self, state: AgentState) -> Literal["direct", "simple", "complex"]:
        """Route based on decision strategy"""
        return state['decision'].strategy

    def _route_after_extraction(self, state: AgentState) -> Literal["simple", "complex", "clarify"]:
        """Route after extraction"""
        # Check for clarification immediately
        if state['extraction_result'].get("needs_clarification"):
            return "clarify"
            
        if state['decision'].strategy == "simple":
            return "simple"
        return "complex"

    def _route_after_validation(self, state: AgentState) -> Literal["success", "retry", "clarify"]:
        """Route after validation"""
        val_result = state['validation_result']
        decision = state['decision']
        
        # Get confidence and next action
        confidence = val_result.confidence_score if hasattr(val_result, 'confidence_score') else val_result.get('confidence_score', 0.5)
        next_action = val_result.next_action if hasattr(val_result, 'next_action') else val_result.get('next_action')
        
        if next_action in ["CLARIFY", NextAction.CLARIFY.value]:
            return "clarify"
            
        if confidence >= 0.7 or next_action not in ["REFINE", NextAction.REFINE.value]:
            return "success"
            
        if state['retry_count'] > decision.max_retries:
            return "success"
            
        return "retry"

    # =================================================================
    # Orchestration Methods
    # =================================================================

    async def orchestrate(
        self,
        user_query: str,
        workspace_id: str,
        user_id: str,
        context_messages: Optional[List[Dict]] = None,
        conversation_state: Optional['ConversationState'] = None,
        entity_mentions: Optional[List[Dict[str, Any]]] = None
    ) -> OrchestrationResult:
        """
        Main entry point - orchestrates query execution using LangGraph
        """
        self._logger.info("=" * 60)
        self._logger.info("ORCHESTRATOR V2 (LangGraph): Starting")
        self._logger.info(f"Query: {user_query}")
        self._logger.info("=" * 60)

        start_time = time.time()
        self.stats["total_queries"] += 1
        
        # Initialize state
        initial_state: AgentState = {
            "user_query": user_query,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "access_token": None, # Not provided in standard orchestrate
            "context_messages": context_messages or [],
            "conversation_state": conversation_state,
            "entity_mentions": entity_mentions or [],
            "decision": None,
            "enriched_context": None,
            "extraction_result": {},
            "validation_result": None,
            "retry_count": 0,
            "final_response": {},
            "agents_executed": [],
            "start_time": start_time
        }
        
        try:
            # Run Graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Update stats
            decision = final_state.get('decision')
            if decision:
                if decision.strategy == "direct":
                    self.stats["direct_responses"] += 1
                elif decision.strategy == "simple":
                    self.stats["simple_executions"] += 1
                elif decision.strategy == "complex":
                    self.stats["complex_executions"] += 1

            # Finalize Result
            final_result = self._finalize_result(
                final_state.get('final_response', {}),
                final_state.get('decision'),
                final_state.get('agents_executed', []),
                start_time
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            self._update_stats(elapsed_ms)
            
            self._logger.info("=" * 60)
            self._logger.info(f"ORCHESTRATOR Complete: success={final_result.success}, time={elapsed_ms}ms")
            self._logger.info("=" * 60)
            
            return final_result

        except Exception as e:
            self._logger.exception(f"Orchestration failed: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_error_result(str(e), [], elapsed_ms)

    async def stream_orchestrate(
        self,
        user_query: str,
        workspace_id: str,
        user_id: str,
        access_token: str,
        context_messages: Optional[List[Dict]] = None,
        conversation_state: Optional['ConversationState'] = None,
        entity_mentions: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Streaming version of orchestrate - yields blocks as they're generated
        """
        start_time = time.time()
        block_order = 0
        
        # Initialize state
        initial_state: AgentState = {
            "user_query": user_query,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "access_token": access_token,
            "context_messages": context_messages or [],
            "conversation_state": conversation_state,
            "entity_mentions": entity_mentions or [],
            "decision": None,
            "enriched_context": None,
            "extraction_result": {},
            "validation_result": None,
            "retry_count": 0,
            "final_response": {},
            "agents_executed": [],
            "start_time": start_time
        }

        try:
            self._logger.info("STREAMING ORCHESTRATOR: Starting")
            
            # Stream execution
            async for event in self.graph.astream(initial_state):
                # Handle events mapped to node names
                for node_name, node_state in event.items():
                    
                    if node_name == "decide_strategy":
                        # Emit Thinking Block
                        decision = node_state['decision']
                        thinking_content = self._generate_user_friendly_status(
                            query=user_query,
                            decision=decision,
                            workspace_id=workspace_id
                        )
                        
                        yield self._create_block_event(
                            BlockType.THINKING,
                            thinking_content,
                            block_order,
                            {
                                "strategy": decision.strategy,
                                "confidence": decision.confidence
                            }
                        )
                        block_order += 1
                        
                    elif node_name == "generate_response":
                        # This is the final step - Generate output blocks
                        final_response = node_state.get('final_response', {})
                        
                        if final_response.get('_direct_response'):
                            # Direct text response
                            yield self._create_block_event(
                                BlockType.TEXT,
                                final_response.get('response', ''),
                                block_order,
                                {"type": "direct_response"}
                            )
                            block_order += 1
                        
                        elif final_response.get('status') == "needs_clarification":
                            # Clarification response
                            yield self._create_block_event(
                                BlockType.TEXT,
                                final_response.get('clarification_question', 'Could you clarify?'),
                                block_order,
                                {"type": "clarification"}
                            )
                            block_order += 1
                            
                        else:
                            # Standard data response (Text + Table)
                            data = final_response.get('data', {})
                            show_table = self._should_show_table(user_query, data)
                            
                            # Intro Text
                            intro_text = self._generate_intro_text(data) if show_table else \
                                         await self._generate_natural_language_response(user_query, data)
                            
                            result_summary = self._build_result_summary(data)
                            
                            yield self._create_block_event(
                                BlockType.TEXT,
                                intro_text,
                                block_order,
                                {
                                    "type": "intro" if show_table else "natural_language_response",
                                    "query_context": {"result_summary": result_summary},
                                    "format": "table" if show_table else "text"
                                }
                            )
                            block_order += 1
                            
                            # Table Blocks
                            if show_table:
                                async for block_event in self._stream_table_blocks(
                                    data, user_query, block_order
                                ):
                                    yield block_event
                                    if block_event.type == "block_complete":
                                        block_order += 1

            elapsed_ms = int((time.time() - start_time) * 1000)
            self._logger.info(f"Streaming complete in {elapsed_ms}ms")

        except Exception as e:
            self._logger.exception(f"Streaming orchestration failed: {e}")
            yield StreamEvent.error(str(e), "ORCHESTRATION_ERROR")

    def _create_block_event(
        self, 
        block_type: BlockType, 
        content: str, 
        order: int, 
        metadata: Dict = None
    ) -> StreamEvent:
        """Helper to create a complete block event"""
        block_id = str(uuid4())
        block = Block(
            block_id=block_id,
            block_type=block_type,
            content=content,
            order=order,
            metadata=metadata or {}
        )
        return StreamEvent.block_complete(
            block_id=block_id,
            block_type=block_type,
            content=content,
            order=order,
            metadata=metadata
        )

    async def _stream_table_blocks(self, data: Dict, user_query: str, start_order: int):
        """Generate table blocks streaming"""
        from src.application.services.blocks.models import StreamEvent, BlockType, Block
        current_order = start_order
        
        for key, value in data.items():
            if key.startswith("_"):
                continue

            if isinstance(value, list) and len(value) > 0:
                table_block_id = str(uuid4())
                
                # Prepare data for formatter
                value_as_dicts = []
                for item in value:
                    if hasattr(item, 'model_dump'):
                        value_as_dicts.append(item.model_dump())
                    elif hasattr(item, 'dict'):
                        value_as_dicts.append(item.dict())
                    elif isinstance(item, dict):
                        value_as_dicts.append(item)
                    else:
                        value_as_dicts.append(item.__dict__ if hasattr(item, '__dict__') else {"value": str(item)})

                csv_generator = get_smart_table_formatter()
                table_metadata = {
                    "data_type": key,
                    "row_count": len(value_as_dicts),
                    "formatting_method": "ai_csv_generator"
                }

                yield StreamEvent.block_start(
                    block_id=table_block_id,
                    block_type=BlockType.TABLE,
                    order=current_order,
                    metadata=table_metadata
                )

                full_content = ""
                for csv_chunk in csv_generator.generate_csv_streaming(
                    data=value_as_dicts,
                    data_type=key,
                    user_query=user_query
                ):
                    yield StreamEvent.block_delta(
                        block_id=table_block_id,
                        content=csv_chunk
                    )
                    full_content += csv_chunk

                yield StreamEvent.block_complete(
                    block_id=table_block_id,
                    block_type=BlockType.TABLE,
                    content=full_content,
                    order=current_order,
                    metadata=table_metadata
                )
                current_order += 1

    # =================================================================
    # Helper Methods (Preserved)
    # =================================================================

    async def _run_agent(
        self,
        agent_name: str,
        operation: callable,
        agents_executed: List[AgentExecution],
        result_summary: str
    ) -> Any:
        """Run an agent and track execution"""
        agent_start = time.time()

        try:
            agent = self.agent_registry.get(agent_name)
            result = operation(agent)

            if hasattr(result, '__await__'):
                result = await result

            duration_ms = int((time.time() - agent_start) * 1000)

            agents_executed.append(AgentExecution(
                agent_name=agent_name,
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=True,
                result_summary=result_summary
            ))

            return result

        except Exception as e:
            duration_ms = int((time.time() - agent_start) * 1000)
            self._logger.error(f"{agent_name} failed: {e}")

            agents_executed.append(AgentExecution(
                agent_name=agent_name,
                completed_at=datetime.now(),
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            ))

            raise

    def _generate_direct_response(self, query: str) -> str:
        """Generate a direct response using LLM"""
        prompt = f"You are Analyst, an AI Business Analyst assistant.\nThe user asked: \"{query}\"\nThis query doesn't require data extraction. Provide a helpful, concise response.\nIf you cannot answer without data, politely explain what information you would need."
        messages = [
            {"role": "system", "content": "You are a helpful business analyst assistant."},
            {"role": "user", "content": prompt}
        ]
        response = self.llm_provider.chat(messages, temperature=0.7, max_tokens=300)
        return response.strip()

    def _finalize_result(
        self,
        execution_result: Dict[str, Any],
        decision: ExecutionDecision,
        agents_executed: List[AgentExecution],
        start_time: float
    ) -> OrchestrationResult:
        """Package execution results into OrchestrationResult"""
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Handle direct responses
        if execution_result.get("_direct_response"):
            return OrchestrationResult(
                success=True,
                data=execution_result,
                query_analysis=self._create_query_analysis(decision, "direct"),
                execution_plan=self._create_execution_plan(decision),
                agents_executed=agents_executed,
                total_time_ms=elapsed_ms,
                confidence_score=decision.confidence,
                retry_count=0,
                needs_clarification=False
            )

        # Handle clarification requests
        if execution_result.get("status") == "needs_clarification":
            data = execution_result.get("data", {})
            clarification = execution_result.get("clarification_question", "Could you provide more details?")

            return OrchestrationResult(
                success=False,
                data=data,
                query_analysis=self._create_query_analysis(decision, "needs_clarification"),
                execution_plan=self._create_execution_plan(decision),
                agents_executed=agents_executed,
                total_time_ms=elapsed_ms,
                confidence_score=0.0,
                retry_count=execution_result.get("retry_count", 0),
                needs_clarification=True,
                clarification_question=clarification
            )

        # Handle normal completion
        data = execution_result.get("data", {})
        validation = execution_result.get("validation")

        # Calculate confidence
        if validation:
            confidence = validation.confidence_score if hasattr(validation, 'confidence_score') else validation.get('confidence_score', 0.7)
        else:
            confidence = decision.confidence if decision else 0.0

        # Determine success
        has_data = self._has_meaningful_data(data)
        success = has_data and confidence >= 0.3

        return OrchestrationResult(
            success=success,
            data=data,
            query_analysis=self._create_query_analysis(decision, "complete"),
            execution_plan=self._create_execution_plan(decision),
            agents_executed=agents_executed,
            total_time_ms=elapsed_ms,
            confidence_score=confidence,
            retry_count=execution_result.get("retry_count", 0),
            needs_clarification=False,
            metadata={
                "strategy": decision.strategy,
                "estimated_cost": decision.estimated_cost
            }
        )

    def _has_meaningful_data(self, data: Any) -> bool:
        """Check if data contains meaningful results"""
        if not data:
            return False
        if isinstance(data, dict):
            return any(
                len(v) > 0 if isinstance(v, list) else v is not None
                for k, v in data.items()
                if not k.startswith("_") and k not in ["needs_clarification", "clarification_question"]
            )
        if hasattr(data, 'data'):
            return self._has_meaningful_data(data.data)
        return True

    def _create_query_analysis(self, decision: ExecutionDecision, status: str) -> QueryAnalysis:
        """Create QueryAnalysis from decision"""
        complexity_map = {
            "direct": QueryComplexity.SIMPLE,
            "simple": QueryComplexity.SIMPLE,
            "complex": QueryComplexity.COMPLEX
        }
        intent_map = {
            "direct": QueryIntent.META,
            "simple": QueryIntent.SEARCH,
            "complex": QueryIntent.ANALYTICS
        }
        return QueryAnalysis(
            complexity=complexity_map.get(decision.strategy, QueryComplexity.MEDIUM),
            intent=intent_map.get(decision.strategy, QueryIntent.SEARCH),
            entities_mentioned=[],
            filters_detected=[],
            clarity_score=decision.confidence,
            requires_optimization=not decision.skip_optimization,
            estimated_steps=len(decision.agents_needed) or 1,
            reasoning=decision.reasoning
        )

    def _create_execution_plan(self, decision: ExecutionDecision) -> ExecutionPlan:
        """Create ExecutionPlan from decision"""
        strategy_map = {
            "direct": ExtractorStrategy.STATIC,
            "simple": ExtractorStrategy.STATIC,
            "complex": ExtractorStrategy.STATIC
        }
        validation_map = {
            "direct": ValidationLevel.NONE,
            "simple": ValidationLevel.NONE,
            "complex": ValidationLevel.SEMANTIC
        }
        return ExecutionPlan(
            should_optimize_query=not decision.skip_optimization,
            extractor_strategy=strategy_map.get(decision.strategy, ExtractorStrategy.STATIC),
            validation_level=validation_map.get(decision.strategy, ValidationLevel.NONE),
            max_retries=decision.max_retries,
            confidence_threshold=0.7,
            reasoning=decision.reasoning,
            estimated_cost=decision.estimated_cost
        )

    def _create_error_result(
        self,
        error: str,
        agents_executed: List[AgentExecution],
        elapsed_ms: int
    ) -> OrchestrationResult:
        """Create error result"""
        return OrchestrationResult(
            success=False,
            data={"_error": error},
            query_analysis=QueryAnalysis(
                complexity=QueryComplexity.SIMPLE,
                intent=QueryIntent.SEARCH,
                clarity_score=0.0,
                requires_optimization=False,
                estimated_steps=1,
                reasoning=f"Error: {error}"
            ),
            execution_plan=ExecutionPlan(
                should_optimize_query=False,
                extractor_strategy=ExtractorStrategy.STATIC,
                validation_level=ValidationLevel.NONE,
                reasoning="Error occurred"
            ),
            agents_executed=agents_executed,
            total_time_ms=elapsed_ms,
            confidence_score=0.0,
            metadata={"error": error}
        )

    def _update_stats(self, elapsed_ms: int):
        """Update performance statistics"""
        total = self.stats["total_queries"]
        if total == 1:
            self.stats["avg_time_ms"] = elapsed_ms
        else:
            self.stats["avg_time_ms"] = int(
                (self.stats["avg_time_ms"] * (total - 1) + elapsed_ms) / total
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        total = self.stats["total_queries"]
        if total == 0:
            return self.stats
        return {
            **self.stats,
            "direct_response_rate": self.stats["direct_responses"] / total if total > 0 else 0,
            "simple_execution_rate": self.stats["simple_executions"] / total if total > 0 else 0,
            "complex_execution_rate": self.stats["complex_executions"] / total if total > 0 else 0
        }

    def _generate_intro_text(self, data: Dict[str, Any]) -> str:
        """Generate introductory text based on extracted data"""
        result_counts = []
        for key, value in data.items():
            if not key.startswith("_") and isinstance(value, list):
                count = len(value)
                if count > 0:
                    result_counts.append(f"{count} {key}")

        if not result_counts:
            return "I couldn't find any results matching your query."

        results_text = ", ".join(result_counts)
        return f"I found {results_text} matching your query."

    def _build_result_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build result summary metadata for conversation state persistence"""
        result_summary = {}

        for key, value in data.items():
            if key.startswith("_") or not isinstance(value, list):
                continue

            value_as_dicts = []
            for item in value:
                if hasattr(item, 'model_dump'):
                    value_as_dicts.append(item.model_dump())
                elif hasattr(item, 'dict'):
                    value_as_dicts.append(item.dict())
                elif isinstance(item, dict):
                    value_as_dicts.append(item)

            if key == "companies" and value_as_dicts:
                result_summary["company.list"] = {
                    "company_names": [c.get("name", "") for c in value_as_dicts],
                    "company_ids": [c.get("id", "") for c in value_as_dicts]
                }
            elif key == "people" and value_as_dicts:
                people_names = []
                for p in value_as_dicts:
                    if "name" in p:
                        people_names.append(p["name"])
                    else:
                        first = p.get("firstName", "")
                        last = p.get("lastName", "")
                        people_names.append(f"{first} {last}".strip())

                result_summary["people.list"] = {
                    "people_names": people_names,
                    "people_ids": [p.get("id", "") for p in value_as_dicts]
                }
            elif key == "emails" and value_as_dicts:
                result_summary["emails.list"] = {
                    "email_ids": [e.get("message_id") or e.get("id", "") for e in value_as_dicts]
                }

        return result_summary

    def _should_show_table(self, query: str, data: Dict[str, Any]) -> bool:
        """Determine if query should return a table or natural language response"""
        query_lower = query.lower()
        
        table_indicators = ["show me all", "show all", "list all", "give me all", "get all", "list of", "list the", "show the list", "export", "download", "table", "show me the", "what are all"]
        text_indicators = ["how many", "how much", "who is", "what is", "tell me about", "describe", "explain", "what does", "summary", "summarize"]

        if any(indicator in query_lower for indicator in table_indicators):
            return True
        if any(indicator in query_lower for indicator in text_indicators):
            return False

        total_items = sum(len(v) for v in data.values() if isinstance(v, list) and not str(v).startswith("_"))
        return total_items > 10

    async def _generate_natural_language_response(self, query: str, data: Dict[str, Any]) -> str:
        """Generate a natural language response using LLM"""
        processed_data = {}
        for key, value in data.items():
            if key.startswith("_") or not isinstance(value, list):
                continue
            
            value_as_dicts = []
            for item in value:
                if hasattr(item, 'model_dump'):
                    value_as_dicts.append(item.model_dump())
                elif hasattr(item, 'dict'):
                    value_as_dicts.append(item.dict())
                elif isinstance(item, dict):
                    value_as_dicts.append(item)
            
            if value_as_dicts:
                processed_data[key] = value_as_dicts

        prompt = f"""You are a helpful business intelligence assistant. Generate a concise, natural language response to the user's query based on the data provided.
User Query: {query}
Data Found:
{json.dumps(processed_data, indent=2)}
Instructions:
- Answer the user's specific question directly
- Be concise but informative
- For "how many" questions, give the count and maybe mention a few examples
- For "who is" or "what is" questions, provide specific details
- For small lists (≤5 items), mention them by name
- For larger lists, mention count and first few examples
- Use natural, conversational language
- Don't use phrases like "based on the data" or "according to the information"
- Just answer as if you know this information
Response:"""

        try:
            response = await self.llm_provider.complete(prompt=prompt, max_tokens=300, temperature=0.3)
            return response.strip()
        except Exception as e:
            self._logger.error(f"Failed to generate natural language response: {e}")
            return self._generate_intro_text(data)

    def _generate_user_friendly_status(self, query: str, decision: 'ExecutionDecision', workspace_id: str) -> str:
        """Generate user-friendly status message"""
        query_lower = query.lower()
        if any(word in query_lower for word in ["company", "companies", "organization"]):
            entity_type = "companies"
        elif any(word in query_lower for word in ["people", "person", "contact", "who"]):
            entity_type = "contacts"
        elif any(word in query_lower for word in ["email", "message", "conversation"]):
            entity_type = "conversations"
        elif any(word in query_lower for word in ["interaction", "meeting", "call"]):
            entity_type = "interactions"
        else:
            entity_type = "data"

        if decision.strategy == "direct":
            return "Processing your question..."
        elif decision.strategy == "simple":
            status_messages = {
                "companies": "Searching your workspace for companies...",
                "contacts": "Looking through your contacts...",
                "conversations": "Analyzing recent conversations...",
                "interactions": "Reviewing interactions in your workspace...",
                "data": "Searching your workspace..."
            }
            return status_messages.get(entity_type, "Searching your workspace...")
        elif decision.strategy == "complex":
            status_messages = {
                "companies": "Analyzing company data across your workspace...",
                "contacts": "Searching and analyzing your contacts...",
                "conversations": "Deep-diving into conversation history...",
                "interactions": "Analyzing interaction patterns...",
                "data": "Performing comprehensive data analysis..."
            }
            return status_messages.get(entity_type, "Analyzing your data...")
        
        return "Working on your request..."

    def _generate_meta_response(self, meta_type: str) -> str:
        """Generate response for meta queries"""
        responses = {
            "greeting": "Hello! I'm Analyst, your AI business intelligence assistant. I can help you search through your companies, people, and interactions. What would you like to know?",
            "help": "I can help you find information about companies, people, emails, and interactions in your workspace. Just ask me questions like 'Show me drone companies' or 'Find recent emails from John'.",
            "introduction": "I'm Analyst, an AI-powered business intelligence assistant. I can search and analyze your business data to help you find insights quickly."
        }
        return responses.get(meta_type, "How can I help you today?")
