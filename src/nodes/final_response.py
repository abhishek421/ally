"""
Final Response node for the LangGraph agent pipeline.

This module exports the final_response_node function, which is responsible for:
1. Converting aggregated execution results into UI-friendly format
2. Building structured message blocks for frontend rendering
3. Organizing entity data for display
4. Providing reasoning traces for transparency

The final_response is the last node in the pipeline:
    User Input → Planner → Validator → Executor → Aggregator → Final Response

This module produces the final structured response that the frontend will render.
It does NOT:
- Call the LLM
- Execute tools
- Make decisions
- Perform business logic

It ONLY organizes data into UI blocks:
- Thinking blocks (reasoning traces)
- Tool activity logs
- Entity lists (people, companies, interactions, etc.)
- Markdown summaries

The actual streaming to the frontend is handled by server/http_server.py or
graph-level streaming mechanisms. This node simply prepares the final structure.

UI Block Types:

1. Thinking Block
   - Type: "thinking"
   - Content: Reasoning traces from state.reasoning
   - Purpose: Show the agent's thought process to the user

2. Tool Activity Log Block
   - Type: "tool_log"
   - Content: List of tool executions with status
   - Purpose: Transparency about what tools were called

3. Entity List Blocks
   - Types: "entity_people_list", "entity_company_list", "entity_interactions_list", etc.
   - Content: Structured entity data from aggregator
   - Purpose: Display search results, entity details, etc.

4. Markdown Summary Block
   - Type: "markdown"
   - Content: Human-readable summary with formatting
   - Purpose: Final response text for the user

Return Structure:

The final_response_node returns a dictionary:
{
    "messages": [
        {"type": "thinking", "content": "..."},
        {"type": "tool_log", "content": [...]},
        {"type": "entity_people_list", "content": [...]},
        {"type": "markdown", "content": "### Summary\\n..."}
    ],
    "final_summary": "The markdown content from the last block",
    "entities": {
        "people": [...],
        "companies": [...],
        ...
    },
    "reasoning": ["Planner: ...", "Validator: ...", "Executor: ...", "Aggregator: ..."]
}

This structure is designed to be easily consumed by the frontend for rendering.
"""

from typing import Dict, Any, List

from src.memory.state import AgentState
from src.config.logger import logger
from src.llm.model import call_summarizer

# ========================================
# Constants
# ========================================

# Maximum number of reasoning lines to show in thinking block
MAX_REASONING_LINES = 5

# Map entity types to UI block types
# TODO: Extend this mapping as new entity types are added
ENTITY_BLOCK_TYPE_MAP: Dict[str, str] = {
    "people": "entity_people_list",
    "person": "entity_person_detail",
    "companies": "entity_company_list",
    "company": "entity_company_detail",
    "interactions": "entity_interactions_list",
    "interaction": "entity_interaction_detail",
    "groups": "entity_groups_list",
    "group": "entity_group_detail",
    "group_companies": "entity_group_companies_list",
    "group_people": "entity_group_people_list",
    "workspace": "entity_workspace_detail",
    "workspaces": "entity_workspaces_list",
    "workspace_members": "entity_workspace_members_list",
    "relationship_updated": "entity_relationship_updated",
    "group_membership_updated": "entity_group_membership_updated",
}


# ========================================
# Helper Functions
# ========================================


def _build_thinking_block(state: AgentState, aggregated: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a user-friendly thinking block (NOT technical jargon).
    
    Translates technical reasoning into plain English that business users can understand.
    
    Args:
        state: Agent state containing reasoning traces
        aggregated: Aggregated results with tool activity
    
    Returns:
        Thinking block dictionary with human-friendly content
    """
    # Build human-friendly thinking steps
    human_steps = []
    
    # Check what happened
    tool_log = aggregated.get("tool_activity_log", [])
    merged_results = aggregated.get("merged_results", {})
    plan_summary = aggregated.get("plan_summary", "")
    
    # Translate technical actions to user-friendly language
    if len(tool_log) == 0:
        # No tools executed - agent is reasoning
        if "previous" in plan_summary.lower() or "existing" in plan_summary.lower():
            human_steps.append("Reviewing data I already have...")
        else:
            human_steps.append("Analyzing your request...")
    else:
        # Tools executed - describe what we're doing
        for log in tool_log:
            tool_name = log.get("tool", "")
            status = log.get("status", "")
            
            if "list" in tool_name or "search" in tool_name:
                if "companies" in tool_name:
                    human_steps.append("Looking through your companies...")
                elif "people" in tool_name:
                    human_steps.append("Searching through your contacts...")
                elif "groups" in tool_name:
                    human_steps.append("Checking your groups...")
            elif "get" in tool_name:
                human_steps.append("Fetching details...")
            elif "create" in tool_name:
                human_steps.append("Creating new record...")
            elif "update" in tool_name:
                human_steps.append("Updating information...")
            elif "delete" in tool_name:
                human_steps.append("Removing record...")
            
            if status == "success":
                # Add result summary
                if "companies" in tool_name and "companies" in merged_results:
                    data = merged_results["companies"]
                    if isinstance(data, dict) and "data" in data:
                        count = len(data.get("data", []))
                        total = data.get("meta", {}).get("total", count)
                        human_steps.append(f"Found {total} companies")
                    elif isinstance(data, list):
                        human_steps.append(f"Found {len(data)} companies")
                elif "people" in tool_name and "people" in merged_results:
                    data = merged_results["people"]
                    if isinstance(data, dict) and "data" in data:
                        count = len(data.get("data", []))
                        total = data.get("meta", {}).get("total", count)
                        human_steps.append(f"Found {total} contacts")
                    elif isinstance(data, list):
                        human_steps.append(f"Found {len(data)} contacts")
    
    # Final step
    if merged_results:
        human_steps.append("Preparing results...")
    
    # Join with line breaks (each step on its own line)
    content = "\n".join(human_steps) if human_steps else "Processing your request..."
    
    return {
        "type": "thinking",
        "content": content
    }


def _build_reasoning_fallback(state: AgentState, aggregated: Dict[str, Any]) -> str | None:
    """
    Build a best-effort reasoning summary when no explicit reasoning logs exist.
    
    Leverages plan/execution metadata so the UI still communicates intent.
    """
    lines: List[str] = []
    
    plan = state.plan or {}
    plan_summary = plan.get("summary")
    decision_type = plan.get("decision_type")
    tasks = plan.get("tasks") or []
    
    if plan_summary:
        lines.append(f"Plan: {plan_summary}")
    elif aggregated.get("plan_summary"):
        lines.append(f"Plan: {aggregated['plan_summary']}")
    
    if decision_type and decision_type != "NONE":
        lines.append(f"Decision: {decision_type} flow with {len(tasks)} task(s)")
    elif not lines and plan:
        lines.append("Plan created with no additional details.")
    
    execution_result = state.execution_results or {}
    executor_summary = execution_result.get("summary") or aggregated.get("executor_summary")
    if executor_summary:
        lines.append(f"Execution: {executor_summary}")
    
    raw_results = execution_result.get("results") or aggregated.get("raw_results") or []
    errors = [r.get("error") for r in raw_results if r.get("status") == "error" and r.get("error")]
    if errors:
        lines.append(f"Issues: {errors[0]}")
    
    tool_activity = aggregated.get("tool_activity_log") or []
    if tool_activity:
        success_count = sum(1 for entry in tool_activity if entry.get("status") == "success")
        failure_count = len(tool_activity) - success_count
        lines.append(f"Tools: {success_count} succeeded, {failure_count} failed")
    
    return "\n".join(lines) if lines else None


def _build_tool_log_block(aggregated: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Build a tool activity log block from aggregated data.
    
    Shows which tools were executed and their status for transparency.
    
    Args:
        aggregated: Aggregated data containing tool_activity_log
    
    Returns:
        Tool log block dictionary or None if no tools were executed:
        {
            "type": "tool_log",
            "content": [
                {"tool": "search_people", "status": "success", "timestamp": "..."},
                ...
            ]
        }
    """
    tool_activity_log = aggregated.get("tool_activity_log", [])
    
    if not tool_activity_log:
        return None
    
    return {
        "type": "tool_log",
        "content": tool_activity_log
    }


def _build_entity_blocks(aggregated: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build entity-specific UI blocks from merged results.
    
    Converts each entity type in merged_results into a corresponding
    UI block for frontend rendering.
    
    Args:
        aggregated: Aggregated data containing merged_results
    
    Returns:
        List of entity block dictionaries:
        [
            {"type": "entity_people_list", "content": [...]},
            {"type": "entity_company_list", "content": [...]},
            ...
        ]
    """
    entity_blocks = []
    merged_results = aggregated.get("merged_results", {})
    
    for entity_type, entity_data in merged_results.items():
        # Map entity type to UI block type
        block_type = ENTITY_BLOCK_TYPE_MAP.get(entity_type)
        
        if block_type is None:
            # Entity type not mapped - use generic block
            logger.debug(
                f"Entity type '{entity_type}' not in ENTITY_BLOCK_TYPE_MAP, "
                f"using generic block"
            )
            block_type = f"entity_{entity_type}"
        
        # Create entity block
        entity_block = {
            "type": block_type,
            "content": entity_data
        }
        
        entity_blocks.append(entity_block)
    
    return entity_blocks


async def _build_markdown_summary(aggregated: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
    """
    Build final markdown summary block using LLM.
    
    Uses the summarizer model to generate a natural language response based on:
    - The user's original query (from state)
    - The plan summary
    - The execution results (from aggregated)
    
    Args:
        aggregated: Aggregated data containing summaries and results
        state: Current agent state
    
    Returns:
        Markdown block dictionary
    """
    # Get context
    user_message = state.messages[-1].content if state.messages else ""
    plan_summary = aggregated.get("plan_summary", "")
    merged_results = aggregated.get("merged_results", {})
    tool_log = aggregated.get("tool_activity_log", [])
    
    # Extract metadata counts BEFORE truncating
    entity_counts = {}
    if merged_results:
        for entity_type, entity_data in merged_results.items():
            if isinstance(entity_data, dict):
                # Check for pagination metadata
                if "meta" in entity_data and "total" in entity_data["meta"]:
                    entity_counts[entity_type] = entity_data["meta"]["total"]
                elif "data" in entity_data:
                    entity_counts[entity_type] = len(entity_data.get("data", []))
            elif isinstance(entity_data, list):
                entity_counts[entity_type] = len(entity_data)
    
    # Prepare context for LLM
    context = f"""
User Query: {user_message}

Plan Summary: {plan_summary}

Execution Results:
- Tools executed: {len(tool_log)}
- Entities found: {list(merged_results.keys())}
"""

    # Add entity counts (CRITICAL: These are the TRUE counts)
    if entity_counts:
        context += f"\n\n**EXACT COUNTS** (use these, not what you count in the preview):\n"
        for entity_type, count in entity_counts.items():
            context += f"- {entity_type}: {count} total\n"

    # Add full result details for intelligent analysis
    if merged_results:
        import json
        # For NONE decisions (no tools executed), provide FULL data for LLM reasoning
        # For tool executions, provide summary + preview
        if len(tool_log) == 0:
            # No tools executed - LLM needs to analyze existing data
            results_str = json.dumps(merged_results, default=str)[:8000]  # Larger limit for reasoning
            context += f"\n\n**IMPORTANT**: No new tools were executed. Use your knowledge and reasoning to answer based on this existing data:\n{results_str}"
        else:
            # Tools executed - provide preview (truncated)
            results_str = json.dumps(merged_results, default=str)[:2000]
            context += f"\n\nResult Data Preview (truncated, use EXACT COUNTS above):\n{results_str}"

    # Check for tool failures
    failed_tools = [log for log in tool_log if log.get("status") == "error"]
    has_failures = len(failed_tools) > 0
    all_failed = len(failed_tools) == len(tool_log) if tool_log else False
    
    # Build prompt
    prompt = f"""You are the voice of the CRM AI Copilot.
Generate a helpful, natural language response for the user based on the execution results.

Context:
{context}

Tool Execution Status:
- Total tools executed: {len(tool_log)}
- Failed: {len(failed_tools)}
- All tools failed: {all_failed}

**CRITICAL RULES**:

1. **Use EXACT COUNTS Provided Above**: 
   - The "EXACT COUNTS" section shows the TRUE total (e.g., companies: 27)
   - The "Result Data Preview" is TRUNCATED and may only show 10-15 items
   - ALWAYS use the EXACT COUNT, NOT what you count in the preview
   - ✅ GOOD: "I found 27 companies in your workspace" (using EXACT COUNT)
   - ❌ BAD: "I found 11 companies" (counting truncated preview)

2. **List Items When Reasonable**: 
   - If ≤10 items: List ALL of them by name from the preview
   - If >10 items: List what you see in preview and say "and X more" (calculate X from EXACT COUNT)

3. **Use Your Knowledge for Analysis**:
   - If user asks "which are AI companies?" and you have a list, USE YOUR KNOWLEDGE to identify them
   - Don't just search for keyword "AI" - actually reason about which companies work in AI
   - Example: OpenAI, Anthropic, DeepSeek AI are AI companies. Netflix is streaming. Mercedes is automotive.

4. **No Hallucination on Failures**:
   - If all_failed=True, apologize and DO NOT make up data

5. **Be Conversational but Precise**:
   - Keep it natural (2-4 sentences)
   - Use markdown for readability (bold names, bullet lists)
   - Offer next steps when appropriate

Response:"""

    try:
        # Call LLM
        logger.debug("Generating final summary with LLM...")
        content = await call_summarizer(prompt)
    except Exception as e:
        logger.error(f"Error generating summary with LLM: {e}")
        content = plan_summary or "I've processed your request."

    return {
        "type": "markdown",
        "content": content
    }


# ========================================
# Main Final Response Node
# ========================================


async def final_response_node(
    state: AgentState
) -> Dict[str, Any]:
    """
    Generate final structured response for frontend rendering.
    
    This is the final node in the LangGraph pipeline. It takes the aggregated
    execution results and current state, then formats them into a structured
    response that the frontend can easily render.
    
    The function builds a list of UI message blocks:
    1. Thinking block - Shows reasoning traces
    2. Tool log block - Shows which tools were executed
    3. Entity blocks - Shows search results, entity details, etc.
    4. Markdown summary - Final response text
    
    These blocks are designed to provide transparency (thinking, tool logs)
    and present data in a user-friendly format (entities, markdown).
    
    Args:
        state: Current agent state with conversation context and reasoning
    
    Returns:
        Dictionary containing state update:
        {
            "final_response": {
                "messages": [
                    {"type": "thinking", "content": "..."},
                    {"type": "tool_log", "content": [...]},
                    {"type": "entity_people_list", "content": [...]},
                    {"type": "markdown", "content": "### Summary\\n..."}
                ],
                "final_summary": "The markdown content from the summary block",
                "entities": {
                    "people": [...],
                    "companies": [...],
                    "...": ...
                },
                "reasoning": [
                    {"text": "Planner: ...", "timestamp": "..."},
                    ...
                ]
            }
        }
    """
    try:
        logger.info("Building final response...")
        
        # Get aggregated results from state
        aggregated = state.aggregated_result or {}
        
        # Initialize messages list
        messages: List[Dict[str, Any]] = []
        
        # ========================================
        # A. Build Thinking Block
        # ========================================
        
        thinking_block = _build_thinking_block(state, aggregated)
        messages.append(thinking_block)
        
        logger.debug("Added thinking block to messages")
        
        # ========================================
        # B. Build Tool Activity Log Block
        # ========================================
        
        tool_log_block = _build_tool_log_block(aggregated)
        if tool_log_block:
            messages.append(tool_log_block)
            logger.debug("Added tool log block to messages")
        
        # ========================================
        # C. Build Entity-Specific UI Blocks
        # ========================================
        
        entity_blocks = _build_entity_blocks(aggregated)
        if entity_blocks:
            messages.extend(entity_blocks)
            logger.debug(f"Added {len(entity_blocks)} entity block(s) to messages")
        
        # ========================================
        # D. Build Final Markdown Summary
        # ========================================
        
        markdown_summary = await _build_markdown_summary(aggregated, state)
        messages.append(markdown_summary)
        
        logger.debug("Added markdown summary block to messages")
        
        # ========================================
        # E. Extract Final Summary
        # ========================================
        
        # The final summary is the markdown content from the summary block
        final_summary = markdown_summary["content"]
        
        # ========================================
        # F. Extract Entities
        # ========================================
        
        entities = aggregated.get("merged_results", {})
        
        # ========================================
        # G. Build and Return Final Response
        # ========================================
        
        response = {
            "messages": messages,
            "final_summary": final_summary,
            "entities": entities,
            "reasoning": state.reasoning,
        }
        
        logger.info(
            f"Final response built: {len(messages)} message block(s), "
            f"{len(entities)} entity type(s)"
        )
        
        # Add final reasoning to state
        state.add_reasoning(
            f"Final Response: Built {len(messages)} UI block(s) for frontend"
        )
        
        return {"final_response": response}
    
    except Exception as e:
        # Catch-all error handler - return safe fallback
        logger.error(f"Error in final_response_node: {e}", exc_info=True)
        
        # Add error reasoning
        state.add_reasoning(f"Final Response: Error during formatting: {str(e)}")
        
        # Return fallback response
        return {"final_response": {
            "messages": [
                {
                    "type": "markdown",
                    "content": "Something went wrong preparing the response. Please try again."
                }
            ],
            "final_summary": "Something went wrong.",
            "entities": {},
            "reasoning": state.reasoning
        }}


# ========================================
# TODO: Future Enhancements
# ========================================

# TODO: Rich entity formatting
# Add more detailed entity blocks with formatted fields:
# - Person blocks with profile pictures, contact info, company affiliations
# - Company blocks with logos, employee counts, interaction summaries
# - Interaction blocks with threaded conversations, attachments

# TODO: Dynamic block ordering
# Reorder blocks based on query type:
# - For "find" queries, put entity lists first
# - For "show details" queries, put detail blocks first
# - For action confirmations, put confirmation blocks first

# TODO: Markdown enhancement
# Generate richer markdown with:
# - Tables for structured data
# - Links to entities for navigation
# - Inline entity previews
# - Code blocks for technical data

# TODO: Error recovery suggestions
# When errors occur, provide actionable suggestions:
# - "Try rephrasing your query"
# - "Check if the entity exists"
# - "You may not have permission"

# TODO: Localization support
# Add support for multiple languages:
# - Translate block labels
# - Format dates/numbers according to locale
# - Support RTL languages

