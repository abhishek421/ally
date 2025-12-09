"""Planner node for generating execution plans."""

import json
from typing import Any, Dict

from ..config import get_settings
from ..graph.state import GraphState
from ..nodes.query_processing.planner import Planner
from ..nodes.query_processing.utils import get_or_create_dspy_lm
from ..tools.registry import get_tool_registry
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def planner_node(state: GraphState) -> Dict[str, Any]:
    """Generate a high-level plan for the query."""
    logger.info("Planner Node: Starting planning")

    enriched_query = state.get("query_builder_result")
    if not enriched_query:
        enriched_query = state.get("user_query", "")

    try:
        # Initialize DSPy
        lm = get_or_create_dspy_lm()
        
        # Get tools
        tool_registry = get_tool_registry()
        tools = tool_registry.get_tool_descriptions() if settings.enable_tools else []

        planner = Planner()
        
        tools_list = "\n".join([f"- {t['name']}: {t['description']}" for t in tools])
        planner_context = f"""
        AVAILABLE TOOLS:
        {tools_list}
        
        CONVERSATION HISTORY (Use ONLY for context, do NOT assume these results answer new queries):
        {enriched_query}
        """
        
        generated_plan = planner(question=enriched_query, context=planner_context)
        logger.info(f"Plan generated: {generated_plan}")

        return {
            "plan": generated_plan,
            "execution_path": state.get("execution_path", []) + ["planner_node"]
        }

    except Exception as e:
        logger.error("Planning failed", error=str(e), exc_info=True)
        return {
            "plan": "Error generating plan. Proceeding with best effort.",
            "errors": (state.get("errors", []) or []) + [f"Planning error: {str(e)}"],
            "execution_path": state.get("execution_path", []) + ["planner_node"]
        }

