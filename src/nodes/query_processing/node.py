"""Query processing node orchestrating planning and execution."""

import json
from typing import Any, Dict

from ...config import get_settings
from ...graph.state import GraphState
from ...tools.registry import get_tool_registry
from ...utils.logger import get_logger
from .executor import ReActWithTools
from .planner import Planner
from .utils import get_or_create_dspy_lm

logger = get_logger(__name__)
settings = get_settings()


def query_processing_node(state: GraphState) -> Dict[str, Any]:
    """Process query using Plan-and-Solve pattern with dspy."""
    logger.info("Query Processing Node: Starting processing")

    enriched_query = state.get("query_builder_result")
    if not enriched_query:
        logger.warning("No query_builder_result found in state")
        enriched_query = state.get("user_query", "")

    if not enriched_query:
        logger.error("No query to process")
        return {
            "query_processing_result": "",
            "query_processing_metadata": {"error": "No query to process"},
            "execution_path": state.get("execution_path", []) + ["query_processing_node"],
            "errors": (state.get("errors", []) or []) + ["No query to process"],
        }

    try:
        lm = get_or_create_dspy_lm()
        _ = lm  # LM kept for completeness; DSPy stores it globally

        tool_registry = get_tool_registry()
        tools = tool_registry.get_tool_descriptions() if settings.enable_tools else []

        workspace_id = state.get("workspace_id") or settings.workspace_id
        user_id = state.get("user_id")
        conversation_id = state.get("conversation_id")

        logger.info("Generating execution plan...")
        planner = Planner()

        tools_list = "\n".join([f"- {t['name']}: {t['description']}" for t in tools])
        planner_context = f"""
        AVAILABLE TOOLS:
        {tools_list}

        CONVERSATION HISTORY (Use ONLY for context, do NOT assume these results answer new queries):
        {enriched_query}
        """

        generated_plan = planner(question=enriched_query, context=planner_context)
        logger.info("Plan generated: %s", generated_plan)

        logger.info("Executing plan with ReAct...", plan_length=len(generated_plan))
        react_module = ReActWithTools(
            tools=tools,
            max_iterations=settings.max_react_iterations,
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        result = react_module(question=enriched_query, plan=generated_plan)

        answer = result.answer if hasattr(result, "answer") else str(result)
        reasoning_steps = result.reasoning_steps if hasattr(result, "reasoning_steps") else []
        tool_calls = result.tool_calls if hasattr(result, "tool_calls") else []

        if tool_calls:
            logger.info("Tool calls made: %s", len(tool_calls), tool_calls=tool_calls)

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

        logger.info(
            "Query Processing Node: Processing complete",
            answer_length=len(answer),
            reasoning_steps_count=len(reasoning_steps),
            tool_calls_count=len(tool_calls),
        )

        execution_path = state.get("execution_path", [])
        execution_path = execution_path + ["query_processing_node"] if execution_path else ["query_processing_node"]

        return {
            "query_processing_result": json.dumps(response_data, indent=2),
            "query_processing_metadata": {
                "reasoning_steps_count": len(reasoning_steps),
                "tool_calls_count": len(tool_calls),
                "tools_used": [tc["tool"] for tc in tool_calls],
                "generated_plan": generated_plan,
            },
            "tool_calls": tool_calls,
            "execution_path": execution_path,
            "metadata": {
                **state.get("metadata", {}),
                "query_processing_completed": True,
            },
        }

    except Exception as exc:  # pragma: no cover
        logger.error("Query processing failed", error=str(exc), exc_info=True)
        return {
            "query_processing_result": json.dumps({"error": str(exc), "answer": ""}),
            "query_processing_metadata": {"error": str(exc)},
            "execution_path": state.get("execution_path", []) + ["query_processing_node"],
            "errors": (state.get("errors", []) or []) + [f"Query processing error: {str(exc)}"],
        }

