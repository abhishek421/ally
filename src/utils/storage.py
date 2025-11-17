"""Storage abstraction for conversation history."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..config import get_settings
from .models import Message

settings = get_settings()


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
    """LangGraph checkpoint-based storage implementation."""

    def __init__(self):
        """Initialize LangGraph storage."""
        self.checkpointer = MemorySaver()
        # In-memory storage for conversation data
        # Key: conversation_id, Value: dict with 'messages' and 'summary'
        self._storage: dict[str, dict] = {}

    def get_conversation_history(self, conversation_id: str) -> List[Message]:
        """Get conversation history from storage.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            List of messages
        """
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
        if conversation_id not in self._storage:
            self._storage[conversation_id] = {"messages": [], "summary": None, "summary_count": 0}

        self._storage[conversation_id]["messages"].append(message.to_dict())

    def save_summary(self, conversation_id: str, summary: str, message_count: int) -> None:
        """Save summary to storage.

        Args:
            conversation_id: Unique conversation identifier
            summary: Summary text
            message_count: Number of messages summarized
        """
        if conversation_id not in self._storage:
            self._storage[conversation_id] = {"messages": [], "summary": None, "summary_count": 0}

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

