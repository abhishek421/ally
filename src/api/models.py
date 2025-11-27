"""Pydantic request/response models for the API."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    query: str = Field(..., description="User query/question")
    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")
    conversation_id: Optional[str] = Field(None, description="Conversation identifier (optional, will be created if not provided)")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    answer: str = Field(..., description="Generated answer")
    conversation_id: str = Field(..., description="Conversation identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tool calls made during processing")
    reasoning_steps: List[str] = Field(default_factory=list, description="Reasoning steps")


class StreamChunkType(str, Enum):
    """Types of stream chunks."""

    TOKEN = "token"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    METADATA = "metadata"
    ERROR = "error"
    DONE = "done"


class StreamChunk(BaseModel):
    """Model for streaming response chunks."""

    type: StreamChunkType = Field(..., description="Type of chunk")
    content: str = Field(..., description="Chunk content")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional chunk data")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")


# Conversation models
class ConversationListRequest(BaseModel):
    """Request model for listing conversations."""

    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum number of conversations to return")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class ConversationMessageModel(BaseModel):
    """Model for a conversation message."""

    id: str = Field(..., description="Message identifier")
    role: str = Field(..., description="Message role (USER, ASSISTANT, SYSTEM, FUNCTION)")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Message metadata")
    function_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Function calls made")
    timestamp: str = Field(..., description="Message timestamp (ISO format)")


class ConversationModel(BaseModel):
    """Model for a conversation."""

    id: str = Field(..., description="Conversation identifier")
    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")
    title: Optional[str] = Field(None, description="Conversation title")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Last update timestamp (ISO format)")
    message_count: Optional[int] = Field(None, description="Number of messages in conversation")
    last_message: Optional[str] = Field(None, description="Preview of last message")


class ConversationDetailModel(ConversationModel):
    """Model for a conversation with messages."""

    messages: List[ConversationMessageModel] = Field(default_factory=list, description="Conversation messages")


class ConversationListResponse(BaseModel):
    """Response model for listing conversations."""

    conversations: List[ConversationModel] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")
    has_more: bool = Field(..., description="Whether there are more conversations")


class ConversationGetRequest(BaseModel):
    """Request model for getting a conversation."""

    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")
    include_messages: bool = Field(default=True, description="Whether to include messages")
    message_limit: int = Field(default=100, ge=1, le=500, description="Maximum number of messages to return")


class ConversationDeleteRequest(BaseModel):
    """Request model for deleting a conversation."""

    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")


class ConversationDeleteResponse(BaseModel):
    """Response model for deleting a conversation."""

    success: bool = Field(..., description="Whether the deletion was successful")
    conversation_id: str = Field(..., description="Deleted conversation identifier")


class ConversationUpdateRequest(BaseModel):
    """Request model for updating a conversation."""

    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")
    title: Optional[str] = Field(None, description="New conversation title")


