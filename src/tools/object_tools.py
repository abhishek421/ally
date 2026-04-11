"""Custom Object tools for querying and managing user-defined object types and records."""

import json
import logging
from typing import Optional

from langchain_core.tools import tool
from langgraph.errors import GraphInterrupt

from src.tools.context_var import get_tool_context
from src.tools.base import (
    LIST_MAX_RESULTS,
    DataChange,
    EntityType,
    ChangeAction,
    get_best_match,
)
from src.tools.confirmation import (
    request_bulk_create_confirmation,
    request_update_confirmation,
    request_delete_confirmation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_object_definition_compact(defn: dict) -> str:
    name = defn.get("name", "Unknown")
    slug = defn.get("slug", "")
    desc = defn.get("description", "")
    parts = [f"{name} (slug: {slug})"]
    if desc:
        parts.append(desc[:60] + "…" if len(desc) > 60 else desc)
    return "- " + " — ".join(parts)


def format_object_record(record: dict, definition_name: str = "") -> str:
    display_name = record.get("displayName", "Unknown")
    label = f"**{display_name}**"
    if definition_name:
        label += f" [{definition_name}]"
    label += f" (ID: {record.get('id', 'N/A')})"
    lines = [label]

    record_data = record.get("recordData") or {}
    if isinstance(record_data, str):
        try:
            record_data = json.loads(record_data)
        except Exception:
            record_data = {}

    if record_data:
        lines.append("  Fields:")
        for key, value in record_data.items():
            lines.append(f"    {key}: {value}")

    return "\n".join(lines)


def format_object_record_compact(record: dict) -> str:
    return f"- {record.get('displayName', 'Unknown')} (ID: {record.get('id', 'N/A')})"


# ---------------------------------------------------------------------------
# Tool getter
# ---------------------------------------------------------------------------

def get_object_tools() -> list:
    """Get all custom object tools (read + write)."""

    async def _resolve_definition_id(client, workspace_id: str, name_or_slug: str) -> tuple[str | None, str]:
        """Resolve object definition by name or slug. Returns (id, display_name) or (None, error)."""
        list_query = """
        query GetObjectDefinitions($workspaceId: ID) {
            getObjectDefinitions(workspaceId: $workspaceId) {
                id name slug description isEnabled
            }
        }
        """
        result = await client.query(list_query, {"workspaceId": workspace_id})
        definitions = result.get("getObjectDefinitions") or []

        if not definitions:
            return None, "No custom object types found in this workspace."

        for defn in definitions:
            if defn.get("slug", "").lower() == name_or_slug.lower():
                return defn["id"], defn["name"]

        match = get_best_match(name_or_slug, definitions, name_key="name", threshold=60.0)
        if match:
            return match["id"], match["name"]

        names = [d.get("name", "") for d in definitions]
        return None, f"Could not find a custom object type matching '{name_or_slug}'. Available: {', '.join(names)}"

    async def _find_record_by_name(client, workspace_id: str, definition_id: str, display_name: str) -> dict | None:
        """Find an object record by display name (fuzzy). Returns record dict or None."""
        query = """
        query GetObjectRecords($objectDefinitionId: String!, $workspaceId: ID, $page: Int, $limit: Int) {
            getObjectRecords(objectDefinitionId: $objectDefinitionId, workspaceId: $workspaceId, page: $page, limit: $limit) {
                data { id displayName recordData createdAt updatedAt }
                meta { total hasNextPage }
            }
        }
        """
        result = await client.query(query, {
            "objectDefinitionId": definition_id,
            "workspaceId": workspace_id,
            "page": 1,
            "limit": 100,
        })
        records = (result.get("getObjectRecords") or {}).get("data") or []
        if not records:
            return None
        return get_best_match(display_name, records, name_key="displayName", threshold=60.0)

    # -----------------------------------------------------------------------
    # READ TOOLS
    # -----------------------------------------------------------------------

    @tool
    async def list_object_definitions() -> str:
        """List all custom object types defined in this workspace."""
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetObjectDefinitions($workspaceId: ID) {
            getObjectDefinitions(workspaceId: $workspaceId) {
                id name slug namePlural description icon color isEnabled sortOrder
            }
        }
        """
        try:
            result = await client.query(query, {"workspaceId": context.workspace_id})
            definitions = result.get("getObjectDefinitions") or []

            if not definitions:
                return "No custom object types found in this workspace."

            enabled = [d for d in definitions if d.get("isEnabled")]
            disabled = [d for d in definitions if not d.get("isEnabled")]

            lines = [f"**Custom Object Types** ({len(definitions)} total)\n"]
            if enabled:
                lines.append("Enabled:")
                for d in sorted(enabled, key=lambda x: x.get("sortOrder", 0)):
                    lines.append(format_object_definition_compact(d))
            if disabled:
                lines.append("\nDisabled:")
                for d in disabled:
                    lines.append(format_object_definition_compact(d))

            return "\n".join(lines)
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"list_object_definitions error: {e}")
            return f"Error fetching custom object types: {e}"

    @tool
    async def list_object_records(
        object_type: str,
        page: int = 1,
        limit: int = 20,
    ) -> str:
        """List records for a custom object type. object_type can be the name or slug (e.g. 'Project', 'projects')."""
        context = get_tool_context()
        client = context.get_client()

        try:
            def_id, def_name = await _resolve_definition_id(client, context.workspace_id, object_type)
            if not def_id:
                return def_name

            query = """
            query GetObjectRecords(
                $objectDefinitionId: String!
                $workspaceId: ID
                $page: Int
                $limit: Int
                $orderBy: String
                $orderDirection: String
            ) {
                getObjectRecords(
                    objectDefinitionId: $objectDefinitionId
                    workspaceId: $workspaceId
                    page: $page
                    limit: $limit
                    orderBy: $orderBy
                    orderDirection: $orderDirection
                ) {
                    data { id displayName recordData createdAt }
                    meta { total page limit hasNextPage }
                }
            }
            """
            result = await client.query(query, {
                "objectDefinitionId": def_id,
                "workspaceId": context.workspace_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "orderBy": "createdAt",
                "orderDirection": "desc",
            })
            data = result.get("getObjectRecords") or {}
            records = data.get("data") or []
            meta = data.get("meta") or {}

            if not records:
                return f"No records found for '{def_name}'."

            total = meta.get("total", len(records))
            has_next = meta.get("hasNextPage", False)
            lines = [f"**{def_name} Records** ({total} total, page {page})\n"]
            for rec in records:
                lines.append(format_object_record_compact(rec))

            if has_next:
                lines.append(f"\n_(More records available — use page={page + 1} to see next page)_")

            return "\n".join(lines)
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"list_object_records error: {e}")
            return f"Error fetching records: {e}"

    @tool
    async def get_object_record(
        object_type: str,
        record_name: str,
    ) -> str:
        """Get full details of a custom object record by name. object_type is the type name/slug, record_name is the display name."""
        context = get_tool_context()
        client = context.get_client()

        try:
            def_id, def_name = await _resolve_definition_id(client, context.workspace_id, object_type)
            if not def_id:
                return def_name

            record = await _find_record_by_name(client, context.workspace_id, def_id, record_name)
            if not record:
                return f"No record matching '{record_name}' found in '{def_name}'."

            return format_object_record(record, def_name)
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"get_object_record error: {e}")
            return f"Error fetching record: {e}"

    # -----------------------------------------------------------------------
    # WRITE TOOLS
    # -----------------------------------------------------------------------

    @tool
    async def create_object_definition(
        name: str,
        name_plural: str,
        slug: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> str:
        """Create a new custom object type in the workspace.

        Args:
            name: Singular name (e.g. 'Project')
            name_plural: Plural name (e.g. 'Projects')
            slug: Unique kebab-case identifier (e.g. 'projects'). Lowercase letters, numbers, hyphens only.
            description: Optional description
            icon: Optional icon identifier
            color: Optional color (hex or name)
        """
        context = get_tool_context()
        client = context.get_client()

        draft = {"name": name, "namePlural": name_plural, "slug": slug, "_draft_id": "draft-0"}
        if description:
            draft["description"] = description

        try:
            confirmation = request_bulk_create_confirmation(
                entities=[draft],
                entity_type="object_definition",
            )

            if not confirmation.confirmed:
                return "Object type creation cancelled. [CANCELLED - stop here, do not retry]"

            accepted = confirmation.accepted_ids
            if accepted is not None and "draft-0" not in accepted:
                return "Object type creation cancelled. [CANCELLED - stop here, do not retry]"

            mutation = """
            mutation CreateObjectDefinition($input: CreateObjectDefinitionInput!) {
                createObjectDefinition(input: $input) {
                    id name slug namePlural description isEnabled createdAt
                }
            }
            """
            input_data: dict = {
                "workspaceId": context.workspace_id,
                "name": name,
                "namePlural": name_plural,
                "slug": slug,
            }
            if description:
                input_data["description"] = description
            if icon:
                input_data["icon"] = icon
            if color:
                input_data["color"] = color

            result = await client.mutate(mutation, {"input": input_data})
            defn = result.get("createObjectDefinition") or {}
            return (
                f"Created custom object type **{defn.get('name')}** "
                f"(slug: `{defn.get('slug')}`, ID: {defn.get('id')})"
            )
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"create_object_definition error: {e}")
            return f"Error creating object type: {e}"

    @tool
    async def create_object_record(
        object_type: str,
        display_name: str,
        fields: Optional[str] = None,
    ) -> str:
        """Create a new record for a custom object type.

        Args:
            object_type: Name or slug of the object type (e.g. 'Project', 'projects')
            display_name: The display name for this record (e.g. 'Q2 Launch')
            fields: Optional JSON string with field values (e.g. '{"status": "active", "budget": "50000"}')
        """
        context = get_tool_context()
        client = context.get_client()

        draft = {"displayName": display_name, "objectType": object_type, "_draft_id": "draft-0"}
        if fields:
            draft["fields"] = fields

        try:
            confirmation = request_bulk_create_confirmation(
                entities=[draft],
                entity_type="object_record",
            )

            if not confirmation.confirmed:
                return "Record creation cancelled. [CANCELLED - stop here, do not retry]"

            accepted = confirmation.accepted_ids
            if accepted is not None and "draft-0" not in accepted:
                return "Record creation cancelled. [CANCELLED - stop here, do not retry]"

            def_id, def_name = await _resolve_definition_id(client, context.workspace_id, object_type)
            if not def_id:
                return def_name

            record_data = None
            if fields:
                try:
                    record_data = json.loads(fields)
                except json.JSONDecodeError:
                    return f"Invalid JSON in fields parameter: {fields}"

            mutation = """
            mutation CreateObjectRecord($input: CreateObjectRecordInput!) {
                createObjectRecord(input: $input) {
                    id displayName recordData objectDefinitionId createdAt
                }
            }
            """
            input_data: dict = {
                "workspaceId": context.workspace_id,
                "objectDefinitionId": def_id,
                "displayName": display_name,
            }
            if record_data:
                input_data["recordData"] = record_data

            result = await client.mutate(mutation, {"input": input_data})
            record = result.get("createObjectRecord") or {}
            return (
                f"Created **{record.get('displayName')}** record in '{def_name}' "
                f"(ID: {record.get('id')})"
            )
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"create_object_record error: {e}")
            return f"Error creating record: {e}"

    @tool
    async def update_object_record(
        object_type: str,
        record_name: str,
        new_display_name: Optional[str] = None,
        fields: Optional[str] = None,
    ) -> str:
        """Update a custom object record by name.

        Args:
            object_type: Name or slug of the object type
            record_name: Display name of the record to update
            new_display_name: New display name (optional)
            fields: JSON string with updated field values (optional, e.g. '{"status": "completed"}')
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            def_id, def_name = await _resolve_definition_id(client, context.workspace_id, object_type)
            if not def_id:
                return def_name

            record = await _find_record_by_name(client, context.workspace_id, def_id, record_name)
            if not record:
                return f"No record matching '{record_name}' found in '{def_name}'."

            record_id = record["id"]
            current_name = record.get("displayName", record_name)

            # Build preview for confirmation
            changes: dict = {}
            if new_display_name:
                changes["displayName"] = new_display_name
            if fields:
                try:
                    changes["fields"] = json.loads(fields)
                except json.JSONDecodeError:
                    return f"Invalid JSON in fields parameter: {fields}"

            if not changes:
                return "Nothing to update — provide new_display_name and/or fields."

            confirmation = request_update_confirmation(
                entity_name=current_name,
                entity_type="object_record",
                changes=changes,
            )

            if not confirmation.confirmed:
                return f"Update of '{current_name}' cancelled. [CANCELLED - stop here, do not retry]"

            input_data: dict = {}
            if new_display_name:
                input_data["displayName"] = new_display_name
            if fields:
                input_data["recordData"] = json.loads(fields)

            mutation = """
            mutation UpdateObjectRecord($id: String!, $workspaceId: ID!, $input: UpdateObjectRecordInput!) {
                updateObjectRecord(id: $id, workspaceId: $workspaceId, input: $input) {
                    id displayName recordData updatedAt
                }
            }
            """
            result = await client.mutate(mutation, {
                "id": record_id,
                "workspaceId": context.workspace_id,
                "input": input_data,
            })
            updated = result.get("updateObjectRecord") or {}
            final_name = updated.get("displayName", new_display_name or current_name)
            return f"Updated '{current_name}' → **{final_name}** in '{def_name}' (ID: {record_id})"
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"update_object_record error: {e}")
            return f"Error updating record: {e}"

    @tool
    async def delete_object_record(
        object_type: str,
        record_name: str,
    ) -> str:
        """Delete a custom object record by name.

        Args:
            object_type: Name or slug of the object type
            record_name: Display name of the record to delete
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            def_id, def_name = await _resolve_definition_id(client, context.workspace_id, object_type)
            if not def_id:
                return def_name

            record = await _find_record_by_name(client, context.workspace_id, def_id, record_name)
            if not record:
                return f"No record matching '{record_name}' found in '{def_name}'."

            record_id = record["id"]
            current_name = record.get("displayName", record_name)

            confirmation = request_delete_confirmation(
                entity_name=current_name,
                entity_type="object_record",
            )

            if not confirmation.confirmed:
                return f"Deletion of '{current_name}' cancelled. [CANCELLED - stop here, do not retry]"

            mutation = """
            mutation DeleteObjectRecord($id: String!, $workspaceId: ID) {
                deleteObjectRecord(id: $id, workspaceId: $workspaceId) {
                    id displayName
                }
            }
            """
            await client.mutate(mutation, {
                "id": record_id,
                "workspaceId": context.workspace_id,
            })
            return f"Deleted record **{current_name}** from '{def_name}' (ID: {record_id})"
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"delete_object_record error: {e}")
            return f"Error deleting record: {e}"

    return [
        list_object_definitions,
        list_object_records,
        get_object_record,
        create_object_definition,
        create_object_record,
        update_object_record,
        delete_object_record,
    ]
