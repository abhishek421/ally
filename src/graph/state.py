"""Graph state schema definitions."""

from typing import Annotated, Any, TypedDict

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

    # Intermediate results
    query_builder_result: NotRequired[str]

    # Metadata
    execution_path: Annotated[list[str], lambda x, y: x + [y] if y else x]
    errors: NotRequired[list[str]]
    metadata: NotRequired[dict[str, Any]]

