"""Graph construction and configuration."""

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from ..nodes import (
    query_builder_node, 
    planner_node,
    agent_node,
    tool_node,
    finalizer_node
)
from ..utils.exceptions import GraphExecutionError
from ..utils.logger import get_logger
from ..config import get_settings
from .state import GraphState

logger = get_logger(__name__)
settings = get_settings()


def should_continue(state: GraphState) -> Literal["tools", "finalizer", "agent"]:
    """Determine the next step based on the agent's decision."""
    # Hard stop to avoid runaway recursion
    max_iters = settings.max_react_iterations or 10
    agent_iters = state.get("agent_iterations", 0)
    if agent_iters >= max_iters:
        return "finalizer"

    current_action = state.get("current_action", {})
    action = current_action.get("action")
    
    if action == "answer":
        return "finalizer"
    elif action == "use_tool":
        return "tools"
    
    # Default behavior for "continue" or unknown
    return "agent"


def build_graph() -> Any:
    """Build and configure the LangGraph state graph.

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Building graph structure")

    try:
        # Initialize the graph with state schema
        graph = StateGraph(GraphState)

        # Add nodes to the graph
        graph.add_node("query_builder", query_builder_node)
        graph.add_node("planner", planner_node)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tool_node)
        graph.add_node("finalizer", finalizer_node)

        # Define the flow
        graph.set_entry_point("query_builder")
        
        # Linear flow start
        graph.add_edge("query_builder", "planner")
        graph.add_edge("planner", "agent")
        
        # Conditional flow from agent
        graph.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                "finalizer": "finalizer",
                "agent": "agent"
            }
        )
        
        # Loop back from tools to agent
        graph.add_edge("tools", "agent")
        
        # End flow
        graph.add_edge("finalizer", END)

        # Compile the graph
        app = graph.compile()

        logger.info("Graph built successfully", nodes=["query_builder", "planner", "agent", "tools", "finalizer"])

        return app

    except Exception as e:
        logger.error("Failed to build graph", error=str(e), exc_info=True)
        raise GraphExecutionError(f"Graph construction failed: {str(e)}", e) from e
