"""
Block Manager - Handles saving and retrieving message blocks
"""
from typing import List, Dict, Any
from uuid import uuid4
from datetime import datetime
from prisma.fields import Json
from src.infrastructure.database.prisma_client import prisma_client
from src.application.services.blocks.models import Block, BlockType
import logging

logger = logging.getLogger(__name__)


async def save_message_with_blocks(
    conversation_id: str,
    message_id: str,
    role: str,
    blocks: List[Block]
) -> str:
    """
    Save a message with its blocks to the database

    Args:
        conversation_id: Conversation ID
        message_id: Message ID
        role: Message role (USER, ASSISTANT)
        blocks: List of Block objects to save

    Returns:
        message_id
    """
    client = await prisma_client.get_client()

    try:
        # Create message (no content field - all data is in blocks)
        await client.conversationmessage.create(
            data={
                "id": message_id,
                "conversationId": conversation_id,
                "role": role.upper(),
                "timestamp": datetime.utcnow()
            }
        )

        # Create all blocks
        for idx, block in enumerate(blocks):
            # Validate content - it's required and cannot be None
            if block.content is None:
                raise ValueError(f"Block {block.block_id} has None content, which is not allowed")

            # Build block data with proper types
            # Use messageId directly (required field in schema)
            create_data = {
                "id": block.block_id,
                "messageId": message_id,
                "blockType": block.block_type.value,
                "content": str(block.content),
                "order": block.order,
                "createdAt": datetime.utcnow()
            }

            # Only add metadata if it's not None and is a valid NON-EMPTY dict
            # Prisma JSON fields need to be wrapped with Json() type
            # We should NOT include the field at all if it's None or empty
            if block.metadata is not None:
                if isinstance(block.metadata, dict) and block.metadata:  # Only add if non-empty dict
                    # Wrap with Json() type for Prisma Python client
                    create_data["metadata"] = Json(block.metadata)
                elif not isinstance(block.metadata, dict):
                    logger.warning(f"Block {block.block_id} - Invalid metadata type: {type(block.metadata)}, skipping")

            # Add entity mentions if present and valid NON-EMPTY list
            # Prisma JSON fields need to be wrapped with Json() type
            # We should NOT include the field at all if it's None or empty
            if block.entity_mentions is not None:
                if isinstance(block.entity_mentions, list) and block.entity_mentions:  # Only add if non-empty list
                    # Wrap with Json() type for Prisma Python client
                    create_data["entityMentions"] = Json(block.entity_mentions)
                elif not isinstance(block.entity_mentions, list):
                    logger.warning(f"Block {block.block_id} - Invalid entity_mentions type: {type(block.entity_mentions)}, skipping")

            try:
                await client.messageblock.create(data=create_data)
            except Exception as block_error:
                logger.error(
                    f"Failed to create block {block.block_id}: {block_error}. "
                    f"Block data keys: {list(create_data.keys())}"
                )
                raise

        # Update conversation timestamp
        await client.conversation.update(
            where={"id": conversation_id},
            data={"updatedAt": datetime.utcnow()}
        )

        logger.info(f"Saved message {message_id} with {len(blocks)} blocks")
        return message_id

    except Exception as e:
        logger.error(f"Failed to save message with blocks: {e}")
        raise


async def get_message_blocks(message_id: str) -> List[Block]:
    """
    Retrieve all blocks for a message, ordered by 'order' field

    Args:
        message_id: Message ID

    Returns:
        List of Block objects
    """
    client = await prisma_client.get_client()

    try:
        blocks = await client.messageblock.find_many(
            where={"messageId": message_id},
            order={"order": "asc"}
        )

        return [
            Block(
                block_id=block.id,
                block_type=BlockType(block.blockType),
                content=block.content,
                order=block.order,
                metadata=block.metadata if block.metadata else None,
                entity_mentions=block.entityMentions if hasattr(block, 'entityMentions') and block.entityMentions else None
            )
            for block in blocks
        ]

    except Exception as e:
        logger.error(f"Failed to retrieve blocks for message {message_id}: {e}")
        return []


def csv_from_table_data(data: List[Dict[str, Any]]) -> str:
    """
    Convert table data to CSV format

    Args:
        data: List of dictionaries representing table rows

    Returns:
        CSV string
    """
    if not data:
        return ""

    import csv
    import io

    output = io.StringIO()

    # Get headers from first row
    headers = list(data[0].keys())

    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(data)

    return output.getvalue()
