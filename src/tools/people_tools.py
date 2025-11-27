"""People query tools for CRM."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class SearchPeopleTool(Tool):
    """Search for people by name, email, job title, company, group, or other criteria."""

    @property
    def name(self) -> str:
        return "search_people"

    @property
    def description(self) -> str:
        return (
            "Search for people by name, email, job title, company, group, or other criteria. "
            "Returns paginated results with total count."
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
                "query": {
                    "type": "string",
                    "description": "Search term for name, email, or job title (case-insensitive)",
                },
                "email": {
                    "type": "string",
                    "description": "Exact email address to match",
                },
                "job_title": {
                    "type": "string",
                    "description": "Filter by job title (case-insensitive contains)",
                },
                "company_id": {
                    "type": "string",
                    "description": "Filter by company UUID",
                },
                "group_id": {
                    "type": "string",
                    "description": "Filter by group UUID",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags",
                },
                "has_interactions_since": {
                    "type": "string",
                    "description": "Filter by people with interactions after this date (ISO format)",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["name", "createdAt", "lastInteraction", "interactionCount"],
                    "description": "Field to sort by",
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort order (default: desc)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 20, max: 100)",
                    "minimum": 1,
                    "maximum": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default: 0)",
                    "minimum": 0,
                },
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        if not workspace_id:
            raise ValueError("workspace_id is required")

        query = kwargs.get("query")
        email = kwargs.get("email")
        job_title = kwargs.get("job_title")
        company_id = kwargs.get("company_id")
        group_id = kwargs.get("group_id")
        tags = kwargs.get("tags")
        has_interactions_since = kwargs.get("has_interactions_since")
        sort_by = kwargs.get("sort_by")
        sort_order = kwargs.get("sort_order", "desc")
        limit = kwargs.get("limit", 20)
        offset = kwargs.get("offset", 0)

        # Parse datetime if provided
        interactions_since = None
        if has_interactions_since:
            try:
                interactions_since = datetime.fromisoformat(has_interactions_since.replace("Z", "+00:00"))
            except Exception as e:
                logger.warning(f"Invalid date format: {has_interactions_since}", error=str(e))

        logger.info(
            "Searching people",
            workspace_id=workspace_id,
            query=query,
            limit=limit,
            offset=offset,
        )

        data_access = get_data_access()
        result = data_access.search_people(
            workspace_id=workspace_id,
            query=query,
            email=email,
            job_title=job_title,
            company_id=company_id,
            group_id=group_id,
            tags=tags,
            has_interactions_since=interactions_since,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        return result


class GetPersonByIdTool(Tool):
    """Get complete person profile with optional related data."""

    @property
    def name(self) -> str:
        return "get_person_by_id"

    @property
    def description(self) -> str:
        return (
            "Get complete person profile with optional related data including companies, "
            "deals, interactions, contact information, custom fields, and groups."
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
                "person_id": {
                    "type": "string",
                    "description": "Person UUID (required)",
                },
                "include": {
                    "type": "object",
                    "properties": {
                        "companies": {"type": "boolean", "description": "Include companies"},
                        "primary_company": {"type": "boolean", "description": "Include primary company"},
                        "deals": {"type": "boolean", "description": "Include deals"},
                        "recent_interactions": {
                            "type": "integer",
                            "description": "Number of recent interactions to include",
                        },
                        "emails": {"type": "boolean", "description": "Include all emails"},
                        "phones": {"type": "boolean", "description": "Include all phone numbers"},
                        "addresses": {"type": "boolean", "description": "Include all addresses"},
                        "urls": {"type": "boolean", "description": "Include all URLs"},
                        "custom_fields": {"type": "boolean", "description": "Include custom fields"},
                        "groups": {"type": "boolean", "description": "Include groups"},
                    },
                    "description": "Optional data to include",
                },
            },
            "required": ["workspace_id", "person_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        include = kwargs.get("include")

        if not workspace_id or not person_id:
            raise ValueError("workspace_id and person_id are required")

        logger.info("Getting person by ID", workspace_id=workspace_id, person_id=person_id, include=include)

        data_access = get_data_access()
        result = data_access.get_person_by_id(workspace_id=workspace_id, person_id=person_id, include=include)

        return result


class GetPersonCompaniesTool(Tool):
    """Get all companies associated with a person."""

    @property
    def name(self) -> str:
        return "get_person_companies"

    @property
    def description(self) -> str:
        return "Get all companies associated with a person, including relationship metadata."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "person_id": {"type": "string", "description": "Person UUID (required)"},
                "current_only": {
                    "type": "boolean",
                    "description": "Only return current companies (default: false)",
                },
                "include_primary": {
                    "type": "boolean",
                    "description": "Include primary company flag (default: true)",
                },
                "include_metadata": {
                    "type": "boolean",
                    "description": "Include relationship metadata (default: false)",
                },
            },
            "required": ["workspace_id", "person_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        current_only = kwargs.get("current_only", False)
        include_primary = kwargs.get("include_primary", True)
        include_metadata = kwargs.get("include_metadata", False)

        if not workspace_id or not person_id:
            raise ValueError("workspace_id and person_id are required")

        logger.info(
            "Getting person companies",
            workspace_id=workspace_id,
            person_id=person_id,
            current_only=current_only,
        )

        data_access = get_data_access()
        return data_access.get_person_companies(
            workspace_id=workspace_id,
            person_id=person_id,
            current_only=current_only,
            include_primary=include_primary,
            include_metadata=include_metadata,
        )


class GetPersonDealsTool(Tool):
    """Get all deals associated with a person."""

    @property
    def name(self) -> str:
        return "get_person_deals"

    @property
    def description(self) -> str:
        return "Get all deals associated with a person with filtering and sorting options."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "person_id": {"type": "string", "description": "Person UUID (required)"},
                "status": {
                    "type": "string",
                    "enum": ["active", "won", "lost", "all"],
                    "description": "Filter by deal status (default: all)",
                },
                "column_id": {"type": "string", "description": "Filter by stage/column UUID"},
                "group_id": {"type": "string", "description": "Filter by group UUID"},
                "sort_by": {
                    "type": "string",
                    "enum": ["createdAt", "updatedAt", "value"],
                    "description": "Field to sort by",
                },
                "limit": {"type": "integer", "description": "Maximum number of results"},
            },
            "required": ["workspace_id", "person_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        status = kwargs.get("status")
        column_id = kwargs.get("column_id")
        group_id = kwargs.get("group_id")
        sort_by = kwargs.get("sort_by")
        limit = kwargs.get("limit")

        if not workspace_id or not person_id:
            raise ValueError("workspace_id and person_id are required")

        logger.info("Getting person deals", workspace_id=workspace_id, person_id=person_id)

        data_access = get_data_access()
        return data_access.get_person_deals(
            workspace_id=workspace_id,
            person_id=person_id,
            status=status,
            column_id=column_id,
            group_id=group_id,
            sort_by=sort_by,
            limit=limit,
        )


class GetPersonInteractionsTool(Tool):
    """Get interactions for a person with filtering and statistics."""

    @property
    def name(self) -> str:
        return "get_person_interactions"

    @property
    def description(self) -> str:
        return (
            "Get interactions for a person with filtering by type, direction, date range, "
            "and includes summary statistics."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "person_id": {"type": "string", "description": "Person UUID (required)"},
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
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "Start date (ISO format)"},
                        "end": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "description": "Filter by date range",
                },
                "limit": {"type": "integer", "description": "Maximum number of results (default: 20)"},
                "offset": {"type": "integer", "description": "Offset for pagination (default: 0)"},
                "sort_by": {
                    "type": "string",
                    "enum": ["date", "createdAt"],
                    "description": "Field to sort by (default: date)",
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort order (default: desc)",
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Include interaction content (default: true)",
                },
            },
            "required": ["workspace_id", "person_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        type_filter = kwargs.get("type")
        direction = kwargs.get("direction")
        date_range = kwargs.get("date_range")
        limit = kwargs.get("limit", 20)
        offset = kwargs.get("offset", 0)
        sort_by = kwargs.get("sort_by")
        sort_order = kwargs.get("sort_order")

        if not workspace_id or not person_id:
            raise ValueError("workspace_id and person_id are required")

        logger.info("Getting person interactions", workspace_id=workspace_id, person_id=person_id)

        # Parse date range if provided
        parsed_date_range = None
        if date_range:
            from datetime import datetime
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        data_access = get_data_access()
        return data_access.get_person_interactions(
            workspace_id=workspace_id,
            person_id=person_id,
            type=type_filter,
            direction=direction,
            date_range=parsed_date_range,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )


class GetPersonTimelineTool(Tool):
    """Get chronological timeline of person's activities."""

    @property
    def name(self) -> str:
        return "get_person_timeline"

    @property
    def description(self) -> str:
        return "Get chronological timeline of person's activities including interactions, deals, and notes."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "person_id": {"type": "string", "description": "Person UUID (required)"},
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "Start date (ISO format)"},
                        "end": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "description": "Filter by date range",
                },
                "include_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["interaction", "deal_created", "deal_updated", "deal_won", "deal_lost", "note_added"],
                    },
                    "description": "Types of events to include (default: all)",
                },
                "limit": {"type": "integer", "description": "Maximum number of events"},
            },
            "required": ["workspace_id", "person_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        date_range = kwargs.get("date_range")
        include_types = kwargs.get("include_types")
        limit = kwargs.get("limit", 50)

        if not workspace_id or not person_id:
            raise ValueError("workspace_id and person_id are required")

        logger.info("Getting person timeline", workspace_id=workspace_id, person_id=person_id)

        # Get interactions as timeline events
        data_access = get_data_access()
        
        # Parse date range if provided
        parsed_date_range = None
        if date_range:
            from datetime import datetime
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        interactions_result = data_access.get_person_interactions(
            workspace_id=workspace_id,
            person_id=person_id,
            date_range=parsed_date_range,
            limit=limit,
        )

        # Convert interactions to timeline events
        timeline = []
        for interaction in interactions_result.get("interactions", []):
            timeline.append({
                "type": "interaction",
                "date": interaction.get("date"),
                "data": interaction,
                "description": f"{interaction.get('type', 'Interaction')}: {interaction.get('subject', 'No subject')}",
            })

        # Sort by date descending
        timeline.sort(key=lambda x: x.get("date", ""), reverse=True)

        return {
            "timeline": timeline[:limit],
            "total": len(timeline),
        }

