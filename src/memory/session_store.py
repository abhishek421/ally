"""
Session store for persisting agent state across conversation turns.

This module is responsible for persisting and retrieving the AgentState for each
conversation using Redis as an ephemeral session store.

Important distinctions:
- This stores conversational MEMORY only (agent state, tool calls, reasoning)
- This does NOT store user-visible chat messages for the frontend
- Redis acts as ephemeral session memory with TTL
- A separate database is responsible for permanent chat history

The SessionStore allows the agent to:
- Resume conversations across multiple requests
- Maintain context and execution history
- Support multi-turn conversations with full state preservation

TODO: Add encryption at rest if needed for sensitive data
TODO: Allow pluggable backends (Postgres, DynamoDB, in-memory mock for testing)
"""

# ========================================
# 1. Imports
# ========================================

import json
from typing import Optional, List
from pydantic import ValidationError
import redis.asyncio as redis

from src.memory.state import AgentState
from src.interfaces.schemas import Conversation
from src.config.settings import settings
from src.config.logger import logger


# ========================================
# 2. SessionStore Class
# ========================================


class SessionStore:
    """
    Async Redis-backed session store for agent state persistence.
    
    This class handles serialization, storage, and retrieval of AgentState objects
    for each conversation. State is stored in Redis with a configurable TTL to
    automatically expire old conversations.
    
    Key format: {prefix}{conversation_id}
    Example: "agent_state:conv-123-abc"
    
    Features:
    - Async operations for high performance
    - Automatic TTL expiration
    - Graceful error handling with fallback to fresh state
    - Filters out non-serializable fields before storage
    
    Usage:
        store = SessionStore(redis_url="redis://localhost:6379")
        state = await store.load_state("conversation-123")
        # ... modify state ...
        await store.save_state("conversation-123", state)
        await store.close()
    """
    
    def __init__(
        self,
        redis_url: str,
        prefix: str = "agent_state:",
        ttl_seconds: int = 7 * 24 * 3600  # 7 days default
    ):
        """
        Initialize the session store with Redis connection.
        
        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            prefix: Key prefix for namespacing agent state keys
            ttl_seconds: Time-to-live for stored sessions in seconds (default: 7 days)
        """
        self.redis_url = redis_url
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self.redis: Optional[redis.Redis] = None
        
        logger.info(
            f"Initializing SessionStore with prefix='{prefix}', ttl={ttl_seconds}s"
        )
    
    async def _ensure_connection(self) -> None:
        """Ensure Redis connection is established."""
        if self.redis is None:
            self.redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {self.redis_url}")
    
    async def load_state(self, conversation_id: str) -> AgentState:
        """
        Load agent state from Redis for a given conversation.
        
        If no state exists in Redis, returns a fresh AgentState with placeholder
        values that should be filled by the server before graph execution.
        
        If parsing fails, logs a warning and returns a fresh state to prevent
        crashes from corrupted data.
        
        Args:
            conversation_id: Unique identifier for the conversation
        
        Returns:
            AgentState object loaded from Redis or a fresh instance
        
        Example:
            state = await store.load_state("conv-123")
            # state.messages will contain history if conversation exists
        """
        await self._ensure_connection()
        
        # Build Redis key
        key = f"{self.prefix}{conversation_id}"
        
        try:
            # Attempt to retrieve from Redis
            data = await self.redis.get(key)
            
            if data is None:
                logger.info(
                    f"No existing state found for conversation {conversation_id}, "
                    f"creating fresh state"
                )
                # Return fresh state with placeholder values
                # Server will populate these before graph execution
                return AgentState(
                    conversation_id=conversation_id,
                    user_id="",
                    workspace_id=""
                )
            
            # Parse JSON data
            parsed_json = json.loads(data)
            
            # Remove non-serializable fields that shouldn't have been stored
            # (defensive programming in case data format changed)
            if "tools" in parsed_json:
                del parsed_json["tools"]
            
            # Reconstruct AgentState from parsed data
            state = AgentState(**parsed_json)
            
            logger.info(
                f"Loaded state for conversation {conversation_id} "
                f"({len(state.messages)} messages, {len(state.tool_calls)} tool calls)"
            )
            
            return state
            
        except ValidationError as e:
            logger.warning(
                f"Failed to validate state for conversation {conversation_id}: {e}. "
                f"Returning fresh state."
            )
            return AgentState(
                conversation_id=conversation_id,
                user_id="",
                workspace_id=""
            )
        
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse JSON for conversation {conversation_id}: {e}. "
                f"Returning fresh state."
            )
            return AgentState(
                conversation_id=conversation_id,
                user_id="",
                workspace_id=""
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error loading state for conversation {conversation_id}: {e}. "
                f"Returning fresh state."
            )
            return AgentState(
                conversation_id=conversation_id,
                user_id="",
                workspace_id=""
            )
    
    async def save_state(self, conversation_id: str, state: AgentState) -> None:
        """
        Save agent state to Redis with TTL.
        
        Serializes the AgentState to JSON, removing non-serializable fields
        like the tools registry (which contains Callable objects). The state
        is stored with the configured TTL for automatic expiration.
        
        Args:
            conversation_id: Unique identifier for the conversation
            state: AgentState object to persist
        
        Raises:
            Exception: Logs errors but does not raise to prevent disrupting the agent
        
        Example:
            await store.save_state("conv-123", state)
        """
        await self._ensure_connection()
        
        # Build Redis key
        key = f"{self.prefix}{conversation_id}"
        
        try:
            # Convert state to dict
            state_dict = state.model_dump()
            
            # Remove non-serializable fields
            # Tools registry contains Callable objects that can't be serialized
            if "tools" in state_dict:
                del state_dict["tools"]
            
            # Additional cleanup for any other non-serializable fields
            # (future-proofing in case new fields are added)
            
            # Serialize to JSON
            json_data = json.dumps(state_dict, default=str)  # default=str handles datetime
            
            # Store in Redis with TTL
            await self.redis.setex(key, self.ttl_seconds, json_data)
            
            logger.info(
                f"Saved state for conversation {conversation_id} "
                f"({len(state.messages)} messages, ttl={self.ttl_seconds}s)"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to save state for conversation {conversation_id}: {e}"
            )
            # Don't raise - we don't want to break the agent flow due to storage issues
    
    async def clear_state(self, conversation_id: str) -> None:
        """
        Delete agent state from Redis for a given conversation.
        
        Use this to manually clear conversation history or implement
        a "reset conversation" feature.
        
        Args:
            conversation_id: Unique identifier for the conversation to clear
        
        Example:
            await store.clear_state("conv-123")
        """
        await self._ensure_connection()
        
        # Build Redis key
        key = f"{self.prefix}{conversation_id}"
        
        try:
            result = await self.redis.delete(key)
            
            if result > 0:
                logger.info(f"Cleared state for conversation {conversation_id}")
            else:
                logger.info(
                    f"No state found to clear for conversation {conversation_id}"
                )
                
        except Exception as e:
            logger.error(
                f"Failed to clear state for conversation {conversation_id}: {e}"
            )
    
    # ========================================
    # Conversation Metadata & Indexing
    # ========================================

    async def save_conversation_metadata(self, conversation: Conversation) -> None:
        """Save conversation metadata and index it for the user."""
        await self._ensure_connection()
        
        # Save metadata
        meta_key = f"conversation_meta:{conversation.id}"
        await self.redis.setex(meta_key, self.ttl_seconds, conversation.model_dump_json())
        
        # Add to user's list
        user_list_key = f"user_conversations:{conversation.workspace_id}:{conversation.user_id}"
        await self.redis.lpush(user_list_key, conversation.id)
        # Optional: cap list size or rely on TTL of metadata
        
    async def get_conversation_metadata(self, conversation_id: str) -> Optional[Conversation]:
        """Retrieve conversation metadata."""
        await self._ensure_connection()
        meta_key = f"conversation_meta:{conversation_id}"
        data = await self.redis.get(meta_key)
        if data:
            try:
                return Conversation.model_validate_json(data)
            except Exception as e:
                logger.error(f"Error parsing conversation metadata for {conversation_id}: {e}")
                return None
        return None

    async def list_user_conversations(
        self, 
        user_id: str, 
        workspace_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Conversation]:
        """List conversations for a user in a workspace."""
        await self._ensure_connection()
        user_list_key = f"user_conversations:{workspace_id}:{user_id}"
        
        # Get IDs (paginate)
        # LRANGE is inclusive for start and stop
        # Redis indices are 0-based
        start = offset
        end = offset + limit - 1
        conv_ids = await self.redis.lrange(user_list_key, start, end)
        
        conversations = []
        for conv_id in conv_ids:
            meta = await self.get_conversation_metadata(conv_id)
            if meta:
                conversations.append(meta)
            else:
                # Metadata expired or missing, maybe cleanup ID from list?
                # For now, just skip
                pass
                
        return conversations

    async def delete_conversation(self, conversation_id: str, user_id: str, workspace_id: str) -> None:
        """Delete conversation data and remove from index."""
        await self._ensure_connection()
        
        # 1. Remove from user list
        user_list_key = f"user_conversations:{workspace_id}:{user_id}"
        await self.redis.lrem(user_list_key, 0, conversation_id)
        
        # 2. Delete metadata
        meta_key = f"conversation_meta:{conversation_id}"
        await self.redis.delete(meta_key)
        
        # 3. Delete agent state
        await self.clear_state(conversation_id)

    async def close(self) -> None:
        """
        Close the Redis connection.
        
        Should be called on application shutdown to cleanly close connections.
        
        Example:
            # On shutdown
            await store.close()
        """
        if self.redis is not None:
            await self.redis.close()
            logger.info("Closed Redis connection")


# ========================================
# 7. Helper Function
# ========================================


def create_session_store() -> SessionStore:
    """
    Create a SessionStore instance using settings from configuration.
    
    This is the recommended way to instantiate a SessionStore, as it
    automatically pulls the Redis URL from the application settings.
    
    Returns:
        Configured SessionStore instance
    
    Example:
        store = create_session_store()
        state = await store.load_state("conv-123")
    """
    # Read Redis URL from settings
    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    
    # Create and return store instance
    return SessionStore(
        redis_url=redis_url,
        prefix="agent_state:",
        ttl_seconds=7 * 24 * 3600  # 7 days
    )
