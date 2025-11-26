"""API route handlers."""

import json
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..config import get_settings
from ..graph.runner import ainvoke_graph
from ..graph.state import GraphState
from ..utils.conversation_message_service import (
    prepare_function_calls,
    prepare_metadata_from_response,
    save_assistant_message_async,
)
from ..utils.exceptions import GraphExecutionError
from ..utils.logger import get_logger
from .models import ChatRequest, ChatResponse, HealthResponse
from .streaming import stream_graph_response, create_sse_response

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.
    
    Returns:
        HealthResponse with status and version
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Non-streaming chat endpoint.
    
    Args:
        request: ChatRequest with query and authentication fields
        
    Returns:
        ChatResponse with answer, metadata, tool calls, and reasoning steps
        
    Raises:
        HTTPException: If graph execution fails
    """
    try:
        logger.info(
            "Chat request received",
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            query_length=len(request.query),
        )
        
        # Create initial graph state
        initial_state: GraphState = {
            "user_query": request.query,
            "workspace_id": request.workspace_id,
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "execution_path": [],
            "metadata": {
                "user_id": request.user_id,
                "workspace_id": request.workspace_id,
            },
        }
        
        # Execute graph
        final_state = await ainvoke_graph(initial_state)
        
        # Parse response
        query_processing_result = final_state.get("query_processing_result", "")
        if not query_processing_result:
            raise HTTPException(
                status_code=500,
                detail="No processing result returned from graph",
            )
        
        try:
            result_data = json.loads(query_processing_result)
        except json.JSONDecodeError:
            # If parsing fails, create a basic response
            result_data = {
                "answer": query_processing_result,
                "reasoning_steps": [],
                "tool_calls": [],
                "metadata": {},
            }
        
        # Extract data
        answer = result_data.get("answer", "No answer generated.")
        reasoning_steps = result_data.get("reasoning_steps", [])
        tool_calls = result_data.get("tool_calls", [])
        metadata = result_data.get("metadata", {})
        
        # Get conversation_id from final state (may have been generated)
        conversation_id = final_state.get("conversation_id", request.conversation_id)
        
        logger.info(
            "Chat request completed",
            conversation_id=conversation_id,
            answer_length=len(answer),
            tool_calls_count=len(tool_calls),
        )
        
        # Prepare response
        response = ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            metadata=metadata,
            tool_calls=tool_calls,
            reasoning_steps=reasoning_steps,
        )
        
        # Save assistant message to database in background (non-blocking)
        try:
            # Prepare metadata for storage
            query_processing_metadata = final_state.get("query_processing_metadata", {})
            storage_metadata = prepare_metadata_from_response(
                result_data,
                query_processing_metadata,
            )
            
            # Prepare function calls for storage
            storage_function_calls = prepare_function_calls(tool_calls)
            
            # Save asynchronously (won't block response)
            save_assistant_message_async(
                conversation_id=conversation_id,
                content=answer,
                metadata=storage_metadata,
                function_calls=storage_function_calls if storage_function_calls else None,
            )
        except Exception as e:
            # Log error but don't fail the request
            logger.error(
                "Failed to initiate message save to database",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
        
        return response
        
    except GraphExecutionError as e:
        logger.error("Graph execution error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Graph execution failed: {str(e)}",
        )
    except Exception as e:
        logger.error("Unexpected error in chat endpoint", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """Streaming chat endpoint using Server-Sent Events.
    
    Args:
        request: ChatRequest with query and authentication fields
        
    Returns:
        EventSourceResponse with streaming chunks
    """
    try:
        logger.info(
            "Streaming chat request received",
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            query_length=len(request.query),
        )
        
        # Create initial graph state
        initial_state: GraphState = {
            "user_query": request.query,
            "workspace_id": request.workspace_id,
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "execution_path": [],
            "metadata": {
                "user_id": request.user_id,
                "workspace_id": request.workspace_id,
            },
        }
        
        # Create streaming response
        stream = stream_graph_response(initial_state)
        return create_sse_response(stream)
        
    except Exception as e:
        logger.error("Error in streaming endpoint", error=str(e), exc_info=True)
        # For streaming, we need to yield an error chunk
        async def error_stream():
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "content": f"Error: {str(e)}",
                }),
            }
        
        return EventSourceResponse(error_stream())

