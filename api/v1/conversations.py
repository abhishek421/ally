"""
Conversation management endpoints
"""
from fastapi import APIRouter, Header, HTTPException, Query
from typing import Optional
from database.prisma_client import prisma_client

router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all conversations for a user (most recent first)
    Like ChatGPT's sidebar conversation list
    """
    client = await prisma_client.get_client()
    
    conversations = await client.conversation.find_many(
        where={
            "workspaceId": workspace_id,
            "userId": user_id,
        },
        order={"updatedAt": "desc"},
        take=limit,
        skip=offset,
    )
    
    total = await client.conversation.count(
        where={
            "workspaceId": workspace_id,
            "userId": user_id,
        }
    )
    
    return {
        "success": True,
        "conversations": conversations,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Get conversation details with basic info
    """
    client = await prisma_client.get_client()
    
    conversation = await client.conversation.find_unique(
        where={"id": conversation_id},
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Verify access
    if conversation.workspaceId != workspace_id or conversation.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get message count separately
    message_count = await client.conversationmessage.count(
        where={"conversationId": conversation_id}
    )
    
    return {
        "success": True,
        "conversation": conversation,
        "message_count": message_count,
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get messages for a conversation (chronological order)
    Like loading chat history in ChatGPT
    """
    client = await prisma_client.get_client()
    
    # Verify conversation exists and user has access
    conversation = await client.conversation.find_unique(
        where={"id": conversation_id},
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.workspaceId != workspace_id or conversation.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get messages
    messages = await client.conversationmessage.find_many(
        where={"conversationId": conversation_id},
        order={"timestamp": "asc"},
        skip=offset,
        take=limit,
    )
    
    total = await client.conversationmessage.count(
        where={"conversationId": conversation_id}
    )
    
    return {
        "success": True,
        "conversation_id": conversation_id,
        "messages": messages,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Delete a conversation (and all its messages via cascade)
    """
    client = await prisma_client.get_client()
    
    # Verify ownership
    conversation = await client.conversation.find_unique(
        where={"id": conversation_id},
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.workspaceId != workspace_id or conversation.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete (cascades to messages)
    await client.conversation.delete(where={"id": conversation_id})
    
    return {
        "success": True,
        "message": "Conversation deleted"
    }

