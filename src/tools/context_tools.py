"""Context tools for fetching entity-specific instructions."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.base import ToolContext

logger = logging.getLogger(__name__)


def get_context_tools(context: ToolContext) -> list:
    """Get context tools configured with the given context.

    Args:
        context: Tool context with auth and workspace info

    Returns:
        List of tool functions
    """

    @tool
    async def get_entity_instructions(
        entity_type: str,
        object_definition_name: Optional[str] = None,
    ) -> str:
        """Get custom instructions that the workspace admin has set for a specific entity type.

        Use this tool when you need guidance on how to handle a specific type of entity
        (e.g., how to draft emails to people, how to describe companies, or how to work
        with custom object types). This provides workspace-specific context for each entity type.

        Args:
            entity_type: The type of entity - one of "PERSON", "COMPANY", or "OBJECT"
            object_definition_name: For custom objects (OBJECT type), the name of the
                object definition (e.g., "Products", "Invoices"). Not needed for PERSON/COMPANY.

        Returns:
            The custom instructions text, or a message indicating no instructions are set.
        """
        client = context.get_client()

        # If it's a custom object, we need to resolve the object definition ID first
        object_definition_id = None
        if entity_type == "OBJECT" and object_definition_name:
            resolve_query = """
            query GetObjectDefinitions($workspaceId: ID!) {
                getObjectDefinitions(workspaceId: $workspaceId) {
                    id
                    name
                    slug
                }
            }
            """
            try:
                result = await client.query(resolve_query, {
                    "workspaceId": context.workspace_id,
                })
                definitions = result.get("getObjectDefinitions", [])
                search_lower = object_definition_name.lower()
                for defn in definitions:
                    if defn["name"].lower() == search_lower or defn["slug"].lower() == search_lower:
                        object_definition_id = defn["id"]
                        break
                if not object_definition_id:
                    return f"No custom object type found matching '{object_definition_name}'."
            except Exception as e:
                logger.warning(f"Failed to resolve object definition: {e}")
                return f"Error resolving object definition: {e}"

        query = """
        query GetEntityCustomInstructions(
            $workspaceId: ID!
            $entityType: EntityType!
            $objectDefinitionId: ID
        ) {
            getEntityCustomInstructions(
                workspaceId: $workspaceId
                entityType: $entityType
                objectDefinitionId: $objectDefinitionId
            ) {
                instructions
                entityType
            }
        }
        """

        try:
            variables = {
                "workspaceId": context.workspace_id,
                "entityType": entity_type,
            }
            if object_definition_id:
                variables["objectDefinitionId"] = object_definition_id

            result = await client.query(query, variables)
            data = result.get("getEntityCustomInstructions")

            if data and data.get("instructions"):
                instructions = data["instructions"]
                entity_label = entity_type.lower()
                if entity_type == "OBJECT" and object_definition_name:
                    entity_label = object_definition_name
                logger.info(f"📋 Fetched {entity_label} instructions ({len(instructions)} chars)")
                return f"Custom instructions for {entity_label}:\n{instructions}"
            else:
                return f"No custom instructions set for {entity_type} entities."

        except Exception as e:
            logger.warning(f"Failed to fetch entity instructions: {e}")
            return f"Could not fetch entity instructions: {e}"
        finally:
            await client.close()

    return [get_entity_instructions]
