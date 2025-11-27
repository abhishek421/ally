"""Storage abstraction for conversation history."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from ..config import get_settings
from ..tools.database import get_db_session
from ..tools.models import Conversation, ConversationMessage, ConversationSummary
from .models import Message
from .logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class StorageInterface(ABC):
    """Abstract interface for conversation storage."""

    @abstractmethod
    def get_conversation_history(self, conversation_id: str) -> List[Message]:
        """Get conversation history for a conversation.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            List of messages in chronological order
        """
        pass

    @abstractmethod
    def save_message(self, conversation_id: str, message: Message) -> None:
        """Save a message to conversation history.

        Args:
            conversation_id: Unique conversation identifier
            message: Message to save
        """
        pass

    @abstractmethod
    def save_summary(
        self,
        conversation_id: str,
        summary: str,
        message_count: int,
        workspace_id: Optional[str] = None,
        start_message_id: Optional[str] = None,
        end_message_id: Optional[str] = None,
        summary_tokens: Optional[int] = None,
    ) -> None:
        """Save a summary of older messages.

        Args:
            conversation_id: Unique conversation identifier
            summary: Summary text
            message_count: Number of messages that were summarized
            workspace_id: Workspace UUID (optional, will be queried if not provided)
            start_message_id: UUID of first message in summary range
            end_message_id: UUID of last message in summary range
            summary_tokens: Token count of summary text
        """
        pass

    @abstractmethod
    def get_summary(self, conversation_id: str) -> Optional[tuple[str, int, Optional[str], Optional[str]]]:
        """Get summary and count of summarized messages.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Tuple of (summary, message_count, start_message_id, end_message_id) or None if no summary exists
        """
        pass


class LangGraphStorage(StorageInterface):
    """LangGraph checkpoint-based storage implementation with database backing."""

    def __init__(self):
        """Initialize LangGraph storage."""
        # In-memory cache for conversation data
        # Key: conversation_id, Value: dict with 'messages', 'summary', 'loaded_from_db'
        self._storage: dict[str, dict] = {}

    def get_workspace_id_from_conversation(self, conversation_id: str) -> Optional[str]:
        """Get workspace_id from conversation table.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Workspace UUID string or None if not found
        """
        try:
            conversation_uuid = UUID(conversation_id)
            with get_db_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_uuid
                ).first()
                if conversation:
                    return str(conversation.workspaceId)
        except Exception as e:
            logger.warning(
                "Failed to get workspace_id from conversation",
                conversation_id=conversation_id,
                error=str(e),
            )
        return None

    def get_message_id_by_offset(
        self, conversation_id: str, offset: int
    ) -> Optional[str]:
        """Get message ID by offset (0-based index).
        
        Checks in-memory cache first (for messages loaded from DB), then falls back to database query.
        
        Args:
            conversation_id: Conversation UUID
            offset: Message offset (0 = first message)
            
        Returns:
            Message UUID string or None if not found
        """
        # First, check in-memory cache (messages loaded from DB have IDs)
        if conversation_id in self._storage:
            messages = self._storage[conversation_id].get("messages", [])
            if offset < len(messages):
                msg_dict = messages[offset]
                # Check if message has an ID (from database)
                if "id" in msg_dict and msg_dict["id"]:
                    logger.debug(
                        "Found message ID in cache",
                        conversation_id=conversation_id,
                        offset=offset,
                        message_id=msg_dict["id"],
                    )
                    return msg_dict["id"]
        
        # Fall back to database query
        try:
            conversation_uuid = UUID(conversation_id)
            with get_db_session() as session:
                message = (
                    session.query(ConversationMessage)
                    .filter(ConversationMessage.conversationId == conversation_uuid)
                    .order_by(ConversationMessage.timestamp)
                    .offset(offset)
                    .limit(1)
                    .first()
                )
                if message:
                    logger.debug(
                        "Found message ID in database",
                        conversation_id=conversation_id,
                        offset=offset,
                        message_id=str(message.id),
                    )
                    return str(message.id)
        except Exception as e:
            logger.warning(
                "Failed to get message ID by offset",
                conversation_id=conversation_id,
                offset=offset,
                error=str(e),
            )
        
        logger.warning(
            "Message ID not found",
            conversation_id=conversation_id,
            offset=offset,
            cache_has_messages=conversation_id in self._storage,
            cache_message_count=len(self._storage[conversation_id].get("messages", [])) if conversation_id in self._storage else 0,
        )
        return None

    def _get_last_message_id(self, conversation_id: str) -> Optional[str]:
        """Get ID of the last message in conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Message UUID string or None if not found
        """
        try:
            conversation_uuid = UUID(conversation_id)
            with get_db_session() as session:
                message = (
                    session.query(ConversationMessage)
                    .filter(ConversationMessage.conversationId == conversation_uuid)
                    .order_by(ConversationMessage.timestamp.desc())
                    .limit(1)
                    .first()
                )
                if message:
                    return str(message.id)
        except Exception as e:
            logger.warning(
                "Failed to get last message ID",
                conversation_id=conversation_id,
                error=str(e),
            )
        return None

    def _get_message_timestamp(self, message_id: str) -> Optional[datetime]:
        """Get timestamp of a message by ID.
        
        Args:
            message_id: Message UUID
            
        Returns:
            Message timestamp or None if not found
        """
        try:
            message_uuid = UUID(message_id)
            with get_db_session() as session:
                message = session.query(ConversationMessage).filter(
                    ConversationMessage.id == message_uuid
                ).first()
                if message:
                    return message.timestamp
        except Exception as e:
            logger.warning(
                "Failed to get message timestamp",
                message_id=message_id,
                error=str(e),
            )
        return None

    def _load_from_database(self, conversation_id: str, force_reload: bool = False) -> None:
        """Load conversation history from database.
        
        Args:
            conversation_id: Unique conversation identifier
            force_reload: If True, reload from DB even if already loaded (to get latest messages)
        """
        # Only skip if already loaded AND not forcing reload
        # This ensures we get assistant messages that were saved asynchronously
        if not force_reload and conversation_id in self._storage and self._storage[conversation_id].get("loaded_from_db"):
            return  # Already loaded
            
        try:
            conversation_uuid = UUID(conversation_id)
            
            with get_db_session() as session:
                # Load messages from database
                db_messages = session.query(ConversationMessage).filter(
                    ConversationMessage.conversationId == conversation_uuid
                ).order_by(ConversationMessage.timestamp).all()
                
                messages = []
                for db_msg in db_messages:
                    # Map database role to our role format
                    role = db_msg.role.lower() if db_msg.role else "user"
                    if role == "assistant":
                        role = "assistant"
                    elif role == "system":
                        role = "system"
                    else:
                        role = "user"
                    
                    msg = Message(
                        role=role,
                        content=db_msg.content or "",
                        timestamp=db_msg.timestamp or datetime.now(),
                    )
                    msg_dict = msg.to_dict()
                    # Store message ID from database for later reference
                    msg_dict["id"] = str(db_msg.id)
                    messages.append(msg_dict)
                
                # Load summary from database
                db_summary = (
                    session.query(ConversationSummary)
                    .filter(ConversationSummary.conversationId == conversation_uuid)
                    .order_by(ConversationSummary.createdAt.desc())
                    .first()
                )
                
                # Initialize or update storage
                if conversation_id not in self._storage:
                    self._storage[conversation_id] = {
                        "messages": messages,
                        "summary": None,
                        "summary_count": 0,
                        "start_message_id": None,
                        "end_message_id": None,
                        "loaded_from_db": True,
                    }
                else:
                    # Merge: database messages first, then any in-memory messages not in DB
                    # Use content + timestamp as key to avoid duplicates more accurately
                    existing_messages = self._storage[conversation_id].get("messages", [])
                    # Create set of (content, timestamp) tuples from DB messages for deduplication
                    db_message_keys = {(m.get("content"), m.get("timestamp")) for m in messages}
                    # Only add in-memory messages that aren't in the DB
                    new_messages = [
                        m for m in existing_messages 
                        if (m.get("content"), m.get("timestamp")) not in db_message_keys
                    ]
                    # Combine: DB messages (authoritative with IDs) + any new in-memory messages not yet in DB
                    # Note: new_messages won't have IDs until they're saved to DB
                    self._storage[conversation_id]["messages"] = messages + new_messages
                    self._storage[conversation_id]["loaded_from_db"] = True
                
                # Load summary if exists
                if db_summary:
                    self._storage[conversation_id]["summary"] = db_summary.summaryText
                    self._storage[conversation_id]["summary_count"] = db_summary.messageCount
                    self._storage[conversation_id]["start_message_id"] = str(db_summary.startMessageId)
                    self._storage[conversation_id]["end_message_id"] = str(db_summary.endMessageId)
                
                logger.info(
                    "Loaded conversation from database",
                    conversation_id=conversation_id,
                    db_message_count=len(messages),
                    cached_message_count=len(self._storage[conversation_id].get("messages", [])) if conversation_id in self._storage else 0,
                    final_message_count=len(self._storage[conversation_id]["messages"]) if conversation_id in self._storage else 0,
                    has_summary=db_summary is not None,
                    message_roles_from_db=[msg.get("role") for msg in messages] if messages else [],
                )
                
        except ValueError:
            # Invalid UUID, just use in-memory
            logger.warning("Invalid conversation_id UUID, using in-memory only", conversation_id=conversation_id)
            if conversation_id not in self._storage:
                self._storage[conversation_id] = {
                    "messages": [],
                    "summary": None,
                    "summary_count": 0,
                    "start_message_id": None,
                    "end_message_id": None,
                    "loaded_from_db": True,
                }
        except Exception as e:
            logger.error("Failed to load conversation from database", error=str(e), conversation_id=conversation_id)
            if conversation_id not in self._storage:
                self._storage[conversation_id] = {
                    "messages": [],
                    "summary": None,
                    "summary_count": 0,
                    "start_message_id": None,
                    "end_message_id": None,
                    "loaded_from_db": True,
                }

    def get_conversation_history(self, conversation_id: str, force_reload: bool = False) -> List[Message]:
        """Get conversation history from storage.

        Args:
            conversation_id: Unique conversation identifier
            force_reload: If True, reload from DB to get latest messages (useful for getting async-saved messages)

        Returns:
            List of messages
        """
        logger.info(
            "Getting conversation history",
            conversation_id=conversation_id,
            force_reload=force_reload,
            already_in_cache=conversation_id in self._storage,
        )
        
        # Load from database (force reload to get latest assistant messages saved asynchronously)
        self._load_from_database(conversation_id, force_reload=force_reload)
        
        if conversation_id not in self._storage:
            logger.warning("Conversation not in storage after load", conversation_id=conversation_id)
            return []

        data = self._storage[conversation_id]
        messages_data = data.get("messages", [])
        
        messages = [Message.from_dict(msg) for msg in messages_data]
        
        logger.info(
            "Returning conversation history",
            conversation_id=conversation_id,
            message_count=len(messages),
            message_roles=[msg.role for msg in messages],
        )

        return messages

    def save_message(self, conversation_id: str, message: Message) -> None:
        """Save message to storage.

        Args:
            conversation_id: Unique conversation identifier
            message: Message to save
        """
        # Load from database first if needed
        self._load_from_database(conversation_id)
        
        if conversation_id not in self._storage:
            self._storage[conversation_id] = {
                "messages": [],
                "summary": None,
                "summary_count": 0,
                "start_message_id": None,
                "end_message_id": None,
                "loaded_from_db": True,
            }

        self._storage[conversation_id]["messages"].append(message.to_dict())

    def save_summary(
        self,
        conversation_id: str,
        summary: str,
        message_count: int,
        workspace_id: Optional[str] = None,
        start_message_id: Optional[str] = None,
        end_message_id: Optional[str] = None,
        summary_tokens: Optional[int] = None,
    ) -> None:
        """Save summary to storage (both in-memory and database).

        Args:
            conversation_id: Unique conversation identifier
            summary: Summary text
            message_count: Number of messages summarized
            workspace_id: Workspace UUID (optional, will be queried if not provided)
            start_message_id: UUID of first message in summary range
            end_message_id: UUID of last message in summary range
            summary_tokens: Token count of summary text
        """
        logger.info(
            "Saving summary to storage",
            conversation_id=conversation_id,
            summary_length=len(summary),
            message_count=message_count,
            workspace_id=workspace_id,
            start_message_id=start_message_id,
            end_message_id=end_message_id,
            summary_tokens=summary_tokens,
        )
        
        # Update in-memory cache
        if conversation_id not in self._storage:
            self._storage[conversation_id] = {
                "messages": [],
                "summary": None,
                "summary_count": 0,
                "start_message_id": None,
                "end_message_id": None,
                "loaded_from_db": False,
            }

        self._storage[conversation_id]["summary"] = summary
        self._storage[conversation_id]["summary_count"] = message_count
        if start_message_id:
            self._storage[conversation_id]["start_message_id"] = start_message_id
        if end_message_id:
            self._storage[conversation_id]["end_message_id"] = end_message_id
        
        logger.info(
            "Summary saved to in-memory cache",
            conversation_id=conversation_id,
        )

        # Save to database (with error handling - fallback to in-memory only)
        try:
            conversation_uuid = UUID(conversation_id)
            
            # Get workspace_id if not provided
            if not workspace_id:
                workspace_id = self.get_workspace_id_from_conversation(conversation_id)
                if not workspace_id:
                    logger.warning(
                        "Cannot save summary to DB: workspace_id not found",
                        conversation_id=conversation_id,
                    )
                    return  # Fallback to in-memory only
            
            workspace_uuid = UUID(workspace_id)
            
            # Get message IDs if not provided
            if not start_message_id:
                # First message ever (offset 0)
                start_message_id = self.get_message_id_by_offset(conversation_id, 0)
            
            if not end_message_id:
                # Last message before current query (offset = message_count - 1)
                # Since message_count includes all messages up to the last one before current query
                # But some messages might not be in DB yet (async saves), so we need to find the last message that HAS an ID
                end_message_id = self.get_message_id_by_offset(conversation_id, message_count - 1)
                
                # If not found, try to find the last message that has an ID in the cache
                if not end_message_id and conversation_id in self._storage:
                    messages = self._storage[conversation_id].get("messages", [])
                    # Search backwards from message_count - 1 to find a message with an ID
                    for offset in range(message_count - 1, -1, -1):
                        if offset < len(messages):
                            msg_dict = messages[offset]
                            if "id" in msg_dict and msg_dict["id"]:
                                end_message_id = msg_dict["id"]
                                logger.info(
                                    "Found end_message_id by searching cache backwards",
                                    conversation_id=conversation_id,
                                    offset=offset,
                                    message_id=end_message_id,
                                )
                                break
                
                # If still not found, try querying DB for the last message
                if not end_message_id:
                    end_message_id = self._get_last_message_id(conversation_id)
                    if end_message_id:
                        logger.info(
                            "Found end_message_id from last message in DB",
                            conversation_id=conversation_id,
                            message_id=end_message_id,
                        )
            
            if not start_message_id or not end_message_id:
                logger.warning(
                    "Cannot save summary to DB: message IDs not found",
                    conversation_id=conversation_id,
                    start_message_id=start_message_id,
                    end_message_id=end_message_id,
                    message_count=message_count,
                    cache_message_count=len(self._storage[conversation_id].get("messages", [])) if conversation_id in self._storage else 0,
                )
                return  # Fallback to in-memory only
            
            start_msg_uuid = UUID(start_message_id)
            end_msg_uuid = UUID(end_message_id)
            
            # Get end message timestamp
            end_message_at = self._get_message_timestamp(end_message_id)
            if not end_message_at:
                logger.warning(
                    "Cannot save summary to DB: end message timestamp not found",
                    conversation_id=conversation_id,
                    end_message_id=end_message_id,
                )
                return  # Fallback to in-memory only
            
            # Calculate summary_tokens if not provided
            if summary_tokens is None:
                from .tokenizer import get_tokenizer
                tokenizer = get_tokenizer()
                summary_tokens = tokenizer.count_tokens(summary)
            
            # Check if summary already exists for this conversation
            with get_db_session() as session:
                existing_summary = (
                    session.query(ConversationSummary)
                    .filter(ConversationSummary.conversationId == conversation_uuid)
                    .order_by(ConversationSummary.createdAt.desc())
                    .first()
                )
                
                if existing_summary:
                    # UPDATE existing record
                    existing_summary.summaryText = summary
                    existing_summary.endMessageId = end_msg_uuid
                    existing_summary.endMessageAt = end_message_at
                    existing_summary.messageCount = message_count
                    existing_summary.summaryTokens = summary_tokens
                    existing_summary.updatedAt = datetime.utcnow()
                    # Keep startMessageId as first message ever (don't change it)
                    
                    session.commit()
                    logger.info(
                        "Updated conversation summary in database",
                        conversation_id=conversation_id,
                        message_count=message_count,
                    )
                else:
                    # INSERT new record
                    new_summary = ConversationSummary(
                        conversationId=conversation_uuid,
                        workspaceId=workspace_uuid,
                        summaryText=summary,
                        startMessageId=start_msg_uuid,
                        endMessageId=end_msg_uuid,
                        endMessageAt=end_message_at,
                        messageCount=message_count,
                        summaryTokens=summary_tokens,
                    )
                    session.add(new_summary)
                    session.commit()
                    logger.info(
                        "Saved conversation summary to database",
                        conversation_id=conversation_id,
                        message_count=message_count,
                    )
                    
        except ValueError as e:
            logger.warning(
                "Invalid UUID format for summary save",
                conversation_id=conversation_id,
                error=str(e),
            )
            # Fallback to in-memory only
        except Exception as e:
            logger.error(
                "Failed to save summary to database",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            # Fallback to in-memory only (already saved above)

    def get_summary(self, conversation_id: str) -> Optional[tuple[str, int, Optional[str], Optional[str]]]:
        """Get summary from storage (checks in-memory cache first, then database).

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Tuple of (summary, message_count, start_message_id, end_message_id) or None
        """
        # Check in-memory cache first
        if conversation_id in self._storage:
            data = self._storage[conversation_id]
            summary = data.get("summary")
            if summary is not None:
                start_msg_id = data.get("start_message_id")
                end_msg_id = data.get("end_message_id")
                return (summary, data.get("summary_count", 0), start_msg_id, end_msg_id)
        
        # Load from database if not in cache
        try:
            conversation_uuid = UUID(conversation_id)
            with get_db_session() as session:
                db_summary = (
                    session.query(ConversationSummary)
                    .filter(ConversationSummary.conversationId == conversation_uuid)
                    .order_by(ConversationSummary.createdAt.desc())
                    .first()
                )
                
                if db_summary:
                    # Load into in-memory cache
                    if conversation_id not in self._storage:
                        self._storage[conversation_id] = {
                            "messages": [],
                            "summary": None,
                            "summary_count": 0,
                            "loaded_from_db": False,
                        }
                    
                    self._storage[conversation_id]["summary"] = db_summary.summaryText
                    self._storage[conversation_id]["summary_count"] = db_summary.messageCount
                    self._storage[conversation_id]["start_message_id"] = str(db_summary.startMessageId)
                    self._storage[conversation_id]["end_message_id"] = str(db_summary.endMessageId)
                    
                    return (
                        db_summary.summaryText,
                        db_summary.messageCount,
                        str(db_summary.startMessageId),
                        str(db_summary.endMessageId),
                    )
        except ValueError:
            logger.warning(
                "Invalid UUID format for summary retrieval",
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.error(
                "Failed to load summary from database",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
        
        return None


def get_storage() -> StorageInterface:
    """Get storage instance based on configuration.

    Returns:
        StorageInterface implementation
    """
    storage_type = settings.storage_type.lower()

    if storage_type == "langgraph":
        return LangGraphStorage()
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")

