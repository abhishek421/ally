"""Service for saving conversation messages to database (non-blocking)."""

import threading
from typing import Any, Dict, List, Optional
from uuid import UUID

from ..tools.database import get_db_session
from ..tools.models import ConversationMessage
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _save_user_message_sync(
    conversation_id: str,
    content: str,
) -> None:
    """Save user message to database synchronously.
    
    This function will raise an exception if the message creation fails.
    Used for new conversations where we need to ensure the message is saved.
    
    Args:
        conversation_id: Conversation UUID
        content: Message content (user query)
        
    Raises:
        ValueError: If UUID conversion fails
        Exception: If database insertion fails
    """
    try:
        # Convert conversation_id to UUID
        conversation_uuid = UUID(conversation_id)
        
        # Create and save message
        with get_db_session() as session:
            message = ConversationMessage(
                conversationId=conversation_uuid,
                role="USER",
                content=content,
                meta_data=None,
                functionCalls=None,
            )
            session.add(message)
            session.commit()
            
        logger.info(
            "Saved user message to database",
            conversation_id=conversation_id,
            content_length=len(content),
        )
    except ValueError as e:
        logger.error(
            "Invalid UUID format for user message",
            conversation_id=conversation_id,
            error=str(e),
        )
        raise
    except Exception as e:
        logger.error(
            "Failed to save user message to database",
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )
        raise


def _save_user_message_sync_background(
    conversation_id: str,
    content: str,
) -> None:
    """Save user message to database synchronously (background version).
    
    This version logs errors but doesn't raise exceptions.
    Used for existing conversations where message saving is non-blocking.
    
    Args:
        conversation_id: Conversation UUID
        content: Message content (user query)
    """
    try:
        _save_user_message_sync(conversation_id, content)
    except Exception as e:
        # Log error but don't raise - this is non-blocking
        logger.error(
            "Failed to save user message to database (non-blocking)",
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )


def save_user_message_async(
    conversation_id: str,
    content: str,
) -> None:
    """Save user message to database asynchronously (non-blocking).
    
    This function starts a background thread to save the message without
    blocking the API response.
    
    Args:
        conversation_id: Conversation UUID
        content: Message content (user query)
    """
    # Start background thread to save message
    thread = threading.Thread(
        target=_save_user_message_sync_background,
        args=(conversation_id, content),
        daemon=True,  # Daemon thread won't prevent program exit
    )
    thread.start()
    
    logger.debug(
        "Started background thread to save user message",
        conversation_id=conversation_id,
    )


def _save_assistant_message_sync(
    conversation_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    function_calls: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Save assistant message to database synchronously.
    
    Args:
        conversation_id: Conversation UUID
        content: Message content (answer text)
        metadata: Optional metadata dictionary
        function_calls: Optional list of function call dictionaries
    """
    try:
        # Convert conversation_id to UUID
        conversation_uuid = UUID(conversation_id)
        
        # Create and save message
        # SQLAlchemy JSONB accepts Python dicts directly - no need to serialize
        with get_db_session() as session:
            message = ConversationMessage(
                conversationId=conversation_uuid,
                role="ASSISTANT",
                content=content,
                meta_data=metadata,  # JSONB accepts dict directly (meta_data maps to "metadata" column)
                functionCalls=function_calls,  # JSONB accepts list directly
            )
            session.add(message)
            session.commit()
            
        logger.info(
            "Saved assistant message to database",
            conversation_id=conversation_id,
            content_length=len(content),
            has_metadata=metadata is not None,
            has_function_calls=function_calls is not None,
        )
    except Exception as e:
        # Log error but don't raise - this is non-blocking
        logger.error(
            "Failed to save assistant message to database",
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )


def save_assistant_message_async(
    conversation_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    function_calls: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Save assistant message to database asynchronously (non-blocking).
    
    This function starts a background thread to save the message without
    blocking the API response.
    
    Args:
        conversation_id: Conversation UUID
        content: Message content (answer text)
        metadata: Optional metadata dictionary
        function_calls: Optional list of function call dictionaries
    """
    # Start background thread to save message
    thread = threading.Thread(
        target=_save_assistant_message_sync,
        args=(conversation_id, content, metadata, function_calls),
        daemon=True,  # Daemon thread won't prevent program exit
    )
    thread.start()
    
    logger.debug(
        "Started background thread to save assistant message",
        conversation_id=conversation_id,
    )


def prepare_metadata_from_response(
    result_data: Dict[str, Any],
    query_processing_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Prepare metadata dictionary from response data.
    
    Args:
        result_data: Parsed query processing result
        query_processing_metadata: Optional metadata from query processing node
        
    Returns:
        Metadata dictionary with model, tokens, reasoning steps, tools used
    """
    metadata = {}
    
    # Get metadata from result_data
    if "metadata" in result_data:
        metadata.update(result_data["metadata"])
    
    # Get metadata from query_processing_metadata
    if query_processing_metadata:
        metadata.update(query_processing_metadata)
    
    # Extract specific fields
    reasoning_steps = result_data.get("reasoning_steps", [])
    tool_calls = result_data.get("tool_calls", [])
    
    # Add structured metadata
    metadata["reasoning_steps_count"] = len(reasoning_steps)
    metadata["tool_calls_count"] = len(tool_calls)
    metadata["tools_used"] = [tc.get("tool", "") for tc in tool_calls if isinstance(tc, dict)]
    
    # Add model if available (from settings or metadata)
    from ..config import get_settings
    settings = get_settings()
    if "model" not in metadata:
        # Try to get model from settings
        metadata["model"] = settings.query_processing_model
    
    return metadata


def prepare_function_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepare function calls list for storage.
    
    Args:
        tool_calls: List of tool call dictionaries from response
        
    Returns:
        List of function call dictionaries formatted for storage
    """
    if not tool_calls:
        return []
    
    formatted_calls = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            formatted_call = {
                "name": tc.get("tool", ""),
                "arguments": tc.get("params", {}),
                "result": str(tc.get("result", ""))[:1000],  # Limit result length
                "iteration": tc.get("iteration", 0),
            }
            formatted_calls.append(formatted_call)
    
    return formatted_calls

