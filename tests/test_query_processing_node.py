"""Integration tests for query processing node with real LLM calls.

This test file requires API keys to be set in the environment.
It performs actual LLM calls and may incur costs.

Set the following environment variables:
- OPENAI_API_KEY (or GOOGLE_API_KEY or ANTHROPIC_API_KEY)
- QUERY_PROCESSING_MODEL (e.g., gpt-4o, gemini-pro, claude-3-opus)
- WORKSPACE_ID (UUID of the workspace to query)
- DATABASE_URL (PostgreSQL connection string)
"""

import json
import os
from typing import Any

import pytest

from src.graph.state import GraphState
from src.nodes import query_processing_node


@pytest.mark.integration
def test_query_processing_total_companies():
    """Test query processing node with query 'total number of companies'.
    
    This test:
    1. Creates a state with the query
    2. Calls query_processing_node (which should call get_workspace_summary tool)
    3. Verifies the ReAct pattern executed
    4. Verifies tool was called
    5. Verifies response format
    """
    # Check if API key is available
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
        pytest.skip("No API key found. Set OPENAI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY")
    
    # Check if workspace_id is set
    workspace_id = os.getenv("WORKSPACE_ID")
    if not workspace_id:
        pytest.skip("WORKSPACE_ID not set in environment")
    
    # Create initial state
    state: GraphState = {
        "user_query": "total number of companies",
        "workspace_id": workspace_id,
        "query_builder_result": "Current query: total number of companies",
        "execution_path": ["query_builder_node"],
        "metadata": {},
    }
    
    print("\n" + "=" * 80)
    print("Testing Query Processing Node")
    print("=" * 80)
    print(f"Query: {state['user_query']}")
    print(f"Workspace ID: {workspace_id}")
    print("\nExecuting query_processing_node...")
    print("-" * 80)
    
    # Execute query processing node
    result = query_processing_node(state)
    
    # Print results
    print("\n" + "=" * 80)
    print("Query Processing Results")
    print("=" * 80)
    
    # Parse JSON result
    if result.get("query_processing_result"):
        try:
            response_data = json.loads(result["query_processing_result"])
            print(f"\nAnswer: {response_data.get('answer', 'N/A')}")
            print(f"\nReasoning Steps: {len(response_data.get('reasoning_steps', []))}")
            for i, step in enumerate(response_data.get("reasoning_steps", []), 1):
                print(f"  Step {i}: {step[:200]}...")
            
            print(f"\nTool Calls: {len(response_data.get('tool_calls', []))}")
            for i, tool_call in enumerate(response_data.get("tool_calls", []), 1):
                print(f"\n  Tool Call {i}:")
                print(f"    Tool: {tool_call.get('tool', 'N/A')}")
                print(f"    Params: {tool_call.get('params', {})}")
                print(f"    Result Preview: {str(tool_call.get('result', ''))[:200]}...")
                print(f"    Iteration: {tool_call.get('iteration', 'N/A')}")
            
            print(f"\nMetadata:")
            print(f"  Iterations: {response_data.get('metadata', {}).get('iterations', 'N/A')}")
            print(f"  Tools Used: {response_data.get('metadata', {}).get('tools_used', [])}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON result: {e}")
            print(f"Raw result: {result.get('query_processing_result', '')[:500]}")
    
    print(f"\nQuery Processing Metadata:")
    print(f"  Reasoning Steps Count: {result.get('query_processing_metadata', {}).get('reasoning_steps_count', 0)}")
    print(f"  Tool Calls Count: {result.get('query_processing_metadata', {}).get('tool_calls_count', 0)}")
    print(f"  Tools Used: {result.get('query_processing_metadata', {}).get('tools_used', [])}")
    
    print(f"\nExecution Path: {' -> '.join(result.get('execution_path', []))}")
    
    if result.get("errors"):
        print(f"\nErrors: {result.get('errors')}")
    
    print("\n" + "=" * 80)
    
    # Assertions
    assert "query_processing_result" in result, "query_processing_result should be in result"
    assert result.get("query_processing_metadata") is not None, "query_processing_metadata should be present"
    
    # Parse and verify JSON response
    response_data = json.loads(result["query_processing_result"])
    assert "answer" in response_data, "Response should contain 'answer'"
    assert "reasoning_steps" in response_data, "Response should contain 'reasoning_steps'"
    assert "tool_calls" in response_data, "Response should contain 'tool_calls'"
    
    # Verify that a tool was called (should call get_workspace_summary or search_companies)
    tool_calls = response_data.get("tool_calls", [])
    assert len(tool_calls) > 0, "At least one tool should be called for this query"
    
    # Verify a relevant tool was called (either get_workspace_summary or search_companies is acceptable)
    tool_names = [tc.get("tool") for tc in tool_calls]
    valid_tools = ["get_workspace_summary", "search_companies"]
    assert any(tool in tool_names for tool in valid_tools), f"Expected one of {valid_tools} to be called. Got: {tool_names}"
    
    # Verify workspace_id was injected
    for tool_call in tool_calls:
        assert "workspace_id" in tool_call.get("params", {}), f"workspace_id should be in tool params for {tool_call.get('tool')}"
        assert tool_call["params"]["workspace_id"] == workspace_id, f"workspace_id should match for {tool_call.get('tool')}"
    
    # Verify answer contains information about companies
    answer = response_data.get("answer", "").lower()
    assert len(answer) > 0, "Answer should not be empty"
    
    print("\nAll assertions passed!")
    print("=" * 80 + "\n")


@pytest.mark.integration
def test_query_processing_search_people():
    """Test query processing node with a search query.
    
    This test verifies that the node can handle queries that require
    searching for people using the search_people tool.
    """
    # Check if API key is available
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
        pytest.skip("No API key found. Set OPENAI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY")
    
    # Check if workspace_id is set
    workspace_id = os.getenv("WORKSPACE_ID")
    if not workspace_id:
        pytest.skip("WORKSPACE_ID not set in environment")
    
    # Create initial state
    state: GraphState = {
        "user_query": "find people with job title manager",
        "workspace_id": workspace_id,
        "query_builder_result": "Current query: find people with job title manager",
        "execution_path": ["query_builder_node"],
        "metadata": {},
    }
    
    print("\n" + "=" * 80)
    print("Testing Query Processing Node - Search People")
    print("=" * 80)
    print(f"Query: {state['user_query']}")
    print(f"Workspace ID: {workspace_id}")
    print("\nExecuting query_processing_node...")
    print("-" * 80)
    
    # Execute query processing node
    result = query_processing_node(state)
    
    # Parse JSON result
    if result.get("query_processing_result"):
        try:
            response_data = json.loads(result["query_processing_result"])
            print(f"\nAnswer: {response_data.get('answer', 'N/A')}")
            
            print(f"\nTool Calls: {len(response_data.get('tool_calls', []))}")
            for i, tool_call in enumerate(response_data.get("tool_calls", []), 1):
                print(f"\n  Tool Call {i}:")
                print(f"    Tool: {tool_call.get('tool', 'N/A')}")
                print(f"    Params: {tool_call.get('params', {})}")
                print(f"    Result Preview: {str(tool_call.get('result', ''))[:200]}...")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON result: {e}")
    
    print("\n" + "=" * 80)
    
    # Assertions
    assert "query_processing_result" in result, "query_processing_result should be in result"
    
    response_data = json.loads(result["query_processing_result"])
    assert "answer" in response_data, "Response should contain 'answer'"
    
    # Verify that a tool was called
    tool_calls = response_data.get("tool_calls", [])
    if len(tool_calls) > 0:
        tool_names = [tc.get("tool") for tc in tool_calls]
        print(f"Tools called: {tool_names}")
    
    print("\n✅ Test completed!")
    print("=" * 80 + "\n")


@pytest.mark.integration
def test_query_processing_with_context():
    """Test query processing node with conversation context.
    
    This test verifies that the node can handle queries with
    conversation history from query_builder_node.
    """
    # Check if API key is available
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
        pytest.skip("No API key found. Set OPENAI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY")
    
    # Check if workspace_id is set
    workspace_id = os.getenv("WORKSPACE_ID")
    if not workspace_id:
        pytest.skip("WORKSPACE_ID not set in environment")
    
    # Create state with enriched query (as would come from query_builder_node)
    enriched_query = """Previous conversation summary:
We discussed company statistics and workspace information.

Recent conversation history:
user: how many companies are there?
assistant: There are 150 companies in the workspace.

Current query: what about people?"""
    
    state: GraphState = {
        "user_query": "what about people?",
        "workspace_id": workspace_id,
        "query_builder_result": enriched_query,
        "execution_path": ["query_builder_node"],
        "metadata": {},
    }
    
    print("\n" + "=" * 80)
    print("Testing Query Processing Node - With Context")
    print("=" * 80)
    print(f"Query: {state['user_query']}")
    print(f"Enriched Query Length: {len(enriched_query)}")
    print("\nExecuting query_processing_node...")
    print("-" * 80)
    
    # Execute query processing node
    result = query_processing_node(state)
    
    # Parse JSON result
    if result.get("query_processing_result"):
        try:
            response_data = json.loads(result["query_processing_result"])
            print(f"\nAnswer: {response_data.get('answer', 'N/A')}")
            
            print(f"\nReasoning Steps: {len(response_data.get('reasoning_steps', []))}")
            for i, step in enumerate(response_data.get("reasoning_steps", [])[:3], 1):
                print(f"  Step {i}: {step[:150]}...")
            
            print(f"\nTool Calls: {len(response_data.get('tool_calls', []))}")
            for i, tool_call in enumerate(response_data.get("tool_calls", []), 1):
                print(f"  Tool {i}: {tool_call.get('tool', 'N/A')}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON result: {e}")
    
    print("\n" + "=" * 80)
    
    # Assertions
    assert "query_processing_result" in result, "query_processing_result should be in result"
    
    response_data = json.loads(result["query_processing_result"])
    assert "answer" in response_data, "Response should contain 'answer'"
    assert len(response_data.get("answer", "")) > 0, "Answer should not be empty"
    
    print("\n✅ Test completed!")
    print("=" * 80 + "\n")


@pytest.mark.integration
def test_query_processing_total_people():
    """Test query processing node with query 'get me total number of people'.
    
    This test:
    1. Creates a state with the query
    2. Calls query_processing_node (which should call get_workspace_summary or search_people tool)
    3. Verifies the ReAct pattern executed
    4. Verifies tool was called
    5. Verifies response format
    """
    # Check if API key is available
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
        pytest.skip("No API key found. Set OPENAI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY")
    
    # Check if workspace_id is set
    workspace_id = os.getenv("WORKSPACE_ID")
    if not workspace_id:
        pytest.skip("WORKSPACE_ID not set in environment")
    
    # Create initial state
    state: GraphState = {
        "user_query": "get me total number of people",
        "workspace_id": workspace_id,
        "query_builder_result": "Current query: get me total number of people",
        "execution_path": ["query_builder_node"],
        "metadata": {},
    }
    
    print("\n" + "=" * 80)
    print("Testing Query Processing Node - Total People")
    print("=" * 80)
    print(f"Query: {state['user_query']}")
    print(f"Workspace ID: {workspace_id}")
    print("\nExecuting query_processing_node...")
    print("-" * 80)
    
    # Execute query processing node
    result = query_processing_node(state)
    
    # Print results
    print("\n" + "=" * 80)
    print("Query Processing Results")
    print("=" * 80)
    
    # Parse JSON result
    if result.get("query_processing_result"):
        try:
            response_data = json.loads(result["query_processing_result"])
            print(f"\nAnswer: {response_data.get('answer', 'N/A')}")
            print(f"\nReasoning Steps: {len(response_data.get('reasoning_steps', []))}")
            for i, step in enumerate(response_data.get("reasoning_steps", []), 1):
                print(f"  Step {i}: {step[:200]}...")
            
            print(f"\nTool Calls: {len(response_data.get('tool_calls', []))}")
            for i, tool_call in enumerate(response_data.get("tool_calls", []), 1):
                print(f"\n  Tool Call {i}:")
                print(f"    Tool: {tool_call.get('tool', 'N/A')}")
                print(f"    Params: {tool_call.get('params', {})}")
                print(f"    Result Preview: {str(tool_call.get('result', ''))[:200]}...")
                print(f"    Iteration: {tool_call.get('iteration', 'N/A')}")
            
            print(f"\nMetadata:")
            print(f"  Iterations: {response_data.get('metadata', {}).get('iterations', 'N/A')}")
            print(f"  Tools Used: {response_data.get('metadata', {}).get('tools_used', [])}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON result: {e}")
            print(f"Raw result: {result.get('query_processing_result', '')[:500]}")
    
    print(f"\nQuery Processing Metadata:")
    print(f"  Reasoning Steps Count: {result.get('query_processing_metadata', {}).get('reasoning_steps_count', 0)}")
    print(f"  Tool Calls Count: {result.get('query_processing_metadata', {}).get('tool_calls_count', 0)}")
    print(f"  Tools Used: {result.get('query_processing_metadata', {}).get('tools_used', [])}")
    
    print(f"\nExecution Path: {' -> '.join(result.get('execution_path', []))}")
    
    if result.get("errors"):
        print(f"\nErrors: {result.get('errors')}")
    
    print("\n" + "=" * 80)
    
    # Assertions
    assert "query_processing_result" in result, "query_processing_result should be in result"
    assert result.get("query_processing_metadata") is not None, "query_processing_metadata should be present"
    
    # Parse and verify JSON response
    response_data = json.loads(result["query_processing_result"])
    assert "answer" in response_data, "Response should contain 'answer'"
    assert "reasoning_steps" in response_data, "Response should contain 'reasoning_steps'"
    assert "tool_calls" in response_data, "Response should contain 'tool_calls'"
    
    # Verify that a tool was called (should call get_workspace_summary or search_people)
    tool_calls = response_data.get("tool_calls", [])
    assert len(tool_calls) > 0, "At least one tool should be called for this query"
    
    # Verify a relevant tool was called
    tool_names = [tc.get("tool") for tc in tool_calls]
    valid_tools = ["get_workspace_summary", "search_people"]
    assert any(tool in tool_names for tool in valid_tools), f"Expected one of {valid_tools} to be called. Got: {tool_names}"
    
    # Verify workspace_id was injected
    for tool_call in tool_calls:
        assert "workspace_id" in tool_call.get("params", {}), f"workspace_id should be in tool params for {tool_call.get('tool')}"
        assert tool_call["params"]["workspace_id"] == workspace_id, f"workspace_id should match for {tool_call.get('tool')}"
    
    # Verify answer contains information about people
    answer = response_data.get("answer", "").lower()
    assert len(answer) > 0, "Answer should not be empty"
    assert "10" in answer, f"Answer should contain the total count '10'. Got: {answer}"
    

    print("\nAll assertions passed!")
    print("=" * 80 + "\n")


@pytest.mark.integration
def test_query_processing_list_all_companies():
    """Test query processing node with query 'list all the companies'.

    This test:
    1. Creates a state with the query
    2. Calls query_processing_node
    3. Prints the response (no assertions)
    """
    # Check if API key is available
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )

    if not api_key:
        pytest.skip("No API key found. Set OPENAI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY")

    # Check if workspace_id is set
    workspace_id = os.getenv("WORKSPACE_ID")
    if not workspace_id:
        pytest.skip("WORKSPACE_ID not set in environment")

    # Create initial state
    state: GraphState = {
        "user_query": "list all the companies",
        "workspace_id": workspace_id,
        "query_builder_result": "Current query: list all the companies",
        "execution_path": ["query_builder_node"],
        "metadata": {},
    }

    print("\n" + "=" * 80)
    print("Testing Query Processing Node - List All Companies")
    print("=" * 80)
    print(f"Query: {state['user_query']}")
    print(f"Workspace ID: {workspace_id}")
    print("\nExecuting query_processing_node...")
    print("-" * 80)

    # Execute query processing node
    result = query_processing_node(state)

    # Print results
    print("\n" + "=" * 80)
    print("Query Processing Results")
    print("=" * 80)

    # Parse JSON result
    if result.get("query_processing_result"):
        try:
            response_data = json.loads(result["query_processing_result"])
            print(f"\nAnswer: {response_data.get('answer', 'N/A')}")
            print(f"\nReasoning Steps: {len(response_data.get('reasoning_steps', []))}")
            for i, step in enumerate(response_data.get("reasoning_steps", []), 1):
                print(f"  Step {i}: {step[:200]}...")

            print(f"\nTool Calls: {len(response_data.get('tool_calls', []))}")
            for i, tool_call in enumerate(response_data.get("tool_calls", []), 1):
                print(f"\n  Tool Call {i}:")
                print(f"    Tool: {tool_call.get('tool', 'N/A')}")
                print(f"    Params: {tool_call.get('params', {})}")
                print(f"    Result Preview: {str(tool_call.get('result', ''))[:200]}...")
                print(f"    Iteration: {tool_call.get('iteration', 'N/A')}")

            print(f"\nMetadata:")
            print(f"  Iterations: {response_data.get('metadata', {}).get('iterations', 'N/A')}")
            print(f"  Tools Used: {response_data.get('metadata', {}).get('tools_used', [])}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON result: {e}")
            print(f"Raw result: {result.get('query_processing_result', '')[:500]}")

    print(f"\nQuery Processing Metadata:")
    print(f"  Reasoning Steps Count: {result.get('query_processing_metadata', {}).get('reasoning_steps_count', 0)}")
    print(f"  Tool Calls Count: {result.get('query_processing_metadata', {}).get('tool_calls_count', 0)}")
    print(f"  Tools Used: {result.get('query_processing_metadata', {}).get('tools_used', [])}")

    print(f"\nExecution Path: {' -> '.join(result.get('execution_path', []))}")

    if result.get("errors"):
        print(f"\nErrors: {result.get('errors')}")

    print("\n" + "=" * 80)

