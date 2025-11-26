"""Service for managing conversations."""

from uuid import UUID

from ..tools.database import get_db_session
from ..tools.models import Conversation
from ..utils.logger import get_logger

logger = get_logger(__name__)


def generate_title_from_query(query: str, max_length: int = 50) -> str:
    """Generate a title from the user query.
    
    Args:
        query: User query string
        max_length: Maximum length for the title (default: 50)
        
    Returns:
        Generated title (truncated if needed)
    """
    # Remove extra whitespace
    query = query.strip()
    
    # If query is short enough, use it as-is
    if len(query) <= max_length:
        return query
    
    # Truncate to max_length and add ellipsis if needed
    title = query[:max_length].strip()
    
    # Try to truncate at word boundary if possible
    if len(query) > max_length:
        last_space = title.rfind(' ')
        if last_space > max_length * 0.7:  # Only use word boundary if it's not too short
            title = title[:last_space]
    
    # Add ellipsis if truncated
    if len(query) > len(title):
        title += "..."
    
    return title


def create_conversation_sync(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
    title: str | None = None,
) -> None:
    """Create a conversation record synchronously.
    
    This function will raise an exception if the conversation creation fails.
    Used for new conversations where we need to ensure the record exists.
    
    Args:
        conversation_id: Conversation UUID
        workspace_id: Workspace UUID
        user_id: User UUID
        title: Optional conversation title (will be generated from query if not provided)
        
    Raises:
        ValueError: If UUID conversion fails
        Exception: If database insertion fails
    """
    try:
        # Convert to UUIDs
        conversation_uuid = UUID(conversation_id)
        workspace_uuid = UUID(workspace_id)
        user_uuid = UUID(user_id)
        
        # Create conversation record
        with get_db_session() as session:
            conversation = Conversation(
                id=conversation_uuid,
                workspaceId=workspace_uuid,
                userId=user_uuid,
                title=title,
                context=None,  # Can be set later if needed
            )
            session.add(conversation)
            session.commit()
            
        logger.info(
            "Created conversation record",
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
        )
    except ValueError as e:
        logger.error(
            "Invalid UUID format for conversation creation",
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            error=str(e),
        )
        raise
    except Exception as e:
        logger.error(
            "Failed to create conversation record",
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            error=str(e),
            exc_info=True,
        )
        raise

