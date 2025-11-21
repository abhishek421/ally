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


def _build_thinking_block(state: AgentState) -> Dict[str, Any]:
    """
    Build a thinking block from state reasoning traces.
    
    Shows the last N reasoning lines to give users insight into
    the agent's decision-making process without overwhelming them.
    
    Args:
        state: Agent state containing reasoning traces
    
    Returns:
        Thinking block dictionary:
        {
            "type": "thinking",
            "content": "Planner: ...\\nValidator: ...\\n..."
        }
    """
    # Get last N reasoning lines
    reasoning_lines = state.reasoning[-MAX_REASONING_LINES:] if state.reasoning else []
    
    if not reasoning_lines:
        content = "Processing your request..."
    else:
        # Join reasoning lines with newlines
        content = "\n".join([r.text for r in reasoning_lines])
    
    return {
        "type": "thinking",
        "content": content
    }


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


def _build_markdown_summary(aggregated: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build final markdown summary block.
    
    Combines plan summary and executor summary into a cohesive
    markdown response for the user.
    
    Args:
        aggregated: Aggregated data containing summaries
    
    Returns:
        Markdown block dictionary:
        {
            "type": "markdown",
            "content": "### Summary\\n..."
        }
    """
    plan_summary = aggregated.get("plan_summary", "")
    executor_summary = aggregated.get("executor_summary", "")
    
    # Build markdown content
    parts = []
    
    if plan_summary:
        parts.append(plan_summary)
    
    if executor_summary:
        parts.append(executor_summary)
    
    if not parts:
        content = "I've processed your request."
    else:
        content = "\n\n".join(parts)
    
    # Wrap in markdown
    markdown_content = f"### Summary\n\n{content}"
    
    return {
        "type": "markdown",
        "content": markdown_content
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
        
        thinking_block = _build_thinking_block(state)
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
        
        markdown_summary = _build_markdown_summary(aggregated)
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

