"""Object Memory tools for saving and retrieving long-term entity memories."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.base import ToolContext

logger = logging.getLogger(__name__)


def format_memory(memory: dict) -> str:
    """Format a memory dict for display.

    Args:
        memory: Memory data from GraphQL

    Returns:
        Formatted string representation
    """
    memory_id = memory.get("id", "N/A")
    text = memory.get("memoryText", "")
    category = memory.get("category", "CONTEXT")
    entity_type = memory.get("entityType", "Unknown")
    created_at = memory.get("createdAt", "Unknown")

    lines = [f"- [{category}] {text}"]
    lines.append(f"  (ID: {memory_id} | Type: {entity_type} | Created: {created_at})")

    return "\n".join(lines)


def get_memory_tools(context: ToolContext) -> list:
    """Get all Object Memory tools configured with the given context.

    Args:
        context: Tool context with auth and workspace info

    Returns:
        List of tool functions
    """

    @tool
    async def save_object_memory(
        entity_id: str,
        entity_type: str,
        memory_text: str,
        category: str = "CONTEXT",
        object_definition_id: Optional[str] = None,
    ) -> str:
        """Save a long-term memory about a CRM entity (person, company, or custom object).

        Use this to remember preferences, behavioral notes, context facts, and interaction
        patterns about entities across conversations. No confirmation needed — this is
        low-stakes and reversible.

        IMPORTANT: Before saving, always call get_object_memories first to check for
        duplicates or conflicting memories.

        Args:
            entity_id: The UUID of the entity (person, company, or object record)
            entity_type: Type of entity — "PERSON", "COMPANY", or "OBJECT"
            memory_text: The fact, preference, or note to remember (keep concise)
            category: Category — "PREFERENCE", "CONTEXT", "INTERACTION", or "BEHAVIORAL". Default: "CONTEXT"
            object_definition_id: Required only for OBJECT entity type — the object definition UUID

        Returns:
            Success message with the saved memory, or error message
        """
        entity_type_upper = entity_type.upper()
        if entity_type_upper not in ("PERSON", "COMPANY", "OBJECT"):
            return f"Invalid entity type '{entity_type}'. Must be 'PERSON', 'COMPANY', or 'OBJECT'."

        category_upper = category.upper()
        if category_upper not in ("PREFERENCE", "CONTEXT", "INTERACTION", "BEHAVIORAL"):
            return f"Invalid category '{category}'. Must be 'PREFERENCE', 'CONTEXT', 'INTERACTION', or 'BEHAVIORAL'."

        if entity_type_upper == "OBJECT" and not object_definition_id:
            return "object_definition_id is required when entity_type is 'OBJECT'."

        client = context.get_client()

        try:
            mutation = """
            mutation CreateObjectMemory($input: CreateObjectMemoryInput!, $workspaceId: String!) {
                createObjectMemory(input: $input, workspaceId: $workspaceId) {
                    id
                    memoryText
                    category
                    entityType
                    entityId
                    isActive
                    createdAt
                }
            }
            """

            input_data = {
                "entityId": entity_id,
                "entityType": entity_type_upper,
                "memoryText": memory_text,
                "category": category_upper,
            }

            if object_definition_id:
                input_data["objectDefinitionId"] = object_definition_id

            result = await client.mutate(mutation, {
                "input": input_data,
                "workspaceId": context.workspace_id,
            })

            memory = result.get("createObjectMemory")

            if memory:
                return f"Memory saved: [{category_upper}] {memory_text}"
            else:
                return "Failed to save memory — no data returned."

        except Exception as e:
            error_msg = str(e)
            if "Memory limit reached" in error_msg:
                return f"Cannot save memory: limit of 50 memories per entity reached. Please delete an old memory first."
            logger.error(f"Error saving object memory: {e}")
            return f"Error saving memory: {error_msg}"
        finally:
            await client.close()

    @tool
    async def get_object_memories(
        entity_id: str,
        entity_type: str,
    ) -> str:
        """Retrieve all saved memories for a CRM entity.

        Call this BEFORE acting on an entity (drafting emails, making recommendations,
        saving new memories) to recall saved preferences, context, and behavioral notes.

        Args:
            entity_id: The UUID of the entity (person, company, or object record)
            entity_type: Type of entity — "PERSON", "COMPANY", or "OBJECT"

        Returns:
            Formatted list of memories, or "No memories found"
        """
        entity_type_upper = entity_type.upper()
        if entity_type_upper not in ("PERSON", "COMPANY", "OBJECT"):
            return f"Invalid entity type '{entity_type}'. Must be 'PERSON', 'COMPANY', or 'OBJECT'."

        client = context.get_client()

        try:
            query = """
            query GetObjectMemories($entityId: String!, $workspaceId: String!) {
                objectMemories(entityId: $entityId, workspaceId: $workspaceId) {
                    id
                    memoryText
                    category
                    entityType
                    entityId
                    isActive
                    createdAt
                }
            }
            """

            result = await client.query(query, {
                "entityId": entity_id,
                "workspaceId": context.workspace_id,
            })

            memories = result.get("objectMemories", [])

            if not memories:
                return "No memories found for this entity."

            lines = [f"Found {len(memories)} memory/memories:\n"]
            for memory in memories:
                lines.append(format_memory(memory))

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error retrieving object memories: {e}")
            return f"Error retrieving memories: {str(e)}"
        finally:
            await client.close()

    return [
        save_object_memory,
        get_object_memories,
    ]
