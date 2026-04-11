"""Object Memory tools for saving and retrieving long-term entity memories."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.base import ToolContext
from src.tools.context_var import get_tool_context

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


def get_memory_tools() -> list:
    """Get all Object Memory tools.

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
        """Save a preference, fact, or behavioral note about an entity for future reference. Check get_object_memories first to avoid duplicates."""
        entity_type_upper = entity_type.upper()
        if entity_type_upper not in ("PERSON", "COMPANY", "OBJECT"):
            return f"Invalid entity type '{entity_type}'. Must be 'PERSON', 'COMPANY', or 'OBJECT'."

        category_upper = category.upper()
        if category_upper not in ("PREFERENCE", "CONTEXT", "INTERACTION", "BEHAVIORAL"):
            return f"Invalid category '{category}'. Must be 'PREFERENCE', 'CONTEXT', 'INTERACTION', or 'BEHAVIORAL'."

        if entity_type_upper == "OBJECT" and not object_definition_id:
            return "object_definition_id is required when entity_type is 'OBJECT'."

        context = get_tool_context()
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
        """Recall saved memories about an entity (preferences, context, past interactions). Call before acting on any entity."""
        entity_type_upper = entity_type.upper()
        if entity_type_upper not in ("PERSON", "COMPANY", "OBJECT"):
            return f"Invalid entity type '{entity_type}'. Must be 'PERSON', 'COMPANY', or 'OBJECT'."

        context = get_tool_context()
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

    @tool
    async def update_object_memory(
        memory_id: str,
        new_text: str,
        category: Optional[str] = None,
    ) -> str:
        """Update an existing memory's text or category.

        Call get_object_memories first to find the correct memory_id.

        Args:
            memory_id: ID of the memory to update (from get_object_memories).
            new_text: Replacement memory text.
            category: Optional new category — "PREFERENCE", "CONTEXT", "INTERACTION", or "BEHAVIORAL".
        """
        if category is not None:
            category_upper = category.upper()
            if category_upper not in ("PREFERENCE", "CONTEXT", "INTERACTION", "BEHAVIORAL"):
                return f"Invalid category '{category}'. Must be 'PREFERENCE', 'CONTEXT', 'INTERACTION', or 'BEHAVIORAL'."
        else:
            category_upper = None

        context = get_tool_context()
        client = context.get_client()

        try:
            mutation = """
            mutation UpdateObjectMemory($id: String!, $input: UpdateObjectMemoryInput!, $workspaceId: String!) {
                updateObjectMemory(id: $id, input: $input, workspaceId: $workspaceId) {
                    id
                    memoryText
                    category
                    entityType
                    entityId
                    updatedAt
                }
            }
            """
            input_data: dict = {"memoryText": new_text}
            if category_upper:
                input_data["category"] = category_upper

            result = await client.mutate(mutation, {
                "id": memory_id,
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            updated = result.get("updateObjectMemory")
            if not updated:
                return "Failed to update memory — no data returned."
            return f"Memory updated: [{updated.get('category')}] {updated.get('memoryText')}"
        except Exception as e:
            logger.error(f"Error updating object memory: {e}")
            return f"Error updating memory: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_object_memory(memory_id: str) -> str:
        """Delete a saved memory by ID.

        Call get_object_memories first to confirm the correct memory_id before deleting.

        Args:
            memory_id: ID of the memory to delete (from get_object_memories).
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            mutation = """
            mutation DeleteObjectMemory($id: String!, $workspaceId: String!) {
                deleteObjectMemory(id: $id, workspaceId: $workspaceId)
            }
            """
            await client.mutate(mutation, {
                "id": memory_id,
                "workspaceId": context.workspace_id,
            })
            return f"Memory {memory_id} deleted."
        except Exception as e:
            logger.error(f"Error deleting object memory: {e}")
            return f"Error deleting memory: {str(e)}"
        finally:
            await client.close()

    return [
        save_object_memory,
        get_object_memories,
        update_object_memory,
        delete_object_memory,
    ]
