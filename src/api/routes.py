"""API route handlers."""

import json
import uuid
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
    save_user_message_async,
    _save_user_message_sync,
)
from ..utils.conversation_service import (
    create_conversation_sync,
    delete_conversation,
    generate_title_from_query,
    get_conversation,
    list_conversations,
    update_conversation,
)
from ..utils.exceptions import GraphExecutionError
from ..utils.logger import get_logger
from .models import (
    ChatRequest,
    ChatResponse,
    ConversationDeleteRequest,
    ConversationDeleteResponse,
    ConversationDetailModel,
    ConversationGetRequest,
    ConversationListRequest,
    ConversationListResponse,
    ConversationModel,
    ConversationUpdateRequest,
    HealthResponse,
)
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
        
        # Determine conversation_id and handle new vs existing conversation
        conversation_id = request.conversation_id
        
        if not conversation_id:
            # New conversation: generate UUID and create conversation record
            conversation_id = str(uuid.uuid4())
            logger.info(
                "Creating new conversation",
                conversation_id=conversation_id,
                workspace_id=request.workspace_id,
                user_id=request.user_id,
            )
            
            # Generate title from query
            title = generate_title_from_query(request.query)
            
            # Create conversation record (synchronous, fail on error)
            try:
                create_conversation_sync(
                    conversation_id=conversation_id,
                    workspace_id=request.workspace_id,
                    user_id=request.user_id,
                    title=title,
                )
            except Exception as e:
                logger.error(
                    "Failed to create conversation record",
                    conversation_id=conversation_id,
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create conversation: {str(e)}",
                )
            
            # Create USER message (synchronous, fail on error)
            try:
                _save_user_message_sync(
                    conversation_id=conversation_id,
                    content=request.query,
                )
            except Exception as e:
                logger.error(
                    "Failed to create user message",
                    conversation_id=conversation_id,
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save user message: {str(e)}",
                )
        else:
            # Existing conversation: save USER message asynchronously (non-blocking)
            save_user_message_async(
                conversation_id=conversation_id,
                content=request.query,
            )
        
        # Create initial graph state
        initial_state: GraphState = {
            "user_query": request.query,
            "workspace_id": request.workspace_id,
            "user_id": request.user_id,
            "conversation_id": conversation_id,
            "execution_path": [],
            "metadata": {
                "user_id": request.user_id,
                "workspace_id": request.workspace_id,
            },
        }
        
        # Execute graph (starts immediately, doesn't wait for message saves)
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
        
        # Get conversation_id from final state (should match what we set)
        conversation_id = final_state.get("conversation_id", conversation_id)
        
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


# ==================== Conversation Management Routes ====================

@router.post("/conversations", response_model=ConversationListResponse)
async def list_conversations_endpoint(request: ConversationListRequest) -> ConversationListResponse:
    """List conversations for a user in a workspace.
    
    Args:
        request: ConversationListRequest with workspace_id, user_id, and pagination
        
    Returns:
        ConversationListResponse with list of conversations
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        logger.info(
            "List conversations request received",
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            limit=request.limit,
            offset=request.offset,
        )
        
        result = list_conversations(
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            limit=request.limit,
            offset=request.offset,
        )
        
        # Convert to response model
        conversations = [
            ConversationModel(
                id=conv["id"],
                workspace_id=conv["workspace_id"],
                user_id=conv["user_id"],
                title=conv["title"],
                created_at=conv["created_at"],
                updated_at=conv["updated_at"],
                message_count=conv["message_count"],
                last_message=conv["last_message"],
            )
            for conv in result["conversations"]
        ]
        
        return ConversationListResponse(
            conversations=conversations,
            total=result["total"],
            has_more=result["has_more"],
        )
        
    except ValueError as e:
        logger.error("Invalid UUID in list conversations", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except Exception as e:
        logger.error("Failed to list conversations", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get("/conversations/{conversation_id}")
async def get_conversation_endpoint(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
    include_messages: bool = True,
    message_limit: int = 100,
) -> ConversationDetailModel:
    """Get a conversation by ID with optional messages.
    
    Args:
        conversation_id: Conversation UUID
        workspace_id: Workspace UUID (query param)
        user_id: User UUID (query param)
        include_messages: Whether to include messages (default: True)
        message_limit: Maximum messages to return (default: 100)
        
    Returns:
        ConversationDetailModel with conversation and messages
        
    Raises:
        HTTPException: If conversation not found or access denied
    """
    try:
        logger.info(
            "Get conversation request received",
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        
        result = get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            include_messages=include_messages,
            message_limit=message_limit,
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Build response
        from .models import ConversationMessageModel
        
        messages = []
        if include_messages and "messages" in result:
            messages = [
                ConversationMessageModel(
                    id=msg["id"],
                    role=msg["role"],
                    content=msg["content"],
                    metadata=msg["metadata"],
                    function_calls=msg["function_calls"],
                    timestamp=msg["timestamp"],
                )
                for msg in result["messages"]
            ]
        
        return ConversationDetailModel(
            id=result["id"],
            workspace_id=result["workspace_id"],
            user_id=result["user_id"],
            title=result["title"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            message_count=result.get("message_count"),
            messages=messages,
        )
        
    except ValueError as e:
        logger.error("Invalid UUID in get conversation", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get conversation: {str(e)}")


@router.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation_endpoint(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
) -> ConversationDeleteResponse:
    """Delete a conversation and all its messages.
    
    Args:
        conversation_id: Conversation UUID
        workspace_id: Workspace UUID (query param)
        user_id: User UUID (query param)
        
    Returns:
        ConversationDeleteResponse with success status
        
    Raises:
        HTTPException: If conversation not found or deletion fails
    """
    try:
        logger.info(
            "Delete conversation request received",
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        
        success = delete_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return ConversationDeleteResponse(
            success=True,
            conversation_id=conversation_id,
        )
        
    except ValueError as e:
        logger.error("Invalid UUID in delete conversation", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")


@router.patch("/conversations/{conversation_id}")
async def update_conversation_endpoint(
    conversation_id: str,
    request: ConversationUpdateRequest,
) -> ConversationModel:
    """Update a conversation's metadata (e.g., title).
    
    Args:
        conversation_id: Conversation UUID
        request: ConversationUpdateRequest with workspace_id, user_id, and fields to update
        
    Returns:
        Updated ConversationModel
        
    Raises:
        HTTPException: If conversation not found or update fails
    """
    try:
        logger.info(
            "Update conversation request received",
            conversation_id=conversation_id,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            title=request.title,
        )
        
        result = update_conversation(
            conversation_id=conversation_id,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            title=request.title,
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return ConversationModel(
            id=result["id"],
            workspace_id=result["workspace_id"],
            user_id=result["user_id"],
            title=result["title"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )
        
    except ValueError as e:
        logger.error("Invalid UUID in update conversation", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update conversation: {str(e)}")

