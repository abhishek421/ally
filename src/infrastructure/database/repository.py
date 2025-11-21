from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.database.models import ConversationModel, MessageModel
from src.interfaces.schemas import Conversation, Message, MessageBlock

class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_conversation(self, conversation: Conversation) -> ConversationModel:
        db_conv = ConversationModel(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        self.session.add(db_conv)
        await self.session.commit()
        await self.session.refresh(db_conv)
        return db_conv

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationModel]:
        stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(
        self, 
        user_id: str, 
        workspace_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ConversationModel]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.workspace_id == workspace_id)
            # .where(ConversationModel.user_id == user_id) # Optional: restrict by user
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_conversation(self, conversation_id: str) -> bool:
        stmt = delete(ConversationModel).where(ConversationModel.id == conversation_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def add_message(self, conversation_id: str, message: Message) -> MessageModel:
        # Convert blocks to dicts for JSONB storage
        blocks_data = [b.model_dump(mode='json') for b in message.blocks]
        
        db_msg = MessageModel(
            id=message.id,
            conversation_id=conversation_id,
            role=message.role,
            content=None, # We rely on blocks primarily now, or can extract text from blocks
            blocks=blocks_data,
            timestamp=message.timestamp
        )
        self.session.add(db_msg)
        await self.session.commit()
        return db_msg
        
    async def get_messages(self, conversation_id: str, limit: int = 100, offset: int = 0) -> List[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.timestamp.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

