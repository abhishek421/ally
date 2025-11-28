"""Service for managing conversations."""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm.attributes import flag_modified

from ..tools.database import get_db_session
from ..tools.models import Conversation, ConversationMessage
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


def list_conversations(
    workspace_id: str,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List conversations for a user in a workspace.
    
    Args:
        workspace_id: Workspace UUID string
        user_id: User UUID string
        limit: Maximum number of conversations to return
        offset: Offset for pagination
        
    Returns:
        Dictionary with conversations list, total count, and has_more flag
    """
    try:
        workspace_uuid = UUID(workspace_id)
        user_uuid = UUID(user_id)
        
        with get_db_session() as session:
            # Base query for user's conversations in workspace
            base_query = session.query(Conversation).filter(
                and_(
                    Conversation.workspaceId == workspace_uuid,
                    Conversation.userId == user_uuid,
                )
            )
            
            # Get total count
            total = base_query.count()
            
            # Get conversations ordered by most recent first
            conversations = base_query.order_by(
                desc(Conversation.updatedAt)
            ).offset(offset).limit(limit).all()
            
            # Build response with message counts and last message preview
            result_conversations = []
            for conv in conversations:
                # Get message count
                message_count = session.query(func.count(ConversationMessage.id)).filter(
                    ConversationMessage.conversationId == conv.id
                ).scalar() or 0
                
                # Get last message preview
                last_message = session.query(ConversationMessage).filter(
                    ConversationMessage.conversationId == conv.id
                ).order_by(desc(ConversationMessage.timestamp)).first()
                
                last_message_preview = None
                if last_message:
                    content = last_message.content or ""
                    last_message_preview = content[:100] + "..." if len(content) > 100 else content
                
                result_conversations.append({
                    "id": str(conv.id),
                    "workspace_id": str(conv.workspaceId),
                    "user_id": str(conv.userId),
                    "title": conv.title,
                    "created_at": conv.createdAt.isoformat() if conv.createdAt else None,
                    "updated_at": conv.updatedAt.isoformat() if conv.updatedAt else None,
                    "message_count": message_count,
                    "last_message": last_message_preview,
                })
            
            return {
                "conversations": result_conversations,
                "total": total,
                "has_more": (offset + limit) < total,
            }
            
    except ValueError as e:
        logger.error("Invalid UUID format for list_conversations", error=str(e))
        raise
    except Exception as e:
        logger.error("Failed to list conversations", error=str(e), exc_info=True)
        raise


def get_conversation(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
    include_messages: bool = True,
    message_limit: int = 100,
) -> Optional[Dict[str, Any]]:
    """Get a conversation by ID with optional messages.
    
    Args:
        conversation_id: Conversation UUID string
        workspace_id: Workspace UUID string
        user_id: User UUID string
        include_messages: Whether to include messages
        message_limit: Maximum number of messages to return
        
    Returns:
        Conversation dictionary or None if not found
    """
    try:
        conversation_uuid = UUID(conversation_id)
        workspace_uuid = UUID(workspace_id)
        user_uuid = UUID(user_id)
        
        with get_db_session() as session:
            # Get conversation (verify ownership)
            conversation = session.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_uuid,
                    Conversation.workspaceId == workspace_uuid,
                    Conversation.userId == user_uuid,
                )
            ).first()
            
            if not conversation:
                return None
            
            # Build response
            result = {
                "id": str(conversation.id),
                "workspace_id": str(conversation.workspaceId),
                "user_id": str(conversation.userId),
                "title": conversation.title,
                "created_at": conversation.createdAt.isoformat() if conversation.createdAt else None,
                "updated_at": conversation.updatedAt.isoformat() if conversation.updatedAt else None,
            }
            
            # Get message count
            message_count = session.query(func.count(ConversationMessage.id)).filter(
                ConversationMessage.conversationId == conversation_uuid
            ).scalar() or 0
            result["message_count"] = message_count
            
            # Include messages if requested
            if include_messages:
                messages = session.query(ConversationMessage).filter(
                    ConversationMessage.conversationId == conversation_uuid
                ).order_by(ConversationMessage.timestamp).limit(message_limit).all()
                
                result["messages"] = [
                    {
                        "id": str(msg.id),
                        "role": msg.role,
                        "content": msg.content,
                        "metadata": msg.meta_data,
                        "function_calls": msg.functionCalls,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    }
                    for msg in messages
                ]
            
            return result
            
    except ValueError as e:
        logger.error("Invalid UUID format for get_conversation", error=str(e))
        raise
    except Exception as e:
        logger.error("Failed to get conversation", error=str(e), exc_info=True)
        raise


def delete_conversation(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
) -> bool:
    """Delete a conversation and all its messages.
    
    Args:
        conversation_id: Conversation UUID string
        workspace_id: Workspace UUID string
        user_id: User UUID string
        
    Returns:
        True if deleted, False if not found
    """
    try:
        conversation_uuid = UUID(conversation_id)
        workspace_uuid = UUID(workspace_id)
        user_uuid = UUID(user_id)
        
        with get_db_session() as session:
            # Find conversation (verify ownership)
            conversation = session.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_uuid,
                    Conversation.workspaceId == workspace_uuid,
                    Conversation.userId == user_uuid,
                )
            ).first()
            
            if not conversation:
                return False
            
            # Delete messages first (cascade should handle this, but being explicit)
            session.query(ConversationMessage).filter(
                ConversationMessage.conversationId == conversation_uuid
            ).delete()
            
            # Delete conversation
            session.delete(conversation)
            session.commit()
            
            logger.info(
                "Deleted conversation",
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            
            return True
            
    except ValueError as e:
        logger.error("Invalid UUID format for delete_conversation", error=str(e))
        raise
    except Exception as e:
        logger.error("Failed to delete conversation", error=str(e), exc_info=True)
        raise


def update_conversation(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
    title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update a conversation's metadata.
    
    Args:
        conversation_id: Conversation UUID string
        workspace_id: Workspace UUID string
        user_id: User UUID string
        title: New title (optional)
        
    Returns:
        Updated conversation dictionary or None if not found
    """
    try:
        conversation_uuid = UUID(conversation_id)
        workspace_uuid = UUID(workspace_id)
        user_uuid = UUID(user_id)
        
        with get_db_session() as session:
            # Find conversation (verify ownership)
            conversation = session.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_uuid,
                    Conversation.workspaceId == workspace_uuid,
                    Conversation.userId == user_uuid,
                )
            ).first()
            
            if not conversation:
                return None
            
            # Update fields
            if title is not None:
                conversation.title = title
            
            session.commit()
            session.refresh(conversation)
            
            logger.info(
                "Updated conversation",
                conversation_id=conversation_id,
                title=title,
            )
            
            return {
                "id": str(conversation.id),
                "workspace_id": str(conversation.workspaceId),
                "user_id": str(conversation.userId),
                "title": conversation.title,
                "created_at": conversation.createdAt.isoformat() if conversation.createdAt else None,
                "updated_at": conversation.updatedAt.isoformat() if conversation.updatedAt else None,
            }
            
    except ValueError as e:
        logger.error("Invalid UUID format for update_conversation", error=str(e))
        raise


def update_conversation_token_usage(
    conversation_id: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Update cumulative token usage stored in conversation context.

    Args:
        conversation_id: Conversation UUID string
        input_tokens: Tokens used for the latest user request/context
        output_tokens: Tokens generated in the latest assistant response
    """
    try:
        conversation_uuid = UUID(conversation_id)
    except ValueError as exc:
        logger.warning(
            "Invalid conversation_id for token usage update",
            conversation_id=conversation_id,
            error=str(exc),
        )
        return

    try:
        with get_db_session() as session:
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_uuid
            ).first()

            if not conversation:
                logger.warning(
                    "Conversation not found for token usage update",
                    conversation_id=conversation_id,
                )
                return

            context_data: Dict[str, Any]
            raw_context = conversation.context

            if raw_context is None:
                context_data = {}
            elif isinstance(raw_context, dict):
                context_data = dict(raw_context)
            elif isinstance(raw_context, str) and raw_context.strip():
                try:
                    context_data = json.loads(raw_context)
                    if not isinstance(context_data, dict):
                        context_data = {}
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse conversation context as JSON; resetting",
                        conversation_id=conversation_id,
                    )
                    context_data = {}
            else:
                context_data = {}

            token_usage = context_data.get("token_usage")
            if not isinstance(token_usage, dict):
                token_usage = {}

            cumulative_input = int(token_usage.get("input_tokens", 0)) + max(input_tokens, 0)
            cumulative_output = int(token_usage.get("output_tokens", 0)) + max(output_tokens, 0)
            token_usage.update(
                {
                    "input_tokens": cumulative_input,
                    "output_tokens": cumulative_output,
                    "total_tokens": cumulative_input + cumulative_output,
                }
            )

            context_data["token_usage"] = token_usage
            conversation.context = context_data

            # Explicitly flag the JSONB field as modified so SQLAlchemy detects the change
            flag_modified(conversation, "context")

            session.add(conversation)
            session.commit()

            logger.info(
                "Updated conversation token usage",
                conversation_id=conversation_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cumulative_input=cumulative_input,
                cumulative_output=cumulative_output,
            )
    except Exception as exc:
        logger.error(
            "Failed to update conversation token usage",
            conversation_id=conversation_id,
            error=str(exc),
            exc_info=True,
        )

