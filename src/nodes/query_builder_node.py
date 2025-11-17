"""Query Builder Node - Builds queries from user input."""

import uuid
from typing import Any

from ..config import get_settings
from ..graph.state import GraphState
from ..utils.conversation_manager import ConversationManager
from ..utils.logger import get_logger
from ..utils.storage import get_storage
from ..utils.summarizer import get_summarizer
from ..utils.tokenizer import get_tokenizer

logger = get_logger(__name__)
settings = get_settings()

# Initialize components (can be made lazy if needed)
_storage = None
_tokenizer = None
_summarizer = None
_conversation_manager = None


def _get_conversation_manager() -> ConversationManager:
    """Get or create conversation manager instance."""
    global _storage, _tokenizer, _summarizer, _conversation_manager

    if _conversation_manager is None:
        _storage = get_storage()
        _tokenizer = get_tokenizer()
        _summarizer = get_summarizer()
        _conversation_manager = ConversationManager(
            storage=_storage,
            tokenizer=_tokenizer,
            summarizer=_summarizer,
        )

    return _conversation_manager


def query_builder_node(state: GraphState) -> dict[str, Any]:
    """Build query from user input and state.

    This node processes user queries and input data to construct
    structured queries with conversation context for downstream processing.

    Args:
        state: Current graph state containing input_data and user_query

    Returns:
        Dictionary with query_builder_result and updated execution_path
    """
    logger.info("Query Builder Node: Starting processing", user_query=state.get("user_query"))

    # Get conversation ID from state or generate one
    conversation_id = state.get("conversation_id") or settings.conversation_id
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        logger.info("Generated new conversation ID", conversation_id=conversation_id)

    # Get user query
    user_query = state.get("user_query") or state.get("input_data", "")
    if not user_query:
        logger.warning("No user query found in state")
        user_query = ""

    # Get conversation manager
    conversation_manager = _get_conversation_manager()

    # Save user query to history
    if user_query:
        conversation_manager.save_user_query(conversation_id, user_query)

    # Build enriched query with context
    enriched_query = conversation_manager.get_context_for_query(conversation_id, user_query)

    # Get updated conversation history
    conversation_history = conversation_manager.storage.get_conversation_history(conversation_id)
    summary_data = conversation_manager.storage.get_summary(conversation_id)
    context_summary = summary_data[0] if summary_data else None

    logger.info(
        "Query Builder Node: Processing complete",
        conversation_id=conversation_id,
        query_length=len(enriched_query),
        history_count=len(conversation_history),
        has_summary=context_summary is not None,
    )

    # Update execution path
    execution_path = state.get("execution_path", [])
    execution_path = execution_path + ["query_builder_node"] if execution_path else ["query_builder_node"]

    return {
        "query_builder_result": enriched_query,
        "conversation_id": conversation_id,
        "conversation_history": conversation_history,
        "context_summary": context_summary,
        "execution_path": execution_path,
        "metadata": {
            **state.get("metadata", {}),
            "query_builder_processed": True,
            "conversation_id": conversation_id,
        },
    }

