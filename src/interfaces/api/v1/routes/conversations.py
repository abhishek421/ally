"""
Conversation management endpoints
"""
from fastapi import APIRouter, Header, HTTPException, Query, Depends
from typing import Optional
from src.infrastructure.database.prisma_client import prisma_client
from src.interfaces.api.v1.middleware.dependencies import get_current_user_id

router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all conversations for a user (most recent first)
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
    user_id: str = Depends(get_current_user_id),
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

    # Return only useful fields (exclude null relation fields)
    return {
        "success": True,
        "conversation": {
            "id": conversation.id,
            "workspace_id": conversation.workspaceId,
            "user_id": conversation.userId,
            "title": conversation.title,
            "created_at": conversation.createdAt,
            "updated_at": conversation.updatedAt,
        },
        "message_count": message_count,
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get messages for a conversation with their blocks (chronological order)
    """
    # Validate conversation_id is not "null" or empty
    if not conversation_id or conversation_id.lower() in ["null", "undefined", "none"]:
        raise HTTPException(status_code=400, detail="Invalid conversation_id")

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

    # Fetch blocks for each message
    messages_with_blocks = []
    for msg in messages:
        blocks = await client.messageblock.find_many(
            where={"messageId": msg.id},
            order={"order": "asc"}
        )

        messages_with_blocks.append({
            "id": msg.id,
            "role": msg.role,
            "timestamp": msg.timestamp,
            "blocks": [
                {
                    "block_id": block.id,
                    "block_type": block.blockType,
                    "content": block.content,
                    "order": block.order,
                    "metadata": block.metadata,
                    "entity_mentions": block.entityMentions if hasattr(block, 'entityMentions') else None,
                    "created_at": block.createdAt
                }
                for block in blocks
            ]
        })

    return {
        "success": True,
        "conversation_id": conversation_id,
        "messages": messages_with_blocks,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Depends(get_current_user_id),
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

