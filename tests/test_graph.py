"""Tests for graph construction and execution."""

import pytest

from src.graph import build_graph
from src.graph.state import GraphState


@pytest.mark.asyncio
async def test_graph_builds_successfully():
    """Test that the graph builds without errors."""
    app = build_graph()
    assert app is not None


@pytest.mark.asyncio
async def test_graph_execution():
    """Test full graph execution."""
    app = build_graph()

    initial_state: GraphState = {
        "input_data": "test execution",
        "user_query": "test query",
        "execution_path": [],
        "metadata": {},
    }

    result = await app.ainvoke(initial_state)

    assert "execution_path" in result
    # Graph structure is currently empty, so execution_path will be empty
    # Update assertions when nodes are added to the graph


@pytest.mark.asyncio
async def test_graph_execution_path():
    """Test that execution path is correctly tracked."""
    app = build_graph()

    initial_state: GraphState = {
        "input_data": "path test",
        "execution_path": [],
    }

    result = await app.ainvoke(initial_state)

    execution_path = result.get("execution_path", [])
    # Graph structure is currently empty, so execution_path will be empty
    # Update assertions when nodes are added to the graph
    assert isinstance(execution_path, list)

