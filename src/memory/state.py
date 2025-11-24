"""
Agent state model for LangGraph.

This is the single source of truth for all runtime memory passed between graph nodes.
The state object flows through all nodes during execution:
- Planner reads messages and populates tool plans
- Executor reads plans and logs tool calls
- Validator checks results and may set pending_action
- Final_response reads everything and produces final output

The state is serialized and stored in the session store per conversation,
allowing for persistent multi-turn conversations and resumable execution.

This file is strictly a typed memory container with no graph logic,
server logic, or tool implementations.
"""

# ========================================
# 1. Imports
# ========================================

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

# Import low-level types from utils
from src.utils.types import (
    Message,
    ReasoningStep,
    ToolCallLog,
    ToolRegistry,
    ToolStatus,
)

# Import schema types from interfaces
from src.interfaces.schemas import PendingAction


# ========================================
# 2. AgentState Class
# ========================================


class AgentState(BaseModel):
    """
    Complete agent state model used by LangGraph.
    
    This state object is passed through all nodes in the graph execution pipeline.
    Each node can read from and write to this state, enabling stateful multi-turn
    conversations with full context preservation.
    
    The state is stored and loaded per conversation in the session store (Redis/DB),
    allowing users to resume conversations and maintaining full execution history.
    
    Lifecycle:
    1. Created when a new conversation starts or loaded from session store
    2. Updated by each node as it executes
    3. Serialized and saved after each graph execution
    4. Passed to the next node or returned to the frontend
    
    State Flow:
    - User message → Planner → Executor → Validator → Final Response
    - Each node reads previous state and writes new state
    - State accumulates messages, reasoning, tool calls, and results
    """
    
    # ----------------------------------
    # Conversation Metadata
    # ----------------------------------
    
    conversation_id: str
    """Unique identifier for this conversation session."""
    
    user_id: str
    """ID of the user having this conversation."""
    
    workspace_id: str
    """ID of the workspace this conversation is scoped to."""

    user_details: Optional[Dict[str, Any]] = None
    """
    Details of the user (name, email, id, etc.) fetched from the backend.
    Used to provide context to the agent about who they are talking to.
    """
    
    # ----------------------------------
    # Message History
    # ----------------------------------
    
    messages: List[Message] = []
    """
    Chat history containing all user and assistant messages.
    
    Used to build LLM context for subsequent turns. Messages are appended
    chronologically and preserved across conversation turns.
    """
    
    # ----------------------------------
    # Reasoning Steps
    # ----------------------------------
    
    reasoning: List[ReasoningStep] = []
    """
    Agent's reasoning steps for the current turn.
    
    Used for streaming "thinking" blocks to the frontend, providing
    transparency into the agent's decision-making process. Cleared or
    accumulated based on node requirements.
    """
    
    # ----------------------------------
    # Tool Calls
    # ----------------------------------
    
    tool_calls: List[ToolCallLog] = []
    """
    Execution logs for all tool invocations in this conversation.
    
    Used for debugging, auditing, and displaying tool execution status
    to users. Each log includes tool name, arguments, status, and timing.
    """
    
    # ----------------------------------
    # Parallel Tool Results
    # ----------------------------------
    
    parallel_results: Dict[str, Dict] = {}
    """
    Temporary storage for intermediate results from parallel node execution.
    
    When multiple tools are executed in parallel, each node stores its result
    here keyed by node name. The aggregator node reads all results, merges them,
    and clears this dict. Not persisted long-term.
    """
    
    # ----------------------------------
    # Pending Action
    # ----------------------------------
    
    pending_action: Optional[PendingAction] = None
    """
    Action awaiting user confirmation before execution.
    
    Set by the validator node when a write operation (create/update/delete)
    requires explicit user approval. The frontend displays this as a
    confirmation dialog. Cleared after the user confirms and action executes.
    """
    
    # ----------------------------------
    # Intermediate State Data
    # ----------------------------------
    
    plan: Optional[Dict[str, Any]] = None
    """
    Current execution plan generated by the planner and validated by the validator.
    Passed to executor.
    """
    
    execution_results: Optional[Dict[str, Any]] = None
    """
    Results from the executor node.
    Passed to aggregator.
    """
    
    aggregated_result: Optional[Dict[str, Any]] = None
    """
    Normalized and aggregated results from the aggregator node.
    Passed to final_response.
    """
    
    graphql_auth_token: Optional[str] = None
    """
    Auth token for GraphQL API calls.
    Injected from request headers.
    """

    # ----------------------------------
    # Final Response Block
    # ----------------------------------
    
    final_response: Optional[Dict] = None
    """
    Final response content produced for the frontend.
    
    Populated by the final_response node, containing the complete answer
    with markdown, entity previews, and other UI blocks. Sent to frontend
    as the final event in the SSE stream.
    """
    
    # ----------------------------------
    # Long-term Memory Chunks
    # ----------------------------------
    
    retrieved_memories: List[Dict] = []
    """
    Relevant memories retrieved from vector store for this turn.
    
    Optional feature for RAG-style memory enhancement. Contains chunks
    of past conversation context or domain knowledge retrieved based on
    semantic similarity to the current query.
    """
    
    # ----------------------------------
    # Tool Registry Reference
    # ----------------------------------
    
    tools: Optional[ToolRegistry] = None
    """
    Reference to the tool registry for this execution.
    
    Populated at graph build time with all available tools. Used by the
    executor node to look up and invoke tools by name. Not serialized
    in session storage (populated fresh on each load).
    """
    
    # ----------------------------------
    # Pydantic Configuration
    # ----------------------------------
    
    model_config = ConfigDict(
        # Allow ORM-style attribute access
        from_attributes=True,
        
        # Allow arbitrary types like ToolRegistry (contains Callable)
        arbitrary_types_allowed=True,
        
        # Validate on assignment to catch errors early
        validate_assignment=True,
    )
    
    # ----------------------------------
    # Helper Methods
    # ----------------------------------
    
    def add_message(self, message: Message) -> None:
        """
        Append a message to the conversation history.
        
        Args:
            message: Message object to add (user, assistant, or system role)
        
        Example:
            state.add_message(Message(
                role=Role.USER,
                content="Find companies in San Francisco",
                timestamp=datetime.utcnow()
            ))
        """
        self.messages.append(message)
    
    def add_reasoning(self, text: str) -> None:
        """
        Create and append a reasoning step.
        
        Args:
            text: Human-readable reasoning text
        
        Example:
            state.add_reasoning("Planning to search companies by location")
        """
        step = ReasoningStep(
            text=text,
            timestamp=datetime.utcnow()
        )
        self.reasoning.append(step)
    
    def log_tool_call(self, name: str, args: Dict) -> None:
        """
        Log a tool call with STARTED status.
        
        Call this when beginning a tool execution to track timing and status.
        
        Args:
            name: Tool name
            args: Tool arguments
        
        Example:
            state.log_tool_call("searchCompanies", {"location": "San Francisco"})
        """
        log = ToolCallLog(
            tool_name=name,
            args=args,
            status=ToolStatus.STARTED,
            timestamp=datetime.utcnow()
        )
        self.tool_calls.append(log)
    
    def complete_tool_call(self, name: str, result: Dict) -> None:
        """
        Log a tool call with COMPLETED status.
        
        Call this after successful tool execution to record the result.
        Note: This creates a new log entry rather than updating the STARTED entry,
        providing a complete audit trail.
        
        Args:
            name: Tool name
            result: Tool execution result
        
        Example:
            state.complete_tool_call("searchCompanies", {"count": 5, "companies": [...]})
        """
        log = ToolCallLog(
            tool_name=name,
            args=result,  # Store result in args field for simplicity
            status=ToolStatus.COMPLETED,
            timestamp=datetime.utcnow()
        )
        self.tool_calls.append(log)
    
    def record_parallel_result(self, node_name: str, result: Dict) -> None:
        """
        Store a result from a parallel node execution.
        
        Used when multiple tools run concurrently. Each parallel node stores
        its result here, and the aggregator node later merges them.
        
        Args:
            node_name: Name of the parallel node (e.g., "search_companies_node")
            result: Result data from the node
        
        Example:
            state.record_parallel_result("search_companies_node", {
                "companies": [...],
                "count": 5
            })
        """
        self.parallel_results[node_name] = result
    
    def clear_parallel_results(self) -> None:
        """
        Clear all parallel results after aggregation.
        
        Call this in the aggregator node after merging all parallel results
        to clean up temporary storage.
        
        Example:
            # In aggregator node:
            merged = merge_results(state.parallel_results)
            state.clear_parallel_results()
        """
        self.parallel_results = {}

