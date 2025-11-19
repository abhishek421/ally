"""
Block-based message models for streaming responses
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


class BlockType(str, Enum):
    """Types of message blocks"""
    TEXT = "TEXT"
    TABLE = "TABLE"
    THINKING = "THINKING"


class StreamEventType(str, Enum):
    """Types of streaming events"""
    MESSAGE_START = "message_start"
    BLOCK_START = "block_start"
    BLOCK_DELTA = "block_delta"
    BLOCK_COMPLETE = "block_complete"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"


@dataclass
class Block:
    """Represents a single message block"""
    block_id: str
    block_type: BlockType
    content: str
    order: int
    metadata: Optional[Dict[str, Any]] = None
    entity_mentions: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary"""
        result = {
            "block_id": self.block_id,
            "block_type": self.block_type.value,
            "content": self.content,
            "order": self.order
        }
        
        # Only include metadata if it's a non-empty dict
        if self.metadata and isinstance(self.metadata, dict) and self.metadata:
            result["metadata"] = self.metadata
        
        # Only include entity_mentions if it's a non-empty list
        if self.entity_mentions and isinstance(self.entity_mentions, list) and self.entity_mentions:
            result["entity_mentions"] = self.entity_mentions
        
        return result


@dataclass
class StreamEvent:
    """Represents a streaming event"""
    type: StreamEventType
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            "type": self.type.value,
            **self.data
        }

    @classmethod
    def message_start(cls, message_id: str, conversation_id: str) -> 'StreamEvent':
        """Create message start event"""
        return cls(
            type=StreamEventType.MESSAGE_START,
            data={
                "message_id": message_id,
                "conversation_id": conversation_id
            }
        )

    @classmethod
    def block_start(cls, block_id: str, block_type: BlockType, order: int, metadata: Optional[Dict] = None, entity_mentions: Optional[List[Dict]] = None) -> 'StreamEvent':
        """Create block start event"""
        # Only include metadata/entity_mentions if they have values
        event_data = {
            "block_id": block_id,
            "block_type": block_type.value,
            "order": order
        }
        
        # Only add metadata if it's a non-empty dict
        if metadata and isinstance(metadata, dict) and metadata:
            event_data["metadata"] = metadata
        
        # Only add entity_mentions if it's a non-empty list
        if entity_mentions and isinstance(entity_mentions, list) and entity_mentions:
            event_data["entity_mentions"] = entity_mentions
        
        return cls(
            type=StreamEventType.BLOCK_START,
            data=event_data
        )

    @classmethod
    def block_delta(cls, block_id: str, content: str) -> 'StreamEvent':
        """Create block delta (partial content) event"""
        return cls(
            type=StreamEventType.BLOCK_DELTA,
            data={
                "block_id": block_id,
                "content": content
            }
        )

    @classmethod
    def block_complete(cls, block_id: str, block_type: BlockType, content: str, order: int, metadata: Optional[Dict] = None, entity_mentions: Optional[List[Dict]] = None) -> 'StreamEvent':
        """Create block complete event"""
        # Keep metadata and entity_mentions as None if they're None or empty
        # Only include non-empty values - this prevents empty dicts/lists from being passed to Prisma
        event_metadata = metadata if metadata and isinstance(metadata, dict) and metadata else None
        event_entity_mentions = entity_mentions if entity_mentions and isinstance(entity_mentions, list) and entity_mentions else None

        # Build event data - only include metadata/entity_mentions if they have values
        event_data = {
            "block_id": block_id,
            "block_type": block_type.value,
            "content": content,
            "order": order
        }

        # Only add metadata if it's a non-empty dict
        if event_metadata is not None:
            event_data["metadata"] = event_metadata

        # Only add entity_mentions if it's a non-empty list
        if event_entity_mentions is not None:
            event_data["entity_mentions"] = event_entity_mentions

        return cls(
            type=StreamEventType.BLOCK_COMPLETE,
            data=event_data
        )

    @classmethod
    def message_complete(cls, message_id: str, blocks_count: int) -> 'StreamEvent':
        """Create message complete event"""
        return cls(
            type=StreamEventType.MESSAGE_COMPLETE,
            data={
                "message_id": message_id,
                "blocks_count": blocks_count
            }
        )

    @classmethod
    def error(cls, error_message: str, error_code: Optional[str] = None) -> 'StreamEvent':
        """Create error event"""
        return cls(
            type=StreamEventType.ERROR,
            data={
                "error": error_message,
                "error_code": error_code
            }
        )
