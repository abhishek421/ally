from typing import Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from prisma import Prisma
from prisma import Json
from database.prisma_client import prisma_client
import json


def _json_safe(obj: Any) -> Any:
    """Ensure value is JSON-serializable (convert datetimes and other types to strings)."""
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return None


async def ensure_conversation(workspace_id: str, user_id: str, conversation_id: Optional[str], title_hint: str) -> str:
    """Ensure a conversation exists; create a new one if no id provided."""
    if conversation_id:
        return conversation_id

    client: Prisma = await prisma_client.get_client()

    new_id = str(uuid4())
    title = (title_hint or "New chat")[:80]

    await client.conversation.create(
        data={
            "id": new_id,
            "workspaceId": workspace_id,
            "userId": user_id,
            "title": title,
            "updatedAt": datetime.utcnow(),
        }
    )

    return new_id


async def create_message(conversation_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Persist a message and (optionally) upsert its embedding to a vector store."""
    client: Prisma = await prisma_client.get_client()

    message_id = str(uuid4())

    # Use relation connect syntax (not conversationId directly)
    create_input: Dict[str, Any] = {
        "id": message_id,
        "content": content,
        "role": role.upper(),
        "timestamp": datetime.utcnow(),
        "conversation": {
            "connect": {
                "id": conversation_id
            }
        }
    }
    
    # Handle metadata: convert to Prisma Json type or omit entirely
    if metadata:
        safe_meta = _json_safe(metadata)
        if safe_meta:
            create_input["metadata"] = Json(safe_meta)

    await client.conversationmessage.create(data=create_input)

    # Update conversation.updatedAt to now
    try:
        await client.conversation.update(
            where={"id": conversation_id},
            data={"updatedAt": datetime.utcnow()},
        )
    except Exception:
        pass

    # Best-effort vector upsert
    try:
        from services.vector_store import upsert_message_embedding
        await upsert_message_embedding(
            message_id=message_id,
            conversation_id=conversation_id,
            workspace_id=(metadata or {}).get("workspace_id") if isinstance(metadata, dict) else None,
            user_id=(metadata or {}).get("user_id") if isinstance(metadata, dict) else None,
            role=role.upper(),
            content=content,
            created_at=datetime.utcnow().isoformat(),
        )
    except Exception:
        # Do not block core path on vector errors
        pass

    return message_id


