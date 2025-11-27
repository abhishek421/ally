"""Deal query tools for CRM."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class SearchDealsTool(Tool):
    """Search for deals by name, stage, value, or other criteria."""

    @property
    def name(self) -> str:
        return "search_deals"

    @property
    def description(self) -> str:
        return "Search for deals by name, stage, value, or other criteria. Returns paginated results with summary."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "query": {"type": "string", "description": "Search term for deal name"},
                "column_id": {"type": "string", "description": "Filter by stage/column UUID"},
                "column_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by multiple stages",
                },
                "group_id": {"type": "string", "description": "Filter by group UUID"},
                "company_id": {"type": "string", "description": "Filter by company UUID"},
                "person_id": {"type": "string", "description": "Filter by person UUID"},
                "min_value": {"type": "number", "description": "Minimum deal value"},
                "max_value": {"type": "number", "description": "Maximum deal value"},
                "created_after": {"type": "string", "description": "Filter by creation date after (ISO format)"},
                "created_before": {"type": "string", "description": "Filter by creation date before (ISO format)"},
                "sort_by": {
                    "type": "string",
                    "enum": ["createdAt", "updatedAt", "value", "name"],
                    "description": "Field to sort by",
                },
                "sort_order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order"},
                "limit": {"type": "integer", "description": "Maximum number of results (default: 20, max: 100)"},
                "offset": {"type": "integer", "description": "Offset for pagination (default: 0)"},
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        if not workspace_id:
            raise ValueError("workspace_id is required")

        logger.info("Searching deals", workspace_id=workspace_id, query=kwargs.get("query"))

        # Parse dates if provided
        created_after = None
        created_before = None
        if kwargs.get("created_after"):
            created_after = datetime.fromisoformat(kwargs["created_after"].replace("Z", "+00:00"))
        if kwargs.get("created_before"):
            created_before = datetime.fromisoformat(kwargs["created_before"].replace("Z", "+00:00"))

        data_access = get_data_access()
        return data_access.search_deals(
            workspace_id=workspace_id,
            query=kwargs.get("query"),
            column_id=kwargs.get("column_id"),
            column_ids=kwargs.get("column_ids"),
            group_id=kwargs.get("group_id"),
            company_id=kwargs.get("company_id"),
            person_id=kwargs.get("person_id"),
            min_value=kwargs.get("min_value"),
            max_value=kwargs.get("max_value"),
            created_after=created_after,
            created_before=created_before,
            sort_by=kwargs.get("sort_by"),
            sort_order=kwargs.get("sort_order"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
        )


class GetDealByIdTool(Tool):
    """Get complete deal information with related data."""

    @property
    def name(self) -> str:
        return "get_deal_by_id"

    @property
    def description(self) -> str:
        return (
            "Get complete deal information with related data including people, companies, "
            "interactions, column values, stage history, and notes."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "deal_id": {"type": "string", "description": "Deal UUID (required)"},
                "include": {
                    "type": "object",
                    "properties": {
                        "people": {"type": "boolean", "description": "Include people"},
                        "companies": {"type": "boolean", "description": "Include companies"},
                        "interactions": {
                            "type": "integer",
                            "description": "Number of interactions to include",
                        },
                        "column_values": {"type": "boolean", "description": "Include column values"},
                        "stage_history": {"type": "boolean", "description": "Include stage transition history"},
                        "notes": {"type": "boolean", "description": "Include notes"},
                    },
                    "description": "Optional data to include",
                },
            },
            "required": ["workspace_id", "deal_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        deal_id = kwargs.get("deal_id")
        include = kwargs.get("include")

        if not workspace_id or not deal_id:
            raise ValueError("workspace_id and deal_id are required")

        logger.info("Getting deal by ID", workspace_id=workspace_id, deal_id=deal_id)

        data_access = get_data_access()
        return data_access.get_deal_by_id(
            workspace_id=workspace_id,
            deal_id=deal_id,
            include=include,
        )


class GetDealPeopleTool(Tool):
    """Get all people associated with a deal."""

    @property
    def name(self) -> str:
        return "get_deal_people"

    @property
    def description(self) -> str:
        return "Get all people associated with a deal with optional interaction counts."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "deal_id": {"type": "string", "description": "Deal UUID (required)"},
                "include_interactions": {
                    "type": "boolean",
                    "description": "Include interaction counts (default: false)",
                },
            },
            "required": ["workspace_id", "deal_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        deal_id = kwargs.get("deal_id")
        include_interactions = kwargs.get("include_interactions", False)

        if not workspace_id or not deal_id:
            raise ValueError("workspace_id and deal_id are required")

        logger.info("Getting deal people", workspace_id=workspace_id, deal_id=deal_id)

        data_access = get_data_access()
        return data_access.get_deal_people(
            workspace_id=workspace_id,
            deal_id=deal_id,
            include_interactions=include_interactions,
        )


class GetDealCompaniesTool(Tool):
    """Get all companies associated with a deal."""

    @property
    def name(self) -> str:
        return "get_deal_companies"

    @property
    def description(self) -> str:
        return "Get all companies associated with a deal."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "deal_id": {"type": "string", "description": "Deal UUID (required)"},
            },
            "required": ["workspace_id", "deal_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        deal_id = kwargs.get("deal_id")

        if not workspace_id or not deal_id:
            raise ValueError("workspace_id and deal_id are required")

        logger.info("Getting deal companies", workspace_id=workspace_id, deal_id=deal_id)

        data_access = get_data_access()
        return data_access.get_deal_companies(
            workspace_id=workspace_id,
            deal_id=deal_id,
        )


class GetDealInteractionsTool(Tool):
    """Get interactions related to a deal."""

    @property
    def name(self) -> str:
        return "get_deal_interactions"

    @property
    def description(self) -> str:
        return "Get interactions related to a deal with summary statistics."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "deal_id": {"type": "string", "description": "Deal UUID (required)"},
                "type": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "EMAIL",
                            "CALENDAR",
                            "CALL",
                            "MEETING",
                            "NOTE",
                            "SMS",
                            "LINKEDIN_MESSAGE",
                            "SOCIAL_MEDIA",
                        ],
                    },
                    "description": "Filter by interaction types",
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "Start date (ISO format)"},
                        "end": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "description": "Filter by date range",
                },
                "limit": {"type": "integer", "description": "Maximum number of results"},
                "offset": {"type": "integer", "description": "Offset for pagination"},
            },
            "required": ["workspace_id", "deal_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        deal_id = kwargs.get("deal_id")
        type_filter = kwargs.get("type")
        date_range = kwargs.get("date_range")
        limit = kwargs.get("limit", 20)
        offset = kwargs.get("offset", 0)

        if not workspace_id or not deal_id:
            raise ValueError("workspace_id and deal_id are required")

        logger.info("Getting deal interactions", workspace_id=workspace_id, deal_id=deal_id)

        # Parse date range if provided
        parsed_date_range = None
        if date_range:
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        data_access = get_data_access()
        return data_access.get_deal_interactions(
            workspace_id=workspace_id,
            deal_id=deal_id,
            type=type_filter,
            date_range=parsed_date_range,
            limit=limit,
            offset=offset,
        )

