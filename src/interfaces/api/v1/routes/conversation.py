import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query

from src.application.services.conversation.service import ConversationService
from src.memory.session_store import create_session_store
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.repository import ConversationRepository
from sqlalchemy.ext.asyncio import AsyncSession
from src.interfaces.schemas import (
    ConversationListResponse, 
    ConversationResponse, 
    MessageListResponse,
    DeleteConversationResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Dependency to get conversation service
async def get_conversation_service(
    db_session: AsyncSession = Depends(get_db_session)
) -> ConversationService:
    store = create_session_store()
    repo = ConversationRepository(db_session)
    return ConversationService(store, repo)

@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    x_workspace_id: str = Header(..., alias="X-Workspace-ID"),
    authorization: str = Header(None), 
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: ConversationService = Depends(get_conversation_service)
):
    user_id = "default_user" # Placeholder
    
    conversations = await service.list_conversations(user_id, x_workspace_id, limit, offset)
    
    return ConversationListResponse(
        success=True,
        conversations=conversations,
        total=len(conversations),
        limit=limit,
        offset=offset
    )

@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str = Path(...),
    x_workspace_id: str = Header(..., alias="X-Workspace-ID"),
    service: ConversationService = Depends(get_conversation_service)
):
    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.workspace_id != x_workspace_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ConversationResponse(
        success=True,
        conversation=conversation,
        message_count=0 # Placeholder
    )

@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    conversation_id: str = Path(...),
    x_workspace_id: str = Header(..., alias="X-Workspace-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: ConversationService = Depends(get_conversation_service)
):
    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if conversation.workspace_id != x_workspace_id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await service.get_conversation_messages(conversation_id, limit, offset)
    
    return MessageListResponse(
        success=True,
        conversation_id=conversation_id,
        messages=messages,
        total=len(messages), 
        limit=limit,
        offset=offset
    )

@router.delete("/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation(
    conversation_id: str = Path(...),
    x_workspace_id: str = Header(..., alias="X-Workspace-ID"),
    service: ConversationService = Depends(get_conversation_service)
):
    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if conversation.workspace_id != x_workspace_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await service.delete_conversation(conversation_id, conversation.user_id, x_workspace_id)
    
    return DeleteConversationResponse(
        success=True,
        message="Conversation deleted"
    )
