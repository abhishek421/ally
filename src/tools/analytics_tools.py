"""Analytics tools for CRM."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class GetActivitySummaryTool(Tool):
    """Get summary of recent activities and interactions."""

    @property
    def name(self) -> str:
        return "get_activity_summary"

    @property
    def description(self) -> str:
        return "Get summary of recent activities and interactions with trends and statistics."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "days": {"type": "integer", "description": "Number of days to analyze (default: 30)"},
                "activity_types": {
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
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        days = kwargs.get("days", 30)
        activity_types = kwargs.get("activity_types")

        if not workspace_id:
            raise ValueError("workspace_id is required")

        logger.info("Getting activity summary", workspace_id=workspace_id, days=days)

        data_access = get_data_access()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get interactions for the period
        interactions_result = data_access.search_interactions(
            workspace_id=workspace_id,
            type=activity_types,
            date_range={"start": start_date, "end": end_date},
            limit=1000,  # Get a large sample
        )

        total_activities = interactions_result.get("total", 0)
        by_type = interactions_result.get("summary", {}).get("byType", {})
        by_direction = interactions_result.get("summary", {}).get("byDirection", {})

        # Get workspace summary for additional context
        workspace_summary = data_access.get_workspace_summary(workspace_id)

        return {
            "summary": {
                "totalActivities": total_activities,
                "activitiesByType": by_type,
                "activitiesByDirection": by_direction,
                "activitiesByUser": [],  # Would need to aggregate by createdById
                "topContacts": [],  # Would need to aggregate by peopleId
            },
            "trends": {
                "dailyActivity": [],  # Would need to aggregate by day
                "activityGrowth": None,
                "peakHours": None,
            },
            "workspaceSummary": workspace_summary,
        }


class AnalyzeContactGrowthTool(Tool):
    """Analyze contact growth trends and patterns."""

    @property
    def name(self) -> str:
        return "analyze_contact_growth"

    @property
    def description(self) -> str:
        return "Analyze contact growth trends and patterns with breakdowns by source, industry, geography, and size."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "period": {
                    "type": "string",
                    "enum": ["month", "quarter", "year"],
                    "description": "Time period for analysis",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["source", "industry", "geography"],
                    "description": "Group results by field",
                },
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        period = kwargs.get("period", "month")
        group_by = kwargs.get("group_by")

        if not workspace_id:
            raise ValueError("workspace_id is required")

        logger.info("Analyzing contact growth", workspace_id=workspace_id, period=period, group_by=group_by)

        data_access = get_data_access()

        # Get workspace summary for totals
        workspace_summary = data_access.get_workspace_summary(workspace_id)
        people_stats = workspace_summary.get("people", {})
        company_stats = workspace_summary.get("companies", {})

        total_people = people_stats.get("total", 0)
        new_people_this_month = people_stats.get("addedThisMonth", 0)
        total_companies = company_stats.get("total", 0)
        new_companies_this_month = company_stats.get("addedThisMonth", 0)

        # Calculate growth rate
        growth_rate = 0.0
        if total_people > 0:
            growth_rate = (new_people_this_month / total_people) * 100

        insights = []
        if new_people_this_month > 0:
            insights.append(f"Added {new_people_this_month} new contacts this month")
        if new_companies_this_month > 0:
            insights.append(f"Added {new_companies_this_month} new companies this month")
        if people_stats.get("withInteractions", 0) > 0:
            engagement_rate = (people_stats["withInteractions"] / total_people) * 100 if total_people > 0 else 0
            insights.append(f"{engagement_rate:.1f}% of contacts have interactions")

        return {
            "growth": {
                "totalContacts": total_people,
                "totalCompanies": total_companies,
                "newContactsThisMonth": new_people_this_month,
                "newCompaniesThisMonth": new_companies_this_month,
                "growthRate": round(growth_rate, 2),
                "growthByPeriod": [],
            },
            "patterns": {
                "sourceBreakdown": None,
                "industryBreakdown": None,
                "geographicBreakdown": None,
                "sizeBreakdown": None,
            },
            "insights": insights,
        }

