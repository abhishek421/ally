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
import re
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
from src.application.services.blocks.entity_models import (
    CompanyEntity,
    PersonEntity,
    DealEntity,
    CompanyReference,
    GroupReference,
    EntityType
)


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
    generated_csv: Optional[str]  # LLM-generated CSV response (fallback)
    primary_entity_type: Optional[str]  # Detected entity type (companies, people, etc.)
    response_plan: List[Dict[str, Any]]  # LLM-planned response blocks
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
        workflow.add_node("generate_query_csv", self.node_generate_query_csv)
        workflow.add_node("plan_response", self.node_plan_response)
        
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
        
        # Direct path -> Response Planning
        workflow.add_edge("handle_direct", "plan_response")

        # Data path -> Enrichment -> Extraction
        workflow.add_edge("enrich_context", "extract_data")
        
        # After extraction -> Route based on strategy/result
        workflow.add_conditional_edges(
            "extract_data",
            self._route_after_extraction,
            {
                "simple": "generate_query_csv",
                "complex": "validate_result",
                "clarify": "plan_response" # Pass through to response planning (which handles clarification status)
            }
        )
        
        # After validation -> Route based on outcome
        workflow.add_conditional_edges(
            "validate_result",
            self._route_after_validation,
            {
                "success": "generate_query_csv",
                "retry": "extract_data",
                "clarify": "plan_response"
            }
        )
        
        # After CSV generation -> Response planning
        workflow.add_edge("generate_query_csv", "plan_response")
        
        # End
        workflow.add_edge("plan_response", END)
        
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

    async def node_generate_query_csv(self, state: AgentState) -> Dict[str, Any]:
        """
        Node: Generate a CSV response that visualizes the answer to the query
        
        This uses LLM to analyze the query and all extracted data, then generates
        a NEW CSV table structure that best answers the query (not just formatting raw data).
        """
        self._logger.info("GENERATE CSV: Creating query-response CSV from extracted data")
        
        extraction_result = state.get('extraction_result', {})
        user_query = state['user_query']
        
        # Check if we have meaningful data
        if not self._has_meaningful_data(extraction_result):
            self._logger.warning("No meaningful data to generate CSV from")
            return {"generated_csv": None}
        
        # Prepare all extracted data for context
        all_data = {}
        for key, value in extraction_result.items():
            if key.startswith("_"):
                continue
                
            if isinstance(value, list) and len(value) > 0:
                # Convert Pydantic models to dicts
                value_as_dicts = []
                for item in value:
                    if hasattr(item, 'model_dump'):
                        value_as_dicts.append(item.model_dump())
                    elif hasattr(item, 'dict'):
                        value_as_dicts.append(item.dict())
                    elif isinstance(item, dict):
                        value_as_dicts.append(item)
                else:
                        # Skip non-serializable items
                        continue
                
                if value_as_dicts:
                    all_data[key] = value_as_dicts
        
        if not all_data:
            self._logger.warning("No serializable data found for CSV generation")
            return {"generated_csv": None}
        
        # Generate CSV using LLM
        try:
            csv_content = await self._generate_query_response_csv(user_query, all_data)
            return {"generated_csv": csv_content}
        except Exception as e:
            self._logger.error(f"Failed to generate query CSV: {e}", exc_info=True)
            return {"generated_csv": None}

    async def _generate_query_response_csv(self, query: str, all_data: Dict[str, List[Dict]]) -> str:
        """
        Use LLM to generate a CSV that answers the query using all extracted data as context
        
        This is different from formatting - it generates a NEW table structure that
        best visualizes the answer to the query.
        """
        # Serialize all data for context
        serialized_data = json.dumps(all_data, indent=2, default=str)
        
        # Build comprehensive prompt
        prompt = f"""You are a Senior Business Intelligence Analyst. Your task is to generate a CSV table that BEST visualizes the answer to the user's query based on the provided raw data.

User Query: "{query}"

Raw Data Extracted:
{serialized_data}

INSTRUCTIONS:
1. Analyze the User Query carefully - what is the user really asking for?
2. Examine ALL the raw data provided (companies, people, emails, interactions, etc.)
3. Generate a CSV table that DIRECTLY ANSWERS the query:
   - If the query asks for a list: Create a clean, relevant list table
   - If the query asks for counts/summaries: Aggregate and show summary statistics
   - If the query asks for comparisons: Create a comparison table
   - If the query asks for specific details: Create a focused detail table
   - If the query asks for relationships: Show how entities relate to each other
4. DO NOT just dump all raw data. Create a SPECIFIC response table that answers the query.
5. Choose the most relevant columns that answer the question.
6. Use human-readable column names (e.g., "Company Name" not "company_name").
7. Format values appropriately (dates, currency, percentages).
8. If aggregating, show meaningful metrics (counts, sums, averages, etc.).

OUTPUT REQUIREMENTS:
- Return ONLY valid CSV content (header row + data rows)
- NO markdown formatting (no ```csv or ``` blocks)
- NO introductory text or explanations
- Use comma (,) as delimiter
- Quote values that contain commas
- Ensure all rows have the same number of columns as the header

Generate the CSV table now:"""

        messages = [
            {"role": "system", "content": "You are an expert at creating business intelligence tables. Generate clean, well-structured CSV that directly answers user queries."},
            {"role": "user", "content": prompt}
        ]

        try:
            # Use chat method (synchronous, but we're in async context)
            response = self.llm_provider.chat(
                messages=messages,
                max_tokens=4000,
                temperature=0.2
            )
            
            # Clean the response (remove markdown if present)
            csv_content = self._clean_csv_output(response)
            return csv_content
            
        except Exception as e:
            self._logger.error(f"LLM CSV generation failed: {e}")
            raise

    def _clean_csv_output(self, text: str) -> str:
        """Remove markdown formatting and clean CSV output"""
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```csv or ```) and last line (```)
            if len(lines) >= 2:
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
        
        # Remove any leading/trailing whitespace
        text = text.strip()
        
        return text

    async def node_plan_response(self, state: AgentState) -> Dict[str, Any]:
        """
        Node: Plan the response structure using LLM.
        Decides which blocks (Text, Table) to use and in what order.
        """
        self._logger.info("PLAN RESPONSE: Planning response structure with LLM")
        
        user_query = state['user_query']
        extraction_result = state.get('extraction_result', {})
        generated_csv = state.get('generated_csv')
        
        # Case 1: Direct Response (already has final_response)
        if state.get('final_response') and state['final_response'].get('_direct_response'):
            return {
                "response_plan": [
                    {"type": "text", "content": state['final_response'].get('response', '')}
                ],
                "final_response": state['final_response']
            }
            
        # Case 2: Clarification needed
        needs_clarification = False
        clarification_q = None
        
        if extraction_result.get("needs_clarification"):
            needs_clarification = True
            clarification_q = extraction_result.get("clarification_question")
        else:
            validation_result = state.get('validation_result')
            if validation_result:
                next_action = validation_result.next_action if hasattr(validation_result, 'next_action') else validation_result.get('next_action')
                if next_action in ["CLARIFY", NextAction.CLARIFY.value]:
                    needs_clarification = True
                    clarification_q = "I need some clarification to answer your question."

        if needs_clarification:
                    return {
                "response_plan": [
                    {"type": "text", "content": clarification_q or "Could you provide more details?"}
                ],
                "final_response": {
                        "status": "needs_clarification",
                        "data": extraction_result,
                    "clarification_question": clarification_q,
                    "retry_count": state.get('retry_count', 0)
                }
            }
            
        # Case 3: Standard Data Response - Detect entity type and plan blocks
        # Detect primary entity type (companies, people, deals)
        primary_entity_type = self._detect_primary_entity_type(extraction_result)
        
        # Build data summary for context
        data_summary = self._build_data_summary(extraction_result, generated_csv)
        
        # Generate response plan based on entity type
        if primary_entity_type in ["companies", "people", "deals"]:
            # Use structured ENTITY_LIST for known entity types
            response_plan = await self._plan_entity_list_response(
                user_query, 
                primary_entity_type, 
                extraction_result,
                data_summary
            )
        else:
            # Fallback to TABLE (CSV) for mixed/aggregated/unknown data
            response_plan = await self._plan_table_response(
                user_query,
                data_summary,
                generated_csv
            )
        
        return {
            "primary_entity_type": primary_entity_type,
            "response_plan": response_plan,
            "final_response": {
                "status": "complete",
                "data": extraction_result,
                "validation": state.get('validation_result'),
                "generated_csv": generated_csv,
                "entity_type": primary_entity_type,
                "retry_count": state.get('retry_count', 0)
            }
        }

    def _build_data_summary(self, extraction_result: Dict[str, Any], generated_csv: Optional[str]) -> Dict[str, Any]:
        """Build a summary of extracted data for the planner"""
        summary = {
            "raw_data_counts": {},
            "csv_info": None
        }
        
        # Count raw data items
        for key, value in extraction_result.items():
            if key.startswith("_") or not isinstance(value, list):
                continue
            summary["raw_data_counts"][key] = len(value)
        
        # Extract CSV info if available
        if generated_csv:
            lines = generated_csv.strip().split('\n')
            if len(lines) > 1:
                header = lines[0]
                row_count = len(lines) - 1  # Exclude header
                summary["csv_info"] = {
                    "row_count": row_count,
                    "header": header,
                    "preview": '\n'.join(lines[:min(4, len(lines))])  # First 3 rows + header
                }
        
        return summary

    async def _plan_entity_list_response(
        self,
        query: str,
        entity_type: str,
        extraction_result: Dict[str, Any],
        data_summary: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Plan response with structured ENTITY_LIST block
        
        Args:
            query: User query
            entity_type: "companies", "people", or "deals"
            extraction_result: Raw extraction data
            data_summary: Summary of data
            
        Returns:
            Response plan with text + entity_list blocks
        """
        entities = extraction_result.get(entity_type, [])
        entity_count = len(entities)
        
        # Generate intro text using LLM
        intro_text = await self._generate_entity_intro_text(query, entity_type, entity_count)
        
        # Build response plan
        plan = [
            {
                "type": "text",
                "content": intro_text
            },
            {
                "type": "entity_list",
                "entity_type": entity_type,
                "entities": entities,  # Will be transformed to NDJSON during streaming
                "metadata": {
                    "total_count": entity_count,
                    "view_mode": "list"
                }
            }
        ]
        
        return plan

    async def _generate_entity_intro_text(self, query: str, entity_type: str, count: int) -> str:
        """Generate natural intro text for entity lists"""
        
        entity_labels = {
            "companies": "companies",
            "people": "people",
            "deals": "deals"
        }
        
        label = entity_labels.get(entity_type, "items")
        
        prompt = f"""You are a helpful business intelligence assistant. Generate a brief, natural introduction for a list of results.

User Query: "{query}"
Results: {count} {label}

Generate a concise, conversational intro (1-2 sentences max) that:
- Acknowledges what the user asked for
- States the count accurately
- Is friendly and natural (no robotic phrases like "based on available data")
- Leads into the list naturally

Example good intros:
- "I found 7 companies working in the AI domain:"
- "Here are the 3 people from your sales team:"
- "I found 12 companies matching your criteria:"

Your intro:"""

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Generate only the intro text, nothing else."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm_provider.chat(
                messages=messages,
                max_tokens=100,
                temperature=0.3
            )
            return response.strip()
        except Exception as e:
            self._logger.error(f"Failed to generate entity intro: {e}")
            return f"I found {count} {label} matching your query:"

    async def _plan_table_response(
        self,
        query: str,
        data_summary: Dict[str, Any],
        generated_csv: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Plan response with TABLE block (fallback for non-entity data)
        
        This is used for:
        - Mixed entity types
        - Aggregated/analytics queries
        - Custom data that doesn't fit entity schemas
        """
        csv_info = data_summary.get("csv_info")
        raw_counts = data_summary.get("raw_data_counts", {})
        
        # Generate intro text
        if csv_info:
            count = csv_info['row_count']
            intro_text = await self._generate_table_intro_text(query, count, csv_info)
        else:
            intro_text = "Here are the results:"
        
        plan = [
            {
                "type": "text",
                "content": intro_text
            }
        ]
        
        # Add table block if CSV exists
        if generated_csv:
            plan.append({
                "type": "table",
                "content": generated_csv
            })
        
        return plan

    async def _generate_table_intro_text(self, query: str, row_count: int, csv_info: Dict) -> str:
        """Generate intro text for table responses"""
        
        prompt = f"""You are a helpful business intelligence assistant. Generate a brief intro for a data table.

User Query: "{query}"
Table: {row_count} rows
Columns: {csv_info['header']}

Generate a concise intro (1 sentence) that:
- Acknowledges the query
- States the row count
- Is natural and conversational

Your intro:"""

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Generate only the intro text."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm_provider.chat(
                messages=messages,
                max_tokens=100,
                temperature=0.3
            )
            return response.strip()
        except Exception as e:
            self._logger.error(f"Failed to generate table intro: {e}")
            return f"Here are the {row_count} results:"

    async def _generate_response_plan(self, query: str, data_summary: Dict[str, Any], generated_csv: Optional[str]) -> List[Dict[str, Any]]:
        """
        Use LLM to generate a response plan (list of blocks: text, table)
        
        The LLM should:
        1. Analyze the query
        2. Look at the CSV (if available) to get accurate counts
        3. Generate appropriate text that references the CSV accurately
        4. Decide the order of blocks
        """
        csv_info = data_summary.get("csv_info")
        raw_counts = data_summary.get("raw_data_counts", {})
        
        # Build prompt
        prompt = f"""You are a Business Intelligence Assistant. Plan the response structure for a user query.

User Query: "{query}"

Available Data:
"""
        
        if csv_info:
            prompt += f"""
Generated CSV Table:
- Rows: {csv_info['row_count']}
- Header: {csv_info['header']}
- Preview:
{csv_info['preview']}

IMPORTANT: The CSV table is the SOURCE OF TRUTH. If the CSV shows 3 companies, say "3 companies" in your text, NOT the raw data count.
"""
        else:
            prompt += f"""
Raw Data Counts: {raw_counts}
(No CSV table was generated)
"""
        
        prompt += """
Your task:
1. Generate a natural language TEXT response that accurately describes the results.
2. If a CSV table exists, reference it accurately (e.g., "Here are the 3 companies..." if CSV has 3 rows).
3. Decide if you need a TABLE block (if CSV exists).
4. Choose the order: [text, table] or [table, text] or just [text] or just [table].

Output Format (JSON):
{
  "blocks": [
    {"type": "text", "content": "Your natural language response here..."},
    {"type": "table", "use_csv": true}
  ]
}

Rules:
- Be accurate about counts based on the CSV, not raw data
- Don't repeat information that's in the table
- Be conversational and helpful
- If no CSV, just provide text response

JSON Response:"""

        messages = [
            {"role": "system", "content": "You are an expert at planning business intelligence responses. Always output valid JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm_provider.chat(
                messages=messages,
                max_tokens=500,
                temperature=0.3
            )
            
            # Parse JSON response
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                plan_data = json.loads(json_str)
                blocks = plan_data.get("blocks", [])
                
                # Ensure table block references the CSV
                for block in blocks:
                    if block.get("type") == "table" and block.get("use_csv"):
                        block["content"] = generated_csv  # Attach CSV content
                
                return blocks
            else:
                # Fallback: simple text response
                self._logger.warning("Failed to parse JSON from LLM response, using fallback")
                return [{"type": "text", "content": response.strip()}]
                
        except Exception as e:
            self._logger.error(f"Failed to generate response plan: {e}", exc_info=True)
            # Fallback plan
            plan = []
            if generated_csv:
                plan.append({"type": "text", "content": f"I found the following results for your query: {query}"})
                plan.append({"type": "table", "content": generated_csv})
            else:
                plan.append({"type": "text", "content": "I've processed your query, but couldn't generate a response table."})
            return plan

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
            "generated_csv": None,
            "primary_entity_type": None,
            "response_plan": [],
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
            "generated_csv": None,
            "primary_entity_type": None,
            "response_plan": [],
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
                        
                    elif node_name == "plan_response":
                        # Execute the response plan dynamically
                        response_plan = node_state.get('response_plan', [])
                        final_response = node_state.get('final_response', {})
                        
                        # Build result summary for conversation state
                        data = final_response.get('data', {})
                        result_summary = self._build_result_summary(data) if data else {}
                        
                        # Execute each block in the plan
                        for block in response_plan:
                            block_type = block.get('type')
                            
                            if block_type == 'text':
                                # Text block
                                content = block.get('content', '')
                                metadata = {
                                    "type": "planned_response",
                                    "query_context": {"result_summary": result_summary} if result_summary else {}
                                }
                                
                                # Add specific type if it's a direct/clarification response
                                if final_response.get('_direct_response'):
                                    metadata["type"] = "direct_response"
                                elif final_response.get('status') == "needs_clarification":
                                    metadata["type"] = "clarification"
                                
                                yield self._create_block_event(
                                    BlockType.TEXT,
                                    content,
                                    block_order,
                                    metadata
                                )
                                block_order += 1
                                
                            elif block_type == 'table':
                                # Table block (using generated CSV)
                                csv_content = block.get('content')
                                if csv_content:
                                    table_block_id = str(uuid4())
                                    table_metadata = {
                                        "data_type": "query_response",
                                        "row_count": len(csv_content.split('\n')) - 1 if csv_content else 0,
                                        "formatting_method": "llm_generated"
                                    }
                                    
                                    yield StreamEvent.block_start(
                                        block_id=table_block_id,
                                        block_type=BlockType.TABLE,
                                        order=block_order,
                                        metadata=table_metadata
                                    )
                                    
                                    # Stream the CSV content
                                    yield StreamEvent.block_delta(
                                        block_id=table_block_id,
                                        content=csv_content
                                    )
                                    
                                    yield StreamEvent.block_complete(
                                        block_id=table_block_id,
                                        block_type=BlockType.TABLE,
                                        content=csv_content,
                                        order=block_order,
                                        metadata=table_metadata
                                    )
                                    block_order += 1
                                    
                            elif block_type == 'entity_list':
                                # Entity list block (structured entities as NDJSON)
                                entity_type = block.get('entity_type')
                                raw_entities = block.get('entities', [])
                                block_metadata = block.get('metadata', {})
                                
                                if raw_entities:
                                    # Transform to entity models
                                    entity_models = self._transform_to_entity_models(entity_type, raw_entities)
                                    
                                    # Create NDJSON content (one JSON object per line)
                                    ndjson_lines = []
                                    for entity in entity_models:
                                        ndjson_lines.append(entity.model_dump_json())
                                    ndjson_content = "\n".join(ndjson_lines)
                                    
                                    # Stream the entity list
                                    list_block_id = str(uuid4())
                                    
                                    # Prepare metadata
                                    stream_metadata = {
                                        "entity_type": entity_type,
                                        "total_count": len(entity_models),
                                        "items_count": len(entity_models),
                                        "view_mode": block_metadata.get("view_mode", "list")
                                    }
                                    
                                    yield StreamEvent.block_start(
                                        block_id=list_block_id,
                                        block_type=BlockType.ENTITY_LIST,
                                        order=block_order,
                                        metadata=stream_metadata
                                    )
                                    
                                    # Stream entities as NDJSON
                                    # Option 1: Stream all at once (simpler, works for most cases)
                                    yield StreamEvent.block_delta(
                                        block_id=list_block_id,
                                        content=ndjson_content
                                    )
                                    
                                    # Option 2: Stream one entity per delta (more real-time feel)
                                    # Uncomment below to stream incrementally:
                                    # for line in ndjson_lines:
                                    #     yield StreamEvent.block_delta(
                                    #         block_id=list_block_id,
                                    #         content=line + "\n"
                                    #     )
                                    
                                    yield StreamEvent.block_complete(
                                        block_id=list_block_id,
                                        block_type=BlockType.ENTITY_LIST,
                                        content=ndjson_content,
                                        order=block_order,
                                        metadata=stream_metadata
                                    )
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
                    user_query=user_query,
                    mode="generative"
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

    # ============================================================================
    # Entity Detection & Transformation
    # ============================================================================

    def _detect_primary_entity_type(self, extraction_result: Dict[str, Any]) -> Optional[str]:
        """
        Detect the primary entity type in extraction results
        
        Returns: "companies", "people", "deals", or None
        """
        entity_counts = {}
        
        for entity_type in ["companies", "people", "deals"]:
            items = extraction_result.get(entity_type, [])
            if isinstance(items, list) and len(items) > 0:
                entity_counts[entity_type] = len(items)
        
        if not entity_counts:
            return None
        
        # Return type with most items
        return max(entity_counts, key=entity_counts.get)

    def _transform_to_entity_models(
        self, 
        entity_type: str, 
        raw_entities: List[Any]
    ) -> List[Union[CompanyEntity, PersonEntity, DealEntity]]:
        """
        Transform raw CRM data to frontend entity models
        
        Args:
            entity_type: "companies", "people", or "deals"
            raw_entities: List of raw entity objects from extractor
            
        Returns:
            List of typed entity models ready for NDJSON serialization
        """
        if entity_type == "companies":
            return [self._to_company_entity(e) for e in raw_entities]
        elif entity_type == "people":
            return [self._to_person_entity(e) for e in raw_entities]
        elif entity_type == "deals":
            return [self._to_deal_entity(e) for e in raw_entities]
        else:
            self._logger.warning(f"Unknown entity type: {entity_type}")
            return []

    def _extract_contact_value(self, data: Any) -> Optional[str]:
        """Helper to extract email/phone value from various formats (string, list, object)"""
        if not data:
            return None
            
        # If it's already a string, return it
        if isinstance(data, str):
            return data
            
        # If it's a list (Prisma relation)
        if isinstance(data, list):
            if not data:
                return None
            
            # Try to find primary
            primary = None
            for item in data:
                if isinstance(item, dict) and item.get("isPrimary"):
                    primary = item
                    break
                elif hasattr(item, "isPrimary") and getattr(item, "isPrimary"):
                    primary = item
                    break
            
            # Fallback to first item
            target = primary if primary else data[0]
            
            if isinstance(target, dict):
                return target.get("value")
            else:
                return getattr(target, "value", None)
        
        # If it's a single object with value field
        if isinstance(data, dict):
            return data.get("value")
        elif hasattr(data, "value"):
            return getattr(data, "value", None)
                
        return None

    def _to_company_entity(self, company: Any) -> CompanyEntity:
        """Transform Company model to CompanyEntity for frontend"""
        
        # Handle both dict and object formats
        if isinstance(company, dict):
            company_id = company.get("id", "")
            name = company.get("name", "")
            logo = company.get("logo_url") or company.get("logo")
            email_raw = company.get("email")
            phone_raw = company.get("phoneNumber") or company.get("phone") # Support both field names
            website = company.get("website") or company.get("url")
            industry = company.get("industry")
            description = company.get("description")
        else:
            company_id = getattr(company, 'id', '')
            name = getattr(company, 'name', '')
            logo = getattr(company, 'logo_url', None) or getattr(company, 'logo', None)
            email_raw = getattr(company, 'email', None)
            phone_raw = getattr(company, 'phoneNumber', None) or getattr(company, 'phone', None)
            website = getattr(company, 'website', None) or getattr(company, 'url', None)
            industry = getattr(company, 'industry', None)
            description = getattr(company, 'description', None)
        
        # Extract simple string values for contact info
        email = self._extract_contact_value(email_raw)
        phone = self._extract_contact_value(phone_raw)

        # TODO: Enrich with peopleCount and groups in future phase
        # For now, we'll use placeholder values
        people_count = 0
        groups = []
        
        # Build metadata with available fields
        metadata = {}
        if website:
            # specialized handling for URL list if coming from Prisma
            if isinstance(website, list) and website:
                metadata["website"] = self._extract_contact_value(website)
            else:
                metadata["website"] = website
        if industry:
            metadata["industry"] = industry
        if description:
            metadata["description"] = description
        
        return CompanyEntity(
            id=str(company_id),
            name=name,
            logo=logo,
            email=email,
            phone=phone,
            peopleCount=people_count,
            groups=groups,
            metadata=metadata if metadata else None
        )

    def _to_person_entity(self, person: Any) -> PersonEntity:
        """Transform Person model to PersonEntity for frontend"""
        
        # Handle both dict and object formats
        if isinstance(person, dict):
            person_id = person.get("id", "")
            first_name = person.get("firstName", "")
            last_name = person.get("lastName", "")
            name = person.get("name") or f"{first_name} {last_name}".strip()
            image = person.get("image") or person.get("avatar_url")
            email_raw = person.get("email")
            phone_raw = person.get("phoneNumber") or person.get("phone")
            role = person.get("role") or person.get("title") or person.get("jobTitle")
            company_data = person.get("company")
        else:
            person_id = getattr(person, 'id', '')
            first_name = getattr(person, 'firstName', '') or getattr(person, 'first_name', '')
            last_name = getattr(person, 'lastName', '') or getattr(person, 'last_name', '')
            name = getattr(person, 'name', None) or f"{first_name} {last_name}".strip()
            image = getattr(person, 'image', None) or getattr(person, 'avatar_url', None)
            email_raw = getattr(person, 'email', None)
            phone_raw = getattr(person, 'phoneNumber', None) or getattr(person, 'phone', None)
            role = getattr(person, 'role', None) or getattr(person, 'title', None) or getattr(person, 'jobTitle', None)
            company_data = getattr(person, 'company', None)
        
        # Extract simple string values for contact info
        email = self._extract_contact_value(email_raw)
        phone = self._extract_contact_value(phone_raw)

        # Transform company reference if available
        company_ref = None
        if company_data:
            if isinstance(company_data, dict):
                company_ref = CompanyReference(
                    id=str(company_data.get("id", "")),
                    name=company_data.get("name", ""),
                    imageUrl=company_data.get("imageUrl") or company_data.get("logo")
                )
            elif hasattr(company_data, 'id'):
                company_ref = CompanyReference(
                    id=str(company_data.id),
                    name=getattr(company_data, 'name', ''),
                    imageUrl=getattr(company_data, 'logo_url', None)
                )
        
        # TODO: Enrich with groups in future phase
        groups = []
        
        # Build metadata
        metadata = {}
        if role:
            metadata["role"] = role
        
        return PersonEntity(
            id=str(person_id),
            name=name,
            firstName=first_name or None,
            lastName=last_name or None,
            image=image,
            email=email,
            phone=phone,
            role=role,
            company=company_ref,
            groups=groups,
            metadata=metadata if metadata else None
        )

    def _to_deal_entity(self, deal: Any) -> DealEntity:
        """Transform Deal model to DealEntity for frontend (future support)"""
        
        # Handle both dict and object formats
        if isinstance(deal, dict):
            deal_id = deal.get("id", "")
            name = deal.get("name", "")
            value = deal.get("value", 0)
            currency = deal.get("currency", "USD")
            stage = deal.get("stage", "")
            probability = deal.get("probability")
            close_date = deal.get("closeDate") or deal.get("close_date")
            company_data = deal.get("company")
            owner_data = deal.get("owner")
        else:
            deal_id = getattr(deal, 'id', '')
            name = getattr(deal, 'name', '')
            value = getattr(deal, 'value', 0)
            currency = getattr(deal, 'currency', 'USD')
            stage = getattr(deal, 'stage', '')
            probability = getattr(deal, 'probability', None)
            close_date = getattr(deal, 'close_date', None)
            company_data = getattr(deal, 'company', None)
            owner_data = getattr(deal, 'owner', None)
        
        # Transform company reference
        company_ref = None
        if company_data:
            if isinstance(company_data, dict):
                company_ref = CompanyReference(
                    id=str(company_data.get("id", "")),
                    name=company_data.get("name", ""),
                    imageUrl=company_data.get("imageUrl")
                )
        
        # Transform owner
        owner = None
        if owner_data:
            if isinstance(owner_data, dict):
                owner = {
                    "id": str(owner_data.get("id", "")),
                    "name": owner_data.get("name", "")
                }
        
        groups = []
        
        return DealEntity(
            id=str(deal_id),
            name=name,
            value=float(value),
            currency=currency,
            stage=stage,
            probability=probability,
            closeDate=close_date,
            company=company_ref,
            owner=owner,
            groups=groups
        )
