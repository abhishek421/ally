"""
Shared low-level types for the CRM agent.

This file contains no Pydantic models and no runtime logic.
Only Python types, enums, dataclasses, and small utility structures.

This file is safe to import anywhere in the codebase without circular
dependency concerns, as it has no dependencies on other application modules.

Use these types for:
- Type hints in function signatures
- Internal data structures
- Tool registry definitions
- Error handling
- Stream events and message formatting
"""

# ========================================
# 1. Imports
# ========================================

from typing import Any, Dict, List, Optional, Callable, TypedDict
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


# ========================================
# 2. Type Aliases
# ========================================

JSON = Dict[str, Any]
"""Generic JSON-like dictionary type for flexible data structures."""

Payload = Dict[str, Any]
"""Generic payload type used for API requests and responses."""

StateDict = Dict[str, Any]
"""Dictionary type for agent state management in LangGraph."""


# ========================================
# 3. Enums
# ========================================


class EventType(str, Enum):
    """
    SSE stream event categories sent from agent to frontend.
    
    These event types correspond to the different blocks that can be
    streamed to the user interface during agent execution.
    """
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MARKDOWN = "markdown"
    ENTITY_PREVIEW = "entity_preview"
    PENDING_ACTION = "pending_action"
    FINAL = "final"
    ERROR = "error"


class ToolStatus(str, Enum):
    """
    Status of a tool execution.
    
    Used to track the lifecycle of tool calls during agent execution.
    """
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class Role(str, Enum):
    """
    Message role in a conversation.
    
    Used to distinguish between different participants in the conversation
    history for LLM context management.
    """
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class PlannerDecisionType(str, Enum):
    """
    Type of execution plan decided by the planner node.
    
    Determines how the executor should process the planned tasks:
    - PARALLEL: Execute all tasks concurrently
    - SEQUENTIAL: Execute tasks one after another
    - CONFIRMATION_REQUIRED: Needs user approval before execution
    """
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CONFIRMATION_REQUIRED = "confirmation_required"
    NONE = "none"


class EntityType(str, Enum):
    """
    CRM entity types supported by the system.
    
    Used for type-safe entity operations and validation.
    """
    WORKSPACE = "workspace"
    COMPANY = "company"
    PERSON = "person"
    GROUP = "group"
    INTERACTION = "interaction"


# ========================================
# 4. Dataclasses / TypedDicts
# ========================================


@dataclass
class Message:
    """
    A single message in a conversation.
    
    Used to build conversation history for the LLM context.
    Lightweight structure for internal message passing.
    """
    role: Role
    content: str
    timestamp: datetime


@dataclass
class ToolCallLog:
    """
    Log entry for a tool execution.
    
    Tracks tool invocations with their arguments, status, and timing.
    Used for debugging, auditing, and displaying tool execution to users.
    """
    tool_name: str
    args: JSON
    status: ToolStatus
    timestamp: datetime


@dataclass
class ReasoningStep:
    """
    A single reasoning step in the agent's thought process.
    
    Captures intermediate reasoning that can be displayed to users
    for transparency and debugging purposes.
    """
    text: str
    timestamp: datetime


@dataclass
class TokenChunk:
    """
    A single token chunk from streaming LLM output.
    
    Used when streaming responses token-by-token to provide
    real-time feedback to users.
    """
    token: str
    timestamp: datetime


# ========================================
# 5. Tool Registry Types
# ========================================


@dataclass
class ToolSpec:
    """
    Specification for a tool in the agent's toolkit.
    
    Defines the metadata and callable function for a tool that
    can be invoked by the LLM during execution.
    
    Fields:
    - name: Unique identifier for the tool
    - description: Human-readable description for LLM context
    - fn: The actual callable function to execute
    """
    name: str
    description: str
    fn: Callable


ToolRegistry = Dict[str, ToolSpec]
"""
Registry mapping tool names to their specifications.

Used by the executor node to look up and invoke tools by name.
Provides a central registry for all available tools in the system.
"""


# ========================================
# 6. Error Types
# ========================================


class AgentValidationError(Exception):
    """
    Raised when agent input validation fails.
    
    Examples:
    - Invalid conversation_id format
    - Missing required fields
    - Invalid workspace context
    """
    pass


class ToolExecutionError(Exception):
    """
    Raised when a tool execution fails.
    
    Examples:
    - GraphQL API returns an error
    - Invalid tool arguments
    - Permission denied
    - Resource not found
    """
    pass


class PlannerError(Exception):
    """
    Raised when the planner node encounters an error.
    
    Examples:
    - Unable to generate a valid plan
    - LLM response parsing failure
    - Invalid task specification
    """
    pass

