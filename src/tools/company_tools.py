"""
GraphQL-backed tools for Company entity operations.

This module provides comprehensive tools for the agent to:
- Read and search company records
- Create, update, and delete companies
- Manage person-company relationships
- Handle company metadata and privacy settings

All tools are async wrappers around GraphQL queries/mutations with no business logic.
They return clean dictionaries that the agent can reason about.

Privacy & Permissions:
- Companies have privacyLevel: PRIVATE (creator only) or PUBLIC (workspace-wide)
- Write operations respect backend permissions automatically
- Relationship operations validate ownership and access rights
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


async def get_company(company_id: str, graphql_auth_token: str) -> Dict[str, Any]:
    """
    Fetch a single company by ID with full details.
    
    The agent uses this tool to:
    - Retrieve complete company information including metadata
    - Confirm that a company record exists before operations
    - Check visibility and privacy level (PRIVATE vs PUBLIC)
    - Prepare for relationship-based actions (view linked people)
    - Display company details to the user
    
    This tool returns comprehensive company data including:
    - Basic info (name, description, image)
    - Contact details (emails, phones, URLs, addresses)
    - Privacy settings
    - Related people metadata
    
    Args:
        company_id: Unique identifier of the company
        graphql_auth_token: Authentication token for GraphQL API
    
    Returns:
        Dictionary containing full company information:
        {
            "id": str,
            "name": str,
            "privacyLevel": str (PRIVATE|PUBLIC),
            "workspaceId": str,
            "createdBy": str,
            "emails": [{"email": str, "type": str}, ...],
            "phoneNumbers": [{"phone": str, "type": str}, ...],
            "urls": [{"url": str, "type": str}, ...],
            "addresses": [{
                "line1": str, "line2": str, "city": str,
                "state": str, "country": str, "postalCode": str
            }, ...],
            "peopleMetaData": [{
                "peopleId": str,
                "isPeoplePrimary": bool,
                "isCompanyPrimary": bool
            }, ...],
            "description": str or None,
            "imageUrl": str or None
        }
    
    Example:
        company = await get_company("company-123")
        print(f"Company: {company['name']}")
        print(f"Privacy: {company['privacyLevel']}")
        print(f"Linked people: {len(company['peopleMetaData'])}")
    """
    query = """
        query GetOneCompany($companyId: ID!) {
            getOneCompany(companyId: $companyId) {
                id
                name
                privacyLevel
                workspaceId
                createdBy
                emails {
                    email
                    type
                }
                phoneNumbers {
                    phone
                    type
                }
                urls {
                    url
                    type
                }
                addresses {
                    line1
                    line2
                    city
                    state
                    country
                    postalCode
                }
                peopleMetaData {
                    peopleId
                    isPeoplePrimary
                    isCompanyPrimary
                }
                description
                imageUrl
            }
        }
    """
    
    variables = {"companyId": company_id}
    
    logger.debug(f"Fetching company: {company_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getOneCompany", {})


async def search_companies(
    workspace_id: str,
    user_id: str,
    graphql_auth_token: str,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Search companies in a workspace with optional text search filter.
    
    The agent uses this tool to:
    - Find companies matching user queries ("companies in San Francisco")
    - Filter companies by name or other text fields
    - Browse paginated company lists
    - Display search results to the user
    
    The search parameter performs text matching across company fields like
    name and description. If omitted, returns all accessible companies.
    
    Visibility Rules:
    - PUBLIC companies are visible to all workspace members
    - PRIVATE companies are only visible to their creator
    - Results are automatically filtered by backend based on user_id
    
    Args:
        workspace_id: ID of the workspace to search in
        user_id: ID of the user performing the search (for permission filtering)
        graphql_auth_token: Authentication token for GraphQL API
        search: Optional text search query to filter results
        page: Page number for pagination (1-indexed, default: 1)
        limit: Number of results per page (default: 50, max recommended: 50)
    
    Returns:
        Dictionary containing:
        {
            "data": [
                {
                    "id": str,
                    "name": str,
                    "privacyLevel": str (PRIVATE|PUBLIC),
                    "createdBy": str,
                    "imageUrl": str or None,
                    "description": str or None
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
        results = await search_companies(
            workspace_id="ws-123",
            user_id="user-456",
            search="Acme",
            page=1,
            limit=50
        )
        print(f"Found {results['meta']['total']} companies")
        for company in results['data']:
            print(f"- {company['name']}")
    """
    query = """
        query GetWorkspaceCompany(
            $workspaceId: ID!,
            $userId: ID!,
            $page: Int,
            $limit: Int,
            $search: String
        ) {
            getWorkspaceCompany(
                workspaceId: $workspaceId,
                userId: $userId,
                page: $page,
                limit: $limit,
                search: $search
            ) {
                data {
                    id
                    name
                    description
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
        "workspaceId": workspace_id,
        "userId": user_id,
        "page": page,
        "limit": limit,
        "search": search
    }
    
    logger.debug(
        f"Searching companies in workspace {workspace_id} "
        f"(search: '{search}', page: {page}, limit: {limit})"
    )
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getWorkspaceCompany", {})


async def list_companies(
    workspace_id: str,
    user_id: str,
    graphql_auth_token: str,
    page: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    List all companies in a workspace without search filter.
    
    This is identical to search_companies but without the search parameter,
    making it clearer when the agent wants to browse all companies rather
    than search for specific ones.
    
    The agent uses this tool to:
    - Display all companies the user has access to
    - Get an overview of the workspace's company database
    - Browse companies page by page
    - Count total companies in the workspace
    
    Visibility Rules:
    - PUBLIC companies are visible to all workspace members
    - PRIVATE companies are only visible to their creator
    - Results are automatically filtered by backend based on user_id
    
    Args:
        workspace_id: ID of the workspace to list companies from
        user_id: ID of the user performing the listing (for permission filtering)
        page: Page number for pagination (1-indexed, default: 1)
        limit: Number of results per page (default: 50, max recommended: 50)
    
    Returns:
        Dictionary containing:
        {
            "data": [
                {
                    "id": str,
                    "name": str,
                    "privacyLevel": str (PRIVATE|PUBLIC),
                    "createdBy": str,
                    "imageUrl": str or None,
                    "description": str or None
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
        results = await list_companies("ws-123", "user-456", page=1, limit=10)
        print(f"Total companies: {results['meta']['total']}")
    """
    # Delegate to search_companies with no search filter
    return await search_companies(
        workspace_id=workspace_id,
        user_id=user_id,
        graphql_auth_token=graphql_auth_token,
        search=None,
        page=page,
        limit=limit
    )


# ========================================
# 3. WRITE TOOLS (Mutations)
# ========================================


async def create_company(
    input: Dict[str, Any],
    user_id: str,
    graphql_auth_token: str,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new company in the workspace.
    
    IMPORTANT: This tool must only be used after the validator node confirms
    user intent and approval. The agent typically shows a preview of the
    company data to the user before calling this tool.
    
    The agent uses this tool to:
    - Create companies from user natural language input
    - Add companies mentioned in conversation
    - Import company data from external sources
    - Initialize company records for relationship mapping
    
    Required fields in input:
    - name: Company name (required)
    - workspaceId: Workspace to create in (required)
    - privacyLevel: PRIVATE or PUBLIC (required)
    
    Optional fields in input:
    - description: Company description
    - emails: [{"email": str, "type": str}, ...]
    - phoneNumbers: [{"phone": str, "type": str}, ...]
    - urls: [{"url": str, "type": str}, ...]
    - addresses: [{city, state, country, ...}, ...]
    - imageUrl: Company logo/image URL
    
    Args:
        input: Company creation input matching CreateCompanyInput schema
        user_id: ID of the user creating the company
        graphql_auth_token: Authentication token for GraphQL API
        group_id: Optional group ID to add the company to
    
    Returns:
        Dictionary containing the created company ID or success confirmation
    
    Example:
        result = await create_company(
            input={
                "name": "Acme Corp",
                "workspaceId": "ws-123",
                "privacyLevel": "PUBLIC",
                "description": "A technology company"
            },
            user_id="user-456"
        )
    """
    query = """
        mutation CreateCompany($input: CreateCompanyInput!, $userId: ID!, $groupId: ID) {
            createCompany(input: $input, userId: $userId, groupId: $groupId)
        }
    """
    
    variables = {
        "input": input,
        "userId": user_id,
        "groupId": group_id
    }
    
    logger.info(f"Creating company: {input.get('name', 'Unknown')}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return {"result": data.get("createCompany")}


async def update_company(input: Dict[str, Any], graphql_auth_token: str) -> Dict[str, Any]:
    """
    Update an existing company's information.
    
    IMPORTANT: This tool must only be used after the validator node confirms
    user intent and approval. Changes should be previewed to the user first.
    
    The agent uses this tool to:
    - Modify company details based on user requests
    - Correct inaccurate company information
    - Update contact information (emails, phones, addresses)
    - Change privacy level or other metadata
    
    Required fields in input:
    - id: Company ID to update (required)
    
    Optional fields in input (only include fields to update):
    - name: New company name
    - description: New description
    - privacyLevel: New privacy level (PRIVATE|PUBLIC)
    - emails, phoneNumbers, urls, addresses: Updated contact info
    - imageUrl: New company image URL
    
    Args:
        input: Company update input matching UpdateCompanyInput schema
        graphql_auth_token: Authentication token for GraphQL API
    
    Returns:
        Dictionary containing update confirmation or updated company data
    
    Example:
        result = await update_company(
            input={
                "id": "company-123",
                "description": "Updated description",
                "privacyLevel": "PUBLIC"
            }
        )
    """
    query = """
        mutation UpdateCompany($input: UpdateCompanyInput!) {
            updateCompany(input: $input)
        }
    """
    
    variables = {"input": input}
    
    logger.info(f"Updating company: {input.get('id', 'Unknown')}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return {"result": data.get("updateCompany")}


async def delete_companies(company_ids: List[str], graphql_auth_token: str) -> Dict[str, Any]:
    """
    Delete one or multiple companies from the workspace.
    
    IMPORTANT: This is a destructive operation that must only be used after
    explicit user confirmation. The validator node must confirm intent.
    
    The agent uses this tool to:
    - Remove companies at user request
    - Clean up duplicate or test records
    - Bulk delete multiple companies
    
    Deletion behavior:
    - Permanently removes company records
    - May cascade to related records (relationships, interactions)
    - Cannot be undone
    - Backend enforces permission checks (only creator or admin can delete)
    
    Args:
        company_ids: List of company IDs to delete
        graphql_auth_token: Authentication token for GraphQL API
    
    Returns:
        Dictionary containing deletion confirmation
    
    Example:
        result = await delete_companies(["company-123", "company-456"])
        # Companies deleted permanently
    """
    query = """
        mutation DeleteCompanies($companyIds: [ID]!) {
            deleteCompanies(companyIds: $companyIds)
        }
    """
    
    variables = {"companyIds": company_ids}
    
    logger.warning(f"Deleting {len(company_ids)} companies: {company_ids}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return {"result": data.get("deleteCompanies")}


# ========================================
# 4. RELATIONSHIP TOOLS
# ========================================


async def add_person_to_company(people_id: str, company_id: str, graphql_auth_token: str) -> Dict[str, Any]:
    """
    Link a person to a company, establishing a relationship.
    
    The agent uses this tool to:
    - Connect people to their employers or affiliated companies
    - Build relationship graphs for sales and networking
    - Associate contacts with organizations
    - Track which people belong to which companies
    
    This creates a many-to-many relationship between Person and Company entities.
    A person can belong to multiple companies, and a company can have multiple people.
    
    Relationship metadata:
    - isPeoplePrimary: Whether this is the person's primary company
    - isCompanyPrimary: Whether this is a primary contact for the company
    
    Args:
        people_id: ID of the person to link
        company_id: ID of the company to link
        graphql_auth_token: Authentication token for GraphQL API
    
    Returns:
        Dictionary containing relationship confirmation
    
    Example:
        result = await add_person_to_company("person-123", "company-456")
        # Person is now linked to company
    """
    query = """
        mutation AddPersonToCompany($peopleId: ID!, $companyId: ID!) {
            addPersonToCompany(peopleId: $peopleId, companyId: $companyId)
        }
    """
    
    variables = {
        "peopleId": people_id,
        "companyId": company_id
    }
    
    logger.info(f"Linking person {people_id} to company {company_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return {"result": data.get("addPersonToCompany")}


async def remove_person_from_company(people_id: str, company_id: str, graphql_auth_token: str) -> Dict[str, Any]:
    """
    Unlink a person from a company, removing the relationship.
    
    The agent uses this tool to:
    - Remove outdated relationships (person left company)
    - Correct mistaken associations
    - Clean up relationship data
    
    This removes the link between Person and Company entities without
    deleting either entity. The person and company records remain intact.
    
    Args:
        people_id: ID of the person to unlink
        company_id: ID of the company to unlink from
        graphql_auth_token: Authentication token for GraphQL API
    
    Returns:
        Dictionary containing unlink confirmation
    
    Example:
        result = await remove_person_from_company("person-123", "company-456")
        # Person is no longer linked to company
    """
    query = """
        mutation RemovePersonFromCompany($peopleId: ID!, $companyId: ID!) {
            removePersonFromCompany(peopleId: $peopleId, companyId: $companyId)
        }
    """
    
    variables = {
        "peopleId": people_id,
        "companyId": company_id
    }
    
    logger.info(f"Unlinking person {people_id} from company {company_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return {"result": data.get("removePersonFromCompany")}


# ========================================
# 5. Tool Registry
# ========================================

COMPANY_TOOLS = [
    get_company,
    search_companies,
    list_companies,
    create_company,
    update_company,
    delete_companies,
    add_person_to_company,
    remove_person_from_company,
]
"""
List of all company-related tools available to the agent.

These tools provide comprehensive CRUD operations and relationship management
for Company entities. They cover:
- Read: get_company, search_companies, list_companies
- Write: create_company, update_company, delete_companies
- Relationships: add_person_to_company, remove_person_from_company

Usage:
    from src.tools.company_tools import COMPANY_TOOLS
    
    # Register tools with agent
    for tool in COMPANY_TOOLS:
        agent.register_tool(tool)
"""

