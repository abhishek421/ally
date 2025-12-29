"""API routes for the Ally AI service."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.api.middleware import AuthContext, get_current_user
from src.agent.graph import stream_agent, resume_agent
from src.graphql.client import GraphQLClient
from src.tools.base import ToolContext

logger = logging.getLogger(__name__)

router = APIRouter()


async def resolve_database_user_id(auth: AuthContext) -> str:
    """Resolve the Cognito sub to the actual database user ID.

    The JWT token contains a Cognito sub, but the backend database uses
    its own user IDs. This function calls the backend to get the real ID.

    Args:
        auth: Auth context from the request

    Returns:
        The database user ID
    """
    client = GraphQLClient(auth.auth_token, auth.workspace_id, auth.session_id)
    try:
        db_user_id = await client.get_current_user_id()
        if db_user_id:
            return db_user_id
        else:
            logger.warning(f"Could not resolve database user ID, using JWT sub")
            return auth.user_id
    except Exception as e:
        logger.error(f"Error resolving database user ID: {e}")
        return auth.user_id
    finally:
        await client.close()


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    
    conversation_id: str = Field(..., description="ID of the conversation thread")
    message: str = Field(..., min_length=1, description="User message to send")


class ChatResponse(BaseModel):
    """Response body for non-streaming chat."""
    
    response: str
    conversation_id: str


async def event_generator(
    context: ToolContext,
    message: str,
    conversation_id: str,
) -> AsyncGenerator[dict, None]:
    """Generate SSE events from the agent stream.
    
    Args:
        context: Tool context with auth and workspace info
        message: User message
        conversation_id: Conversation thread ID
        
    Yields:
        SSE event dictionaries
    """
    try:
        async for event in stream_agent(context, message, conversation_id):
            event_type = event.get("type", "unknown")
            event_data = event.get("data", {})
            
            yield {
                "event": event_type,
                "data": json.dumps(event_data),
            }
            
    except Exception as e:
        logger.error(f"Error in agent stream: {e}")
        yield {
            "event": "error",
            "data": json.dumps({"message": str(e)}),
        }
        yield {
            "event": "done",
            "data": json.dumps({}),
        }


@router.post("/chat")
async def chat(
    request: ChatRequest,
    auth: AuthContext = Depends(get_current_user),
):
    """Stream a chat response from Ally.
    
    This endpoint uses Server-Sent Events (SSE) to stream the response
    as the agent processes the request.
    
    **Headers:**
    - `Authorization: Bearer <token>` - JWT token
    - `X-Workspace-ID: <workspace_id>` - Current workspace ID
    
    **Request Body:**
    - `conversation_id` - ID of the conversation thread
    - `message` - User message to send
    
    **Response (SSE):**
    Events are sent as SSE with the following types:
    - `thinking` - Agent's reasoning process
    - `tool_call` - Tool being called with arguments
    - `tool_result` - Result from tool execution
    - `response` - Final response text
    - `confirmation_required` - Agent needs user confirmation before proceeding
    - `error` - Error message if something went wrong
    - `done` - Stream completion signal
    """
    # Resolve the database user ID upfront (JWT contains Cognito sub, not DB ID)
    db_user_id = await resolve_database_user_id(auth)

    # Log the incoming query in a clean format
    query_preview = request.message[:80] + "..." if len(request.message) > 80 else request.message
    logger.info(f"📩 QUERY: \"{query_preview}\"")
    
    # Create tool context with the resolved database user ID
    context = ToolContext(
        auth_token=auth.auth_token,
        workspace_id=auth.workspace_id,
        user_id=db_user_id,
        session_id=auth.session_id,
    )
    
    return EventSourceResponse(
        event_generator(context, request.message, request.conversation_id),
        media_type="text/event-stream",
    )


class ConfirmationRequest(BaseModel):
    """Request body for the confirmation endpoint."""
    
    conversation_id: str = Field(..., description="ID of the conversation thread")
    confirmed: bool = Field(False, description="Whether the user confirmed the action")
    selected_id: str | None = Field(None, description="Selected option ID for SELECT_ONE")
    selected_ids: list[str] | None = Field(None, description="Selected option IDs for SELECT_MANY")
    feedback: str | None = Field(None, description="Optional feedback from user")


async def confirmation_event_generator(
    context: ToolContext,
    conversation_id: str,
    confirmation_response: dict,
) -> AsyncGenerator[dict, None]:
    """Generate SSE events from resumed agent stream.
    
    Args:
        context: Tool context with auth and workspace info
        conversation_id: Conversation thread ID
        confirmation_response: User's confirmation response
        
    Yields:
        SSE event dictionaries
    """
    try:
        async for event in resume_agent(context, conversation_id, confirmation_response):
            event_type = event.get("type", "unknown")
            event_data = event.get("data", {})
            
            yield {
                "event": event_type,
                "data": json.dumps(event_data),
            }
            
    except Exception as e:
        logger.error(f"Error in resumed agent stream: {e}")
        yield {
            "event": "error",
            "data": json.dumps({"message": str(e)}),
        }
        yield {
            "event": "done",
            "data": json.dumps({}),
        }


@router.post("/chat/confirm")
async def confirm_action(
    request: ConfirmationRequest,
    auth: AuthContext = Depends(get_current_user),
):
    """Resume agent execution after user confirmation.
    
    This endpoint is called when the user responds to a confirmation request.
    It resumes the agent from where it was interrupted and continues streaming
    the response.
    
    **Headers:**
    - `Authorization: Bearer <token>` - JWT token
    - `X-Workspace-ID: <workspace_id>` - Current workspace ID
    
    **Request Body:**
    - `conversation_id` - ID of the conversation thread
    - `confirmed` - Whether the user confirmed the action
    - `selected_id` - Selected option ID for SELECT_ONE confirmations
    - `selected_ids` - Selected option IDs for SELECT_MANY confirmations
    - `feedback` - Optional feedback from user (e.g., on cancel)
    
    **Response (SSE):**
    Same event types as /chat endpoint.
    """
    # Resolve the database user ID upfront
    db_user_id = await resolve_database_user_id(auth)
    
    # Create tool context
    context = ToolContext(
        auth_token=auth.auth_token,
        workspace_id=auth.workspace_id,
        user_id=db_user_id,
        session_id=auth.session_id,
    )
    
    # Build confirmation response dict
    confirmation_response = {
        "confirmed": request.confirmed,
        "selected_id": request.selected_id,
        "selected_ids": request.selected_ids,
        "feedback": request.feedback,
    }
    
    return EventSourceResponse(
        confirmation_event_generator(context, request.conversation_id, confirmation_response),
        media_type="text/event-stream",
    )


@router.get("/conversations/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Get the conversation history from the LangGraph checkpointer.
    
    Note: This retrieves the agent's internal state. For full message
    history with user messages, use the backend's GraphQL API.
    
    **Headers:**
    - `Authorization: Bearer <token>` - JWT token
    - `X-Workspace-ID: <workspace_id>` - Current workspace ID
    
    **Path Parameters:**
    - `conversation_id` - ID of the conversation
    
    **Response:**
    Returns the conversation's message history from the checkpointer.
    """
    from src.agent.graph import get_checkpointer
    
    try:
        checkpointer = await get_checkpointer()
        
        config = {"configurable": {"thread_id": conversation_id}}
        
        # Get the latest state from checkpointer
        state = await checkpointer.aget(config)
        
        if not state:
            return {"messages": [], "conversation_id": conversation_id}
        
        # Extract messages from state
        messages = []
        for msg in state.values.get("messages", []):
            if hasattr(msg, "content"):
                messages.append({
                    "role": getattr(msg, "type", "unknown"),
                    "content": msg.content,
                })
        
        return {
            "messages": messages,
            "conversation_id": conversation_id,
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation history: {str(e)}",
        )

