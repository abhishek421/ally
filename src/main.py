"""Main application entry point."""

import asyncio
import sys
from typing import Any

from .config import get_settings
from .graph import build_graph
from .graph.state import GraphState
from .utils.exceptions import GraphExecutionError
from .utils.logger import configure_logging, get_logger

# Configure logging first
configure_logging()
logger = get_logger(__name__)


def create_initial_state(input_data: str | None = None, user_query: str | None = None) -> GraphState:
    """Create initial graph state.

    Args:
        input_data: Optional input data string
        user_query: Optional user query string

    Returns:
        Initial GraphState
    """
    return GraphState(
        input_data=input_data or "Sample input data",
        user_query=user_query or "Process this data",
        execution_path=[],
        metadata={"initialized": True},
    )


async def run_graph_async(input_data: str | None = None, user_query: str | None = None) -> dict[str, Any]:
    """Run the graph asynchronously.

    Args:
        input_data: Optional input data string
        user_query: Optional user query string

    Returns:
        Final state after graph execution
    """
    try:
        logger.info("Starting graph execution")

        # Build the graph
        app = build_graph()

        # Create initial state
        initial_state = create_initial_state(input_data=input_data, user_query=user_query)

        logger.info("Executing graph", initial_state_keys=list(initial_state.keys()))

        # Execute the graph
        final_state = await app.ainvoke(initial_state)

        logger.info(
            "Graph execution completed",
            execution_path=final_state.get("execution_path", []),
            has_query_builder_result="query_builder_result" in final_state,
        )

        return final_state

    except GraphExecutionError:
        raise
    except Exception as e:
        logger.error("Unexpected error during graph execution", error=str(e), exc_info=True)
        raise GraphExecutionError(f"Graph execution failed: {str(e)}", e) from e


def run_graph_sync(input_data: str | None = None, user_query: str | None = None) -> dict[str, Any]:
    """Run the graph synchronously.

    Args:
        input_data: Optional input data string
        user_query: Optional user query string

    Returns:
        Final state after graph execution
    """
    return asyncio.run(run_graph_async(input_data=input_data, user_query=user_query))


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    settings = get_settings()

    logger.info(
        "Starting application",
        app_name=settings.app_name,
        app_version=settings.app_version,
    )

    try:
        # Run the graph
        result = run_graph_sync(
            input_data="Hello from LangGraph",
            user_query="Process this message",
        )

        # Print results
        print("\n" + "=" * 60)
        print("Graph Execution Results")
        print("=" * 60)
        print(f"Execution Path: {' -> '.join(result.get('execution_path', []))}")
        print(f"\nQuery Builder Result: {result.get('query_builder_result', 'N/A')}")
        print(f"\nMetadata: {result.get('metadata', {})}")
        print("=" * 60 + "\n")

        logger.info("Application completed successfully")
        return 0

    except Exception as e:
        logger.error("Application failed", error=str(e), exc_info=True)
        print(f"\nError: {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

