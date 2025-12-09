"""Graph state schema definitions."""

from typing import Annotated, Any, TypedDict, List

from typing_extensions import NotRequired

from ..utils.models import Message


class GraphState(TypedDict):
    """Main graph state schema."""

    # Input data
    input_data: NotRequired[str]
    user_query: NotRequired[str]

    # Conversation management
    conversation_id: NotRequired[str]
    conversation_history: NotRequired[list[Message]]
    context_summary: NotRequired[str]
    workspace_id: NotRequired[str]
    user_id: NotRequired[str]

    # Intermediate results
    query_builder_result: NotRequired[str]
    query_processing_result: NotRequired[str]
    query_processing_metadata: NotRequired[dict[str, Any]]
    
    # ReAct Loop State
    plan: NotRequired[str]
    reasoning_steps: NotRequired[List[str]]
    tool_calls: NotRequired[List[dict[str, Any]]]
    context_history: NotRequired[List[str]]
    previous_actions: NotRequired[List[str]]
    current_action: NotRequired[dict[str, Any]]
    final_answer: NotRequired[str]
    agent_iterations: NotRequired[int]

    # Metadata
    execution_path: Annotated[list[str], lambda x, y: x + [y] if y else x]
    errors: NotRequired[list[str]]
    metadata: NotRequired[dict[str, Any]]
