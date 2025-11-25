"""Pydantic request/response models for the API."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    query: str = Field(..., description="User query/question")
    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")
    conversation_id: str = Field(..., description="Conversation identifier")


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


