"""Interaction query tools for CRM."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class SearchInteractionsTool(Tool):
    """Search for interactions by content, type, date, or related entities."""

    @property
    def name(self) -> str:
        return "search_interactions"

    @property
    def description(self) -> str:
        return "Search for interactions by content, type, date, or related entities. Returns paginated results with summary."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "query": {"type": "string", "description": "Search in subject and content"},
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
                "direction": {
                    "type": "string",
                    "enum": ["INBOUND", "OUTBOUND", "both"],
                    "description": "Filter by direction (default: both)",
                },
                "person_id": {"type": "string", "description": "Filter by person UUID"},
                "company_id": {"type": "string", "description": "Filter by company UUID"},
                "created_by": {"type": "string", "description": "Filter by creator UUID"},
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "Start date (ISO format)"},
                        "end": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "description": "Filter by date range",
                },
                "has_content": {
                    "type": "boolean",
                    "description": "Only interactions with content (default: false)",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["date", "createdAt"],
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

        logger.info("Searching interactions", workspace_id=workspace_id, query=kwargs.get("query"))

        # Parse date range if provided
        date_range = kwargs.get("date_range")
        parsed_date_range = None
        if date_range:
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        data_access = get_data_access()
        return data_access.search_interactions(
            workspace_id=workspace_id,
            query=kwargs.get("query"),
            type=kwargs.get("type"),
            direction=kwargs.get("direction"),
            person_id=kwargs.get("person_id"),
            company_id=kwargs.get("company_id"),
            created_by=kwargs.get("created_by"),
            date_range=parsed_date_range,
            has_content=kwargs.get("has_content"),
            sort_by=kwargs.get("sort_by"),
            sort_order=kwargs.get("sort_order"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
        )


class GetInteractionByIdTool(Tool):
    """Get complete interaction details."""

    @property
    def name(self) -> str:
        return "get_interaction_by_id"

    @property
    def description(self) -> str:
        return "Get complete interaction details with optional related person, company, and deals."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "interaction_id": {"type": "string", "description": "Interaction UUID (required)"},
                "include": {
                    "type": "object",
                    "properties": {
                        "person": {"type": "boolean", "description": "Include related person"},
                        "company": {"type": "boolean", "description": "Include related company"},
                        "related_deals": {"type": "boolean", "description": "Include related deals"},
                    },
                    "description": "Optional data to include",
                },
            },
            "required": ["workspace_id", "interaction_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        interaction_id = kwargs.get("interaction_id")
        include = kwargs.get("include")

        if not workspace_id or not interaction_id:
            raise ValueError("workspace_id and interaction_id are required")

        logger.info("Getting interaction by ID", workspace_id=workspace_id, interaction_id=interaction_id)

        data_access = get_data_access()
        return data_access.get_interaction_by_id(
            workspace_id=workspace_id,
            interaction_id=interaction_id,
            include=include,
        )

