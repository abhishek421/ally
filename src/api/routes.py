"""API routes for the Ally AI service."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.api.middleware import AuthContext, get_current_user
from src.agent.graph import stream_agent, resume_agent, is_first_message, generate_conversation_title
from src.graphql.client import GraphQLClient
from src.tools.base import ToolContext

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class UserProfile:
    """User profile information for personalization."""
    user_id: str
    first_name: str | None = None
    email: str | None = None


async def resolve_user_profile(auth: AuthContext, client: GraphQLClient) -> UserProfile:
    """Resolve the user's profile including database ID and name.

    The JWT token contains a Cognito sub, but the backend database uses
    its own user IDs. This function calls the backend to get the real ID
    and user profile information for personalization.

    Args:
        auth: Auth context from the request
        client: Shared GraphQL client for this request

    Returns:
        UserProfile with database user ID and profile info
    """
    try:
        profile = await client.get_current_user_profile()
        if profile:
            return UserProfile(
                user_id=profile.get("id") or auth.user_id,
                first_name=profile.get("firstName"),
                email=profile.get("email"),
            )
        else:
            logger.warning(f"Could not resolve user profile, using JWT sub")
            return UserProfile(user_id=auth.user_id)
    except Exception as e:
        logger.error(f"Error resolving user profile: {e}")
        return UserProfile(user_id=auth.user_id)


async def resolve_workspace_instructions(auth: AuthContext, client: GraphQLClient) -> str | None:
    """Fetch custom instructions for the workspace.

    These instructions are set by workspace admins to provide business
    context to the AI agent.

    Args:
        auth: Auth context from the request
        client: Shared GraphQL client for this request

    Returns:
        Custom instructions string or None if not set
    """
    logger.info(f"🔍 Fetching custom instructions for workspace: {auth.workspace_id}")
    try:
        instructions = await client.get_workspace_custom_instructions()
        if instructions:
            logger.info(f"✅ Loaded workspace custom instructions ({len(instructions)} chars)")
            logger.info(f"📋 Instructions preview: {instructions[:100]}...")
        else:
            logger.info(f"ℹ️  No custom instructions set for workspace {auth.workspace_id}")
        return instructions
    except Exception as e:
        logger.warning(f"❌ Error fetching workspace instructions: {e}")
        return None


def extract_group_id_from_url(active_url: str | None) -> str | None:
    """Extract group ID from the active URL.

    Matches patterns like /apps/groups/{uuid}/...

    Args:
        active_url: The current page URL the user is viewing

    Returns:
        Group UUID or None if not on a group page
    """
    if not active_url:
        return None
    match = re.search(
        r'/apps/groups/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
        active_url,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


async def resolve_group_instructions(auth: AuthContext, active_url: str | None, client: GraphQLClient) -> str | None:
    """Fetch custom instructions for the active group.

    These instructions are set by group creators or workspace admins to provide
    group-specific context to the AI agent.

    Args:
        auth: Auth context from the request
        active_url: The current page URL the user is viewing
        client: Shared GraphQL client for this request

    Returns:
        Custom instructions string or None if not set or not on a group page
    """
    group_id = extract_group_id_from_url(active_url)
    if not group_id:
        return None

    logger.info(f"🔍 Fetching custom instructions for group: {group_id}")
    try:
        instructions = await client.get_group_custom_instructions(group_id)
        if instructions:
            logger.info(f"✅ Loaded group custom instructions ({len(instructions)} chars)")
        else:
            logger.info(f"ℹ️  No custom instructions set for group {group_id}")
        return instructions
    except Exception as e:
        logger.warning(f"❌ Error fetching group instructions: {e}")
        return None


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    conversation_id: str = Field(..., description="ID of the conversation thread")
    message: str = Field(..., min_length=1, description="User message to send")
    activeURL: str | None = Field(None, description="Current page URL the user is viewing")


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
    # Check if this is the first message (for title generation)
    first_message = False
    try:
        first_message = await is_first_message(conversation_id)
    except Exception as e:
        logger.warning(f"Could not check if first message: {e}")
    
    # Accumulate the assistant response for title generation
    accumulated_response = ""
    
    try:
        async for event in stream_agent(context, message, conversation_id):
            event_type = event.get("type", "unknown")
            event_data = event.get("data", {})
            
            # Accumulate response content for title generation
            if event_type == "response" and first_message:
                accumulated_response += event_data.get("content", "")
            
            # Yield the event immediately so frontend can respond without delay
            yield {
                "event": event_type,
                "data": json.dumps(event_data),
            }

            # For "done" event, generate title AFTER sending done (so input is available immediately)
            if event_type == "done" and first_message and accumulated_response:
                try:
                    title, title_token_usage = await generate_conversation_title(message, accumulated_response)
                    if title:
                        logger.info(f"📝 Generated title: \"{title}\"")
                        yield {
                            "event": "conversation_title",
                            "data": json.dumps({
                                "title": title,
                                "conversation_id": conversation_id,
                            }),
                        }
                    # Emit title generation token usage separately
                    if title_token_usage:
                        logger.info(
                            f"📊 TITLE TOKEN USAGE: {title_token_usage['input_tokens']} input "
                            f"+ {title_token_usage['output_tokens']} output "
                            f"= {title_token_usage['total_tokens']} total"
                        )
                        yield {
                            "event": "token_usage",
                            "data": json.dumps({
                                **title_token_usage,
                                "llm_calls": 1,
                                "request_type": "title_generation",
                            }),
                        }
                except Exception as e:
                    logger.warning(f"Failed to generate conversation title: {e}")
                    # Continue without title - not critical
            
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
    finally:
        # Clean up the tool-level shared GraphQL client
        await context.close_client()


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
    # Use a single shared GraphQL client for all parallel resolution calls
    resolution_client = GraphQLClient(auth.auth_token, auth.workspace_id, auth.session_id)
    try:
        # Fetch user profile, workspace instructions, and group instructions in parallel
        user_profile, workspace_instructions, group_instructions = await asyncio.gather(
            resolve_user_profile(auth, resolution_client),
            resolve_workspace_instructions(auth, resolution_client),
            resolve_group_instructions(auth, request.activeURL, resolution_client),
        )
    finally:
        await resolution_client.close()

    # Log the incoming query in a clean format
    query_preview = request.message[:80] + "..." if len(request.message) > 80 else request.message
    user_name = user_profile.first_name or "User"
    logger.info(f"📩 QUERY from {user_name}: \"{query_preview}\"")

    # Create tool context with user profile, workspace instructions, and group instructions
    context = ToolContext(
        auth_token=auth.auth_token,
        workspace_id=auth.workspace_id,
        user_id=user_profile.user_id,
        session_id=auth.session_id,
        user_first_name=user_profile.first_name,
        user_email=user_profile.email,
        active_url=request.activeURL,
        workspace_instructions=workspace_instructions,
        group_instructions=group_instructions,
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
    activeURL: str | None = Field(None, description="Current page URL for group context")


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
    finally:
        # Clean up the tool-level shared GraphQL client
        await context.close_client()


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

    # Use a single shared GraphQL client for all parallel resolution calls
    resolution_client = GraphQLClient(auth.auth_token, auth.workspace_id, auth.session_id)
    try:
        # Fetch user profile, workspace instructions, and group instructions in parallel
        user_profile, workspace_instructions, group_instructions = await asyncio.gather(
            resolve_user_profile(auth, resolution_client),
            resolve_workspace_instructions(auth, resolution_client),
            resolve_group_instructions(auth, request.activeURL, resolution_client),
        )
    finally:
        await resolution_client.close()

    # Create tool context with user profile, workspace instructions, and group instructions
    context = ToolContext(
        auth_token=auth.auth_token,
        workspace_id=auth.workspace_id,
        user_id=user_profile.user_id,
        session_id=auth.session_id,
        user_first_name=user_profile.first_name,
        user_email=user_profile.email,
        workspace_instructions=workspace_instructions,
        group_instructions=group_instructions,
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
