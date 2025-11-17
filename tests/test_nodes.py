"""Tests for node implementations."""

import pytest

from src.graph.state import GraphState
from src.nodes import query_builder_node


def test_query_builder_node_basic_execution():
    """Test Query Builder Node with basic input."""
    state: GraphState = {
        "input_data": "test input",
        "user_query": "test query",
        "execution_path": [],
    }

    result = query_builder_node(state)

    assert "query_builder_result" in result
    assert "execution_path" in result
    assert "query_builder_node" in result["execution_path"]


def test_query_builder_node_with_user_query():
    """Test Query Builder Node with user query."""
    state: GraphState = {
        "user_query": "What is the weather?",
        "execution_path": [],
    }

    result = query_builder_node(state)

    assert "query_builder_result" in result
    assert "execution_path" in result


def test_query_builder_node_no_input():
    """Test Query Builder Node with no input data."""
    state: GraphState = {
        "execution_path": [],
    }

    result = query_builder_node(state)

    assert "query_builder_result" in result
    assert "execution_path" in result
