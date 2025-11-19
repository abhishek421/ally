from typing import Optional
from uuid import uuid4
from datetime import datetime
import logging
import time
from prisma import Prisma
from src.infrastructure.database.prisma_client import prisma_client
from src.application.services.conversation.title_generator import get_title_generator

logger = logging.getLogger(__name__)


async def ensure_conversation(workspace_id: str, user_id: str, conversation_id: Optional[str], title_hint: str) -> str:
    """Ensure a conversation exists; create a new one if no id provided."""
    if conversation_id:
        return conversation_id

    client: Prisma = await prisma_client.get_client()

    # Validate that the user exists before creating conversation
    user = await client.user.find_unique(where={"id": user_id})
    if not user:
        raise ValueError(f"User with id {user_id} does not exist")

    # Validate that the workspace exists
    workspace = await client.workspace.find_unique(where={"id": workspace_id})
    if not workspace:
        raise ValueError(f"Workspace with id {workspace_id} does not exist")

    new_id = str(uuid4())

    # Generate AI-powered title using Gemini Flash
    try:
        perf_title_start = time.time()
        title_generator = get_title_generator()
        title = await title_generator.generate_title(title_hint or "New conversation", max_length=60)
        perf_title_end = time.time()
        logger.info(f"[PERF] Title generation took {(perf_title_end - perf_title_start)*1000:.0f}ms - Generated: '{title}'")
    except Exception as e:
        logger.error(f"Title generation failed: {e}, using fallback")
        title = (title_hint or "New chat")[:60]

    perf_db_start = time.time()
    await client.conversation.create(
        data={
            "id": new_id,
            "workspaceId": workspace_id,
            "userId": user_id,
            "title": title,
            "updatedAt": datetime.utcnow(),
        }
    )
    perf_db_end = time.time()
    logger.info(f"[PERF] Conversation DB insert took {(perf_db_end - perf_db_start)*1000:.0f}ms")

    return new_id


async def get_message_count(conversation_id: str) -> int:
    """Get the total number of messages in a conversation"""
    client: Prisma = await prisma_client.get_client()

    count = await client.conversationmessage.count(
        where={"conversationId": conversation_id}
    )

    return count


