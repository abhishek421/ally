"""
GraphQL-backed tools for Person entity operations.

This module provides comprehensive tools for the agent to:
- Read and search person records
- Create, update, and delete people
- Manage person-company relationships
- Handle person metadata and privacy settings

All tools are async wrappers around GraphQL queries/mutations with no business logic.
They return clean dictionaries that the agent can reason about.

Privacy & Permissions:
- People have privacyLevel: PRIVATE (creator only) or PUBLIC (workspace-wide)
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


async def get_person(people_id: str) -> Dict[str, Any]:
    """
    Fetch a single person by ID with full details.
    
    The agent uses this tool to:
    - Retrieve complete person information including metadata
    - Confirm that a person record exists before operations
    - Inspect visibility and privacy level (PRIVATE vs PUBLIC)
    - Prepare for relationship-based actions (view linked companies, groups)
    - Display person details to the user
    
    This tool returns comprehensive person data including:
    - Basic info (name, job title, description, image)
    - Contact details (emails, phones, URLs, addresses)
    - Demographics (gender, date of birth)
    - Privacy settings
    - Related company metadata
    
    Args:
        people_id: Unique identifier of the person
    
    Returns:
        Dictionary containing full person information:
        {
            "id": str,
            "firstName": str,
            "lastName": str or None,
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
            "companyMetaData": [{
                "companyId": str,
                "isPeoplePrimary": bool,
                "isCompanyPrimary": bool
            }, ...],
            "jobTitle": str or None,
            "description": str or None,
            "imageUrl": str or None,
            "gender": str or None,
            "dateOfBirth": str or None
        }
    
    Example:
        person = await get_person("person-123")
        print(f"Person: {person['firstName']} {person['lastName']}")
        print(f"Job: {person['jobTitle']}")
        print(f"Privacy: {person['privacyLevel']}")
        print(f"Linked companies: {len(person['companyMetaData'])}")
    """
    query = """
        query GetPerson($peopleId: ID!) {
            getPerson(peopleId: $peopleId) {
                id
                firstName
                lastName
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
                    line3
                    city
                    state
                    country
                    postalCode
                }
                companyMetaData {
                    companyId
                    isPeoplePrimary
                    isCompanyPrimary
                }
                jobTitle
                description
                imageUrl
                gender
                dateOfBirth
            }
        }
    """
    # Note: Added line3 to addresses in query to be safe, though not in mock return desc
    
    variables = {"peopleId": people_id}
    
    logger.debug(f"Fetching person: {people_id}")
    
    data = await gql_request(query, variables)
    
    return data.get("getPerson", {})


async def search_people(
    workspace_id: str,
    user_id: str,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search people in a workspace with optional text search filter.
    
    The agent uses this tool to:
    - Find people matching user queries ("find John Smith")
    - Filter people by name, job title, or other text fields
    - Browse paginated people lists
    - Display search results to the user
    
    The search parameter performs text matching across person fields like
    firstName, lastName, jobTitle, and description. If omitted, returns
    all accessible people.
    
    Visibility Rules:
    - PUBLIC people are visible to all workspace members
    - PRIVATE people are only visible to their creator
    - Results are automatically filtered by backend based on user_id
    
    Args:
        workspace_id: ID of the workspace to search in
        user_id: ID of the user performing the search (for permission filtering)
        search: Optional text search query to filter results
        page: Page number for pagination (1-indexed, default: 1)
        limit: Number of results per page (default: 10, max recommended: 50)
    
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
        results = await search_people(
            workspace_id="ws-123",
            user_id="user-456",
            search="John",
            page=1,
            limit=10
        )
        print(f"Found {results['meta']['total']} people")
        for person in results['data']:
            print(f"- {person['firstName']} {person['lastName']}")
    """
    query = """
        query GetWorkspacePeople(
            $workspaceId: ID!,
            $userId: ID!,
            $page: Int,
            $limit: Int,
            $search: String
        ) {
            getWorkspacePeople(
                workspaceId: $workspaceId,
                userId: $userId,
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
        "workspaceId": workspace_id,
        "userId": user_id,
        "page": page,
        "limit": limit,
        "search": search
    }
    
    logger.debug(
        f"Searching people in workspace {workspace_id} "
        f"(search: '{search}', page: {page}, limit: {limit})"
    )
    
    data = await gql_request(query, variables)
    
    return data.get("getWorkspacePeople", {})


async def list_people(
    workspace_id: str,
    user_id: str,
    page: int = 1,
    limit: int = 10
) -> Dict[str, Any]:
    """
    List all people in a workspace without search filter.
    
    This is identical to search_people but without the search parameter,
    making it clearer when the agent wants to browse all people rather
    than search for specific ones.
    
    The agent uses this tool to:
    - Display all people the user has access to
    - Get an overview of contacts in the workspace
    - Browse people page by page
    - Count total people in the workspace
    
    Visibility Rules:
    - PUBLIC people are visible to all workspace members
    - PRIVATE people are only visible to their creator
    - Results are automatically filtered by backend based on user_id
    
    Args:
        workspace_id: ID of the workspace to list people from
        user_id: ID of the user performing the listing (for permission filtering)
        page: Page number for pagination (1-indexed, default: 1)
        limit: Number of results per page (default: 10, max recommended: 50)
    
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
        results = await list_people("ws-123", "user-456", page=1, limit=10)
        print(f"Total people: {results['meta']['total']}")
    """
    # Delegate to search_people with no search filter
    return await search_people(
        workspace_id=workspace_id,
        user_id=user_id,
        search=None,
        page=page,
        limit=limit
    )


# ========================================
# 3. WRITE TOOLS (Mutations)
# ========================================


async def create_person(
    input: Dict[str, Any],
    user_id: str,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new person in the workspace.
    
    WARNING: This tool must only be used after the validator node confirms
    user intent and approval. The agent will always preview the person data
    to the user before calling this mutation.
    
    The agent uses this tool to:
    - Create people from user natural language input
    - Add contacts mentioned in conversation
    - Import person data from external sources
    - Initialize person records for relationship mapping
    
    Required fields in input:
    - firstName: Person's first name (required)
    - workspaceId: Workspace to create in (required)
    - privacyLevel: PRIVATE or PUBLIC (required)
    
    Optional fields in input:
    - lastName: Person's last name
    - jobTitle: Job title or role
    - description: Person description or notes
    - emails: [{"email": str, "type": str}, ...]
    - phoneNumbers: [{"phone": str, "type": str}, ...]
    - urls: [{"url": str, "type": str}, ...]
    - addresses: [{city, state, country, ...}, ...]
    - imageUrl: Profile picture URL
    - gender: Gender identifier
    - dateOfBirth: Date of birth (ISO format)
    
    Args:
        input: Person creation input matching CreatePeopleInput schema
        user_id: ID of the user creating the person
        group_id: Optional group ID to add the person to
    
    Returns:
        Dictionary containing the created person ID or success confirmation
    
    Example:
        result = await create_person(
            input={
                "firstName": "John",
                "lastName": "Smith",
                "workspaceId": "ws-123",
                "privacyLevel": "PUBLIC",
                "jobTitle": "CEO",
                "emails": [{"email": "john@example.com", "type": "work"}]
            },
            user_id="user-456"
        )
    """
    query = """
        mutation CreatePerson($input: CreatePeopleInput!, $userId: ID!, $groupId: ID) {
            createPerson(input: $input, userId: $userId, groupId: $groupId)
        }
    """
    
    variables = {
        "input": input,
        "userId": user_id,
        "groupId": group_id
    }
    
    logger.info(
        f"Creating person: {input.get('firstName', 'Unknown')} {input.get('lastName', '')}"
    )
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("createPerson")}


async def update_person(input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing person's information.
    
    WARNING: This tool must only be used after the validator node confirms
    user intent and approval. Changes should be previewed to the user first.
    
    The agent uses this tool to:
    - Modify person details based on user requests
    - Correct inaccurate person information
    - Update contact information (emails, phones, addresses)
    - Change job title, description, or other metadata
    - Change privacy level
    
    Required fields in input:
    - id: Person ID to update (required)
    
    Optional fields in input (only include fields to update):
    - firstName, lastName: Updated name
    - jobTitle: New job title
    - description: New description
    - privacyLevel: New privacy level (PRIVATE|PUBLIC)
    - emails, phoneNumbers, urls, addresses: Updated contact info
    - imageUrl: New profile picture URL
    - gender, dateOfBirth: Updated demographics
    
    Args:
        input: Person update input matching UpdatePeopleInput schema
    
    Returns:
        Dictionary containing update confirmation or updated person data
    
    Example:
        result = await update_person(
            input={
                "id": "person-123",
                "jobTitle": "Senior Engineer",
                "privacyLevel": "PUBLIC"
            }
        )
    """
    query = """
        mutation UpdatePerson($input: UpdatePeopleInput!) {
            updatePerson(input: $input)
        }
    """
    
    variables = {"input": input}
    
    logger.info(f"Updating person: {input.get('id', 'Unknown')}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("updatePerson")}


async def delete_people(people_ids: List[str]) -> Dict[str, Any]:
    """
    Delete one or multiple people from the workspace.
    
    WARNING: This is a destructive operation that must only be used after
    explicit user confirmation. The validator node must confirm intent.
    
    The agent uses this tool to:
    - Remove people at user request
    - Clean up duplicate or test records
    - Bulk delete multiple people
    
    Deletion behavior:
    - Permanently removes person records
    - May cascade to related records (relationships, interactions)
    - Cannot be undone
    - Backend enforces permission checks (only creator or admin can delete)
    
    Args:
        people_ids: List of person IDs to delete
    
    Returns:
        Dictionary containing deletion confirmation
    
    Example:
        result = await delete_people(["person-123", "person-456"])
        # People deleted permanently
    """
    query = """
        mutation DeletePeoples($peopleIds: [ID]!) {
            deletePeoples(peopleIds: $peopleIds)
        }
    """
    
    variables = {"peopleIds": people_ids}
    
    logger.warning(f"Deleting {len(people_ids)} people: {people_ids}")
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("deletePeoples")}


# ========================================
# 4. RELATIONSHIP TOOLS
# ========================================


async def add_company_to_person(people_id: str, company_id: str) -> Dict[str, Any]:
    """
    Link a person to a company, establishing a relationship.
    
    The agent uses this tool to:
    - Connect people to their employers or affiliated companies
    - Build relationship graphs for sales and networking
    - Associate contacts with organizations
    - Track which companies a person is affiliated with
    
    This creates a many-to-many relationship between Person and Company entities.
    A person can belong to multiple companies, and a company can have multiple people.
    
    Relationship metadata:
    - isPeoplePrimary: Whether this is the person's primary company
    - isCompanyPrimary: Whether this is a primary contact for the company
    
    Note: This uses the same GraphQL mutation as add_person_to_company,
    just from the person-centric perspective.
    
    Args:
        people_id: ID of the person to link
        company_id: ID of the company to link
    
    Returns:
        Dictionary containing relationship confirmation
    
    Example:
        result = await add_company_to_person("person-123", "company-456")
        # Person is now affiliated with company
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
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("addPersonToCompany")}


async def remove_company_from_person(people_id: str, company_id: str) -> Dict[str, Any]:
    """
    Unlink a person from a company, removing the relationship.
    
    The agent uses this tool to:
    - Remove outdated relationships (person left company)
    - Correct mistaken associations
    - Clean up relationship data
    
    This removes the link between Person and Company entities without
    deleting either entity. The person and company records remain intact.
    
    Note: This uses the same GraphQL mutation as remove_person_from_company,
    just from the person-centric perspective.
    
    Args:
        people_id: ID of the person to unlink
        company_id: ID of the company to unlink from
    
    Returns:
        Dictionary containing unlink confirmation
    
    Example:
        result = await remove_company_from_person("person-123", "company-456")
        # Person is no longer affiliated with company
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
    
    data = await gql_request(query, variables)
    
    return {"result": data.get("removePersonFromCompany")}


# ========================================
# 5. Tool Registry
# ========================================

PEOPLE_TOOLS = [
    get_person,
    search_people,
    list_people,
    create_person,
    update_person,
    delete_people,
    add_company_to_person,
    remove_company_from_person,
]
"""
List of all people-related tools available to the agent.

These tools provide comprehensive CRUD operations and relationship management
for Person entities. They cover:
- Read: get_person, search_people, list_people
- Write: create_person, update_person, delete_people
- Relationships: add_company_to_person, remove_company_from_person

Usage:
    from src.tools.people_tools import PEOPLE_TOOLS
    
    # Register tools with agent
    for tool in PEOPLE_TOOLS:
        agent.register_tool(tool)
"""
