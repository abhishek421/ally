"""Register all CRM tools with the tool registry."""

from .analytics_tools import AnalyzeContactGrowthTool, GetActivitySummaryTool
from .company_tools import (
    GetCompanyByIdTool,
    GetCompanyDealsTool,
    GetCompanyInteractionsTool,
    GetCompanyPeopleTool,
    GetCompanyTimelineTool,
    SearchCompaniesTool,
)
from .contact_tools import GetContactDetailsTool, SearchContactsTool
from .context_tools import (
    FindRelationshipsTool,
    GetAccountContextTool,
    GetDealContextTool,
    GetRelationshipNetworkTool,
)
from .deal_analysis_tools import AnalyzePipelineTool
from .deal_tools import (
    GetDealByIdTool,
    GetDealCompaniesTool,
    GetDealInteractionsTool,
    GetDealPeopleTool,
    SearchDealsTool,
)
from .group_tools import (
    GetGroupByIdTool,
    GetGroupMembersTool,
    GetWorkspaceGroupsTool,
)
from .interaction_tools import (
    GetInteractionByIdTool,
    SearchInteractionsTool,
    CreateNoteTool,
    GetNotesTool,
    UpdateNoteTool,
    DeleteNoteTool,
)
from .people_tools import (
    GetPersonByIdTool,
    GetPersonCompaniesTool,
    GetPersonDealsTool,
    GetPersonInteractionsTool,
    GetPersonTimelineTool,
    SearchPeopleTool,
)
from .registry import get_tool_registry
from .utility_tools import GetBulkEntitiesTool, GetWorkspaceSummaryTool
from .write_tools import (
    CreatePersonTool,
    CreateCompanyTool,
    CreateGroupTool,
    AddPersonToCompanyTool,
    AddPersonToGroupTool,
    AddCompanyToGroupTool,
    AddMultiplePeopleToGroupTool,
    AddMultipleCompaniesToGroupTool,
)


def register_all_tools() -> None:
    """Register all CRM tools with the tool registry."""
    registry = get_tool_registry()

    # People tools
    registry.register(SearchPeopleTool())
    registry.register(GetPersonByIdTool())
    registry.register(GetPersonCompaniesTool())
    registry.register(GetPersonDealsTool())
    registry.register(GetPersonInteractionsTool())
    registry.register(GetPersonTimelineTool())

    # Company tools
    registry.register(SearchCompaniesTool())
    registry.register(GetCompanyByIdTool())
    registry.register(GetCompanyPeopleTool())
    registry.register(GetCompanyDealsTool())
    registry.register(GetCompanyInteractionsTool())
    registry.register(GetCompanyTimelineTool())

    # Deal tools
    registry.register(SearchDealsTool())
    registry.register(GetDealByIdTool())
    registry.register(GetDealPeopleTool())
    registry.register(GetDealCompaniesTool())
    registry.register(GetDealInteractionsTool())

    # Interaction tools
    registry.register(SearchInteractionsTool())
    registry.register(GetInteractionByIdTool())

    # Note tools (notes are a type of interaction)
    registry.register(CreateNoteTool())
    registry.register(GetNotesTool())
    registry.register(UpdateNoteTool())
    registry.register(DeleteNoteTool())

    # Contact tools
    registry.register(SearchContactsTool())
    registry.register(GetContactDetailsTool())

    # Analytics tools
    registry.register(GetActivitySummaryTool())
    registry.register(AnalyzeContactGrowthTool())

    # Deal analysis tools
    registry.register(AnalyzePipelineTool())

    # Context tools
    registry.register(GetAccountContextTool())
    registry.register(GetDealContextTool())
    registry.register(FindRelationshipsTool())
    registry.register(GetRelationshipNetworkTool())

    # Group tools
    registry.register(GetWorkspaceGroupsTool())
    registry.register(GetGroupByIdTool())
    registry.register(GetGroupMembersTool())

    # Utility tools
    registry.register(GetWorkspaceSummaryTool())
    registry.register(GetBulkEntitiesTool())

    # Write/Creation tools
    registry.register(CreatePersonTool())
    registry.register(CreateCompanyTool())
    registry.register(CreateGroupTool())
    registry.register(AddPersonToCompanyTool())
    registry.register(AddPersonToGroupTool())
    registry.register(AddCompanyToGroupTool())
    registry.register(AddMultiplePeopleToGroupTool())
    registry.register(AddMultipleCompaniesToGroupTool())


# Auto-register on import (can be disabled if needed)
register_all_tools()

