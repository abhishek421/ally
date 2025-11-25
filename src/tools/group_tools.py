"""
GraphQL-backed tools for Group entity operations.

This module provides comprehensive tools for the agent to:
- Read and manage groups
- View group membership (companies and people)
- Create, update, and delete groups
- Manage group membership and visibility rules

All tools are async wrappers around GraphQL queries/mutations with no business logic.
They return clean dictionaries that the agent can reason about.

Privacy & Visibility Rules:
- Groups have isPrivate flag (true = private, false = public)
- Groups have type: COMPANY, PEOPLE, or DEAL
- IMPORTANT: When adding a PRIVATE entity to a PUBLIC group, the entity becomes PUBLIC
- Backend enforces permission checks automatically
"""

# ========================================
# 1. Imports
# ========================================

from typing import Dict, Any, Optional, List

from src.config.logger import logger
from src.tools.graphql_client import gql_request


# ========================================
# 2. READ TOOLS
# ========================================


async def get_group(group_id: str) -> Dict[str, Any]:
    """
    Fetch a single group by ID.
    
    The agent uses this tool for:
    - Confirming that a group exists before operations
    - Checking group privacy (isPrivate) and type
    - Planning membership additions or visibility updates
    - Displaying group details to the user
    
    Note: Current backend implementation returns all groups via getGroups.
    We filter by group_id client-side. A dedicated getGroup(groupId) query
    would be more efficient if available.
    
    Args:
        group_id: Unique identifier of the group
    
    Returns:
        Dictionary containing group information:
        {
            "id": str,
            "name": str,
            "description": str or None,
            "emoji": str or None,
            "isPrivate": bool,
            "type": str (COMPANY|PEOPLE|DEAL),
            "isCollapse": bool,
            "createdBy": str
        }
    
    Example:
        group = await get_group("group-123")
        print(f"Group: {group['name']}")
        print(f"Type: {group['type']}")
        print(f"Private: {group['isPrivate']}")
    """
    query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                name
                description
                emoji
                isPrivate
                type
                isCollapse
                createdBy
            }
        }
    """
    
    # TODO: Backend should provide a dedicated getGroup(groupId) query
    # For now, we fetch all and filter client-side
    variables = {"workspaceId": ""}
    
    logger.debug(f"Fetching group: {group_id}")
    
    data = await gql_request(query, variables)
    
    groups = data.get("getGroups", [])
    
    # Filter to find the specific group
    for group in groups:
        if group.get("id") == group_id:
            return group
    
    # Group not found
    logger.warning(f"Group {group_id} not found")
    return {}


async def list_groups(workspace_id: str) -> Dict[str, Any]:
    """
    List all groups in a workspace.
    
    The agent uses this tool when:
    - User refers to a group by name (need to resolve name to ID)
    - User wants to see all available groups
    - Planning bulk actions across multiple groups
    - Displaying group overview to user
    
    This returns all groups the user has access to in the workspace,
    including both public and private groups they created or have access to.
    
    Args:
        workspace_id: ID of the workspace to list groups from
    
    Returns:
        Dictionary containing:
        {
            "groups": [
                {
                    "id": str,
                    "name": str,
                    "description": str or None,
                    "emoji": str or None,
                    "isPrivate": bool,
                    "type": str (COMPANY|PEOPLE|DEAL),
                    "isCollapse": bool,
                    "createdBy": str
                },
                ...
            ]
        }
    
    Example:
        result = await list_groups("ws-123")
        groups = result["groups"]
        for group in groups:
            print(f"- {group['name']} ({group['type']})")
    """
    query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                name
                description
                emoji
                isPrivate
                type
                isCollapse
                createdBy
            }
        }
    """
    
    variables = {"workspaceId": workspace_id}
    
    logger.debug(f"Listing groups for workspace: {workspace_id}")
    
    data = await gql_request(query, variables)
    
    return {"groups": data.get("getGroups", [])}


async def get_group_companies(
    group_id: str,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    Return companies that belong to a specific group.
    
    The agent uses this tool to:
    - Display group membership to the user
    - Check if a company is already in a group
    - Browse group contents with pagination
    - Search for specific companies within a group
    
    Useful for questions like:
    - "Which companies are in the Enterprise group?"
    - "Show me all companies in this segment"
    
    Args:
        group_id: ID of the group to fetch companies from
        page: Page number for pagination (1-indexed, default: 1)
        limit: Number of results per page (default: 10)
        search: Optional text search to filter companies within the group
    
    Returns:
        Dictionary containing:
        {
            "data": [
                {
                    "id": str,
                    "name": str,
                    "privacyLevel": str (PRIVATE|PUBLIC),
                    "createdBy": str,
                    "imageUrl": str or None
                },
                ...
            ],
            "meta": {
                "total": int,
                "page": int,
                "limit": int,
                "totalPages": int,
                "hasNextPage": bool
            }
        }
    
    Example:
        result = await get_group_companies("group-123", page=1, limit=10)
        print(f"Found {result['meta']['total']} companies in group")
    """
    query = """
        query GetCompaniesByGroup(
            $groupId: ID!,
            $page: Number,
            $limit: Number,
            $search: String
        ) {
            getCompaniesByGroup(
                groupId: $groupId,
                page: $page,
                limit: $limit,
                search: $search
            ) {
                data {
                    id
                    name
                    privacyLevel
                    createdBy
                    imageUrl
                }
                meta {
                    total
                    page
                    limit
                    totalPages
                    hasNextPage
                }
            }
        }
    """
    
    variables = {
        "groupId": group_id,
        "page": page,
        "limit": limit,
        "search": search
    }
    
    logger.debug(
        f"Fetching companies for group {group_id} "
        f"(page: {page}, limit: {limit}, search: '{search}')"
    )
    
    data = await gql_request(query, variables)
    
    return data.get("getCompaniesByGroup", {})


async def get_group_people(
    group_id: str,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    Return people that belong to a specific group.
    
    The agent uses this tool to:
    - Display group membership to the user
    - Check if a person is already in a group
    - Browse group contents with pagination
    - Search for specific people within a group
    
    Useful for questions like:
    - "Who is in the VIP Contacts group?"
    - "Show me all people in this segment"
    
    Args:
        group_id: ID of the group to fetch people from
        page: Page number for pagination (1-indexed, default: 1)
        limit: Number of results per page (default: 10)
        search: Optional text search to filter people within the group
    
    Returns:
        Dictionary containing:
        {
            "data": [
                {
                    "id": str,
                    "firstName": str,
                    "lastName": str or None,
                    "privacyLevel": str (PRIVATE|PUBLIC),
                    "createdBy": str,
                    "imageUrl": str or None,
                    "jobTitle": str or None
                },
                ...
            ],
            "meta": {
                "total": int,
                "page": int,
                "limit": int,
                "totalPages": int,
                "hasNextPage": bool
            }
        }
    
    Example:
        result = await get_group_people("group-123", page=1, limit=10)
        print(f"Found {result['meta']['total']} people in group")
    """
    query = """
        query GetPeopleByGroup(
            $groupId: ID!,
            $page: Number,
            $limit: Number,
            $search: String
        ) {
            getPeopleByGroup(
                groupId: $groupId,
                page: $page,
                limit: $limit,
                search: $search
            ) {
                data {
                    id
                    firstName
                    lastName
                    privacyLevel
                    createdBy
                    imageUrl
                    jobTitle
                }
                meta {
                    total
                    page
                    limit
                    totalPages
                    hasNextPage
                }
            }
        }
    """
    
    variables = {
        "groupId": group_id,
        "page": page,
        "limit": limit,
        "search": search
    }
    
    logger.debug(
        f"Fetching people for group {group_id} "
        f"(page: {page}, limit: {limit}, search: '{search}')"
    )
    
    data = await gql_request(query, variables)
    
    return data.get("getPeopleByGroup", {})


# ========================================
# 3. WRITE TOOLS (Mutations)
# ========================================


async def create_group(input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new group in the workspace.
    
    WARNING: This tool should only be triggered after the validator node
    confirms user intent and approval. The agent should preview group
    properties to the user before calling this mutation.
    
    The agent uses this tool to:
    - Create groups from user natural language input
    - Organize companies or people into segments
    - Set up workspace structure based on user needs
    
    Required fields in input:
    - name: Group name (required)
    - workspaceId: Workspace to create in (required)
    - type: Group type - COMPANY, PEOPLE, or DEAL (required)
    - isPrivate: Privacy flag (required)
    
    Optional fields in input:
    - description: Group description
    - emoji: Emoji icon for the group
    - isCollapse: Whether the group is collapsed in UI
    
    Args:
        input: Group creation input matching CreateGroupRequest schema
    
    Returns:
        Dictionary containing the created group ID or success confirmation
    
    Example:
        result = await create_group(
            input={
                "name": "Enterprise Customers",
                "workspaceId": "ws-123",
                "type": "COMPANY",
                "isPrivate": false,
                "description": "Large enterprise accounts",
                "emoji": "🏢"
            }
        )
    """
    query = """
        mutation CreateGroup($input: CreateGroupRequest!) {
            createGroup(input: $input)
        }
    """
    
    variables = {"input": input}
    
    logger.info(f"Creating group: {input.get('name', 'Unknown')}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("createGroup")}


async def update_group(group_id: str, input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a group's properties such as name, description, emoji, isPrivate, etc.
    
    WARNING: This tool should only be used after the validator node confirms
    user intent and approval. Changes should be previewed to the user first.
    
    The agent uses this tool to:
    - Rename groups based on user requests
    - Update group descriptions or emoji
    - Change group privacy settings
    - Modify group display properties
    
    Args:
        group_id: ID of the group to update
        input: Group update input matching UpdateGroupRequest schema
               (only include fields to update)
    
    Returns:
        Dictionary containing update confirmation
    
    Example:
        result = await update_group(
            group_id="group-123",
            input={
                "name": "Updated Group Name",
                "description": "New description",
                "isPrivate": true
            }
        )
    """
    query = """
        mutation UpdateGroup($id: String!, $input: UpdateGroupRequest!) {
            updateGroup(id: $id, input: $input)
        }
    """
    
    variables = {
        "id": group_id,
        "input": input
    }
    
    logger.info(f"Updating group: {group_id}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("updateGroup")}


async def delete_group(group_id: str) -> Dict[str, Any]:
    """
    Delete a group from the workspace.
    
    WARNING: This is a destructive operation that must only be used after
    explicit user confirmation. The validator node must confirm intent.
    
    The agent uses this tool to:
    - Remove groups at user request
    - Clean up unused or obsolete groups
    
    Deletion behavior:
    - Permanently removes the group
    - Does NOT delete entities within the group (companies/people remain)
    - Only removes the grouping/organization structure
    - Cannot be undone
    - Backend enforces permission checks (only creator or admin can delete)
    
    Args:
        group_id: ID of the group to delete
    
    Returns:
        Dictionary containing deletion confirmation
    
    Example:
        result = await delete_group("group-123")
        # Group deleted, but companies/people within it are preserved
    """
    query = """
        mutation DeleteGroup($id: String!) {
            deleteGroup(id: $id)
        }
    """
    
    variables = {"id": group_id}
    
    logger.warning(f"Deleting group: {group_id}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("deleteGroup")}


# ========================================
# 4. MEMBERSHIP TOOLS
# ========================================


async def add_company_to_group(
    group_id: str,
    company_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Add a company to a group.
    
    IMPORTANT BACKEND RULE:
    If the group is PUBLIC (isPrivate=false) and the company is PRIVATE,
    the company will automatically become PUBLIC when added to the group.
    This ensures consistent visibility rules.
    
    The agent uses this tool to:
    - Organize companies into segments or categories
    - Add companies to sales pipelines or deal stages
    - Tag companies with group memberships
    
    The agent should warn the user if adding a PRIVATE company to a PUBLIC group,
    as this changes the company's visibility.
    
    Args:
        group_id: ID of the group to add the company to
        company_id: ID of the company to add
        user_id: ID of the user performing the action (for audit trail)
    
    Returns:
        Dictionary containing confirmation of the addition
    
    Example:
        result = await add_company_to_group(
            group_id="group-123",
            company_id="company-456",
            user_id="user-789"
        )
    """
    query = """
        mutation CreateGroupCompany($input: CreateGroupCompanyInput!, $userId: String!) {
            createGroupCompany(input: $input, userId: $userId)
        }
    """
    
    variables = {
        "input": {
            "groupId": group_id,
            "companyId": company_id
        },
        "userId": user_id
    }
    
    logger.info(f"Adding company {company_id} to group {group_id}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("createGroupCompany")}


async def remove_company_from_group(group_id: str, company_id: str) -> Dict[str, Any]:
    """
    Remove a company from a group.
    
    The agent uses this tool to:
    - Remove companies from segments or categories
    - Clean up group memberships
    - Reorganize company groupings
    
    This removes the group membership without affecting the company itself.
    The company record remains intact, just unlinked from this group.
    
    Note: Removing a company from a PUBLIC group does NOT change the
    company's privacy level back to PRIVATE. Privacy escalation is permanent.
    
    Args:
        group_id: ID of the group to remove the company from
        company_id: ID of the company to remove
    
    Returns:
        Dictionary containing confirmation of the removal
    
    Example:
        result = await remove_company_from_group("group-123", "company-456")
        # Company is no longer in the group but still exists
    """
    query = """
        mutation DeleteGroupCompany($groupId: ID!, $companyId: ID!) {
            deleteGroupCompany(groupId: $groupId, companyId: $companyId)
        }
    """
    
    variables = {
        "groupId": group_id,
        "companyId": company_id
    }
    
    logger.info(f"Removing company {company_id} from group {group_id}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("deleteGroupCompany")}


async def add_person_to_group(
    group_id: str,
    people_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Add a person to a group.
    
    IMPORTANT BACKEND RULE:
    If the group is PUBLIC (isPrivate=false) and the person is PRIVATE,
    the person will automatically become PUBLIC when added to the group.
    This ensures consistent visibility rules.
    
    The agent uses this tool to:
    - Organize people into segments or categories
    - Add people to contact lists or distribution groups
    - Tag people with group memberships
    
    The agent should warn the user if adding a PRIVATE person to a PUBLIC group,
    as this changes the person's visibility.
    
    Args:
        group_id: ID of the group to add the person to
        people_id: ID of the person to add
        user_id: ID of the user performing the action (for audit trail)
    
    Returns:
        Dictionary containing confirmation of the addition
    
    Example:
        result = await add_person_to_group(
            group_id="group-123",
            people_id="person-456",
            user_id="user-789"
        )
    """
    query = """
        mutation CreateGroupPeople($input: CreateGroupPeopleInput!, $userId: String!) {
            createGroupPeople(input: $input, userId: $userId)
        }
    """
    
    variables = {
        "input": {
            "groupId": group_id,
            "peopleId": people_id
        },
        "userId": user_id
    }
    
    logger.info(f"Adding person {people_id} to group {group_id}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("createGroupPeople")}


async def remove_person_from_group(group_id: str, people_id: str) -> Dict[str, Any]:
    """
    Remove a person from a group.
    
    The agent uses this tool to:
    - Remove people from segments or categories
    - Clean up group memberships
    - Reorganize people groupings
    
    This removes the group membership without affecting the person itself.
    The person record remains intact, just unlinked from this group.
    
    Note: Removing a person from a PUBLIC group does NOT change the
    person's privacy level back to PRIVATE. Privacy escalation is permanent.
    
    Args:
        group_id: ID of the group to remove the person from
        people_id: ID of the person to remove
    
    Returns:
        Dictionary containing confirmation of the removal
    
    Example:
        result = await remove_person_from_group("group-123", "person-456")
        # Person is no longer in the group but still exists
    """
    query = """
        mutation DeleteGroupPeople($groupId: ID!, $peopleId: ID!) {
            deleteGroupPeople(groupId: $groupId, peopleId: $peopleId)
        }
    """
    
    variables = {
        "groupId": group_id,
        "peopleId": people_id
    }
    
    logger.info(f"Removing person {people_id} from group {group_id}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("deleteGroupPeople")}


# ========================================
# 5. Tool Registry
# ========================================

GROUP_TOOLS = [
    get_group,
    list_groups,
    get_group_companies,
    get_group_people,
    create_group,
    update_group,
    delete_group,
    add_company_to_group,
    remove_company_from_group,
    add_person_to_group,
    remove_person_from_group,
]
"""
List of all group-related tools available to the agent.

These tools provide comprehensive group management operations including:
- Read: get_group, list_groups, get_group_companies, get_group_people
- Write: create_group, update_group, delete_group
- Membership: add_company_to_group, remove_company_from_group,
              add_person_to_group, remove_person_from_group

Important visibility rules:
- Adding a PRIVATE entity to a PUBLIC group makes the entity PUBLIC
- This privacy escalation is permanent (removing from group doesn't revert it)
- The agent should warn users about privacy implications

Usage:
    from src.tools.group_tools import GROUP_TOOLS
    
    # Register tools with agent
    for tool in GROUP_TOOLS:
        agent.register_tool(tool)
"""
