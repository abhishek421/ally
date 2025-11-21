"""
GraphQL-backed tools for workspace-related actions.

This module provides tools for the agent to:
- Fetch workspace metadata and settings
- List workspaces a user belongs to
- Get workspace member information and roles

All tools are async wrappers around GraphQL queries with no business logic.
They return clean dictionaries that the agent can reason about.

Privacy & Permissions:
- Workspace data is scoped to authenticated user
- Member lists include role information (OWNER, ADMIN, MEMBER)
- Tools respect backend permissions automatically
"""

# ========================================
# 1. Imports
# ========================================

from typing import Dict, Any, Optional

from src.config.logger import logger
from src.tools.graphql_client import gql_request


# ========================================
# 2. Tool Definitions
# ========================================


async def get_workspace(workspace_id: str, graphql_auth_token: str) -> Dict[str, Any]:
    """
    Fetch a single workspace by ID.
    
    The agent uses this tool to:
    - Understand workspace metadata and configuration
    - Confirm workspace existence before performing actions
    - Validate context before running entity operations
    - Display workspace details to the user
    
    This is typically the first tool called when starting a conversation
    to ensure the workspace context is valid and accessible.
    
    Args:
        workspace_id: Unique identifier of the workspace
    
    Returns:
        Dictionary containing workspace information:
        {
            "id": str,
            "name": str,
            "createdAt": str (ISO datetime),
            "updatedAt": str (ISO datetime),
            "avatarUrl": str or None
        }
    
    Example:
        workspace = await get_workspace("workspace-123")
        print(f"Working in: {workspace['name']}")
    """
    query = """
        query GetWorkspace($id: ID!) {
            workspace(id: $id) {
                id
                name
                createdAt
                updatedAt
                avatarUrl
            }
        }
    """
    
    variables = {"id": workspace_id}
    
    logger.debug(f"Fetching workspace: {workspace_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("workspace", {})


async def get_workspaces_for_user(graphql_auth_token: str, cursor: Optional[str] = None) -> Dict[str, Any]:
    """
    List workspaces the current user belongs to.
    
    The agent uses this tool to:
    - Display all workspaces available to the user
    - Enable workspace switching or comparison
    - Validate the user's active workspace membership
    - Support onboarding flows and workspace discovery
    
    This tool is useful when the user asks questions like:
    - "What workspaces do I have access to?"
    - "Show me all my workspaces"
    - "Which workspace am I in?"
    
    Returns paginated results with cursor-based pagination for large workspace lists.
    
    Args:
        cursor: Optional cursor for pagination (to fetch next page)
    
    Returns:
        Dictionary containing:
        {
            "items": [
                {
                    "id": str,
                    "name": str,
                    "avatarUrl": str or None,
                    "createdAt": str (ISO datetime)
                },
                ...
            ],
            "metaData": {
                "nextCursor": str or None,
                "totalCount": int,
                "hasMore": bool,
                "take": int
            }
        }
    
    Example:
        workspaces = await get_workspaces_for_user()
        for ws in workspaces["items"]:
            print(f"- {ws['name']} ({ws['id']})")
    """
    query = """
        query GetWorkspacesForUser($cursor: String, $take: Int) {
            getWorkspacesForUser(cursor: $cursor, take: $take) {
                items {
                    id
                    name
                    avatarUrl
                    createdAt
                }
                metaData {
                    nextCursor
                    totalCount
                    hasMore
                    take
                }
            }
        }
    """
    
    variables = {
        "cursor": cursor,
        "take": 10
    }
    
    logger.debug(f"Fetching workspaces for user (cursor: {cursor})")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getWorkspacesForUser", {})


async def get_workspace_members(
    workspace_id: str,
    graphql_auth_token: str,
    cursor: Optional[str] = None,
    take: int = 10
) -> Dict[str, Any]:
    """
    Fetch members of a workspace with their roles and metadata.
    
    The agent uses this tool to:
    - Validate permissions before write operations (check for ADMIN/OWNER roles)
    - Identify who created an entity (match createdBy ID with member list)
    - Enrich reasoning with user context ("John created this company")
    - Answer questions about team structure and member access
    - Display workspace collaborators to the user
    
    Role Types:
    - OWNER: Full control, cannot be removed
    - ADMIN: Can manage members and settings
    - MEMBER: Standard access, can view/edit based on privacy settings
    
    This tool is essential for permission-aware operations and providing
    context about who has access to entities in the workspace.
    
    Args:
        workspace_id: ID of the workspace to fetch members for
        cursor: Optional cursor for pagination
        take: Number of members to fetch (default: 10, max recommended: 50)
    
    Returns:
        Dictionary containing:
        {
            "items": [
                {
                    "id": str,
                    "email": str,
                    "firstName": str,
                    "lastName": str,
                    "role": str (OWNER|ADMIN|MEMBER),
                    "metaData": dict,
                    "createdAt": str (ISO datetime),
                    "avatarUrl": str or None
                },
                ...
            ],
            "metaData": {
                "nextCursor": str or None,
                "totalCount": int,
                "take": int,
                "hasMore": bool
            }
        }
    
    Privacy Implications:
    - Only returns members the current user has permission to see
    - Email addresses are visible to all workspace members
    - Role information helps enforce access control in the UI
    
    Example:
        members = await get_workspace_members("workspace-123")
        admins = [m for m in members["items"] if m["role"] in ["ADMIN", "OWNER"]]
        print(f"Found {len(admins)} administrators")
    """
    query = """
        query GetUsers($cursor: String, $take: Int, $workspaceId: String!) {
            getUsers(cursor: $cursor, take: $take, workspaceId: $workspaceId) {
                items {
                    id
                    email
                    firstName
                    lastName
                    role
                    metaData
                    createdAt
                    avatarUrl
                }
                metaData {
                    nextCursor
                    totalCount
                    take
                    hasMore
                }
            }
        }
    """
    
    variables = {
        "cursor": cursor,
        "take": take,
        "workspaceId": workspace_id
    }
    
    logger.debug(
        f"Fetching members for workspace {workspace_id} (cursor: {cursor}, take: {take})"
    )
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getUsers", {})


# ========================================
# 3. Tool Registry
# ========================================

WORKSPACE_TOOLS = [
    get_workspace,
    get_workspaces_for_user,
    get_workspace_members,
]
"""
List of all workspace-related tools available to the agent.

These tools provide workspace context and member information that the agent
needs to operate within a workspace scope. They are typically used early in
the conversation to establish context before performing entity operations.

Usage:
    from src.tools.workspace_tools import WORKSPACE_TOOLS
    
    # Register tools with agent
    for tool in WORKSPACE_TOOLS:
        agent.register_tool(tool)
"""

