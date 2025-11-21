"""
Shared data models for the CRM copilot.

This file contains only type definitions using Pydantic BaseModel classes.
No business logic or imports from other application modules.
"""

from datetime import datetime
from typing import Literal, List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


# ========================================
# 1. Core Request Schemas
# ========================================

class EntityMentionSpan(BaseModel):
    start: int
    end: int

class EntityMention(BaseModel):
    entityId: str
    entityType: Literal["company", "person", "email", "group", "interaction"]
    name: str
    span: EntityMentionSpan

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    entity_mentions: Optional[List[EntityMention]] = None

# Kept for backward compatibility or internal use if needed, but QueryRequest is preferred for the new API
class UserMessageInput(BaseModel):
    conversation_id: str
    user_id: str
    workspace_id: str
    message: str
    metadata: dict | None = None

class ConfirmActionInput(BaseModel):
    conversation_id: str
    user_id: str
    workspace_id: str
    action_id: str
    payload: dict  # edited values from frontend

class WorkspaceContext(BaseModel):
    workspace_id: str
    member_id: str
    role: str

# ========================================
# 2. CRM Entity Schemas (Backend-Accurate)
# ========================================

class WorkspaceSchema(BaseModel):
    id: str
    name: str | None = None

class CompanySchema(BaseModel):
    id: str
    name: str
    privacyLevel: Literal["PRIVATE", "PUBLIC"]
    workspaceId: str
    createdBy: str

class PersonSchema(BaseModel):
    id: str
    firstName: str
    lastName: str | None = None
    privacyLevel: Literal["PRIVATE", "PUBLIC"]
    workspaceId: str
    createdBy: str

class GroupSchema(BaseModel):
    id: str
    name: str
    type: Literal["COMPANY", "PEOPLE", "DEAL"]
    isPrivate: bool
    workspaceId: str
    createdBy: str

class InteractionSchema(BaseModel):
    id: str
    type: Literal[
        "EMAIL",
        "CALENDAR",
        "CALL",
        "MEETING",
        "NOTE",
        "SMS",
        "LINKEDIN_MESSAGE",
        "SOCIAL_MEDIA"
    ]
    direction: Literal["INBOUND", "OUTBOUND"]
    date: datetime
    workspaceId: str
    createdById: str
    peopleId: str | None = None
    companyId: str | None = None

# ========================================
# 3. Relationship Schemas
# ========================================

class PersonCompanyLink(BaseModel):
    peopleId: str
    companyId: str
    isPeoplePrimary: bool | None = None
    isCompanyPrimary: bool | None = None

class GroupCompanyLink(BaseModel):
    groupId: str
    companyId: str
    addedBy: str
    addedAt: datetime

class GroupPersonLink(BaseModel):
    groupId: str
    peopleId: str
    addedBy: str
    addedAt: datetime

# ========================================
# 4. Agent Internal Structures
# ========================================

class ToolInvocation(BaseModel):
    tool_name: str
    args: dict

class ToolResult(BaseModel):
    tool_name: str
    result: dict | list | None

class PlannedTask(BaseModel):
    tool: str
    args: dict

class PendingAction(BaseModel):
    action_id: str
    action: str  # e.g. "createPerson"
    payload: dict  # final values AI wants to use
    description: str  # human-readable text for UI
    requires_confirmation: bool = True

# ========================================
# 5. Output Blocks (Agent → Frontend)
# ========================================

BlockType = Literal[
    "TEXT",
    "TABLE",
    "THINKING",
    "ENTITY_LIST",
    "ENTITY_CARD",
    "INSIGHT_WIDGET",
    "tool_call", # Kept for backward compat/internal use
    "tool_result", # Kept for backward compat/internal use
    "markdown", # Kept for backward compat/internal use
    "entity_preview", # Kept for backward compat/internal use
    "pending_action", # Kept for backward compat/internal use
    "final", # Kept for backward compat/internal use
    "error" # Kept for backward compat/internal use
]

class MessageBlock(BaseModel):
    block_id: str
    block_type: BlockType
    content: str
    order: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entity_mentions: List[EntityMention] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime

class Message(BaseModel):
    id: str
    role: Literal["USER", "ASSISTANT"]
    timestamp: datetime
    blocks: List[MessageBlock]

# Response Schemas

class ConversationListResponse(BaseModel):
    success: bool
    conversations: List[Conversation]
    total: int
    limit: int
    offset: int

class ConversationResponse(BaseModel):
    success: bool
    conversation: Conversation
    message_count: int

class MessageListResponse(BaseModel):
    success: bool
    conversation_id: str
    messages: List[Message]
    total: int
    limit: int
    offset: int

class DeleteConversationResponse(BaseModel):
    success: bool
    message: str

# Streaming Event Schemas

class MessageStartEvent(BaseModel):
    type: Literal["message_start"] = "message_start"
    message_id: str
    conversation_id: str

class BlockStartEvent(BaseModel):
    type: Literal["block_start"] = "block_start"
    block_id: str
    block_type: BlockType
    order: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entity_mentions: List[EntityMention] = Field(default_factory=list)

class BlockDeltaEvent(BaseModel):
    type: Literal["block_delta"] = "block_delta"
    block_id: str
    content: str

class BlockCompleteEvent(BaseModel):
    type: Literal["block_complete"] = "block_complete"
    block_id: str
    block_type: BlockType
    content: str
    order: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entity_mentions: List[EntityMention] = Field(default_factory=list)

class MessageCompleteEvent(BaseModel):
    type: Literal["message_complete"] = "message_complete"
    message_id: str
    blocks_count: int

class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    error: str
    error_code: Optional[str] = None

# Legacy Block Models (maintained for compatibility with existing code if needed, 
# but should ideally be mapped to the new Block structure)

class ThinkingBlock(BaseModel):
    type: Literal["thinking"] = "thinking"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ToolCallBlock(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MarkdownBlock(BaseModel):
    type: Literal["markdown"] = "markdown"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class EntityPreviewBlock(BaseModel):
    type: Literal["entity_preview"] = "entity_preview"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PendingActionBlock(BaseModel):
    type: Literal["pending_action"] = "pending_action"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class FinalResponseBlock(BaseModel):
    type: Literal["final"] = "final"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorBlock(BaseModel):
    type: Literal["error"] = "error"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ========================================
# 6. Unified Envelope
# ========================================

class AgentEvent(BaseModel):
    type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
