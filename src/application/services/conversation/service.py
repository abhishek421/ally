from typing import List, Optional
import uuid
from datetime import datetime

from src.interfaces.schemas import Conversation, Message, MessageBlock
from src.memory.session_store import SessionStore
from src.memory.state import AgentState
from src.infrastructure.database.repository import ConversationRepository
from src.infrastructure.database.models import ConversationModel, MessageModel

class ConversationService:
    def __init__(self, session_store: SessionStore, repository: ConversationRepository):
        self.store = session_store
        self.repo = repository

    async def list_conversations(
        self, 
        user_id: str, 
        workspace_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Conversation]:
        # Fetch from DB instead of Redis
        models = await self.repo.list_conversations(user_id, workspace_id, limit, offset)
        return [
            Conversation(
                id=m.id,
                workspace_id=m.workspace_id,
                user_id=m.user_id,
                title=m.title,
                created_at=m.created_at,
                updated_at=m.updated_at
            ) for m in models
        ]

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        # Fetch from DB
        model = await self.repo.get_conversation(conversation_id)
        if not model:
            return None
        return Conversation(
            id=model.id,
            workspace_id=model.workspace_id,
            user_id=model.user_id,
            title=model.title,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Message]:
        # Fetch from DB
        models = await self.repo.get_messages(conversation_id, limit, offset)
        
        messages = []
        for m in models:
            # Convert JSON blocks back to pydantic models
            blocks = [MessageBlock(**b) for b in m.blocks] if m.blocks else []
            
            messages.append(Message(
                id=m.id,
                role=m.role,
                timestamp=m.timestamp,
                blocks=blocks
            ))
        return messages

    async def create_conversation(
        self, 
        user_id: str, 
        workspace_id: str, 
        title: str = "New Conversation"
    ) -> Conversation:
        conversation_id = str(uuid.uuid4())
        now = datetime.utcnow()
        conversation = Conversation(
            id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now
        )
        
        # Save to DB
        await self.repo.create_conversation(conversation)
        
        # Also save metadata to Redis (SessionStore) if we want to keep using it for quick lookups
        # or compatibility, but DB is source of truth now.
        await self.store.save_conversation_metadata(conversation)
        
        return conversation

    async def delete_conversation(self, conversation_id: str, user_id: str, workspace_id: str) -> None:
        # Delete from DB
        await self.repo.delete_conversation(conversation_id)
        
        # Delete from Redis
        await self.store.delete_conversation(conversation_id, user_id, workspace_id)

    async def persist_messages(self, conversation_id: str, messages: List[Message]):
        """Save new messages to DB."""
        # This is called after an agent turn
        # We might need logic to only save NEW messages, or we just append what we know is new.
        # For now, the caller handles 'new' messages.
        for msg in messages:
            await self.repo.add_message(conversation_id, msg)
