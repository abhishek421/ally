"""OBJECT tools for custom object record CRUD operations."""

import logging
from typing import Optional

from langchain_core.tools import tool
from langgraph.errors import GraphInterrupt

from src.tools.context_var import get_tool_context
from src.tools.base import DataChange, EntityType, ChangeAction, LIST_MAX_RESULTS
from src.tools.confirmation import (
    request_bulk_create_confirmation,
    request_update_confirmation,
    request_delete_confirmation,
)

logger = logging.getLogger(__name__)


def get_object_tools() -> list:
    """Get all custom object CRUD tools."""

    @tool
    async def list_object_types() -> str:
        """List all custom object types defined in this workspace."""
        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg — backend resolves workspace from JWT via @WorkspaceId()
        query = """
        query GetObjectDefinitions {
            getObjectDefinitions {
                id name namePlural slug description icon isEnabled
            }
        }
        """

        try:
            result = await client.query(query, {})
            definitions = result.get("getObjectDefinitions") or []

            enabled = [d for d in definitions if d.get("isEnabled")]
            if not enabled:
                return "No custom object types found in this workspace."

            lines = [f"Found {len(enabled)} custom object type(s):"]
            for d in enabled:
                icon = d.get("icon", "")
                name = d.get("name", "")
                plural = d.get("namePlural", "")
                slug = d.get("slug", "")
                desc = d.get("description", "")
                line = f"- {icon} {name} (plural: {plural}, slug: {slug}, id: {d['id']})"
                if desc:
                    line += f"\n    {desc}"
                lines.append(line)

            return "\n".join(lines)

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error listing object types: {e}")
            return f"Error listing object types: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_object_records(
        object_definition_id: str,
        object_type_name: str,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> str:
        """List records for a custom object type. Use resolve_object_type first to get object_definition_id."""
        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg — backend resolves workspace from JWT.
        # getObjectRecordsByWorkspaceView supports search; getObjectRecords does not.
        query = """
        query GetObjectRecordsByWorkspaceView(
            $objectDefinitionId: String!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getObjectRecordsByWorkspaceView(
                objectDefinitionId: $objectDefinitionId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id displayName createdAt updatedAt
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        try:
            result = await client.query(query, {
                "objectDefinitionId": object_definition_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
            })

            data = result.get("getObjectRecordsByWorkspaceView", {})
            records = data.get("data") or []
            meta = data.get("meta") or {}

            if not records:
                return f"No {object_type_name} records found."

            total = meta.get("total", len(records))
            current_page = meta.get("page", 1)
            lines = [f"Found {total} {object_type_name} record(s) (page {current_page}):"]
            for r in records:
                lines.append(f"- {r.get('displayName', '(unnamed)')} (id: {r['id']})")

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} to continue)")

            return "\n".join(lines)

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error listing object records: {e}")
            return f"Error listing object records: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_object_records_in_group(
        group_id: str,
        object_type_name: str,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> str:
        """List custom object records in a specific group."""
        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg. GroupObjectRecordModel has no objectDefinitionId field.
        query = """
        query GetObjectRecordsByGroup(
            $groupId: String!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getObjectRecordsByGroup(
                groupId: $groupId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id displayName createdAt updatedAt
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        try:
            result = await client.query(query, {
                "groupId": group_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
            })

            data = result.get("getObjectRecordsByGroup", {})
            records = data.get("data") or []
            meta = data.get("meta") or {}

            if not records:
                return f"No {object_type_name} records found in this group."

            total = meta.get("total", len(records))
            current_page = meta.get("page", 1)
            lines = [f"Found {total} {object_type_name} record(s) in group (page {current_page}):"]
            for r in records:
                lines.append(f"- {r.get('displayName', '(unnamed)')} (id: {r['id']})")

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} to continue)")

            return "\n".join(lines)

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error listing object records in group: {e}")
            return f"Error listing object records in group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_object_record_by_id(
        object_record_id: str,
        object_type_name: str,
    ) -> str:
        """Get a single custom object record by ID, including all field values."""
        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg — backend resolves workspace from JWT.
        query = """
        query GetObjectRecord($id: String!) {
            getObjectRecord(id: $id) {
                id displayName objectDefinitionId recordData createdAt updatedAt
            }
        }
        """

        try:
            result = await client.query(query, {"id": object_record_id})

            record = result.get("getObjectRecord")
            if not record:
                return f"{object_type_name} record with ID '{object_record_id}' not found."

            lines = [
                f"**{record.get('displayName', '(unnamed)')}** (id: {record['id']})",
                f"  Type ID: {record.get('objectDefinitionId', '')}",
                f"  Created: {record.get('createdAt', '')}",
                f"  Updated: {record.get('updatedAt', '')}",
            ]

            record_data = record.get("recordData")
            if record_data:
                lines.append("  Fields:")
                if isinstance(record_data, dict):
                    for k, v in record_data.items():
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"    {record_data}")

            return "\n".join(lines)

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error getting object record: {e}")
            return f"Error getting object record: {str(e)}"
        finally:
            await client.close()

    @tool
    async def search_object_records(
        object_definition_id: str,
        object_type_name: str,
        query: str,
    ) -> str:
        """Search custom object records by display name within a type."""
        context = get_tool_context()
        client = context.get_client()

        gql_query = """
        query GetObjectRecordsByWorkspaceView(
            $objectDefinitionId: String!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getObjectRecordsByWorkspaceView(
                objectDefinitionId: $objectDefinitionId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id displayName createdAt updatedAt
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        try:
            result = await client.query(gql_query, {
                "objectDefinitionId": object_definition_id,
                "page": 1,
                "limit": LIST_MAX_RESULTS,
                "search": query,
            })

            data = result.get("getObjectRecordsByWorkspaceView", {})
            records = data.get("data") or []
            meta = data.get("meta") or {}

            if not records:
                return f"No {object_type_name} records found matching '{query}'."

            total = meta.get("total", len(records))
            lines = [f"Found {total} {object_type_name} record(s) matching '{query}':"]
            for r in records:
                lines.append(f"- {r.get('displayName', '(unnamed)')} (id: {r['id']})")

            return "\n".join(lines)

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error searching object records: {e}")
            return f"Error searching object records: {str(e)}"
        finally:
            await client.close()

    @tool
    async def create_object_record(
        object_definition_id: str,
        object_type_name: str,
        display_name: str,
        group_id: Optional[str] = None,
    ) -> str:
        """Create a new record of a custom object type. Shows confirmation before creating. Use resolve_object_type first."""
        draft_data = {
            "displayName": display_name,
            "_draft_id": "draft-0",
            "_object_type": object_type_name,
        }

        confirmation = request_bulk_create_confirmation(
            entities=[draft_data],
            entity_type="object",
            group_id=group_id,
        )

        if not confirmation.confirmed:
            return f"{object_type_name} record creation cancelled by user. [CANCELLED - stop here, do not retry or reattempt]"

        accepted_ids = confirmation.accepted_ids
        if accepted_ids is not None and "draft-0" not in accepted_ids:
            return f"{object_type_name} record creation cancelled by user. [CANCELLED - stop here, do not retry or reattempt]"

        final = {**draft_data}
        final.pop("_draft_id", None)
        final.pop("_object_type", None)
        if confirmation.edited_entities and "draft-0" in confirmation.edited_entities:
            final.update(confirmation.edited_entities["draft-0"])

        final_display_name = final.get("displayName", display_name)

        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg — backend injects it from JWT into input.workspaceId.
        # CreateObjectRecordInput accepts: objectDefinitionId, displayName, groupId, columnId, selectOptionId.
        # recordData is NOT an accepted field.
        mutation = """
        mutation CreateObjectRecord($input: CreateObjectRecordInput!) {
            createObjectRecord(input: $input) {
                id displayName objectDefinitionId recordData createdAt
            }
        }
        """

        input_data: dict = {
            "objectDefinitionId": object_definition_id,
            "displayName": final_display_name,
        }
        if group_id:
            input_data["groupId"] = group_id

        try:
            result = await client.mutate(mutation, {"input": input_data})

            record = result.get("createObjectRecord")
            if record:
                group_msg = " and added to group" if group_id else ""
                change = DataChange(
                    entity_type=EntityType.OBJECT,
                    action=ChangeAction.CREATED,
                    entity_id=record.get("id"),
                    group_id=group_id,
                    object_definition_id=object_definition_id,
                )
                return (
                    f"Successfully created {object_type_name} record{group_msg}: "
                    f"'{record.get('displayName')}' (id: {record['id']})"
                    + change.to_marker()
                )
            else:
                return f"Failed to create {object_type_name} record - no data returned."

        except GraphInterrupt:
            raise
        except Exception as e:
            errors = getattr(e, "errors", None)
            msg = str(errors) if errors else repr(e)
            logger.error(f"Error creating object record: {msg}")
            return f"Error creating {object_type_name} record: {msg}"
        finally:
            await client.close()

    @tool
    async def update_object_record(
        object_record_id: str,
        object_type_name: str,
        display_name_label: str,
        new_display_name: Optional[str] = None,
    ) -> str:
        """Update a custom object record's display name. Shows confirmation with old→new diff."""
        old_data = {"displayName": display_name_label}
        new_data = {}
        if new_display_name:
            new_data["displayName"] = new_display_name

        confirmation = request_update_confirmation(
            entity_type="object",
            entity_name=display_name_label,
            old_data=old_data,
            new_data=new_data,
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Update cancelled by user.{feedback} [CANCELLED - stop here, do not retry or reattempt]"

        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg — backend resolves from JWT.
        mutation = """
        mutation UpdateObjectRecord($id: String!, $input: UpdateObjectRecordInput!) {
            updateObjectRecord(id: $id, input: $input) {
                id displayName recordData updatedAt
            }
        }
        """

        input_data = {}
        if new_display_name:
            input_data["displayName"] = new_display_name

        try:
            result = await client.mutate(mutation, {
                "id": object_record_id,
                "input": input_data,
            })

            record = result.get("updateObjectRecord")
            if record:
                change = DataChange(
                    entity_type=EntityType.OBJECT,
                    action=ChangeAction.UPDATED,
                    entity_id=record.get("id"),
                )
                return (
                    f"Successfully updated {object_type_name} record: '{record.get('displayName')}'"
                    + change.to_marker()
                )
            else:
                return f"Failed to update {object_type_name} record - no data returned."

        except GraphInterrupt:
            raise
        except Exception as e:
            errors = getattr(e, "errors", None)
            msg = str(errors) if errors else repr(e)
            logger.error(f"Error updating object record: {msg}")
            return f"Error updating {object_type_name} record: {msg}"
        finally:
            await client.close()

    @tool
    async def add_object_record_to_group(
        object_record_id: str,
        group_id: str,
        object_type_name: str,
    ) -> str:
        """Add a custom object record to a group."""
        context = get_tool_context()
        client = context.get_client()

        # Args: groupId: String!, objectRecordId: String! — no workspaceId, no userId (both from JWT)
        mutation = """
        mutation AddObjectRecordToGroup($groupId: String!, $objectRecordId: String!) {
            addObjectRecordToGroup(groupId: $groupId objectRecordId: $objectRecordId)
        }
        """

        try:
            await client.mutate(mutation, {
                "groupId": group_id,
                "objectRecordId": object_record_id,
            })

            change = DataChange(
                entity_type=EntityType.OBJECT,
                action=ChangeAction.UPDATED,
                entity_id=object_record_id,
                group_id=group_id,
            )
            return f"Successfully added {object_type_name} record to group." + change.to_marker()

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error adding object record to group: {e}")
            return f"Error adding {object_type_name} record to group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_object_record_from_group(
        object_record_id: str,
        group_id: str,
        object_type_name: str,
    ) -> str:
        """Remove a custom object record from a group."""
        context = get_tool_context()
        client = context.get_client()

        # Args: groupId: String!, objectRecordId: String! — no workspaceId (from JWT)
        mutation = """
        mutation RemoveObjectRecordFromGroup($groupId: String!, $objectRecordId: String!) {
            removeObjectRecordFromGroup(groupId: $groupId objectRecordId: $objectRecordId)
        }
        """

        try:
            await client.mutate(mutation, {
                "groupId": group_id,
                "objectRecordId": object_record_id,
            })

            change = DataChange(
                entity_type=EntityType.OBJECT,
                action=ChangeAction.UPDATED,
                entity_id=object_record_id,
                group_id=group_id,
            )
            return f"Successfully removed {object_type_name} record from group." + change.to_marker()

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error removing object record from group: {e}")
            return f"Error removing {object_type_name} record from group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_object_record(
        object_record_id: str,
        object_type_name: str,
        display_name_label: str,
    ) -> str:
        """Delete a custom object record. Requires confirmation before proceeding."""
        confirmation = request_delete_confirmation(
            entity_type="object",
            entity_name=display_name_label,
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Deletion cancelled by user.{feedback} [CANCELLED - stop here, do not retry or reattempt]"

        context = get_tool_context()
        client = context.get_client()

        # No workspaceId arg — backend resolves from JWT.
        mutation = """
        mutation DeleteObjectRecord($id: String!) {
            deleteObjectRecord(id: $id) {
                id displayName
            }
        }
        """

        try:
            result = await client.mutate(mutation, {"id": object_record_id})

            record = result.get("deleteObjectRecord")
            if record:
                change = DataChange(
                    entity_type=EntityType.OBJECT,
                    action=ChangeAction.DELETED,
                    entity_id=record.get("id"),
                )
                return (
                    f"Successfully deleted {object_type_name} record '{display_name_label}'."
                    + change.to_marker()
                )
            else:
                return f"Failed to delete {object_type_name} record - no data returned."

        except GraphInterrupt:
            raise
        except Exception as e:
            errors = getattr(e, "errors", None)
            msg = str(errors) if errors else repr(e)
            logger.error(f"Error deleting object record: {msg}")
            return f"Error deleting {object_type_name} record: {msg}"
        finally:
            await client.close()

    return [
        list_object_types,
        list_object_records,
        list_object_records_in_group,
        get_object_record_by_id,
        search_object_records,
        create_object_record,
        update_object_record,
        add_object_record_to_group,
        remove_object_record_from_group,
        delete_object_record,
    ]
