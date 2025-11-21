"""Interaction query tools for CRM."""

from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool

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

        return {
            "results": [],
            "total": 0,
            "hasMore": False,
            "summary": {
                "byType": {},
                "byDirection": {"inbound": 0, "outbound": 0},
            },
            "error": "Not yet implemented - requires data access layer",
        }


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

        if not workspace_id or not interaction_id:
            raise ValueError("workspace_id and interaction_id are required")

        logger.info("Getting interaction by ID", workspace_id=workspace_id, interaction_id=interaction_id)

        return {
            "interaction": None,
            "person": None,
            "company": None,
            "relatedDeals": None,
            "error": "Not yet implemented - requires data access layer",
        }

