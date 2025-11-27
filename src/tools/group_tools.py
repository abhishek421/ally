"""Group query tools for CRM."""

from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class GetWorkspaceGroupsTool(Tool):
    """Get all groups in a workspace."""

    @property
    def name(self) -> str:
        return "get_workspace_groups"

    @property
    def description(self) -> str:
        return (
            "Get all groups in a workspace. Groups can be of type PEOPLE, COMPANY, or DEAL. "
            "Returns group names, types, member counts, and other metadata."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "type": {
                    "type": "string",
                    "enum": ["PEOPLE", "COMPANY", "DEAL"],
                    "description": "Filter by group type (optional)",
                },
                "include_deleted": {
                    "type": "boolean",
                    "description": "Include deleted groups (default: false)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 100)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default: 0)",
                },
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        if not workspace_id:
            raise ValueError("workspace_id is required")

        logger.info(
            "Getting workspace groups",
            workspace_id=workspace_id,
            type=kwargs.get("type"),
        )

        data_access = get_data_access()
        return data_access.get_workspace_groups(
            workspace_id=workspace_id,
            type=kwargs.get("type"),
            include_deleted=kwargs.get("include_deleted", False),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
        )


class GetGroupByIdTool(Tool):
    """Get group details by ID."""

    @property
    def name(self) -> str:
        return "get_group_by_id"

    @property
    def description(self) -> str:
        return (
            "Get group details by ID with optional members. "
            "Returns group metadata and optionally the list of members (people or companies)."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group UUID (required)",
                },
                "include_members": {
                    "type": "boolean",
                    "description": "Include group members (default: false)",
                },
                "member_limit": {
                    "type": "integer",
                    "description": "Maximum number of members to include (default: 50)",
                },
            },
            "required": ["workspace_id", "group_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        group_id = kwargs.get("group_id")

        if not workspace_id or not group_id:
            raise ValueError("workspace_id and group_id are required")

        logger.info(
            "Getting group by ID",
            workspace_id=workspace_id,
            group_id=group_id,
        )

        data_access = get_data_access()
        return data_access.get_group_by_id(
            workspace_id=workspace_id,
            group_id=group_id,
            include_members=kwargs.get("include_members", False),
            member_limit=kwargs.get("member_limit"),
        )


class GetGroupMembersTool(Tool):
    """Get members of a group."""

    @property
    def name(self) -> str:
        return "get_group_members"

    @property
    def description(self) -> str:
        return (
            "Get all members of a group. For PEOPLE groups, returns people. "
            "For COMPANY groups, returns companies."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group UUID (required)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of members (default: 100)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default: 0)",
                },
            },
            "required": ["workspace_id", "group_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        group_id = kwargs.get("group_id")
        limit = kwargs.get("limit", 100)

        if not workspace_id or not group_id:
            raise ValueError("workspace_id and group_id are required")

        logger.info(
            "Getting group members",
            workspace_id=workspace_id,
            group_id=group_id,
        )

        data_access = get_data_access()
        result = data_access.get_group_by_id(
            workspace_id=workspace_id,
            group_id=group_id,
            include_members=True,
            member_limit=limit,
        )

        if result.get("error"):
            return result

        return {
            "group": result.get("group"),
            "members": result.get("members", []),
            "total": result.get("group", {}).get("memberCount", 0),
        }

