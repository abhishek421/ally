"""Agent node for deciding next steps."""

from typing import Any, Dict

from ..config import get_settings
from ..graph.state import GraphState
from ..nodes.query_processing.executor import ReActWithTools
from ..nodes.query_processing.utils import get_or_create_dspy_lm
from ..tools.registry import get_tool_registry
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def agent_node(state: GraphState) -> Dict[str, Any]:
    """Decide the next action (reasoning + tool/answer)."""
    logger.info("Agent Node: Deciding next step")

    # Guardrail: stop runaway loops
    iterations = state.get("agent_iterations", 0) + 1
    max_iters = settings.max_react_iterations or 10
    if iterations > max_iters:
        logger.warning("Agent iteration cap reached. Forcing final answer.")
        failover_answer = (
            "I tried multiple steps but could not retrieve more data. "
            "Here's the best I can offer with what I have."
        )
        return {
            "current_action": {"action": "answer", "answer": failover_answer},
            "agent_iterations": iterations,
            "execution_path": state.get("execution_path", []) + ["agent_node"],
        }

    enriched_query = state.get("query_builder_result") or state.get("user_query", "")
    plan = state.get("plan")
    context_history = state.get("context_history", [])
    previous_actions = state.get("previous_actions", [])
    
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

    result = react.decide_next_step(
        question=enriched_query,
        plan=plan,
        context_history=context_history,
        previous_actions=previous_actions
    )

    action = result["action"]
    reasoning = result.get("reasoning", "")
    
    # Update reasoning steps log
    reasoning_steps = state.get("reasoning_steps", []) + [reasoning]
    
    # Update context history with the reasoning
    # This ensures the model sees its own thought process in the next turn
    updated_history = context_history + [reasoning[:200]]  # Truncate for context window if needed

    return {
        "current_action": result,
        "reasoning_steps": reasoning_steps,
        "context_history": updated_history,
        "agent_iterations": iterations,
        "execution_path": state.get("execution_path", []) + ["agent_node"]
    }

