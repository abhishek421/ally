"""
GraphQL-backed tools for Interaction entity operations.

This module provides comprehensive tools for the agent to:
- Fetch interactions (emails, calls, meetings, notes, etc.) for people and companies
- Create manual interactions (calls, meetings, notes)
- Update and delete interactions
- View interaction history and timeline

All tools are async wrappers around GraphQL queries/mutations with no business logic.
They return clean dictionaries that the agent can reason about.

Interaction Types:
- EMAIL: Synced email communications
- CALENDAR: Calendar events
- CALL: Phone calls
- MEETING: In-person or virtual meetings
- NOTE: Manual notes and memos
- SMS: Text messages
- LINKEDIN_MESSAGE: LinkedIn messages
- SOCIAL_MEDIA: Social media interactions

Backend Constraints:
- Exactly ONE of personId or companyId must be provided (XOR constraint)
- Synced emails cannot be deleted (only manual interactions)
- Direction must be INBOUND or OUTBOUND
"""

# ========================================
# 1. Imports
# ========================================

from typing import Dict, Any, Optional

from src.config.logger import logger
from src.tools.graphql_client import gql_request


# ========================================
# 2. READ TOOLS
# ========================================


async def get_person_interactions(
    person_id: str,
    workspace_id: str,
    graphql_auth_token: str,
    limit: int = 20,
    next_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch all interactions (emails + manual interactions) linked to a specific person.
    
    The agent uses this tool to:
    - Display interaction history for a person
    - Review communication timeline
    - Analyze engagement patterns
    - Find specific emails or notes about a person
    
    This returns both synced emails and manually created interactions
    (calls, meetings, notes, etc.) in chronological order.
    
    Backend API: getPersonEmails (despite the name, returns all interaction types)
    
    Args:
        person_id: ID of the person to fetch interactions for
        workspace_id: ID of the workspace
        limit: Maximum number of interactions to return (default: 20)
        next_token: Pagination token for next page of results
    
    Returns:
        Dictionary containing:
        {
            "emails": [  # Note: Contains all interaction types, not just emails
                {
                    "messageId": str,
                    "subject": str or None,
                    "from": str or None,
                    "to": str or None,
                    "direction": str (INBOUND|OUTBOUND),
                    "body": str or None,
                    "bodyHtml": str or None,
                    "date": str (ISO datetime),
                    "threadId": str or None,
                    "participants": [
                        {
                            "email": str,
                            "name": str,
                            "role": str,
                            "relationship": str
                        },
                        ...
                    ],
                    "workspaceId": str,
                    "userId": str,
                    "processed": bool,
                    "createdAt": str,
                    "updatedAt": str,
                    "deleted": bool,
                    "labels": [str, ...],
                    "notes": str or None,
                    "ownerPrivacyLevel": str,
                    "canEdit": bool,
                    "canDelete": bool,
                    "isOwn": bool,
                    "source": str,
                    "interactionType": str,
                    "eventName": str or None,
                    "description": str or None,
                    "dateTime": str or None,
                    "duration": int or None,
                    "personId": str or None,
                    "companyId": str or None,
                    "createdById": str
                },
                ...
            ],
            "totalCount": int,
            "hasNextPage": bool,
            "nextToken": str or None,
            "pagination": {
                "limit": int,
                "offset": int
            }
        }
    
    Example:
        result = await get_person_interactions("person-123", "ws-456", limit=20)
        interactions = result["emails"]
        print(f"Found {result['totalCount']} interactions")
        for interaction in interactions:
            print(f"- {interaction['interactionType']}: {interaction['eventName']}")
    """
    query = """
        query GetPersonEmails(
            $personId: ID!,
            $workspaceId: String!,
            $limit: Int,
            $nextToken: String
        ) {
            getPersonEmails(
                personId: $personId,
                workspaceId: $workspaceId,
                limit: $limit,
                nextToken: $nextToken
            ) {
                emails {
                    messageId
                    subject
                    from
                    to
                    direction
                    body
                    bodyHtml
                    date
                    threadId
                    participants {
                        email
                        name
                        role
                        relationship
                    }
                    workspaceId
                    userId
                    processed
                    createdAt
                    updatedAt
                    deleted
                    labels
                    notes
                    ownerPrivacyLevel
                    canEdit
                    canDelete
                    isOwn
                    source
                    interactionType
                    eventName
                    description
                    dateTime
                    duration
                    personId
                    companyId
                    createdById
                }
                totalCount
                hasNextPage
                nextToken
                pagination {
                    limit
                    offset
                }
            }
        }
    """
    
    variables = {
        "personId": person_id,
        "workspaceId": workspace_id,
        "limit": limit,
        "nextToken": next_token
    }
    
    logger.debug(
        f"Fetching interactions for person {person_id} "
        f"(limit: {limit}, nextToken: {next_token})"
    )
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getPersonEmails", {})


async def get_company_interactions(
    company_id: str,
    workspace_id: str,
    graphql_auth_token: str,
    limit: int = 20,
    next_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch all interactions (emails + manual interactions) linked to a specific company.
    
    The agent uses this tool to:
    - Display interaction history for a company
    - Review communication timeline with the company
    - Analyze engagement patterns
    - Find specific emails or notes about a company
    
    This returns both synced emails and manually created interactions
    (calls, meetings, notes, etc.) in chronological order.
    
    Backend API: getCompanyEmails (despite the name, returns all interaction types)
    
    Args:
        company_id: ID of the company to fetch interactions for
        workspace_id: ID of the workspace
        limit: Maximum number of interactions to return (default: 20)
        next_token: Pagination token for next page of results
    
    Returns:
        Dictionary containing:
        {
            "emails": [  # Note: Contains all interaction types, not just emails
                {
                    "messageId": str,
                    "subject": str or None,
                    "from": str or None,
                    "to": str or None,
                    "direction": str (INBOUND|OUTBOUND),
                    "body": str or None,
                    "bodyHtml": str or None,
                    "date": str (ISO datetime),
                    "threadId": str or None,
                    "participants": [...],
                    "workspaceId": str,
                    "userId": str,
                    "processed": bool,
                    "createdAt": str,
                    "updatedAt": str,
                    "deleted": bool,
                    "labels": [str, ...],
                    "notes": str or None,
                    "ownerPrivacyLevel": str,
                    "canEdit": bool,
                    "canDelete": bool,
                    "isOwn": bool,
                    "source": str,
                    "interactionType": str,
                    "eventName": str or None,
                    "description": str or None,
                    "dateTime": str or None,
                    "duration": int or None,
                    "personId": str or None,
                    "companyId": str or None,
                    "createdById": str
                },
                ...
            ],
            "totalCount": int,
            "hasNextPage": bool,
            "nextToken": str or None,
            "pagination": {
                "limit": int,
                "offset": int
            }
        }
    
    Example:
        result = await get_company_interactions("company-123", "ws-456", limit=20)
        interactions = result["emails"]
        print(f"Found {result['totalCount']} interactions")
    """
    query = """
        query GetCompanyEmails(
            $companyId: ID!,
            $workspaceId: String!,
            $limit: Int,
            $nextToken: String
        ) {
            getCompanyEmails(
                companyId: $companyId,
                workspaceId: $workspaceId,
                limit: $limit,
                nextToken: $nextToken
            ) {
                emails {
                    messageId
                    subject
                    from
                    to
                    direction
                    body
                    bodyHtml
                    date
                    threadId
                    participants {
                        email
                        name
                        role
                        relationship
                    }
                    workspaceId
                    userId
                    processed
                    createdAt
                    updatedAt
                    deleted
                    labels
                    notes
                    ownerPrivacyLevel
                    canEdit
                    canDelete
                    isOwn
                    source
                    interactionType
                    eventName
                    description
                    dateTime
                    duration
                    personId
                    companyId
                    createdById
                }
                totalCount
                hasNextPage
                nextToken
                pagination {
                    limit
                    offset
                }
            }
        }
    """
    
    variables = {
        "companyId": company_id,
        "workspaceId": workspace_id,
        "limit": limit,
        "nextToken": next_token
    }
    
    logger.debug(
        f"Fetching interactions for company {company_id} "
        f"(limit: {limit}, nextToken: {next_token})"
    )
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getCompanyEmails", {})


async def get_interaction(message_id: str, workspace_id: str, graphql_auth_token: str) -> Dict[str, Any]:
    """
    Fetch a single interaction/email by messageId.
    
    The agent uses this tool to:
    - Retrieve full details of a specific interaction
    - Display interaction content to the user
    - Check interaction metadata and permissions
    - Prepare for update or delete operations
    
    This works for both synced emails and manually created interactions.
    
    Args:
        message_id: Unique identifier of the interaction
        workspace_id: ID of the workspace
    
    Returns:
        Dictionary containing full interaction details:
        {
            "messageId": str,
            "subject": str or None,
            "from": str or None,
            "to": str or None,
            "direction": str (INBOUND|OUTBOUND),
            "body": str or None,
            "bodyHtml": str or None,
            "date": str (ISO datetime),
            "threadId": str or None,
            "participants": [
                {
                    "email": str,
                    "name": str,
                    "role": str,
                    "relationship": str
                },
                ...
            ],
            "workspaceId": str,
            "userId": str,
            "processed": bool,
            "createdAt": str,
            "updatedAt": str,
            "deleted": bool,
            "labels": [str, ...],
            "notes": str or None,
            "ownerPrivacyLevel": str,
            "canEdit": bool,
            "canDelete": bool,
            "isOwn": bool,
            "source": str,
            "interactionType": str,
            "eventName": str or None,
            "description": str or None,
            "dateTime": str or None,
            "duration": int or None,
            "personId": str or None,
            "companyId": str or None,
            "createdById": str
        }
    
    Example:
        interaction = await get_interaction("msg-123", "ws-456")
        print(f"Type: {interaction['interactionType']}")
        print(f"Can edit: {interaction['canEdit']}")
        print(f"Can delete: {interaction['canDelete']}")
    """
    query = """
        query GetEmail($messageId: ID!, $workspaceId: String!) {
            getEmail(messageId: $messageId, workspaceId: $workspaceId) {
                messageId
                subject
                from
                to
                direction
                body
                bodyHtml
                date
                threadId
                participants {
                    email
                    name
                    role
                    relationship
                }
                workspaceId
                userId
                processed
                createdAt
                updatedAt
                deleted
                labels
                notes
                ownerPrivacyLevel
                canEdit
                canDelete
                isOwn
                source
                interactionType
                eventName
                description
                dateTime
                duration
                personId
                companyId
                createdById
            }
        }
    """
    
    variables = {
        "messageId": message_id,
        "workspaceId": workspace_id
    }
    
    logger.debug(f"Fetching interaction: {message_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("getEmail", {})


# ========================================
# 3. WRITE TOOLS (Mutations)
# ========================================


async def create_interaction(
    workspace_id: str,
    interaction_type: str,
    event_name: str,
    date_time: str,
    graphql_auth_token: str,
    person_id: Optional[str] = None,
    company_id: Optional[str] = None,
    description: Optional[str] = None,
    duration: Optional[int] = None,
    direction: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a manual interaction (CALL, MEETING, NOTE, SMS, LINKEDIN_MESSAGE, SOCIAL_MEDIA, etc).
    
    CRITICAL BACKEND CONSTRAINT:
    Exactly ONE of personId or companyId must be provided (XOR constraint).
    The planner and validator layers must enforce this before calling this tool.
    
    The agent uses this tool to:
    - Log phone calls with contacts
    - Record meeting notes
    - Document interactions from other channels
    - Track communication history manually
    
    Supported interaction types:
    - CALL: Phone calls
    - MEETING: In-person or virtual meetings
    - NOTE: Manual notes or memos
    - SMS: Text messages
    - LINKEDIN_MESSAGE: LinkedIn messages
    - SOCIAL_MEDIA: Social media interactions
    
    Args:
        workspace_id: ID of the workspace
        interaction_type: Type of interaction (CALL, MEETING, NOTE, SMS, etc.)
        event_name: Title or name of the interaction
        date_time: Date and time of the interaction (ISO datetime format)
        person_id: ID of the person (exactly one of person_id or company_id required)
        company_id: ID of the company (exactly one of person_id or company_id required)
        description: Optional description or notes about the interaction
        duration: Duration in minutes (optional, for calls/meetings)
        direction: Direction of interaction (INBOUND or OUTBOUND, optional)
    
    Returns:
        Dictionary containing the created interaction:
        {
            "messageId": str,
            "eventName": str,
            "interactionType": str,
            "description": str or None,
            "dateTime": str,
            "duration": int or None,
            "direction": str or None,
            "personId": str or None,
            "companyId": str or None,
            "createdById": str,
            "ownerPrivacyLevel": str,
            "canEdit": bool,
            "canDelete": bool,
            "isOwn": bool,
            "source": str
        }
    
    Example:
        interaction = await create_interaction(
            workspace_id="ws-123",
            interaction_type="CALL",
            event_name="Discovery call with John",
            date_time="2024-01-15T10:00:00Z",
            person_id="person-456",
            description="Discussed product requirements",
            duration=30,
            direction="OUTBOUND"
        )
    """
    query = """
        mutation CreateInteraction(
            $workspaceId: String!,
            $interactionType: String!,
            $eventName: String!,
            $dateTime: DateTime!,
            $personId: ID,
            $companyId: ID,
            $description: String,
            $duration: Int,
            $direction: String
        ) {
            createInteraction(
                workspaceId: $workspaceId,
                interactionType: $interactionType,
                eventName: $eventName,
                dateTime: $dateTime,
                personId: $personId,
                companyId: $companyId,
                description: $description,
                duration: $duration,
                direction: $direction
            ) {
                messageId
                eventName
                interactionType
                description
                dateTime
                duration
                direction
                personId
                companyId
                createdById
                ownerPrivacyLevel
                canEdit
                canDelete
                isOwn
                source
            }
        }
    """
    
    variables = {
        "workspaceId": workspace_id,
        "interactionType": interaction_type,
        "eventName": event_name,
        "dateTime": date_time,
        "personId": person_id,
        "companyId": company_id,
        "description": description,
        "duration": duration,
        "direction": direction
    }
    
    logger.info(
        f"Creating {interaction_type} interaction: {event_name} "
        f"(person: {person_id}, company: {company_id})"
    )
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("createInteraction", {})


async def update_interaction(
    interaction_id: str,
    workspace_id: str,
    graphql_auth_token: str,
    interaction_type: Optional[str] = None,
    event_name: Optional[str] = None,
    description: Optional[str] = None,
    date_time: Optional[str] = None,
    duration: Optional[int] = None,
    direction: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update a manual interaction (not synced emails).
    
    WARNING: This tool can only update manually created interactions.
    Synced emails cannot be edited through this API.
    
    The agent uses this tool to:
    - Correct interaction details
    - Update meeting notes or call summaries
    - Change interaction metadata
    
    Only include fields that should be updated in the arguments.
    Omitted optional fields will remain unchanged.
    
    Args:
        interaction_id: ID of the interaction to update
        workspace_id: ID of the workspace
        interaction_type: New interaction type (optional)
        event_name: New event name/title (optional)
        description: New description (optional)
        date_time: New date/time (optional, ISO datetime format)
        duration: New duration in minutes (optional)
        direction: New direction (INBOUND or OUTBOUND, optional)
    
    Returns:
        Dictionary containing the updated interaction details
    
    Example:
        result = await update_interaction(
            interaction_id="msg-123",
            workspace_id="ws-456",
            description="Updated meeting notes with action items",
            duration=45
        )
    """
    query = """
        mutation UpdateInteraction(
            $interactionId: String!,
            $workspaceId: String!,
            $interactionType: String,
            $eventName: String,
            $description: String,
            $dateTime: DateTime,
            $duration: Int,
            $direction: String
        ) {
            updateInteraction(
                interactionId: $interactionId,
                workspaceId: $workspaceId,
                interactionType: $interactionType,
                eventName: $eventName,
                description: $description,
                dateTime: $dateTime,
                duration: $duration,
                direction: $direction
            ) {
                messageId
                eventName
                interactionType
                description
                dateTime
                duration
                direction
                personId
                companyId
                createdById
                ownerPrivacyLevel
                canEdit
                canDelete
                isOwn
                source
            }
        }
    """
    
    variables = {
        "interactionId": interaction_id,
        "workspaceId": workspace_id,
        "interactionType": interaction_type,
        "eventName": event_name,
        "description": description,
        "dateTime": date_time,
        "duration": duration,
        "direction": direction
    }
    
    logger.info(f"Updating interaction: {interaction_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return data.get("updateInteraction", {})


async def delete_interaction(
    interaction_id: str,
    workspace_id: str,
    graphql_auth_token: str
) -> Dict[str, Any]:
    """
    Delete a manual interaction.
    
    IMPORTANT CONSTRAINTS:
    - This is a soft delete (interaction is marked as deleted, not removed)
    - Synced emails CANNOT be deleted through this API
    - Only manually created interactions (calls, meetings, notes) can be deleted
    - Backend enforces permission checks (only owner or admin can delete)
    
    The agent uses this tool to:
    - Remove incorrect or duplicate interactions
    - Clean up test data
    - Delete interactions at user request
    
    Args:
        interaction_id: ID of the interaction to delete
        workspace_id: ID of the workspace
    
    Returns:
        Dictionary containing deletion confirmation
    
    Example:
        result = await delete_interaction("msg-123", "ws-456")
        # Interaction soft-deleted
    """
    query = """
        mutation DeleteInteraction(
            $interactionId: String!,
            $workspaceId: String!
        ) {
            deleteInteraction(
                interactionId: $interactionId,
                workspaceId: $workspaceId
            )
        }
    """
    
    variables = {
        "interactionId": interaction_id,
        "workspaceId": workspace_id
    }
    
    logger.warning(f"Deleting interaction: {interaction_id}")
    
    data = await gql_request(query, variables, auth_token=graphql_auth_token)
    
    return {"result": data.get("deleteInteraction")}


# ========================================
# 4. Tool Registry
# ========================================

INTERACTION_TOOLS = [
    get_person_interactions,
    get_company_interactions,
    get_interaction,
    create_interaction,
    update_interaction,
    delete_interaction,
]
"""
List of all interaction-related tools available to the agent.

These tools provide comprehensive interaction management operations including:
- Read: get_person_interactions, get_company_interactions, get_interaction
- Write: create_interaction, update_interaction, delete_interaction

Important constraints enforced by planner/validator:
- XOR rule: Exactly one of personId or companyId must be provided
- Synced emails cannot be edited or deleted
- Only manual interactions can be modified
- Mutation confirmations required for all write operations

Usage:
    from src.tools.interactions_tools import INTERACTION_TOOLS
    
    # Register tools with agent
    for tool in INTERACTION_TOOLS:
        agent.register_tool(tool)
"""

