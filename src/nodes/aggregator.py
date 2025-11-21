"""
Aggregator node for the LangGraph agent pipeline.

This module exports the aggregator_node function, which is responsible for:
1. Merging executor results into a normalized structure
2. Building a tool activity log for debugging and transparency
3. Combining plan metadata with execution results
4. Preparing structured data for the final_response node

The aggregator sits between the executor and final_response in the pipeline:
    User Input → Planner → Validator → Executor → Aggregator → Final Response

The aggregator is a pure data transformation node that:
- Does NOT execute tools
- Does NOT call the LLM
- Does NOT make decisions
- Performs deterministic data merging and normalization

Why the Aggregator Exists:

The executor returns raw tool results in a flat list:
    [{"tool": "search_people", "result": {...}}, {"tool": "search_companies", "result": {...}}]

The final_response node needs organized, semantic data:
    {"people": [...], "companies": [...], "activity_log": [...]}

The aggregator bridges this gap by:
1. Normalizing tool results into semantic categories
2. Creating activity logs for transparency
3. Preserving raw results for debugging
4. Combining all metadata into one structure

This separation of concerns makes the pipeline cleaner and more maintainable.

Mapping Logic:

Tool results are mapped to semantic categories using TOOL_RESULT_MAP:
    "search_people" → merged_results["people"]
    "search_companies" → merged_results["companies"]
    "get_person" → merged_results["person"]
    "get_company" → merged_results["company"]
    "get_person_interactions" → merged_results["interactions"]
    ...

This mapping is deterministic and can be extended as new tools are added.

Return Structure:

The aggregator returns a dictionary consumed by final_response:
{
    "merged_results": {
        "people": [...],
        "companies": [...],
        "person": {...},
        ...
    },
    "tool_activity_log": [
        {"tool": "search_people", "status": "success", "timestamp": "..."},
        ...
    ],
    "execution_mode": "SEQUENTIAL" | "PARALLEL" | "NONE",
    "plan_summary": "Plan summary from planner",
    "executor_summary": "Execution summary from executor",
    "raw_results": [...]  # Original executor results for debugging
}
"""

from datetime import datetime
from typing import Dict, Any, List

from src.memory.state import AgentState
from src.config.logger import logger


# ========================================
# Constants
# ========================================

# Map tool names to semantic result categories
# This allows the final_response node to organize results meaningfully
# TODO: Extend this mapping as new tools are added to the system
TOOL_RESULT_MAP: Dict[str, str] = {
    # Person tools
    "search_people": "people",
    "list_people": "people",
    "get_person": "person",
    "create_person": "person",
    "update_person": "person",
    "delete_people": "people_deleted",
    
    # Company tools
    "search_companies": "companies",
    "list_companies": "companies",
    "get_company": "company",
    "create_company": "company",
    "update_company": "company",
    "delete_companies": "companies_deleted",
    
    # Interaction tools
    "get_person_interactions": "interactions",
    "get_company_interactions": "interactions",
    "get_interaction": "interaction",
    "create_interaction": "interaction",
    "update_interaction": "interaction",
    "delete_interaction": "interaction_deleted",
    
    # Group tools
    "list_groups": "groups",
    "get_group": "group",
    "get_group_companies": "group_companies",
    "get_group_people": "group_people",
    "create_group": "group",
    "update_group": "group",
    "delete_group": "group_deleted",
    
    # Group membership tools
    "add_company_to_group": "group_membership_updated",
    "remove_company_from_group": "group_membership_updated",
    "add_person_to_group": "group_membership_updated",
    "remove_person_from_group": "group_membership_updated",
    
    # Relationship tools
    "add_person_to_company": "relationship_updated",
    "remove_person_from_company": "relationship_updated",
    "add_company_to_person": "relationship_updated",
    "remove_company_from_person": "relationship_updated",
    
    # Workspace tools
    "get_workspace": "workspace",
    "get_workspaces_for_user": "workspaces",
    "get_workspace_members": "workspace_members",
}


# ========================================
# Helper Functions
# ========================================


def _normalize_tool_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize a list of tool results into semantic categories.
    
    Takes raw executor results and organizes them into a dictionary
    where keys are semantic categories (people, companies, etc.) and
    values are the corresponding tool results.
    
    Multiple results for the same category are combined into lists.
    
    Args:
        results: List of result dictionaries from executor
    
    Returns:
        Dictionary mapping categories to results:
        {
            "people": [...],
            "companies": [...],
            "person": {...},
            ...
        }
    
    Example:
        Input: [
            {"tool": "search_people", "result": {"data": [...]}, "status": "success"},
            {"tool": "search_companies", "result": {"data": [...]}, "status": "success"}
        ]
        Output: {
            "people": {"data": [...]},
            "companies": {"data": [...]}
        }
    """
    merged = {}
    
    for result in results:
        # Skip failed results
        if result.get("status") != "success":
            logger.debug(f"Skipping failed result for tool: {result.get('tool')}")
            continue
        
        tool_name = result.get("tool", "unknown")
        tool_result = result.get("result")
        
        # Skip if no result data
        if tool_result is None:
            logger.debug(f"Skipping null result for tool: {tool_name}")
            continue
        
        # Get semantic category from mapping
        category = TOOL_RESULT_MAP.get(tool_name)
        
        if category is None:
            # Tool not in mapping - use generic category
            logger.debug(f"Tool '{tool_name}' not in TOOL_RESULT_MAP, using 'other'")
            category = "other"
        
        # Add to merged results
        if category in merged:
            # Category already exists - append to list
            if not isinstance(merged[category], list):
                # Convert single item to list
                merged[category] = [merged[category]]
            merged[category].append(tool_result)
        else:
            # First result for this category
            merged[category] = tool_result
    
    return merged


def _build_activity_log(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build a tool activity log from executor results.
    
    Creates a concise log of tool executions with their status and timing.
    Useful for debugging, auditing, and displaying execution history to users.
    
    Args:
        results: List of result dictionaries from executor
    
    Returns:
        List of activity log entries:
        [
            {
                "tool": "search_people",
                "status": "success",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            ...
        ]
    
    Example:
        Input: [
            {"tool": "search_people", "status": "success", ...},
            {"tool": "search_companies", "status": "error", "error": "...", ...}
        ]
        Output: [
            {"tool": "search_people", "status": "success", "timestamp": "..."},
            {"tool": "search_companies", "status": "error", "timestamp": "..."}
        ]
    """
    activity_log = []
    
    for result in results:
        tool_name = result.get("tool", "unknown")
        status = result.get("status", "unknown")
        
        # Create log entry
        log_entry = {
            "tool": tool_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add error message if failed
        if status == "error":
            error = result.get("error")
            if error:
                log_entry["error"] = str(error)[:200]  # Truncate long errors
        
        activity_log.append(log_entry)
    
    return activity_log


# ========================================
# Main Aggregator Node
# ========================================


async def aggregator_node(
    state: AgentState
) -> Dict[str, Any]:
    """
    Merge and normalize execution results for the final_response node.
    
    This is the aggregator node in the LangGraph pipeline. It receives results
    from the executor along with the original plan and current state, then
    combines them into a structured format for the final_response node.
    
    The aggregator performs three main operations:
    
    1. Result Normalization
       - Maps tool results to semantic categories (people, companies, etc.)
       - Organizes flat result list into meaningful structure
       - Combines multiple results of same type
    
    2. Activity Logging
       - Creates concise log of tool executions
       - Records success/failure status
       - Adds timestamps for each tool call
    
    3. Metadata Combination
       - Combines plan summary with execution summary
       - Preserves execution mode information
       - Includes raw results for debugging
    
    Args:
        state: Current agent state with conversation context, plan, and execution results
    
    Returns:
        Dictionary containing state update:
        {
            "aggregated_result": {
                "merged_results": {
                    "people": [...],
                    "companies": [...],
                    "person": {...},
                    ...
                },
                "tool_activity_log": [
                    {"tool": "search_people", "status": "success", "timestamp": "..."},
                    ...
                ],
                "execution_mode": "SEQUENTIAL" | "PARALLEL" | "NONE",
                "plan_summary": "Plan summary from planner",
                "executor_summary": "Execution summary from executor",
                "raw_results": [...]
            }
        }
    """
    try:
        logger.info("Aggregating execution results...")
        
        # Get data from state
        plan = state.plan or {}
        execution_result = state.execution_results or {}
        
        # Extract results from executor
        raw_results = execution_result.get("results", [])
        execution_mode = execution_result.get("execution_mode", "NONE")
        executor_summary = execution_result.get("summary", "")
        
        # Extract metadata from plan
        plan_summary = plan.get("summary", "")
        
        logger.debug(
            f"Aggregating {len(raw_results)} results from {execution_mode} execution"
        )
        
        # ========================================
        # A. Normalize Tool Results
        # ========================================
        
        merged_results = _normalize_tool_results(raw_results)
        
        logger.debug(
            f"Normalized results into {len(merged_results)} categories: "
            f"{list(merged_results.keys())}"
        )
        
        # ========================================
        # B. Build Activity Log
        # ========================================
        
        tool_activity_log = _build_activity_log(raw_results)
        
        # Count successes and failures for logging
        success_count = sum(
            1 for entry in tool_activity_log if entry["status"] == "success"
        )
        error_count = len(tool_activity_log) - success_count
        
        logger.info(
            f"Activity log: {len(tool_activity_log)} tools "
            f"({success_count} succeeded, {error_count} failed)"
        )
        
        # ========================================
        # C. Add Aggregation Reasoning
        # ========================================
        
        state.add_reasoning(
            f"Aggregator: Merged {len(raw_results)} tool result(s) "
            f"into {len(merged_results)} category/categories"
        )
        
        if merged_results:
            categories = list(merged_results.keys())
            state.add_reasoning(
                f"Aggregator: Result categories: {', '.join(categories)}"
            )
        
        # ========================================
        # D. Build and Return Merged Object
        # ========================================
        
        aggregated_data = {
            "merged_results": merged_results,
            "tool_activity_log": tool_activity_log,
            "execution_mode": execution_mode,
            "plan_summary": plan_summary,
            "executor_summary": executor_summary,
            "raw_results": raw_results,
        }
        
        logger.info("Aggregation completed successfully")
        
        return {"aggregated_result": aggregated_data}
    
    except Exception as e:
        # Catch-all error handler - return safe fallback
        logger.error(f"Error in aggregator_node: {e}", exc_info=True)
        
        # Add error reasoning
        state.add_reasoning(f"Aggregator: Error during aggregation: {str(e)}")
        
        # Return fallback structure
        return {"aggregated_result": {
            "merged_results": {},
            "tool_activity_log": [],
            "execution_mode": "NONE",
            "plan_summary": plan.get("summary", ""),
            "executor_summary": "Aggregator encountered an error.",
            "raw_results": execution_result.get("results", [])
        }}


# ========================================
# TODO: Future Enhancements
# ========================================

# TODO: Smart result deduplication
# If multiple tools return overlapping data (e.g., same person from different queries),
# deduplicate based on entity IDs to avoid showing duplicates to the user

# TODO: Result enrichment
# Add computed fields to results, such as:
# - Summary counts (total people found, total companies, etc.)
# - Relevance scores for search results
# - Relationship graphs between entities

# TODO: Pagination metadata preservation
# When tools return paginated results with hasNextPage/cursor,
# preserve this metadata for the frontend to implement "load more"

# TODO: Error result categorization
# Group failed tool results by error type for better error reporting:
# - Permission errors
# - Not found errors
# - Validation errors
# - Network errors

# TODO: Performance metrics
# Add execution timing information:
# - Time taken per tool
# - Total execution time
# - Slowest tool identification

