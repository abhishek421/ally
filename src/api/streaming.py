"""Streaming utilities for the API."""

import json
import logging
import uuid
from typing import AsyncGenerator, Dict, Any, Optional

from sse_starlette.sse import EventSourceResponse

from ..graph.runner import astream_graph
from ..graph.state import GraphState
from ..utils.conversation_service import create_conversation_sync, generate_title_from_query
from ..utils.conversation_message_service import (
    _save_user_message_sync,
    save_assistant_message_async,
    prepare_metadata_from_response,
    prepare_function_calls,
)
from ..utils.reasoning_formatter import (
    format_reasoning_step,
    format_tool_call_for_display,
)
from .models import StreamChunk, StreamChunkType

logger = logging.getLogger(__name__)


def _create_chunk(chunk_type: StreamChunkType, content: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a formatted SSE chunk."""
    chunk = StreamChunk(
        type=chunk_type,
        content=content,
        data=data
    )
    return {
        "event": "message",
        "data": chunk.model_dump_json()
    }


async def stream_graph_response(initial_state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream graph execution results as SSE events.
    
    This implementation runs the graph and streams results in real-time
    as nodes complete their execution.
    
    Args:
        initial_state: The initial state of the graph.
        
    Yields:
        Dict containing the SSE event data.
    """
    conversation_id = initial_state.get("conversation_id")
    workspace_id = initial_state.get("workspace_id")
    user_id = initial_state.get("user_id")
    user_query = initial_state.get("user_query", "")
    
    try:
        # Handle conversation creation if needed
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            initial_state["conversation_id"] = conversation_id
            
            logger.info(
                "Creating new conversation for streaming",
                extra={
                    "conversation_id": conversation_id,
                    "workspace_id": workspace_id,
                }
            )
            
            # Generate title and create conversation
            title = generate_title_from_query(user_query)
            try:
                create_conversation_sync(
                    conversation_id=conversation_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    title=title,
                )
            except Exception as e:
                logger.error(f"Failed to create conversation: {e}")
                yield _create_chunk(StreamChunkType.ERROR, f"Failed to create conversation: {str(e)}")
                return
            
            # Save user message
            try:
                _save_user_message_sync(
                    conversation_id=conversation_id,
                    content=user_query,
                )
            except Exception as e:
                logger.error(f"Failed to save user message: {e}")
                # Continue anyway - don't fail the whole request
        
        # Send initial reasoning chunk to indicate processing started
        yield _create_chunk(StreamChunkType.REASONING, "🔄 Let me look into that for you...")
        
        # Execute the graph with streaming
        logger.info(f"Starting graph execution for streaming, conversation_id={conversation_id}")
        
        final_state = initial_state.copy()
        
        # Keep track of seen items to avoid duplicates if nodes yield cumulative lists
        seen_reasoning = set()
        
        async for chunk in astream_graph(initial_state):
            # chunk is a dict like {node_name: state_update}
            for node_name, state_update in chunk.items():
                # Update final state with the new data
                final_state.update(state_update)
                
                if node_name == "agent":
                    # Stream new reasoning steps
                    reasoning_steps = state_update.get("reasoning_steps", [])
                    if reasoning_steps:
                        # Get the last step which is the new one
                        last_step = reasoning_steps[-1]
                        if last_step not in seen_reasoning:
                            seen_reasoning.add(last_step)
                            formatted_step = format_reasoning_step(last_step)
                            if formatted_step:
                                yield _create_chunk(StreamChunkType.REASONING, formatted_step)
                            
                elif node_name == "tools":
                    # Stream new tool calls
                    tool_calls = state_update.get("tool_calls", [])
                    if tool_calls:
                        last_tool_call = tool_calls[-1]
                        formatted_tool = format_tool_call_for_display(last_tool_call)
                        yield _create_chunk(
                            StreamChunkType.TOOL_CALL,
                            f"✅ {formatted_tool['tool']}",
                            data={
                                "tool": formatted_tool['tool'],
                                "tool_id": formatted_tool['tool_id'],
                                "params": formatted_tool['params'],
                                "status": "completed",
                            }
                        )
        
        # Graph execution finished. Process final result.
        query_processing_result = final_state.get("query_processing_result", "")
        
        if not query_processing_result:
            yield _create_chunk(StreamChunkType.ERROR, "No response generated")
            return
        
        # Parse the result
        try:
            result_data = json.loads(query_processing_result)
        except json.JSONDecodeError:
            result_data = {
                "answer": query_processing_result,
                "reasoning_steps": [],
                "tool_calls": [],
            }
        
        # Stream the answer token by token (simulated streaming for now)
        answer = result_data.get("answer", "")
        if answer:
            # Stream in chunks for better UX
            chunk_size = 10  # Characters per chunk
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield _create_chunk(StreamChunkType.TOKEN, chunk)
        
        # Get final conversation_id from state
        final_conversation_id = final_state.get("conversation_id", conversation_id)
        
        # Send done signal with conversation_id
        yield _create_chunk(
            StreamChunkType.DONE,
            "",
            data={"conversation_id": final_conversation_id}
        )
        
        # Save assistant message in background
        try:
            query_processing_metadata = final_state.get("query_processing_metadata", {})
            tool_calls = result_data.get("tool_calls", [])
            storage_metadata = prepare_metadata_from_response(result_data, query_processing_metadata)
            storage_function_calls = prepare_function_calls(tool_calls)
            
            save_assistant_message_async(
                conversation_id=final_conversation_id,
                content=answer,  # Already cleaned above
                metadata=storage_metadata,
                function_calls=storage_function_calls if storage_function_calls else None,
            )
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")

    except Exception as e:
        logger.error(f"Error in stream_graph_response: {e}", exc_info=True)
        yield _create_chunk(StreamChunkType.ERROR, f"Error: {str(e)}")


def create_sse_response(generator: AsyncGenerator[Dict[str, Any], None]) -> EventSourceResponse:
    """
    Create an EventSourceResponse from an async generator.
    
    Args:
        generator: The async generator yielding SSE events.
        
    Returns:
        EventSourceResponse configured for the generator.
    """
    return EventSourceResponse(generator)
