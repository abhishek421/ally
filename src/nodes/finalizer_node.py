"""Finalizer node to format response."""

import json
from typing import Any, Dict

from ..graph.state import GraphState
from ..utils.logger import get_logger

logger = get_logger(__name__)


def finalizer_node(state: GraphState) -> Dict[str, Any]:
    """Format the final answer into the expected JSON structure."""
    logger.info("Finalizer Node: Formatting response")
    
    current_action = state.get("current_action", {})
    answer = current_action.get("answer") or state.get("final_answer")
    if not answer:
        answer = "I couldn't gather more details, so here's the best available summary."
    
    # Fallback if no answer in current_action (e.g. from error)
    if not answer and state.get("final_answer"):
        answer = state.get("final_answer")
        
    reasoning_steps = state.get("reasoning_steps", [])
    tool_calls = state.get("tool_calls", [])
    enriched_query = state.get("query_builder_result", "")
    generated_plan = state.get("plan", "")
    
    response_data = {
        "answer": answer,
        "reasoning_steps": reasoning_steps,
        "tool_calls": tool_calls,
        "query": enriched_query,
        "plan": generated_plan,
        "metadata": {
            "iterations": len(reasoning_steps),
            "tools_used": [tc["tool"] for tc in tool_calls],
            "timestamp": None,
        },
    }
    
    return {
        "query_processing_result": json.dumps(response_data, indent=2),
        "query_processing_metadata": {
            "reasoning_steps_count": len(reasoning_steps),
            "tool_calls_count": len(tool_calls),
            "tools_used": [tc["tool"] for tc in tool_calls],
            "generated_plan": generated_plan,
        },
        "execution_path": state.get("execution_path", []) + ["finalizer_node"],
        "metadata": {
            **state.get("metadata", {}),
            "query_processing_completed": True,
        },
    }

