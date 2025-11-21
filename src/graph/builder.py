"""Graph construction and configuration."""

from typing import Any

from langgraph.graph import END, StateGraph

from ..nodes import query_builder_node, query_processing_node
from ..utils.exceptions import GraphExecutionError
from ..utils.logger import get_logger
from .state import GraphState

logger = get_logger(__name__)


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
        graph.add_node("query_processing", query_processing_node)

        # Define the flow: query_builder -> query_processing -> END
        graph.set_entry_point("query_builder")
        graph.add_edge("query_builder", "query_processing")
        graph.add_edge("query_processing", END)

        # Compile the graph
        app = graph.compile()

        logger.info("Graph built successfully", nodes=["query_builder", "query_processing"])

        return app

    except Exception as e:
        logger.error("Failed to build graph", error=str(e), exc_info=True)
        raise GraphExecutionError(f"Graph construction failed: {str(e)}", e) from e

