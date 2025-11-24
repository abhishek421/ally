"""
Executor node for the LangGraph agent pipeline.

This module exports the executor_node function, which is responsible for:
1. Executing planned and validated tasks (tool calls)
2. Handling different execution modes (SEQUENTIAL, PARALLEL, CONFIRMATION_REQUIRED)
3. Writing tool call logs and results into agent state
4. Returning structured execution results for the aggregator node

The executor sits after the validator in the pipeline:
    User Input → Planner → Validator → Executor → Aggregator → Final Response

The executor does NOT:
- Plan what tools to call (that's the planner's job)
- Validate arguments (that's the validator's job)
- Format responses for the UI (that's the aggregator/final_response's job)
- Make decisions about confirmations (that's the validator's job)

Execution Modes:

SEQUENTIAL:
- Executes tasks one after another in order
- Each task completes before the next starts
- Use when tasks depend on each other's results
- Example: Get person → Get their company → Get company interactions

PARALLEL:
- Executes all tasks concurrently using asyncio.gather
- All tasks run simultaneously for maximum speed
- Use when tasks are independent of each other
- Example: Search companies + Search people + List groups

CONFIRMATION_REQUIRED:
- Executor does nothing and returns empty results
- The validator has already blocked execution pending user confirmation
- Once user confirms, validator converts to executable task
- Example: User must approve before creating a person

Tool Registry:

The executor uses a global TOOL_REGISTRY injected at graph build time.
This registry is a dictionary mapping tool names to async callable functions:

TOOL_REGISTRY = {
    "search_companies": async_function,
    "create_person": async_function,
    ...
}

Each tool function signature:
    async def tool_function(**kwargs) -> Dict[str, Any]

The executor:
1. Looks up the tool by name in the registry
2. Calls it with validated arguments
3. Captures the result or error
4. Stores the result in state and returns it

Return Structure:

The executor returns a dictionary for the aggregator node:
{
    "results": [
        {"tool": "search_companies", "result": {...}, "args": {...}},
        {"tool": "get_person", "result": {...}, "args": {...}},
        ...
    ],
    "execution_mode": "SEQUENTIAL" | "PARALLEL" | "NONE",
    "summary": "Executed 2 tasks in SEQUENTIAL mode"
}

The aggregator uses this to format the final response for the user.
"""

import asyncio
import inspect
from functools import lru_cache
from typing import Dict, Any, List, Callable, Optional, Set

from src.memory.state import AgentState
from src.utils.types import PlannerDecisionType, ToolStatus
from src.config.logger import logger


# ========================================
# Tool Registry
# ========================================

# Global tool registry injected at graph build time
# TODO: This will be injected by graph.py during graph construction
# Format: {"tool_name": async_callable_function, ...}
TOOL_REGISTRY: Optional[Dict[str, Callable]] = None


@lru_cache(maxsize=256)
def _get_tool_param_names(tool_function: Callable) -> Set[str]:
    """
    Cache and return the parameter names for a tool function.

    Using a cache prevents repeated inspection overhead when tools are
    executed multiple times in a single session.
    """
    try:
        return set(inspect.signature(tool_function).parameters.keys())
    except (ValueError, TypeError):
        # Some callables (like functools.partial) may not expose signatures cleanly
        return set()


# ========================================
# Helper Functions
# ========================================


def _camel_to_snake(name: str) -> str:
    """
    Convert camelCase to snake_case.
    
    Handles cases where the LLM generates camelCase argument names
    but Python functions expect snake_case.
    
    Args:
        name: camelCase string (e.g., "workspaceId", "userId")
    
    Returns:
        snake_case string (e.g., "workspace_id", "user_id")
    
    Examples:
        >>> _camel_to_snake("workspaceId")
        'workspace_id'
        >>> _camel_to_snake("userId")
        'user_id'
        >>> _camel_to_snake("firstName")
        'first_name'
        >>> _camel_to_snake("already_snake")
        'already_snake'
    """
    import re
    # Insert underscore before uppercase letters and convert to lowercase
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


async def _execute_single_task(
    tool_name: str,
    args: Dict[str, Any],
    state: AgentState
) -> Dict[str, Any]:
    """
    Execute a single tool call and return the result.
    
    This function:
    1. Looks up the tool in the registry
    2. Logs the tool call start
    3. Executes the tool with provided arguments
    4. Captures success or error
    5. Logs completion
    6. Returns structured result
    
    Args:
        tool_name: Name of the tool to execute
        args: Arguments dictionary for the tool
        state: Agent state (for logging tool calls)
    
    Returns:
        Dictionary containing:
        {
            "tool": str,
            "args": dict,
            "result": dict | None,
            "error": str | None,
            "status": "success" | "error"
        }
    """
    try:
        # Check if tool exists in registry
        if TOOL_REGISTRY is None:
            logger.error("Tool registry not initialized")
            return {
                "tool": tool_name,
                "args": args,
                "result": None,
                "error": "Tool registry not initialized",
                "status": "error"
            }
        
        if tool_name not in TOOL_REGISTRY:
            logger.warning(f"Tool '{tool_name}' not found in registry")
            return {
                "tool": tool_name,
                "args": args,
                "result": None,
                "error": f"Tool '{tool_name}' not found",
                "status": "error"
            }
        
        # Get tool function
        tool_function = TOOL_REGISTRY[tool_name]
        
        # Normalize argument names from camelCase to snake_case
        # This handles cases where the LLM generates camelCase args but Python functions expect snake_case
        normalized_args = {}
        for key, value in args.items():
            # Convert camelCase to snake_case
            snake_case_key = _camel_to_snake(key)
            normalized_args[snake_case_key] = value
        
        # Handle common parameter aliases (LLM might use different names)
        # Map 'query' -> 'search' for search_companies/search_people
        if "query" in normalized_args and "search" not in normalized_args:
            if tool_name in ["search_companies", "search_people"]:
                normalized_args["search"] = normalized_args.pop("query")
                logger.debug(f"Aliased 'query' -> 'search' for tool '{tool_name}'")

        # Determine which parameters the tool actually accepts so we only inject relevant context.
        tool_param_names = _get_tool_param_names(tool_function)

        def _inject_context_arg(arg_name: str, value: Any) -> None:
            """Helper to inject state context only when the tool accepts the argument."""
            if value is None or arg_name in normalized_args:
                return
            if arg_name in tool_param_names:
                normalized_args[arg_name] = value

        # Inject common context arguments when the tool expects them.
        _inject_context_arg("workspace_id", state.workspace_id)
        _inject_context_arg("user_id", state.user_id)
        _inject_context_arg("conversation_id", state.conversation_id)
        _inject_context_arg("graphql_auth_token", state.graphql_auth_token)
        
        # Log tool call start with full argument details
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool '{tool_name}' arguments after normalization and injection: {normalized_args}")
        state.log_tool_call(tool_name, normalized_args)
        
        # Execute tool
        result = await tool_function(**normalized_args)
        
        # Log successful completion with result summary
        logger.info(f"Tool '{tool_name}' completed successfully")
        
        # Log result structure for debugging
        if isinstance(result, dict):
            result_keys = list(result.keys())
            logger.debug(f"Tool '{tool_name}' returned dict with keys: {result_keys}")
            # Log data counts if present
            if "data" in result:
                data = result.get("data")
                if isinstance(data, list):
                    logger.info(f"Tool '{tool_name}' returned {len(data)} item(s)")
                elif isinstance(data, dict):
                    logger.debug(f"Tool '{tool_name}' returned data dict with keys: {list(data.keys())}")
            if "meta" in result:
                meta = result.get("meta", {})
                total = meta.get("total")
                if total is not None:
                    logger.info(f"Tool '{tool_name}' meta.total: {total}")
        
        state.complete_tool_call(tool_name, {"success": True})
        
        return {
            "tool": tool_name,
            "args": normalized_args,
            "result": result,
            "error": None,
            "status": "success"
        }
    
    except Exception as e:
        # Log error
        logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
        
        # Log failed tool call
        try:
            state.log_tool_call(tool_name, {"error": str(e)})
        except Exception:
            pass  # Don't fail if logging fails
        
        return {
            "tool": tool_name,
            "args": args,
            "result": None,
            "error": str(e),
            "status": "error"
        }


async def _execute_sequential(
    tasks: List[Dict[str, Any]],
    state: AgentState
) -> List[Dict[str, Any]]:
    """
    Execute tasks one after another in sequence.
    
    Each task completes before the next one starts. This is useful when
    tasks may depend on each other's results or when order matters.
    
    Args:
        tasks: List of task dictionaries with 'tool' and 'args' keys
        state: Agent state for logging
    
    Returns:
        List of result dictionaries in the same order as tasks
    """
    logger.info(f"Executing {len(tasks)} tasks in SEQUENTIAL mode")
    
    results = []
    
    for i, task in enumerate(tasks, 1):
        tool_name = task.get("tool", "unknown")
        args = task.get("args", {})
        
        logger.debug(f"Sequential execution: Task {i}/{len(tasks)} - {tool_name}")
        
        result = await _execute_single_task(tool_name, args, state)
        results.append(result)
        
        # Log progress
        if result["status"] == "success":
            logger.debug(f"Task {i}/{len(tasks)} completed successfully")
        else:
            logger.warning(f"Task {i}/{len(tasks)} failed: {result['error']}")
    
    return results


async def _execute_parallel(
    tasks: List[Dict[str, Any]],
    state: AgentState
) -> List[Dict[str, Any]]:
    """
    Execute all tasks concurrently using asyncio.gather.
    
    All tasks run simultaneously for maximum speed. Results are returned
    in the same order as the input tasks (order is preserved).
    
    This is useful when tasks are independent and don't depend on each
    other's results.
    
    Args:
        tasks: List of task dictionaries with 'tool' and 'args' keys
        state: Agent state for logging
    
    Returns:
        List of result dictionaries in the same order as tasks
    """
    logger.info(f"Executing {len(tasks)} tasks in PARALLEL mode")
    
    # Create coroutines for all tasks
    coroutines = []
    for i, task in enumerate(tasks):
        tool_name = task.get("tool", "unknown")
        args = task.get("args", {})
        
        logger.debug(f"Parallel execution: Scheduling task {i+1} - {tool_name}")
        
        coroutine = _execute_single_task(tool_name, args, state)
        coroutines.append(coroutine)
    
    # Execute all tasks concurrently
    # return_exceptions=True ensures one failure doesn't stop others
    results = await asyncio.gather(*coroutines, return_exceptions=False)
    
    # Log completion
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    
    logger.info(
        f"Parallel execution completed: {success_count} succeeded, {error_count} failed"
    )
    
    return list(results)


# ========================================
# Main Executor Node
# ========================================


async def executor_node(
    state: AgentState
) -> Dict[str, Any]:
    """
    Execute planned tasks and return structured results.
    
    This is the executor node in the LangGraph pipeline. It receives a
    validated plan from the validator and executes the specified tools
    according to the execution mode.
    
    The executor:
    1. Checks if there are tasks to execute
    2. Determines execution mode (SEQUENTIAL, PARALLEL, CONFIRMATION_REQUIRED)
    3. Executes tools using the global tool registry
    4. Handles errors gracefully (never raises exceptions)
    5. Logs execution progress to state
    6. Returns structured results for the aggregator
    
    Execution Modes:
    - SEQUENTIAL: Tasks run one after another (order matters)
    - PARALLEL: Tasks run concurrently (maximum speed)
    - CONFIRMATION_REQUIRED: No execution (waiting for user confirmation)
    - NONE: No tasks to execute
    
    Args:
        state: Current agent state with conversation context and validated plan
    
    Returns:
        Dictionary containing state update:
        {
            "execution_results": {
                "results": [
                    {
                        "tool": str,
                        "args": dict,
                        "result": dict | None,
                        "error": str | None,
                        "status": "success" | "error"
                    },
                    ...
                ],
                "execution_mode": str,
                "summary": str
            }
        }
    """
    try:
        # Get plan from state
        plan = state.plan
        if not plan:
            logger.warning("No plan in state for executor")
            return {"execution_results": {
                "results": [],
                "execution_mode": "NONE",
                "summary": "No plan to execute"
            }}
            
        decision_type = plan.get("decision_type", "NONE")
        tasks = plan.get("tasks", [])
        
        # Normalize decision_type to lowercase (LLM might return uppercase)
        decision_type = decision_type.lower() if isinstance(decision_type, str) else "none"
        
        logger.info(f"Executor received plan: {decision_type} with {len(tasks)} task(s)")
        
        # ========================================
        # A. Handle Empty or NONE Plans
        # ========================================
        
        if decision_type == PlannerDecisionType.NONE.value or not tasks:
            logger.info("No tasks to execute (NONE or empty task list)")
            
            state.add_reasoning("Executor: No tasks to execute")
            
            return {"execution_results": {
                "results": [],
                "execution_mode": decision_type,
                "summary": "No tasks executed"
            }}
        
        # ========================================
        # B. Handle CONFIRMATION_REQUIRED
        # ========================================
        
        if decision_type == PlannerDecisionType.CONFIRMATION_REQUIRED.value:
            logger.info("Plan requires confirmation - executor skipping execution")
            
            state.add_reasoning("Executor: Awaiting user confirmation")
            
            return {"execution_results": {
                "results": [],
                "execution_mode": decision_type,
                "summary": "Awaiting user confirmation"
            }}
        
        # ========================================
        # C. Execute Tasks
        # ========================================
        
        # Determine execution mode (decision_type is now lowercase)
        if decision_type == PlannerDecisionType.SEQUENTIAL.value:
            execution_mode = "sequential"
            results = await _execute_sequential(tasks, state)
        
        elif decision_type == PlannerDecisionType.PARALLEL.value:
            execution_mode = "parallel"
            results = await _execute_parallel(tasks, state)
        
        else:
            # Unknown decision type - default to sequential for safety
            logger.warning(
                f"Unknown decision_type '{decision_type}', defaulting to sequential"
            )
            execution_mode = "sequential"
            results = await _execute_sequential(tasks, state)
        
        # ========================================
        # D. Log Execution Summary
        # ========================================
        
        # Count successes and failures
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = len(results) - success_count
        
        # Build summary
        if error_count == 0:
            summary = f"Executed {len(results)} task(s) in {execution_mode} mode"
        else:
            summary = (
                f"Executed {len(results)} task(s) in {execution_mode} mode "
                f"({success_count} succeeded, {error_count} failed)"
            )
        
        # Add reasoning to state
        tool_names = [t.get("tool", "unknown") for t in tasks]
        state.add_reasoning(
            f"Executor: Ran {len(tasks)} task(s) in {execution_mode} mode: "
            f"{', '.join(tool_names)}"
        )
        
        if error_count > 0:
            failed_tools = [
                r.get("tool", "unknown")
                for r in results
                if r.get("status") == "error"
            ]
            state.add_reasoning(
                f"Executor: {error_count} task(s) failed: {', '.join(failed_tools)}"
            )
        
        logger.info(f"Execution completed: {summary}")
        
        # ========================================
        # E. Return Structured Results
        # ========================================
        
        return {"execution_results": {
            "results": results,
            "execution_mode": execution_mode,
            "summary": summary
        }}
    
    except Exception as e:
        # Catch-all error handler - executor must never raise
        logger.error(f"Critical error in executor_node: {e}", exc_info=True)
        
        # Add error reasoning
        state.add_reasoning(f"Executor: Critical error during execution: {str(e)}")
        
        # Return empty results
        return {"execution_results": {
            "results": [],
            "execution_mode": "NONE",
            "summary": f"Execution failed: {str(e)}"
        }}


# ========================================
# TODO: Future Enhancements
# ========================================

# TODO: Integration with streaming for real-time progress updates
# As tasks complete, stream intermediate results to the frontend
# This would require yielding results as they become available

# TODO: Parallel execution with resource limits
# Implement semaphore to limit concurrent tool calls (e.g., max 5 at once)
# Prevents overwhelming external APIs or databases

# TODO: Retry logic for transient failures
# Some tools may fail due to temporary network issues
# Could implement exponential backoff retry for specific error types

# TODO: Task timeout support
# Add configurable timeouts per tool to prevent hanging
# Cancel tasks that exceed timeout threshold

# TODO: Result caching
# Cache tool results for identical calls within same conversation
# Reduces redundant API calls and improves response time

