"""Tool execution node."""

import json
from typing import Any, Dict

from ..config import get_settings
from ..graph.state import GraphState
from ..nodes.query_processing.executor import ReActWithTools
from ..nodes.query_processing.utils import get_or_create_dspy_lm
from ..tools.registry import get_tool_registry
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def tool_node(state: GraphState) -> Dict[str, Any]:
    """Execute the tool selected by the agent."""
    logger.info("Tool Node: Executing tool")
    
    current_action = state.get("current_action", {})
    action_type = current_action.get("action")
    tool_name = current_action.get("tool_name")
    tool_params = current_action.get("tool_params", {})
    
    if action_type != "use_tool" or not tool_name:
        logger.warning("Tool node called but no tool action present")
        return {"execution_path": state.get("execution_path", []) + ["tool_node"]}

    # Initialize dependencies
    get_or_create_dspy_lm()
    tool_registry = get_tool_registry()
    tools = tool_registry.get_tool_descriptions() if settings.enable_tools else []
    
    workspace_id = state.get("workspace_id")
    user_id = state.get("user_id")

    react = ReActWithTools(
        tools=tools,
        workspace_id=workspace_id,
        user_id=user_id
    )

    # Execute tool
    logger.info(f"Executing tool: {tool_name}")
    try:
        result = react.execute_tool(tool_name, tool_params)
    except Exception as e:
        result = f"Error executing tool: {str(e)}"

    # Record the result
    tool_call_record = {
        "tool": tool_name,
        "params": tool_params,
        "result": str(result)[:20000],
    }
    
    # Update state
    tool_calls = state.get("tool_calls", []) + [tool_call_record]
    
    # Update context history and previous actions for loop detection
    result_preview = str(result)
    if len(result_preview) > settings.tool_result_limit:
        result_preview = result_preview[:settings.tool_result_limit] + "... (truncated)"
        
    context_entry = f"Tool {tool_name} called with params {tool_params}\nResult: {result_preview}"
    context_history = state.get("context_history", []) + [context_entry]
    
    # Create canonical signature for loop detection
    current_call_signature = f"{tool_name}:{json.dumps(tool_params, sort_keys=True)}"
    previous_actions = state.get("previous_actions", []) + [current_call_signature]

    return {
        "tool_calls": tool_calls,
        "context_history": context_history,
        "previous_actions": previous_actions,
        "execution_path": state.get("execution_path", []) + ["tool_node"]
    }

