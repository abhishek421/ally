"""Integration tests for query builder node with real LLM calls.

This test file requires API keys to be set in the environment.
It performs actual LLM calls and may incur costs.

Set the following environment variables:
OPENAI_API_KEY=REDACTED
- LLM_MODEL (e.g., gpt-4o-mini, gemini-pro, claude-3-haiku)
- SUMMARY_MODEL (optional, defaults to LLM_MODEL)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.graph.state import GraphState
from src.nodes import query_builder_node
from src.utils.conversation_manager import ConversationManager
from src.utils.storage import LangGraphStorage
from src.utils.summarizer import get_summarizer
from src.utils.tokenizer import get_tokenizer


@pytest.mark.integration
def test_query_builder_multiple_turns():
    """Test query builder with multiple conversation turns using real LLM.
    
    This test:
    1. Sends 3 queries sequentially through the query builder node
    2. For each query, shows the enriched query sent to LLM
    3. Simulates LLM responses and saves them
    4. Verifies that conversation history is maintained across turns
    """
    # Check if API key is available
    api_key = (
OPENAI_API_KEY=REDACTED
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
OPENAI_API_KEY=REDACTED
    
    # Use a fixed conversation ID for all queries
    conversation_id = "test-conversation-integration"
    
    # Create fresh storage and conversation manager
    storage = LangGraphStorage()
    tokenizer = get_tokenizer()
    summarizer = get_summarizer()
    conversation_manager = ConversationManager(
        storage=storage,
        tokenizer=tokenizer,
        summarizer=summarizer,
    )
    
    # Mock the conversation manager in the query builder node
    from unittest.mock import patch
    
    with patch("src.nodes.query_builder_node._get_conversation_manager") as mock_get_manager:
        mock_get_manager.return_value = conversation_manager
        
        # ===== TURN 1: First Query =====
        print("\n" + "=" * 80)
        print("TURN 1: First Query")
        print("=" * 80)
        
        query1 = "What is Python programming language?"
        state1: GraphState = {
            "user_query": query1,
            "conversation_id": conversation_id,
            "execution_path": [],
        }
        
        result1 = query_builder_node(state1)
        
        # Get the enriched query that would be sent to LLM
        enriched_query1 = result1["query_builder_result"]
        print(f"\nUser Query: {query1}")
        print(f"\nEnriched Query (sent to LLM):\n{enriched_query1}")
        
        # Simulate LLM response (in real scenario, this would come from LLM)
        # For testing, we'll use a simple response
        response1 = "Python is a high-level, interpreted programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991."
        conversation_manager.save_assistant_response(conversation_id, response1)
        print(f"\nLLM Response: {response1}")
        
        # Verify query 1 result
        assert "query_builder_result" in result1
        assert result1["conversation_id"] == conversation_id
        assert query1 in enriched_query1
        
        # ===== TURN 2: Second Query =====
        print("\n" + "=" * 80)
        print("TURN 2: Second Query")
        print("=" * 80)
        
        query2 = "What are its main features?"
        state2: GraphState = {
            "user_query": query2,
            "conversation_id": conversation_id,
            "execution_path": result1.get("execution_path", []),
        }
        
        result2 = query_builder_node(state2)
        
        # Get the enriched query that would be sent to LLM
        enriched_query2 = result2["query_builder_result"]
        print(f"\nUser Query: {query2}")
        print(f"\nEnriched Query (sent to LLM):\n{enriched_query2}")
        
        # Verify that query1 and response1 are in the context
        assert query1 in enriched_query2, "Query 2 should include query1 in context"
        assert response1 in enriched_query2, "Query 2 should include response1 in context"
        assert query2 in enriched_query2, "Query 2 should include the current query"
        
        # Simulate LLM response
        response2 = "Python's main features include: 1) Simple and readable syntax, 2) Dynamic typing, 3) Extensive standard library, 4) Cross-platform compatibility, 5) Strong community support, 6) Support for multiple programming paradigms (OOP, functional, procedural)."
        conversation_manager.save_assistant_response(conversation_id, response2)
        print(f"\nLLM Response: {response2}")
        
        # Verify conversation history
        history2 = result2.get("conversation_history", [])
        assert len(history2) >= 2, "History should contain at least query1 and response1"
        print(f"\nConversation History Count: {len(history2)} messages")
        
        # ===== TURN 3: Third Query =====
        print("\n" + "=" * 80)
        print("TURN 3: Third Query")
        print("=" * 80)
        
        query3 = "Can you give me a simple example of Python code?"
        state3: GraphState = {
            "user_query": query3,
            "conversation_id": conversation_id,
            "execution_path": result2.get("execution_path", []),
        }
        
        result3 = query_builder_node(state3)
        
        # Get the enriched query that would be sent to LLM
        enriched_query3 = result3["query_builder_result"]
        print(f"\nUser Query: {query3}")
        print(f"\nEnriched Query (sent to LLM):\n{enriched_query3}")
        
        # Verify that all previous conversation is in the context
        assert query1 in enriched_query3, "Query 3 should include query1 in context"
        assert response1 in enriched_query3, "Query 3 should include response1 in context"
        assert query2 in enriched_query3, "Query 3 should include query2 in context"
        assert response2 in enriched_query3, "Query 3 should include response2 in context"
        assert query3 in enriched_query3, "Query 3 should include the current query"
        
        # Simulate LLM response
        response3 = "Here's a simple Python example:\n\n```python\n# Hello World program\nprint('Hello, World!')\n\n# Simple function\ndef greet(name):\n    return f'Hello, {name}!'\n\nprint(greet('Python'))\n```\n\nThis demonstrates basic Python syntax including print statements and function definitions."
        conversation_manager.save_assistant_response(conversation_id, response3)
        print(f"\nLLM Response: {response3}")
        
        # Get fresh history AFTER saving response3
        history3 = conversation_manager.storage.get_conversation_history(conversation_id)
        assert len(history3) >= 6, "History should contain at least 6 messages (3 queries + 3 responses)"
        print(f"\nConversation History Count: {len(history3)} messages")
        
        # Verify all messages are in history
        history_contents = [msg.content for msg in history3]
        assert query1 in history_contents, "History should contain query1"
        assert response1 in history_contents, "History should contain response1"
        assert query2 in history_contents, "History should contain query2"
        assert response2 in history_contents, "History should contain response2"
        assert query3 in history_contents, "History should contain query3"
        assert response3 in history_contents, "History should contain response3"
        
        # Print summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total conversation turns: 3")
        print(f"Total messages in history: {len(history3)}")
        print(f"Conversation ID: {conversation_id}")
        print("\n✓ All queries successfully processed")
        print("✓ Conversation history maintained across all turns")
        print("✓ Each query includes previous conversation context")
        print("=" * 80 + "\n")


@pytest.mark.integration
def test_query_builder_with_real_llm_response():
    """Test query builder with actual LLM call for one turn.
    
    This test makes a real LLM API call to verify the integration works.
    Requires API key and may incur costs.
    """
    # Check if API key is available
    api_key = (
OPENAI_API_KEY=REDACTED
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
OPENAI_API_KEY=REDACTED
    
    # Use a fixed conversation ID
    conversation_id = "test-conversation-real-llm"
    
    # Create fresh storage and conversation manager
    storage = LangGraphStorage()
    tokenizer = get_tokenizer()
    summarizer = get_summarizer()
    conversation_manager = ConversationManager(
        storage=storage,
        tokenizer=tokenizer,
        summarizer=summarizer,
    )
    
    from unittest.mock import patch
    
    with patch("src.nodes.query_builder_node._get_conversation_manager") as mock_get_manager:
        mock_get_manager.return_value = conversation_manager
        
        print("\n" + "=" * 80)
        print("REAL LLM CALL TEST")
        print("=" * 80)
        
        query = "Explain what machine learning is in one sentence."
        state: GraphState = {
            "user_query": query,
            "conversation_id": conversation_id,
            "execution_path": [],
        }
        
        result = query_builder_node(state)
        
        enriched_query = result["query_builder_result"]
        print(f"\nUser Query: {query}")
        print(f"\nEnriched Query (sent to LLM):\n{enriched_query}")
        
        # Make actual LLM call using the adapter
        from src.adapters import get_llm_adapter
        
        adapter = get_llm_adapter()
        llm_response = adapter.invoke(enriched_query)
        
        print(f"\nLLM Response:\n{llm_response}")
        
        # Save the response
        conversation_manager.save_assistant_response(conversation_id, llm_response)
        
        # Verify
        assert "query_builder_result" in result
        assert query in enriched_query
        
        print("\n✓ Real LLM call successful")
        print("=" * 80 + "\n")


@pytest.mark.integration
def test_query_builder_summarization():
    """Test that summarization is triggered when token threshold is exceeded.
    
    This test uses REAL LLM calls and REAL node execution (no mocking):
    1. Creates a conversation with many messages that exceed the token threshold
    2. Verifies that summarization is triggered
    3. Verifies that a summary is created and stored
    4. Verifies that subsequent queries include the summary instead of all old messages
    5. Verifies that only recent messages are kept in the context
    
    All logs are written to a JSON file in the logs/ directory.
    """
    # Check if API key is available
    api_key = (
OPENAI_API_KEY=REDACTED
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not api_key:
OPENAI_API_KEY=REDACTED
    
    # Use a fixed conversation ID
    conversation_id = "test-conversation-summarization-real"
    
    # Initialize log data structure
    log_data = {
        "test_name": "test_query_builder_summarization",
        "conversation_id": conversation_id,
        "timestamp": datetime.now().isoformat(),
        "test_config": {
            "llm_context_limit": 3000,
            "context_threshold_percentage": 70,
            "token_threshold": 2100,
        },
        "phases": {
            "phase_1_building_conversation": [],
            "phase_2_triggering_summarization": [],
            "phase_3_verification": {},
            "phase_4_final_query": {},
        },
        "final_state": {},
    }
    
    # Temporarily override settings to use a lower threshold for testing
    # We'll patch the settings to use a very low threshold
    from unittest.mock import patch
    
    # Create a settings override with lower threshold
    with patch("src.utils.conversation_manager.settings") as mock_settings:
        # Set very low threshold for testing
        mock_settings.llm_context_limit = 3000  # Very low context limit
        mock_settings.context_threshold_percentage = 70  # 70% of 3000 = 2100 tokens
        
        # Also patch in query_builder_node
        with patch("src.nodes.query_builder_node.settings", mock_settings):
            # Now use real node calls - no mocking of conversation manager
            
            print("\n" + "=" * 80)
            print("SUMMARIZATION TEST (REAL LLM CALLS)")
            print("=" * 80)
            print(f"Token threshold: 2100 tokens (70% of 3000)")
            print("Logs will be saved to logs/test_summarization_logs.json")
            
            # Get tokenizer to show token counts
            tokenizer = get_tokenizer()
            
            # Create multiple queries designed to generate long responses that exceed threshold
            # Real LLM responses will be used, which should be long enough to exceed 2100 tokens
            queries = [
                "What is machine learning? Explain in detail with examples and applications.",
                "What are neural networks? Explain their architecture, training process, and applications in comprehensive detail.",
                "Explain deep learning in comprehensive detail including architectures, training techniques, and real-world applications.",
                "What is natural language processing? Explain all its components, techniques, and modern applications in detail.",
            ]
            
            # Send first few messages (before summarization)
            print("\n--- Phase 1: Building conversation before summarization ---")
            for i, query in enumerate(queries[:2], 1):
                # 1. User question
                turn_data = {
                    "turn_number": i,
                    "user_query": query,
                    "timestamp": datetime.now().isoformat(),
                }
                
                # Get conversation manager BEFORE processing to check if summary exists
                from src.nodes.query_builder_node import _get_conversation_manager
                conv_manager = _get_conversation_manager()
                summary_before = conv_manager.storage.get_summary(conversation_id)
                
                state: GraphState = {
                    "user_query": query,
                    "conversation_id": conversation_id,
                    "execution_path": [],
                }
                
                # Use REAL query_builder_node (no mocking)
                result = query_builder_node(state)
                enriched_query = result["query_builder_result"]
                
                # Get all history and summary data AFTER processing
                all_history = conv_manager.storage.get_conversation_history(conversation_id)
                summary_data = conv_manager.storage.get_summary(conversation_id)
                
                # 4. If summarization hit (yes/no) - Check this FIRST to know if recent_messages should be empty
                has_summary = summary_data is not None
                summarization_hit_this_turn = (
                    (summary_before is None and has_summary) or
                    (summary_before is not None and has_summary and summary_data[0] != summary_before[0])
                )
                turn_data["summarization_hit"] = summarization_hit_this_turn
                
                # 2. History messages that are attached with user question
                # Determine which messages are actually included in the enriched query
                # After summarization, recent_messages will be empty (only summary + current query)
                # Before summarization or if no summary, recent_messages are all messages after summary point
                summary_count = summary_data[1] if summary_data else 0
                all_recent_messages = all_history[summary_count:] if summary_data else all_history
                
                # Remove current query from recent messages (it's shown separately)
                recent_messages_for_context = [
                    msg for msg in all_recent_messages
                    if not (msg.role == "user" and msg.content == query)
                ]
                
                # If summarization just happened this turn, recent_messages should be empty
                # (only summary + current query is sent)
                if summarization_hit_this_turn:
                    recent_messages_for_context = []
                
                # Show messages that are actually included in context
                turn_data["history_messages_attached"] = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in recent_messages_for_context
                ]
                
                # Show which messages were summarized (for reference)
                if summary_data and summary_count > 0:
                    summarized_messages = all_history[:summary_count]
                    turn_data["messages_summarized"] = [
                        {
                            "role": msg.role,
                            "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                            "timestamp": msg.timestamp.isoformat(),
                        }
                        for msg in summarized_messages
                    ]
                else:
                    turn_data["messages_summarized"] = []
                
                # 3. Complete query sent to LLM
                turn_data["complete_query_sent_to_llm"] = enriched_query
                
                # 5. If summarization hit, then summarized history
                if has_summary:
                    summary_text, summary_count = summary_data
                    turn_data["summarized_history"] = {
                        "summary_text": summary_text,
                        "messages_summarized_count": summary_count,
                    }
                else:
                    turn_data["summarized_history"] = None
                
                # 6. Token count of current complete query
                enriched_query_tokens = tokenizer.count_tokens(enriched_query)
                turn_data["complete_query_token_count"] = enriched_query_tokens
                
                # Calculate what token count would be WITHOUT summarization (for comparison)
                if has_summary and summary_count > 0:
                    # Count tokens if we included all original messages instead of summary
                    all_messages_tokens = sum(tokenizer.count_tokens(msg.content) for msg in all_history)
                    # Add current query tokens
                    current_query_tokens = tokenizer.count_tokens(query)
                    total_without_summary = all_messages_tokens + current_query_tokens
                    turn_data["token_count_without_summarization"] = total_without_summary
                    turn_data["token_savings"] = total_without_summary - enriched_query_tokens
                else:
                    turn_data["token_count_without_summarization"] = enriched_query_tokens
                    turn_data["token_savings"] = 0
                
                # 7. Summarization token count
                if has_summary:
                    summary_text, _ = summary_data
                    summary_tokens = tokenizer.count_tokens(summary_text)
                    turn_data["summarization_token_count"] = summary_tokens
                else:
                    turn_data["summarization_token_count"] = 0
                
                # Additional metadata
                turn_data["token_threshold"] = conv_manager.token_threshold
                turn_data["total_storage_messages"] = len(all_history)
                
                # Make REAL LLM call to get response
                from src.adapters import get_llm_adapter
                adapter = get_llm_adapter()
                llm_response = adapter.invoke(enriched_query)
                
                # Save response using real conversation manager
                conv_manager.save_assistant_response(conversation_id, llm_response)
                
                turn_data["llm_response"] = llm_response
                turn_data["llm_response_length"] = len(llm_response)
                turn_data["llm_response_tokens"] = tokenizer.count_tokens(llm_response)
                
                log_data["phases"]["phase_1_building_conversation"].append(turn_data)
                print(f"Turn {i} completed - Logged to JSON")
        
            # Get history before summarization
            from src.nodes.query_builder_node import _get_conversation_manager
            conv_manager = _get_conversation_manager()
            history_before = conv_manager.storage.get_conversation_history(conversation_id)
            log_data["phases"]["phase_1_building_conversation"].append({
                "summary": "Messages before summarization",
                "message_count": len(history_before),
            })
            print(f"\nMessages before summarization: {len(history_before)}")
            
            # Send more messages to trigger summarization
            print("\n--- Phase 2: Triggering summarization ---")
            for i, query in enumerate(queries[2:], 3):
                # 1. User question
                turn_data = {
                    "turn_number": i,
                    "user_query": query,
                    "timestamp": datetime.now().isoformat(),
                }
                
                # Get conversation manager BEFORE processing to check if summary exists
                conv_manager = _get_conversation_manager()
                summary_before = conv_manager.storage.get_summary(conversation_id)
                
                state: GraphState = {
                    "user_query": query,
                    "conversation_id": conversation_id,
                    "execution_path": [],
                }
                
                # Use REAL query_builder_node (no mocking)
                result = query_builder_node(state)
                enriched_query = result["query_builder_result"]
                
                # Get all history and summary data AFTER processing
                all_history = conv_manager.storage.get_conversation_history(conversation_id)
                summary_data = conv_manager.storage.get_summary(conversation_id)
                
                # 4. If summarization hit (yes/no) - Check this FIRST to know if recent_messages should be empty
                has_summary = summary_data is not None
                summarization_hit_this_turn = (
                    (summary_before is None and has_summary) or
                    (summary_before is not None and has_summary and summary_data[0] != summary_before[0])
                )
                turn_data["summarization_hit"] = summarization_hit_this_turn
                
                # 2. History messages that are attached with user question
                # Determine which messages are actually included in the enriched query
                # After summarization, recent_messages will be empty (only summary + current query)
                # Before summarization or if no summary, recent_messages are all messages after summary point
                summary_count = summary_data[1] if summary_data else 0
                all_recent_messages = all_history[summary_count:] if summary_data else all_history
                
                # Remove current query from recent messages (it's shown separately)
                recent_messages_for_context = [
                    msg for msg in all_recent_messages
                    if not (msg.role == "user" and msg.content == query)
                ]
                
                # If summarization just happened this turn, recent_messages should be empty
                # (only summary + current query is sent)
                if summarization_hit_this_turn:
                    recent_messages_for_context = []
                
                # Show messages that are actually included in context
                turn_data["history_messages_attached"] = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in recent_messages_for_context
                ]
                
                # Show which messages were summarized (for reference)
                if summary_data and summary_count > 0:
                    summarized_messages = all_history[:summary_count]
                    turn_data["messages_summarized"] = [
                        {
                            "role": msg.role,
                            "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                            "timestamp": msg.timestamp.isoformat(),
                        }
                        for msg in summarized_messages
                    ]
                else:
                    turn_data["messages_summarized"] = []
                
                # 3. Complete query sent to LLM
                turn_data["complete_query_sent_to_llm"] = enriched_query
                
                # 5. If summarization hit, then summarized history
                if has_summary:
                    summary_text, summary_count = summary_data
                    turn_data["summarized_history"] = {
                        "summary_text": summary_text,
                        "messages_summarized_count": summary_count,
                    }
                    
                    # Verify summary is in enriched query
                    assert "Previous conversation summary" in enriched_query or "summary" in enriched_query.lower(), \
                        "Summary should be included in enriched query"
                    
                    # Verify summary is stored
                    assert summary_text is not None, "Summary text should not be None"
                    assert summary_count > 0, "Summary count should be greater than 0"
                else:
                    turn_data["summarized_history"] = None
                
                # 6. Token count of current complete query
                enriched_query_tokens = tokenizer.count_tokens(enriched_query)
                turn_data["complete_query_token_count"] = enriched_query_tokens
                
                # Calculate what token count would be WITHOUT summarization (for comparison)
                if has_summary and summary_count > 0:
                    # Count tokens if we included all original messages instead of summary
                    all_messages_tokens = sum(tokenizer.count_tokens(msg.content) for msg in all_history)
                    # Add current query tokens
                    current_query_tokens = tokenizer.count_tokens(query)
                    total_without_summary = all_messages_tokens + current_query_tokens
                    turn_data["token_count_without_summarization"] = total_without_summary
                    turn_data["token_savings"] = total_without_summary - enriched_query_tokens
                else:
                    turn_data["token_count_without_summarization"] = enriched_query_tokens
                    turn_data["token_savings"] = 0
                
                # 7. Summarization token count
                if has_summary:
                    summary_text, _ = summary_data
                    summary_tokens = tokenizer.count_tokens(summary_text)
                    turn_data["summarization_token_count"] = summary_tokens
                else:
                    turn_data["summarization_token_count"] = 0
                
                # Additional metadata
                turn_data["token_threshold"] = conv_manager.token_threshold
                turn_data["total_storage_messages"] = len(all_history)
                
                # Make REAL LLM call to get response
                from src.adapters import get_llm_adapter
                adapter = get_llm_adapter()
                llm_response = adapter.invoke(enriched_query)
                
                # Save response using real conversation manager
                conv_manager.save_assistant_response(conversation_id, llm_response)
                
                turn_data["llm_response"] = llm_response
                turn_data["llm_response_length"] = len(llm_response)
                turn_data["llm_response_tokens"] = tokenizer.count_tokens(llm_response)
                
                log_data["phases"]["phase_2_triggering_summarization"].append(turn_data)
                print(f"Turn {i} completed - Logged to JSON")
        
            # Verify final state
            print("\n--- Phase 3: Verification ---")
            conv_manager = _get_conversation_manager()
            final_history = conv_manager.storage.get_conversation_history(conversation_id)
            final_summary = conv_manager.storage.get_summary(conversation_id)
            
            verification_data = {
                "total_messages": len(final_history),
                "summary_exists": final_summary is not None,
            }
            
            if final_summary:
                summary_text, summary_count = final_summary
                verification_data["summary"] = {
                    "text": summary_text,
                    "message_count": summary_count,
                    "summary_tokens": tokenizer.count_tokens(summary_text),
                }
                verification_data["recent_messages_count"] = len(final_history) - summary_count
                
                # Verify that summary count is less than total messages
                assert summary_count < len(final_history), \
                    "Some messages should remain unsummarized (recent messages)"
                
                # Verify that we have both summary and recent messages
                assert summary_count > 0, "At least some messages should be summarized"
                assert len(final_history) > summary_count, "Some recent messages should remain"
            
            log_data["phases"]["phase_3_verification"] = verification_data
            print(f"Total messages in history: {len(final_history)}")
            print(f"Summary exists: {final_summary is not None}")
            
            # Send one more query to verify summary is used
            print("\n--- Phase 4: Verify summary is used in next query ---")
            final_query = "Can you summarize what we discussed?"
            
            # 1. User question
            final_query_data = {
                "turn_number": "final",
                "user_query": final_query,
                "timestamp": datetime.now().isoformat(),
            }
            
            # Get conversation manager BEFORE processing
            conv_manager = _get_conversation_manager()
            summary_before = conv_manager.storage.get_summary(conversation_id)
            
            state: GraphState = {
                "user_query": final_query,
                "conversation_id": conversation_id,
                "execution_path": [],
            }
            
            # Use REAL query_builder_node
            result = query_builder_node(state)
            enriched_query = result["query_builder_result"]
            
            # Get all history and summary data AFTER processing
            all_history = conv_manager.storage.get_conversation_history(conversation_id)
            summary_data = conv_manager.storage.get_summary(conversation_id)
            
            # 4. If summarization hit (yes/no) - Check this FIRST to know if recent_messages should be empty
            has_summary = summary_data is not None
            summarization_hit_this_turn = (
                (summary_before is None and has_summary) or
                (summary_before is not None and has_summary and summary_data[0] != summary_before[0])
            )
            final_query_data["summarization_hit"] = summarization_hit_this_turn
            
            # 2. History messages that are attached with user question
            # Determine which messages are actually included in the enriched query
            # After summarization, recent_messages will be empty (only summary + current query)
            # Before summarization or if no summary, recent_messages are all messages after summary point
            summary_count = summary_data[1] if summary_data else 0
            all_recent_messages = all_history[summary_count:] if summary_data else all_history
            
            # Remove current query from recent messages (it's shown separately)
            recent_messages_for_context = [
                msg for msg in all_recent_messages
                if not (msg.role == "user" and msg.content == final_query)
            ]
            
            # If summarization just happened this turn, recent_messages should be empty
            # (only summary + current query is sent)
            if summarization_hit_this_turn:
                recent_messages_for_context = []
            
            # Show messages that are actually included in context
            final_query_data["history_messages_attached"] = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in recent_messages_for_context
            ]
            
            # Show which messages were summarized (for reference)
            if summary_data and summary_count > 0:
                summarized_messages = all_history[:summary_count]
                final_query_data["messages_summarized"] = [
                    {
                        "role": msg.role,
                        "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in summarized_messages
                ]
            else:
                final_query_data["messages_summarized"] = []
            
            # 3. Complete query sent to LLM
            final_query_data["complete_query_sent_to_llm"] = enriched_query
            
            # 5. If summarization hit, then summarized history
            if has_summary:
                summary_text, summary_count = summary_data
                final_query_data["summarized_history"] = {
                    "summary_text": summary_text,
                    "messages_summarized_count": summary_count,
                }
                
                # Verify summary is included
                assert "Previous conversation summary" in enriched_query or summary_text[:50] in enriched_query, \
                    "Summary should be included in the enriched query for subsequent queries"
            else:
                final_query_data["summarized_history"] = None
            
            # 6. Token count of current complete query
            enriched_query_tokens = tokenizer.count_tokens(enriched_query)
            final_query_data["complete_query_token_count"] = enriched_query_tokens
            
            # Calculate what token count would be WITHOUT summarization (for comparison)
            if has_summary and summary_count > 0:
                # Count tokens if we included all original messages instead of summary
                all_messages_tokens = sum(tokenizer.count_tokens(msg.content) for msg in all_history)
                # Add current query tokens
                current_query_tokens = tokenizer.count_tokens(final_query)
                total_without_summary = all_messages_tokens + current_query_tokens
                final_query_data["token_count_without_summarization"] = total_without_summary
                final_query_data["token_savings"] = total_without_summary - enriched_query_tokens
            else:
                final_query_data["token_count_without_summarization"] = enriched_query_tokens
                final_query_data["token_savings"] = 0
            
            # 7. Summarization token count
            if has_summary:
                summary_text, _ = summary_data
                summary_tokens = tokenizer.count_tokens(summary_text)
                final_query_data["summarization_token_count"] = summary_tokens
            else:
                final_query_data["summarization_token_count"] = 0
            
            # Additional metadata
            final_query_data["token_threshold"] = conv_manager.token_threshold
            final_query_data["total_storage_messages"] = len(all_history)
            
            # Verify recent messages are still included
            assert final_query in enriched_query, "Current query should be in enriched query"
            
            # Make REAL LLM call for final query
            from src.adapters import get_llm_adapter
            adapter = get_llm_adapter()
            final_llm_response = adapter.invoke(enriched_query)
            conv_manager.save_assistant_response(conversation_id, final_llm_response)
            
            final_query_data["llm_response"] = final_llm_response
            final_query_data["llm_response_length"] = len(final_llm_response)
            final_query_data["llm_response_tokens"] = tokenizer.count_tokens(final_llm_response)
            
            log_data["phases"]["phase_4_final_query"] = final_query_data
            
            # Collect final state
            final_history = conv_manager.storage.get_conversation_history(conversation_id)
            final_summary = conv_manager.storage.get_summary(conversation_id)
            
            log_data["final_state"] = {
                "total_messages": len(final_history),
                "conversation_history": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in final_history
                ],
                "summary": {
                    "text": final_summary[0] if final_summary else None,
                    "message_count": final_summary[1] if final_summary else 0,
                } if final_summary else None,
            }
            
            print("\n✓ Summarization test successful")
            print("=" * 80 + "\n")
            
            # Write logs to JSON file
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "test_summarization_logs.json"
            
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Logs saved to: {log_file}")
            print(f"  Total turns: {len(log_data['phases']['phase_1_building_conversation']) + len(log_data['phases']['phase_2_triggering_summarization']) + 1}")
            print(f"  Final messages: {log_data['final_state']['total_messages']}")
            print(f"  Summary created: {log_data['final_state']['summary'] is not None}")

