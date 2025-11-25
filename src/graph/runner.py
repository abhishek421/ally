"""Helpers for running the LangGraph application."""

from functools import lru_cache
from typing import Any, Dict

from .builder import build_graph
from .state import GraphState


@lru_cache(maxsize=1)
def _get_compiled_graph():
    """Build and cache the compiled LangGraph application."""
    return build_graph()


def invoke_graph(state: GraphState) -> Dict[str, Any]:
    """Execute the compiled graph synchronously."""
    app = _get_compiled_graph()
    return app.invoke(state)


async def ainvoke_graph(state: GraphState) -> Dict[str, Any]:
    """Execute the compiled graph asynchronously."""
    app = _get_compiled_graph()
    return await app.ainvoke(state)


__all__ = ["invoke_graph", "ainvoke_graph"]


