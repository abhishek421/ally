"""Streaming utilities for API responses."""

import json
from typing import AsyncIterator, Dict, Any

from sse_starlette.sse import EventSourceResponse

from ..config import get_settings
from ..graph.runner import ainvoke_graph
from ..graph.state import GraphState
from ..utils.conversation_message_service import (
    prepare_function_calls,
    prepare_metadata_from_response,
    save_assistant_message_async,
)
from ..utils.logger import get_logger
from .models import StreamChunk, StreamChunkType

logger = get_logger(__name__)
settings = get_settings()


async def stream_graph_response(
    state: GraphState,
) -> AsyncIterator[StreamChunk]:
    """Stream graph execution response with intermediate updates.

    This function executes the graph and streams:
    - Reasoning steps as they're generated
    - Tool calls when tools are executed
    - Final answer token-by-token

    Args:
        state: Initial graph state with user_query, workspace_id, user_id, conversation_id

    Yields:
        StreamChunk objects with different types
    """
    try:
        # First, execute query_builder_node to get enriched query
        logger.info("Starting streaming graph execution")
        
        # Create initial state for query builder
        query_builder_state: GraphState = {
            "user_query": state.get("user_query", ""),
            "conversation_id": state.get("conversation_id"),
            "workspace_id": state.get("workspace_id"),
            "execution_path": [],
            "metadata": state.get("metadata", {}),
        }
        
        # We need to manually execute query_builder_node
        # For now, let's use the full graph and extract what we need
        # This is a simplified approach - in production, you might want to
        # execute nodes individually for better streaming control
        
        # Execute full graph first to get the enriched query
        # Then we'll stream the answer generation
        final_state = await ainvoke_graph(state)
        
        # Extract enriched query
        enriched_query = final_state.get("query_builder_result", "")
        if not enriched_query:
            enriched_query = state.get("user_query", "")
        
        # Extract the actual question from enriched query
        if "Current query:" in enriched_query:
            question = enriched_query.split("Current query:")[-1].strip()
        else:
            question = enriched_query
        
        # Get the parsed result if available
        query_processing_result = final_state.get("query_processing_result", "")
        if query_processing_result:
            try:
                result_data = json.loads(query_processing_result)
                
                # Stream reasoning steps
                reasoning_steps = result_data.get("reasoning_steps", [])
                for step in reasoning_steps:
                    yield StreamChunk(
                        type=StreamChunkType.REASONING,
                        content=step,
                    )
                
                # Stream tool calls
                tool_calls = result_data.get("tool_calls", [])
                for tool_call in tool_calls:
                    yield StreamChunk(
                        type=StreamChunkType.TOOL_CALL,
                        content=f"Tool {tool_call.get('tool', 'unknown')} called",
                        data=tool_call,
                    )
                
                # Stream final answer token-by-token
                answer = result_data.get("answer", "")
                if answer:
                    # Stream answer character by character for smooth streaming effect
                    # In a more sophisticated implementation, we could re-generate the answer
                    # using the LLM adapter's astream method for true token-by-token streaming
                    for char in answer:
                        yield StreamChunk(
                            type=StreamChunkType.TOKEN,
                            content=char,
                        )
                
                # Send done signal
                yield StreamChunk(
                    type=StreamChunkType.DONE,
                    content="",
                    data={"metadata": result_data.get("metadata", {})},
                )
                
                # Save assistant message to database in background (non-blocking)
                try:
                    conversation_id = state.get("conversation_id")
                    if conversation_id:
                        # Prepare metadata for storage
                        query_processing_metadata = final_state.get("query_processing_metadata", {})
                        storage_metadata = prepare_metadata_from_response(
                            result_data,
                            query_processing_metadata,
                        )
                        
                        # Prepare function calls for storage
                        storage_function_calls = prepare_function_calls(tool_calls)
                        
                        # Save asynchronously (won't block streaming)
                        save_assistant_message_async(
                            conversation_id=conversation_id,
                            content=answer,
                            metadata=storage_metadata,
                            function_calls=storage_function_calls if storage_function_calls else None,
                        )
                except Exception as e:
                    # Log error but don't fail streaming
                    logger.error(
                        "Failed to initiate message save to database in streaming",
                        conversation_id=state.get("conversation_id"),
                        error=str(e),
                        exc_info=True,
                    )
                
            except json.JSONDecodeError:
                # If parsing fails, just stream the raw result
                yield StreamChunk(
                    type=StreamChunkType.TOKEN,
                    content=query_processing_result,
                )
                yield StreamChunk(
                    type=StreamChunkType.DONE,
                    content="",
                )
        else:
            # No result available, send error
            yield StreamChunk(
                type=StreamChunkType.ERROR,
                content="No processing result available",
            )
            
    except Exception as e:
        logger.error("Streaming error", error=str(e), exc_info=True)
        yield StreamChunk(
            type=StreamChunkType.ERROR,
            content=f"Error during streaming: {str(e)}",
        )


def create_sse_response(stream: AsyncIterator[StreamChunk]) -> EventSourceResponse:
    """Create SSE response from stream chunks.

    Args:
        stream: Async iterator of StreamChunk objects

    Returns:
        EventSourceResponse configured for SSE
    """
    async def event_generator():
        async for chunk in stream:
            # Convert chunk to JSON
            chunk_json = chunk.model_dump_json()
            # SSE format: event: <type>\ndata: <json>\n\n
            yield {
                "event": chunk.type.value,
                "data": chunk_json,
            }
    
    return EventSourceResponse(event_generator())

