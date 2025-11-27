"""Storage abstraction for conversation history."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from ..config import get_settings
from ..tools.database import get_db_session
from ..tools.models import ConversationMessage
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
    def save_summary(self, conversation_id: str, summary: str, message_count: int) -> None:
        """Save a summary of older messages.

        Args:
            conversation_id: Unique conversation identifier
            summary: Summary text
            message_count: Number of messages that were summarized
        """
        pass

    @abstractmethod
    def get_summary(self, conversation_id: str) -> Optional[tuple[str, int]]:
        """Get summary and count of summarized messages.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Tuple of (summary, message_count) or None if no summary exists
        """
        pass


class LangGraphStorage(StorageInterface):
    """LangGraph checkpoint-based storage implementation with database backing."""

    def __init__(self):
        """Initialize LangGraph storage."""
        # In-memory cache for conversation data
        # Key: conversation_id, Value: dict with 'messages', 'summary', 'loaded_from_db'
        self._storage: dict[str, dict] = {}

    def _load_from_database(self, conversation_id: str) -> None:
        """Load conversation history from database if not already loaded.
        
        Args:
            conversation_id: Unique conversation identifier
        """
        if conversation_id in self._storage and self._storage[conversation_id].get("loaded_from_db"):
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
                    messages.append(msg.to_dict())
                
                # Initialize or update storage
                if conversation_id not in self._storage:
                    self._storage[conversation_id] = {
                        "messages": messages,
                        "summary": None,
                        "summary_count": 0,
                        "loaded_from_db": True,
                    }
                else:
                    # Merge: database messages first, then any in-memory messages not in DB
                    existing_messages = self._storage[conversation_id].get("messages", [])
                    # Only add new messages that aren't in the DB
                    db_contents = {m.get("content") for m in messages}
                    new_messages = [m for m in existing_messages if m.get("content") not in db_contents]
                    self._storage[conversation_id]["messages"] = messages + new_messages
                    self._storage[conversation_id]["loaded_from_db"] = True
                
                logger.debug(
                    "Loaded conversation from database",
                    conversation_id=conversation_id,
                    message_count=len(messages),
                )
                
        except ValueError:
            # Invalid UUID, just use in-memory
            logger.warning("Invalid conversation_id UUID, using in-memory only", conversation_id=conversation_id)
            if conversation_id not in self._storage:
                self._storage[conversation_id] = {"messages": [], "summary": None, "summary_count": 0, "loaded_from_db": True}
        except Exception as e:
            logger.error("Failed to load conversation from database", error=str(e), conversation_id=conversation_id)
            if conversation_id not in self._storage:
                self._storage[conversation_id] = {"messages": [], "summary": None, "summary_count": 0, "loaded_from_db": True}

    def get_conversation_history(self, conversation_id: str) -> List[Message]:
        """Get conversation history from storage.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            List of messages
        """
        # Load from database first if needed
        self._load_from_database(conversation_id)
        
        if conversation_id not in self._storage:
            return []

        data = self._storage[conversation_id]
        messages_data = data.get("messages", [])

        return [Message.from_dict(msg) for msg in messages_data]

    def save_message(self, conversation_id: str, message: Message) -> None:
        """Save message to storage.

        Args:
            conversation_id: Unique conversation identifier
            message: Message to save
        """
        # Load from database first if needed
        self._load_from_database(conversation_id)
        
        if conversation_id not in self._storage:
            self._storage[conversation_id] = {"messages": [], "summary": None, "summary_count": 0, "loaded_from_db": True}

        self._storage[conversation_id]["messages"].append(message.to_dict())

    def save_summary(self, conversation_id: str, summary: str, message_count: int) -> None:
        """Save summary to storage.

        Args:
            conversation_id: Unique conversation identifier
            summary: Summary text
            message_count: Number of messages summarized
        """
        if conversation_id not in self._storage:
            self._storage[conversation_id] = {"messages": [], "summary": None, "summary_count": 0, "loaded_from_db": False}

        self._storage[conversation_id]["summary"] = summary
        self._storage[conversation_id]["summary_count"] = message_count

    def get_summary(self, conversation_id: str) -> Optional[tuple[str, int]]:
        """Get summary from storage.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Tuple of (summary, message_count) or None
        """
        if conversation_id not in self._storage:
            return None

        data = self._storage[conversation_id]
        summary = data.get("summary")
        if summary is None:
            return None

        return (summary, data.get("summary_count", 0))


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

