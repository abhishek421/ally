"""Company query tools for CRM."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class SearchCompaniesTool(Tool):
    """Search for companies by name, industry, size, or other criteria."""

    @property
    def name(self) -> str:
        return "search_companies"

    @property
    def description(self) -> str:
        return "Search for companies by name, industry, size, or other criteria. Returns paginated results."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "query": {"type": "string", "description": "Search term for name, description, email"},
                "industry": {"type": "string", "description": "Industry filter"},
                "size": {"type": "string", "description": "Company size filter"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                "has_interactions_since": {
                    "type": "string",
                    "description": "Filter by companies with interactions after this date (ISO format)",
                },
                "has_deals_since": {
                    "type": "string",
                    "description": "Filter by companies with deals after this date (ISO format)",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["name", "createdAt", "lastInteraction", "dealValue"],
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

        logger.info("Searching companies", workspace_id=workspace_id, query=kwargs.get("query"))

        try:
            # Use the data access layer to get real data
            data_access = get_data_access()
            return data_access.search_companies(
                workspace_id=workspace_id,
                query=kwargs.get("query"),
                industry=kwargs.get("industry"),
                size=kwargs.get("size"),
                tags=kwargs.get("tags"),
                has_interactions_since=kwargs.get("has_interactions_since"),
                has_deals_since=kwargs.get("has_deals_since"),
                sort_by=kwargs.get("sort_by"),
                sort_order=kwargs.get("sort_order"),
                limit=kwargs.get("limit"),
                offset=kwargs.get("offset"),
            )
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return {
                "results": [],
                "total": 0,
                "hasMore": False,
                "error": f"Error accessing database: {str(e)}",
            }


class GetCompanyByIdTool(Tool):
    """Get complete company profile with optional related data."""

    @property
    def name(self) -> str:
        return "get_company_by_id"

    @property
    def description(self) -> str:
        return (
            "Get complete company profile with optional related data including people, "
            "key contacts, deals, interactions, contact information, custom fields, and groups."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "company_id": {"type": "string", "description": "Company UUID (required)"},
                "include": {
                    "type": "object",
                    "properties": {
                        "people": {"type": "boolean", "description": "Include all people"},
                        "key_contacts": {
                            "type": "integer",
                            "description": "Number of key contacts to include",
                        },
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
            "required": ["workspace_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        company_id = kwargs.get("company_id")
        include = kwargs.get("include")

        if not workspace_id or not company_id:
            raise ValueError("workspace_id and company_id are required")

        logger.info("Getting company by ID", workspace_id=workspace_id, company_id=company_id)

        data_access = get_data_access()
        return data_access.get_company_by_id(
            workspace_id=workspace_id,
            company_id=company_id,
            include=include,
        )


class GetCompanyPeopleTool(Tool):
    """Get all people associated with a company."""

    @property
    def name(self) -> str:
        return "get_company_people"

    @property
    def description(self) -> str:
        return "Get all people associated with a company with engagement metrics."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "company_id": {"type": "string", "description": "Company UUID (required)"},
                "current_only": {
                    "type": "boolean",
                    "description": "Only return current employees (default: false)",
                },
                "roles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by job titles/roles",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["name", "lastInteraction", "interactionCount"],
                    "description": "Field to sort by",
                },
                "limit": {"type": "integer", "description": "Maximum number of results"},
            },
            "required": ["workspace_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        company_id = kwargs.get("company_id")
        current_only = kwargs.get("current_only", False)
        roles = kwargs.get("roles")
        sort_by = kwargs.get("sort_by")
        limit = kwargs.get("limit")

        if not workspace_id or not company_id:
            raise ValueError("workspace_id and company_id are required")

        logger.info("Getting company people", workspace_id=workspace_id, company_id=company_id)

        data_access = get_data_access()
        return data_access.get_company_people(
            workspace_id=workspace_id,
            company_id=company_id,
            current_only=current_only,
            roles=roles,
            sort_by=sort_by,
            limit=limit,
        )


class GetCompanyDealsTool(Tool):
    """Get all deals associated with a company."""

    @property
    def name(self) -> str:
        return "get_company_deals"

    @property
    def description(self) -> str:
        return "Get all deals associated with a company with summary statistics."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "company_id": {"type": "string", "description": "Company UUID (required)"},
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
                "include_contacts": {
                    "type": "boolean",
                    "description": "Include people on deals (default: false)",
                },
            },
            "required": ["workspace_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        company_id = kwargs.get("company_id")
        status = kwargs.get("status")
        column_id = kwargs.get("column_id")
        group_id = kwargs.get("group_id")
        sort_by = kwargs.get("sort_by")
        limit = kwargs.get("limit")
        include_contacts = kwargs.get("include_contacts", False)

        if not workspace_id or not company_id:
            raise ValueError("workspace_id and company_id are required")

        logger.info("Getting company deals", workspace_id=workspace_id, company_id=company_id)

        data_access = get_data_access()
        return data_access.get_company_deals(
            workspace_id=workspace_id,
            company_id=company_id,
            status=status,
            column_id=column_id,
            group_id=group_id,
            sort_by=sort_by,
            limit=limit,
            include_contacts=include_contacts,
        )


class GetCompanyInteractionsTool(Tool):
    """Get interactions for a company (and optionally employees)."""

    @property
    def name(self) -> str:
        return "get_company_interactions"

    @property
    def description(self) -> str:
        return "Get interactions for a company with optional employee interactions and grouping."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "company_id": {"type": "string", "description": "Company UUID (required)"},
                "include_employee_interactions": {
                    "type": "boolean",
                    "description": "Include interactions with employees (default: false)",
                },
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
                "limit": {"type": "integer", "description": "Maximum number of results"},
                "offset": {"type": "integer", "description": "Offset for pagination"},
                "group_by": {
                    "type": "string",
                    "enum": ["person", "type", "date"],
                    "description": "Group results by field",
                },
            },
            "required": ["workspace_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        company_id = kwargs.get("company_id")
        include_employee_interactions = kwargs.get("include_employee_interactions", False)
        type_filter = kwargs.get("type")
        direction = kwargs.get("direction")
        date_range = kwargs.get("date_range")
        limit = kwargs.get("limit", 20)
        offset = kwargs.get("offset", 0)

        if not workspace_id or not company_id:
            raise ValueError("workspace_id and company_id are required")

        logger.info("Getting company interactions", workspace_id=workspace_id, company_id=company_id)

        # Parse date range if provided
        parsed_date_range = None
        if date_range:
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        data_access = get_data_access()
        return data_access.get_company_interactions(
            workspace_id=workspace_id,
            company_id=company_id,
            include_employee_interactions=include_employee_interactions,
            type=type_filter,
            direction=direction,
            date_range=parsed_date_range,
            limit=limit,
            offset=offset,
        )


class GetCompanyTimelineTool(Tool):
    """Get chronological timeline of company activities."""

    @property
    def name(self) -> str:
        return "get_company_timeline"

    @property
    def description(self) -> str:
        return "Get chronological timeline of company activities including interactions, deals, and employee activity."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "company_id": {"type": "string", "description": "Company UUID (required)"},
                "include_employee_activity": {
                    "type": "boolean",
                    "description": "Include employee activity (default: false)",
                },
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
                        "enum": [
                            "interaction",
                            "deal_created",
                            "deal_updated",
                            "deal_won",
                            "deal_lost",
                            "person_added",
                        ],
                    },
                    "description": "Types of events to include (default: all)",
                },
                "limit": {"type": "integer", "description": "Maximum number of events"},
            },
            "required": ["workspace_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        company_id = kwargs.get("company_id")
        include_employee_activity = kwargs.get("include_employee_activity", False)
        date_range = kwargs.get("date_range")
        include_types = kwargs.get("include_types")
        limit = kwargs.get("limit", 50)

        if not workspace_id or not company_id:
            raise ValueError("workspace_id and company_id are required")

        logger.info("Getting company timeline", workspace_id=workspace_id, company_id=company_id)

        # Parse date range if provided
        parsed_date_range = None
        if date_range:
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        data_access = get_data_access()
        
        # Get interactions as timeline events
        interactions_result = data_access.get_company_interactions(
            workspace_id=workspace_id,
            company_id=company_id,
            include_employee_interactions=include_employee_activity,
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

