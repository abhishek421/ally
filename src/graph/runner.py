"""Helpers for running the LangGraph application."""

from functools import lru_cache
from typing import Any, Dict, AsyncIterator

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


async def astream_graph(state: GraphState) -> AsyncIterator[Dict[str, Any]]:
    """Stream the compiled graph execution asynchronously."""
    app = _get_compiled_graph()
    async for event in app.astream(state):
        yield event


__all__ = ["invoke_graph", "ainvoke_graph", "astream_graph"]
