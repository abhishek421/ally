# AI Analyst Tools - Complete Specification for Python Implementation

This document provides a comprehensive specification of all AI Analyst tools in the SoftSync CRM system. Use this specification to implement equivalent tools in Python for LLM function calling.

## Table of Contents

1. [Overview](#overview)
2. [Data Models](#data-models)
3. [People Query Functions](#people-query-functions)
4. [Company Query Functions](#company-query-functions)
5. [Deal Query Functions](#deal-query-functions)
6. [Interaction Query Functions](#interaction-query-functions)
7. [Contact Search Functions](#contact-search-functions)
8. [Analytics Functions](#analytics-functions)
9. [Deal Analysis Functions](#deal-analysis-functions)
10. [Context Query Functions](#context-query-functions)
11. [Utility Query Functions](#utility-query-functions)

---

## Overview

The AI Analyst system provides a comprehensive set of query and analysis functions that allow an LLM to interact with CRM data. All functions operate within a workspace context and require proper authentication. Functions are designed to be:

- **Idempotent**: Safe to call multiple times
- **Read-only**: No data modification (except where explicitly noted)
- **Context-aware**: All operations are scoped to a workspace
- **Efficient**: Support pagination, filtering, and selective data loading

### Core Context

Every function receives an `AIAnalystContext` object containing:
- `workspaceId` (string, required): The workspace identifier
- `userId` (string, required): The user making the request
- `conversationId` (string, optional): Current conversation ID
- `sessionId` (string, optional): Current session ID

---

## Data Models

### Person

```python
{
    "id": "uuid",
    "firstName": "string",
    "lastName": "string | null",
    "jobTitle": "string | null",
    "description": "string | null",
    "dateOfBirth": "datetime | null",
    "gender": "string | null",
    "imageUrl": "string | null",
    "privacyLevel": "PRIVATE | PUBLIC | null",
    "createdAt": "datetime",
    "updatedAt": "datetime",
    "workspaceId": "uuid",
    "createdBy": "uuid"
}
```

### Company

```python
{
    "id": "uuid",
    "name": "string",
    "description": "string | null",
    "imageUrl": "string | null",
    "privacyLevel": "PRIVATE | PUBLIC | null",
    "createdAt": "datetime",
    "updatedAt": "datetime",
    "workspaceId": "uuid",
    "createdBy": "uuid"
}
```

### Deal

```python
{
    "id": "uuid",
    "name": "string",
    "columnId": "uuid",  # Represents the stage/column
    "createdAt": "datetime",
    "updatedAt": "datetime",
    "createdBy": "uuid | null"
}
```

### Interaction

```python
{
    "id": "uuid",
    "type": "EMAIL | CALENDAR | CALL | MEETING | NOTE | SMS | LINKEDIN_MESSAGE | SOCIAL_MEDIA",
    "direction": "INBOUND | OUTBOUND",
    "subject": "string | null",
    "content": "string | null",
    "date": "datetime",
    "metadata": "dict | null",
    "isDeleted": "bool",
    "createdAt": "datetime",
    "updatedAt": "datetime",
    "workspaceId": "uuid",
    "createdById": "uuid",
    "peopleId": "uuid | null",
    "companyId": "uuid | null",
    "externalId": "string | null",
    "externalType": "string | null"
}
```

### Email

```python
{
    "id": "uuid",
    "value": "string",
    "type": "personal | work | other | null",
    "isPrimary": "bool",
    "verified": "bool",
    "personId": "uuid | null",
    "companyId": "uuid | null",
    "createdAt": "datetime",
    "updatedAt": "datetime"
}
```

### PhoneNumber

```python
{
    "id": "uuid",
    "value": "string",
    "type": "mobile | work | home | other | null",
    "isPrimary": "bool",
    "personId": "uuid | null",
    "companyId": "uuid | null",
    "createdAt": "datetime",
    "updatedAt": "datetime"
}
```

### Address

```python
{
    "id": "uuid",
    "value": "string | null",
    "type": "home | work | other | null",
    "isPrimary": "bool",
    "personId": "uuid | null",
    "companyId": "uuid | null",
    "createdAt": "datetime",
    "updatedAt": "datetime"
}
```

### URL

```python
{
    "id": "uuid",
    "label": "string | null",
    "value": "string",
    "isPrimary": "bool",
    "personId": "uuid | null",
    "companyId": "uuid | null",
    "createdAt": "datetime",
    "updatedAt": "datetime"
}
```

### Group

```python
{
    "id": "uuid",
    "name": "string",
    "type": "PEOPLE | COMPANY | DEAL",
    "description": "string | null",
    "emoji": "string | null",
    "isPrivate": "bool",
    "isFavourite": "bool",
    "isDeleted": "bool",
    "isCollapse": "bool",
    "createdAt": "datetime",
    "updatedAt": "datetime",
    "workspaceId": "uuid",
    "createdBy": "uuid",
    "favouriteOrder": "int",
    "privateOrder": "int",
    "publicOrder": "int"
}
```

### Column

```python
{
    "id": "uuid",
    "name": "string",
    "description": "string | null",
    "dataType": "TEXT | NUMBER | DATE | BOOLEAN | JSON | MULTISELECT | SELECT | DEALS | LARGE_TEXT | MEMBER | CONTACT | URL | PHONE_NUMBERS | EMAILS | ADDRESS | LONG_TEXT | GROUPS | CREATED_BY | GROUP_ADDED_AT | COMPANIES | PEOPLE | MAGIC_FIELD",
    "isDefault": "bool",
    "type": "COMPANY | PEOPLE | DEAL",
    "isDeleted": "bool",
    "createdAt": "datetime",
    "updatedAt": "datetime",
    "groupId": "uuid",
    "dealId": "uuid | null",
    "selectOptions": "dict | null"
}
```

---

## People Query Functions

### 1. searchPeople

**Purpose**: Search for people by name, email, job title, company, group, or other criteria.

**Input Parameters**:
```python
{
    "query": "string | null",  # Search term for name, email, job title
    "email": "string | null",  # Exact email match
    "jobTitle": "string | null",  # Job title filter
    "companyId": "uuid | null",  # Filter by company
    "groupId": "uuid | null",  # Filter by group
    "tags": "list[string] | null",  # Filter by tags
    "customFields": "dict | null",  # Custom field filters
    "hasInteractionsSince": "datetime | null",  # Filter by interaction date
    "sortBy": "name | createdAt | lastInteraction | interactionCount | null",
    "sortOrder": "asc | desc | null",  # Default: desc
    "limit": "int | null",  # Default: 20, max: 100
    "offset": "int | null"  # Default: 0
}
```

**Output**:
```python
{
    "results": [
        {
            "id": "uuid",
            "firstName": "string",
            "lastName": "string | null",
            "jobTitle": "string | null",
            "description": "string | null",
            "createdAt": "datetime",
            "updatedAt": "datetime",
            "workspaceId": "uuid",
            "createdBy": "uuid",
            "privacyLevel": "PRIVATE | PUBLIC | null"
        }
    ],
    "total": "int",
    "hasMore": "bool"
}
```

**Business Logic**:
- Build WHERE clause with workspaceId filter
- If `query` provided, search in firstName, lastName, jobTitle, and email values (case-insensitive)
- If `email` provided, match exact email (case-insensitive)
- If `jobTitle` provided, filter by job title (case-insensitive contains)
- If `companyId` provided, filter by people linked to that company via metadata
- If `groupId` provided, filter by people in that group
- If `tags` provided, filter by tags (array contains)
- If `hasInteractionsSince` provided, filter by people with interactions after that date
- Apply sorting based on `sortBy` parameter
- Apply pagination with `limit` and `offset`
- Return total count for pagination

**Database Queries**:
- Use case-insensitive text search (ILIKE in PostgreSQL, or equivalent)
- Join with emails, phoneNumbers, and interaction tables for filtering
- Count total matching records
- Fetch limited results with includes for primary email/phone

---

### 2. getPersonById

**Purpose**: Get complete person profile with optional related data.

**Input Parameters**:
```python
{
    "personId": "uuid",  # Required
    "include": {
        "companies": "bool | null",
        "primaryCompany": "bool | null",
        "deals": "bool | null",
        "recentInteractions": "int | null",  # Number of interactions to include
        "emails": "bool | null",
        "phones": "bool | null",
        "addresses": "bool | null",
        "urls": "bool | null",
        "customFields": "bool | null",
        "groups": "bool | null"
    } | null
}
```

**Output**:
```python
{
    "person": {
        # Person object (see Data Models)
    },
    "companies": [
        {
            "company": {
                # Company object
            },
            "isPrimary": "bool",
            "relationship": "current | past | other",
            "metadata": {
                "isPeoplePrimary": "bool",
                "isCompanyPrimary": "bool",
                "createdAt": "datetime",
                "updatedAt": "datetime"
            } | null
        }
    ] | null,
    "primaryCompany": {
        # Company object
    } | null,
    "deals": [
        {
            "deal": {
                # Deal object
            },
            "role": "string | null",
            "company": {
                # Company object
            } | null,
            "stage": {
                "columnId": "uuid",
                "columnName": "string",
                "groupId": "uuid",
                "groupName": "string"
            }
        }
    ] | null,
    "interactions": [
        # Interaction objects
    ] | null,
    "emails": [
        # Email objects
    ] | null,
    "phones": [
        # PhoneNumber objects
    ] | null,
    "addresses": [
        # Address objects
    ] | null,
    "urls": [
        # URL objects
    ] | null,
    "customFields": "dict | null",
    "groups": [
        # Group objects
    ] | null
}
```

**Business Logic**:
- Fetch person by ID and workspaceId (must match)
- If `include.companies` or `include.primaryCompany`, fetch company relationships via metadata table
- Determine primary company based on metadata flags
- If `include.deals`, fetch deals linked to person via dealMetaData
- If `include.recentInteractions` specified, fetch N most recent interactions
- If `include.emails`, fetch all emails (otherwise just primary)
- If `include.phones`, fetch all phone numbers (otherwise just primary)
- If `include.addresses`, fetch all addresses (otherwise just primary)
- If `include.urls`, fetch all URLs (otherwise just primary)
- If `include.customFields`, fetch column values for custom fields
- If `include.groups`, fetch groups person belongs to

**Database Queries**:
- Main query: SELECT person WHERE id = ? AND workspaceId = ?
- Conditional joins based on include flags
- Use metadata table to link people to companies
- Use dealMetaData table to link people to deals

---

### 3. getPersonCompanies

**Purpose**: Get all companies associated with a person.

**Input Parameters**:
```python
{
    "personId": "uuid",  # Required
    "currentOnly": "bool | null",  # Default: false
    "includePrimary": "bool | null",  # Default: true
    "includeMetadata": "bool | null"  # Default: false
}
```

**Output**:
```python
{
    "companies": [
        {
            "company": {
                # Company object
            },
            "isPrimary": "bool",
            "relationship": "current | past | other",
            "metadata": {
                "isPeoplePrimary": "bool",
                "isCompanyPrimary": "bool",
                "createdAt": "datetime",
                "updatedAt": "datetime"
            } | null
        }
    ]
}
```

**Business Logic**:
- Fetch all metadata records linking person to companies
- Filter by `currentOnly` if specified (requires relationship field)
- Determine primary company based on metadata flags
- Include metadata if `includeMetadata` is true

---

### 4. getPersonDeals

**Purpose**: Get all deals associated with a person.

**Input Parameters**:
```python
{
    "personId": "uuid",  # Required
    "status": "active | won | lost | all | null",  # Default: all
    "columnId": "uuid | null",  # Filter by stage
    "groupId": "uuid | null",  # Filter by group
    "sortBy": "createdAt | updatedAt | value | null",
    "limit": "int | null"
}
```

**Output**:
```python
{
    "deals": [
        {
            "deal": {
                # Deal object
            },
            "role": "string | null",
            "company": {
                # Company object
            } | null,
            "stage": {
                "columnId": "uuid",
                "columnName": "string",
                "groupId": "uuid",
                "groupName": "string"
            }
        }
    ],
    "total": "int"
}
```

**Business Logic**:
- Fetch deals linked to person via dealMetaData
- Filter by status if specified (requires deal status field or column mapping)
- Filter by columnId (stage) if specified
- Filter by groupId if specified
- Sort by specified field
- Include associated company if available
- Include stage information (column and group)

---

### 5. getPersonInteractions

**Purpose**: Get interactions for a person with filtering and statistics.

**Input Parameters**:
```python
{
    "personId": "uuid",  # Required
    "type": "InteractionType | list[InteractionType] | null",
    "direction": "INBOUND | OUTBOUND | both | null",  # Default: both
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "limit": "int | null",  # Default: 20
    "offset": "int | null",  # Default: 0
    "sortBy": "date | createdAt | null",  # Default: date
    "sortOrder": "asc | desc | null",  # Default: desc
    "includeContent": "bool | null"  # Default: true
}
```

**Output**:
```python
{
    "interactions": [
        # Interaction objects
    ],
    "total": "int",
    "summary": {
        "totalCount": "int",
        "byType": {
            "EMAIL": "int",
            "CALL": "int",
            "MEETING": "int",
            # ... other types
        },
        "byDirection": {
            "inbound": "int",
            "outbound": "int"
        },
        "lastInteractionDate": "datetime | null",
        "averageResponseTime": "float | null"  # In hours
    }
}
```

**Business Logic**:
- Fetch interactions where peopleId = personId
- Filter by type if specified (can be single or array)
- Filter by direction if specified (exclude 'both')
- Filter by date range if specified
- Calculate summary statistics:
  - Count by type
  - Count by direction
  - Find most recent interaction date
  - Calculate average response time (requires pairing inbound/outbound interactions)
- Apply pagination
- Sort by date or createdAt

---

### 6. getPersonTimeline

**Purpose**: Get chronological timeline of person's activities.

**Input Parameters**:
```python
{
    "personId": "uuid",  # Required
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "includeTypes": [
        "interaction",
        "deal_created",
        "deal_updated",
        "deal_won",
        "deal_lost",
        "note_added"
    ] | null,  # Default: all
    "limit": "int | null"
}
```

**Output**:
```python
{
    "timeline": [
        {
            "timestamp": "datetime",
            "type": "interaction | deal_created | deal_updated | deal_won | deal_lost | note_added",
            "entity": {
                # Interaction, Deal, or Note object
            },
            "summary": "string"  # Human-readable summary
        }
    ],
    "total": "int"
}
```

**Business Logic**:
- Fetch interactions, deal changes, and notes for the person
- Merge all events into single timeline
- Sort by timestamp (most recent first)
- Generate human-readable summary for each event
- Filter by date range if specified
- Filter by includeTypes if specified
- Apply limit

---

## Company Query Functions

### 1. searchCompanies

**Purpose**: Search for companies by name, industry, size, or other criteria.

**Input Parameters**:
```python
{
    "query": "string | null",  # Search term for name, description, email
    "industry": "string | null",  # Industry filter
    "size": "string | null",  # Company size filter
    "tags": "list[string] | null",
    "customFields": "dict | null",
    "hasInteractionsSince": "datetime | null",
    "hasDealsSince": "datetime | null",
    "sortBy": "name | createdAt | lastInteraction | dealValue | null",
    "sortOrder": "asc | desc | null",
    "limit": "int | null",  # Default: 20, max: 100
    "offset": "int | null"  # Default: 0
}
```

**Output**:
```python
{
    "results": [
        # Company objects
    ],
    "total": "int",
    "hasMore": "bool"
}
```

**Business Logic**:
- Similar to searchPeople but for companies
- Search in name, description, and email values
- Filter by industry and size if provided
- Filter by interactions or deals if date provided
- Sort by specified field

---

### 2. getCompanyById

**Purpose**: Get complete company profile with optional related data.

**Input Parameters**:
```python
{
    "companyId": "uuid",  # Required
    "include": {
        "people": "bool | null",
        "keyContacts": "int | null",  # Number of key contacts to include
        "deals": "bool | null",
        "recentInteractions": "int | null",
        "emails": "bool | null",
        "phones": "bool | null",
        "addresses": "bool | null",
        "urls": "bool | null",
        "customFields": "bool | null",
        "groups": "bool | null"
    } | null
}
```

**Output**:
```python
{
    "company": {
        # Company object
    },
    "people": [
        # Person objects
    ] | null,
    "keyContacts": [
        {
            "person": {
                # Person object
            },
            "engagementScore": "float",  # Calculated based on interactions
            "interactionCount": "int",
            "lastInteraction": "datetime | null"
        }
    ] | null,
    "deals": [
        # Deal objects
    ] | null,
    "interactions": [
        # Interaction objects
    ] | null,
    "emails": [
        # Email objects
    ] | null,
    "phones": [
        # PhoneNumber objects
    ] | null,
    "addresses": [
        # Address objects
    ] | null,
    "urls": [
        # URL objects
    ] | null,
    "customFields": "dict | null",
    "groups": [
        # Group objects
    ] | null
}
```

**Business Logic**:
- Fetch company by ID and workspaceId
- If `include.people`, fetch all people linked via metadata
- If `include.keyContacts`, fetch top N people by engagement (interaction count, recency)
- Calculate engagement score based on:
  - Number of interactions
  - Recency of last interaction
  - Interaction types (meetings > calls > emails)
- Include deals, interactions, contact info as specified

---

### 3. getCompanyPeople

**Purpose**: Get all people associated with a company.

**Input Parameters**:
```python
{
    "companyId": "uuid",  # Required
    "currentOnly": "bool | null",  # Default: false
    "roles": "list[string] | null",  # Filter by job titles/roles
    "sortBy": "name | lastInteraction | interactionCount | null",
    "limit": "int | null"
}
```

**Output**:
```python
{
    "people": [
        {
            "person": {
                # Person object
            },
            "isPrimary": "bool",
            "jobTitle": "string | null",
            "interactionCount": "int",
            "lastInteraction": "datetime | null"
        }
    ],
    "total": "int",
    "summary": {
        "totalEmployees": "int",
        "keyContacts": "int",  # People with > 0 interactions
        "decisionMakers": "int"  # People with executive titles
    }
}
```

**Business Logic**:
- Fetch people linked to company via metadata
- Filter by currentOnly if specified
- Filter by roles/job titles if specified
- Calculate interaction counts and last interaction dates
- Identify primary contact
- Generate summary statistics

---

### 4. getCompanyDeals

**Purpose**: Get all deals associated with a company.

**Input Parameters**:
```python
{
    "companyId": "uuid",  # Required
    "status": "active | won | lost | all | null",
    "columnId": "uuid | null",
    "groupId": "uuid | null",
    "sortBy": "createdAt | updatedAt | value | null",
    "limit": "int | null",
    "includeContacts": "bool | null"  # Include people on deals
}
```

**Output**:
```python
{
    "deals": [
        {
            "deal": {
                # Deal object
            },
            "stage": {
                "columnId": "uuid",
                "columnName": "string",
                "groupId": "uuid",
                "groupName": "string"
            },
            "contacts": [
                # Person objects
            ] | null,
            "value": "float | null"
        }
    ],
    "total": "int",
    "summary": {
        "totalValue": "float",
        "activeDeals": "int",
        "wonDeals": "int",
        "lostDeals": "int",
        "averageDealSize": "float"
    }
}
```

**Business Logic**:
- Fetch deals linked to company via dealMetaData
- Filter by status, stage, group if specified
- Include contacts if requested
- Calculate deal values (from columnValues)
- Generate summary statistics

---

### 5. getCompanyInteractions

**Purpose**: Get interactions for a company (and optionally employees).

**Input Parameters**:
```python
{
    "companyId": "uuid",  # Required
    "includeEmployeeInteractions": "bool | null",  # Default: false
    "type": "InteractionType | list[InteractionType] | null",
    "direction": "INBOUND | OUTBOUND | both | null",
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "limit": "int | null",
    "offset": "int | null",
    "groupBy": "person | type | date | null"
}
```

**Output**:
```python
{
    "interactions": [
        # Interaction objects
    ],
    "total": "int",
    "summary": {
        "companyLevel": "int",  # Interactions directly with company
        "employeeLevel": "int",  # Interactions with employees
        "byType": {
            # InteractionType -> count
        },
        "byPerson": {
            # personId -> count
        } | null,
        "lastInteractionDate": "datetime | null"
    }
}
```

**Business Logic**:
- Fetch interactions where companyId = companyId
- If `includeEmployeeInteractions`, also fetch interactions for all people at company
- Filter by type, direction, date range
- Group results if `groupBy` specified
- Calculate summary statistics

---

### 6. getCompanyTimeline

**Purpose**: Get chronological timeline of company activities.

**Input Parameters**:
```python
{
    "companyId": "uuid",  # Required
    "includeEmployeeActivity": "bool | null",  # Default: false
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "includeTypes": [
        "interaction",
        "deal_created",
        "deal_updated",
        "deal_won",
        "deal_lost",
        "person_added"
    ] | null,
    "limit": "int | null"
}
```

**Output**:
```python
{
    "timeline": [
        {
            "timestamp": "datetime",
            "type": "string",
            "entity": {
                # Interaction, Deal, or Person object
            },
            "summary": "string",
            "relatedPerson": {
                # Person object
            } | null
        }
    ],
    "total": "int"
}
```

**Business Logic**:
- Similar to getPersonTimeline but for company
- Include employee activity if requested
- Merge all events chronologically

---

## Deal Query Functions

### 1. searchDeals

**Purpose**: Search for deals by name, stage, value, or other criteria.

**Input Parameters**:
```python
{
    "query": "string | null",  # Search term for deal name
    "columnId": "uuid | null",  # Filter by stage/column
    "columnIds": "list[uuid] | null",  # Filter by multiple stages
    "groupId": "uuid | null",  # Filter by group
    "companyId": "uuid | null",  # Filter by company
    "personId": "uuid | null",  # Filter by person
    "minValue": "float | null",
    "maxValue": "float | null",
    "createdAfter": "datetime | null",
    "createdBefore": "datetime | null",
    "customFields": "dict | null",
    "sortBy": "createdAt | updatedAt | value | name | null",
    "sortOrder": "asc | desc | null",
    "limit": "int | null",  # Default: 20, max: 100
    "offset": "int | null"  # Default: 0
}
```

**Output**:
```python
{
    "results": [
        # Deal objects
    ],
    "total": "int",
    "hasMore": "bool",
    "summary": {
        "totalValue": "float",
        "averageValue": "float",
        "byStage": {
            # columnId -> count
        }
    }
}
```

**Business Logic**:
- Search deals by name (case-insensitive)
- Filter by columnId(s) for stage filtering
- Filter by groupId, companyId, personId via relationships
- Filter by value range if specified
- Filter by creation date range
- Extract deal values from columnValues
- Calculate summary statistics

---

### 2. getDealById

**Purpose**: Get complete deal information with related data.

**Input Parameters**:
```python
{
    "dealId": "uuid",  # Required
    "include": {
        "people": "bool | null",
        "companies": "bool | null",
        "interactions": "int | null",  # Number of interactions
        "columnValues": "bool | null",
        "stageHistory": "bool | null",  # Stage transition history
        "notes": "bool | null"
    } | null
}
```

**Output**:
```python
{
    "deal": {
        # Deal object
    },
    "stage": {
        "column": {
            # Column object
        },
        "group": {
            # Group object
        }
    },
    "people": [
        # Person objects
    ] | null,
    "companies": [
        # Company objects
    ] | null,
    "interactions": [
        # Interaction objects
    ] | null,
    "columnValues": [
        {
            "columnId": "uuid",
            "columnName": "string",
            "value": "any"
        }
    ] | null,
    "stageHistory": [
        {
            "fromColumn": {
                # Column object
            } | null,
            "toColumn": {
                # Column object
            },
            "movedAt": "datetime",
            "movedBy": "uuid | null",
            "daysInPreviousStage": "int | null"
        }
    ] | null,
    "notes": [
        # Note objects
    ] | null,
    "metadata": {
        "daysInCurrentStage": "int",
        "totalDaysInPipeline": "int",
        "createdBy": "uuid | null"
    }
}
```

**Business Logic**:
- Fetch deal by ID
- Include stage information (column and group)
- Fetch related people and companies via dealMetaData
- Fetch interactions if specified
- Fetch all column values for custom fields
- Calculate stage history if requested (requires audit log or history table)
- Calculate metadata: days in current stage, total days in pipeline

---

### 3. getDealPeople

**Purpose**: Get all people associated with a deal.

**Input Parameters**:
```python
{
    "dealId": "uuid",  # Required
    "includeInteractions": "bool | null"  # Default: false
}
```

**Output**:
```python
{
    "people": [
        {
            "person": {
                # Person object
            },
            "company": {
                # Company object
            } | null,
            "role": "string | null",
            "interactionCount": "int | null",
            "lastInteraction": "datetime | null"
        }
    ],
    "total": "int"
}
```

**Business Logic**:
- Fetch people linked to deal via dealMetaData
- Include company if person has company relationship
- Calculate interaction counts if requested

---

### 4. getDealCompanies

**Purpose**: Get all companies associated with a deal.

**Input Parameters**:
```python
{
    "dealId": "uuid"  # Required
}
```

**Output**:
```python
{
    "companies": [
        {
            "company": {
                # Company object
            },
            "isPrimary": "bool | null"
        }
    ]
}
```

**Business Logic**:
- Fetch companies linked to deal via dealMetaData
- Determine primary company if applicable

---

### 5. getDealInteractions

**Purpose**: Get interactions related to a deal.

**Input Parameters**:
```python
{
    "dealId": "uuid",  # Required
    "type": "InteractionType | list[InteractionType] | null",
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "limit": "int | null",
    "offset": "int | null"
}
```

**Output**:
```python
{
    "interactions": [
        {
            "interaction": {
                # Interaction object
            },
            "relatedPerson": {
                # Person object
            } | null,
            "relatedCompany": {
                # Company object
            } | null
        }
    ],
    "total": "int",
    "summary": {
        "byType": {
            # InteractionType -> count
        },
        "byPerson": {
            # personId -> count
        },
        "lastInteractionDate": "datetime | null",
        "daysSinceLastInteraction": "int"
    }
}
```

**Business Logic**:
- Fetch interactions for people/companies on the deal
- Filter by type and date range
- Include related person and company
- Calculate summary statistics

---

## Interaction Query Functions

### 1. searchInteractions

**Purpose**: Search for interactions by content, type, date, or related entities.

**Input Parameters**:
```python
{
    "query": "string | null",  # Search in subject and content
    "type": "InteractionType | list[InteractionType] | null",
    "direction": "INBOUND | OUTBOUND | both | null",
    "personId": "uuid | null",
    "companyId": "uuid | null",
    "createdBy": "uuid | null",
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "hasContent": "bool | null",  # Only interactions with content
    "sortBy": "date | createdAt | null",
    "sortOrder": "asc | desc | null",
    "limit": "int | null",  # Default: 20, max: 100
    "offset": "int | null"  # Default: 0
}
```

**Output**:
```python
{
    "results": [
        # Interaction objects
    ],
    "total": "int",
    "hasMore": "bool",
    "summary": {
        "byType": {
            # InteractionType -> count
        },
        "byDirection": {
            "inbound": "int",
            "outbound": "int"
        }
    }
}
```

**Business Logic**:
- Search in subject and content fields (case-insensitive)
- Filter by type, direction, person, company, creator
- Filter by date range
- Filter by hasContent if specified
- Calculate summary statistics
- Apply pagination

---

### 2. getInteractionById

**Purpose**: Get complete interaction details.

**Input Parameters**:
```python
{
    "interactionId": "uuid",  # Required
    "include": {
        "person": "bool | null",
        "company": "bool | null",
        "relatedDeals": "bool | null"
    } | null
}
```

**Output**:
```python
{
    "interaction": {
        # Interaction object
    },
    "person": {
        # Person object
    } | null,
    "company": {
        # Company object
    } | null,
    "relatedDeals": [
        # Deal objects
    ] | null
}
```

**Business Logic**:
- Fetch interaction by ID
- Include related person and company if requested
- Find related deals via person/company relationships

---

## Contact Search Functions

### 1. searchContacts

**Purpose**: Unified search for both people and companies.

**Input Parameters**:
```python
{
    "query": "string",  # Required - search term
    "type": "people | companies | both | null",  # Default: both
    "filters": "dict | null",  # Additional filters
    "limit": "int | null"  # Default: 10
}
```

**Output**:
```python
{
    "results": [
        {
            "id": "uuid",
            "name": "string",
            "type": "people | companies",
            "email": "string | null",
            "phone": "string | null",
            "company": "string | null",  # For people: job title or company name
            "lastInteraction": "datetime | null"
        }
    ],
    "total": "int",
    "query": "string"
}
```

**Business Logic**:
- Search both people and companies if type is 'both'
- Combine results and sort by relevance
- Include primary contact info
- Include last interaction date

---

### 2. getContactDetails

**Purpose**: Get detailed information about a specific contact.

**Input Parameters**:
```python
{
    "contactId": "uuid",  # Required
    "contactType": "people | companies",  # Required
    "includeRelated": "bool | null"  # Default: false
}
```

**Output**:
```python
{
    "contact": {
        "id": "uuid",
        "name": "string",
        "type": "people | companies",
        "email": "string | null",
        "phone": "string | null",
        "address": "string | null",
        "website": "string | null",
        "industry": "string | null",
        "size": "string | null",
        "description": "string | null",
        "tags": "list[string] | null",
        "customFields": "dict | null"
    },
    "relatedData": {
        "deals": [
            {
                "id": "uuid",
                "title": "string",
                "value": "float",
                "stage": "string",
                "closeDate": "datetime | null"
            }
        ] | null,
        "interactions": [
            {
                "id": "uuid",
                "type": "string",
                "date": "datetime",
                "summary": "string"
            }
        ] | null,
        "notes": [
            {
                "id": "uuid",
                "content": "string",
                "createdAt": "datetime",
                "author": "string"
            }
        ] | null
    } | null
}
```

**Business Logic**:
- Fetch contact by ID and type
- Include related deals, interactions, notes if requested
- Format data consistently for both people and companies

---

## Analytics Functions

### 1. getActivitySummary

**Purpose**: Get summary of recent activities and interactions.

**Input Parameters**:
```python
{
    "days": "int | null",  # Default: 30
    "activityTypes": "list[string] | null"  # Filter by interaction types
}
```

**Output**:
```python
{
    "summary": {
        "totalActivities": "int",
        "activitiesByType": {
            # InteractionType -> count
        },
        "activitiesByUser": [
            {
                "userId": "uuid",
                "userName": "string",
                "count": "int"
            }
        ],
        "topContacts": [
            {
                "contactName": "string",
                "activityCount": "int",
                "_ref": "string"  # Reference ID for follow-up queries
            }
        ]
    },
    "trends": {
        "dailyActivity": [
            {
                "date": "string",  # ISO date string
                "count": "int"
            }
        ],
        "activityGrowth": "float | null",  # Percentage change
        "peakHours": [
            {
                "hour": "int",  # 0-23
                "count": "int"
            }
        ] | null
    }
}
```

**Business Logic**:
- Fetch interactions for the specified period
- Count by type
- Count by user (if user tracking available)
- Identify top contacts by interaction count
- Calculate daily activity trends
- Calculate growth rate (requires previous period comparison)
- Identify peak hours (requires hour extraction from timestamps)

---

### 2. analyzeContactGrowth

**Purpose**: Analyze contact growth trends and patterns.

**Input Parameters**:
```python
{
    "period": "string | null",  # e.g., "month", "quarter", "year"
    "groupBy": "string | null"  # e.g., "source", "industry", "geography"
}
```

**Output**:
```python
{
    "growth": {
        "totalContacts": "int",
        "newContacts": "int",
        "growthRate": "float",  # Percentage
        "growthByPeriod": [
            {
                "period": "string",
                "newContacts": "int",
                "totalContacts": "int",
                "growthRate": "float"
            }
        ]
    },
    "patterns": {
        "sourceBreakdown": {
            # source -> count
        } | null,
        "industryBreakdown": {
            # industry -> count
        } | null,
        "geographicBreakdown": {
            # location -> count
        } | null,
        "sizeBreakdown": {
            # size -> count
        } | null
    },
    "insights": [
        {
            "type": "trend | pattern | anomaly",
            "title": "string",
            "description": "string",
            "impact": "low | medium | high"
        }
    ]
}
```

**Business Logic**:
- Calculate total contacts and new contacts in period
- Calculate growth rate
- Break down by period (daily, weekly, monthly)
- Group by source, industry, geography, size if data available
- Generate insights based on patterns and anomalies

---

## Deal Analysis Functions

### 1. analyzePipeline

**Purpose**: Analyze deal pipeline and stage performance.

**Input Parameters**:
```python
{
    "dateRange": {
        "start": "datetime",
        "end": "datetime"
    } | null,
    "includeMetrics": "bool | null"  # Default: false
}
```

**Output**:
```python
{
    "pipeline": {
        "stages": [
            {
                "name": "string",
                "deals": "int",
                "value": "float",
                "averageDealSize": "float",
                "conversionRate": "float | null",  # Requires stage transition data
                "averageTimeInStage": "float | null"  # In days
            }
        ],
        "totalDeals": "int",
        "totalValue": "float",
        "averageDealSize": "float"
    },
    "metrics": {
        "winRate": "float",  # Percentage
        "averageSalesCycle": "float",  # In days
        "pipelineVelocity": "float",  # Deals per time period
        "forecastAccuracy": "float | null"  # Requires historical data
    } | null
}
```

**Business Logic**:
- Fetch all deals in date range
- Group by stage (column)
- Calculate deal counts and values per stage
- Calculate average deal size per stage
- Calculate conversion rates (requires stage transition tracking)
- Calculate average time in stage (requires stage history)
- Calculate overall metrics if requested

---

## Context Query Functions

### 1. getAccountContext

**Purpose**: Get complete account context (company + people + deals + activity).

**Input Parameters**:
```python
{
    "companyId": "uuid",  # Required
    "includeEmployeeInteractions": "bool | null",  # Default: false
    "interactionLimit": "int | null",  # Default: 50
    "dealsLimit": "int | null"  # Default: 50
}
```

**Output**:
```python
{
    "company": {
        # Company object
    },
    "people": [
        {
            "person": {
                # Person object
            },
            "interactionCount": "int",
            "lastInteraction": "datetime | null",
            "deals": [
                # Deal objects
            ]
        }
    ],
    "deals": [
        {
            "deal": {
                # Deal object
            },
            "stage": {
                "column": {
                    # Column object
                },
                "group": {
                    # Group object
                }
            },
            "contacts": [
                # Person objects
            ]
        }
    ],
    "interactions": [
        # Interaction objects
    ],
    "summary": {
        "totalPeople": "int",
        "keyContacts": "int",  # People with interactions
        "totalDeals": "int",
        "totalDealValue": "float",
        "totalInteractions": "int",
        "lastInteractionDate": "datetime | null",
        "engagementTrend": "increasing | stable | decreasing"
    }
}
```

**Business Logic**:
- Fetch company
- Fetch all people at company
- Fetch all deals for company
- Fetch interactions (company-level and optionally employee-level)
- Calculate engagement trend (compare recent vs older interactions)
- Generate comprehensive summary

---

### 2. getDealContext

**Purpose**: Get complete deal context with all related information.

**Input Parameters**:
```python
{
    "dealId": "uuid",  # Required
    "interactionLimit": "int | null"  # Default: 50
}
```

**Output**:
```python
{
    "deal": {
        # Deal object
    },
    "stage": {
        "column": {
            # Column object
        },
        "group": {
            # Group object
        }
    },
    "people": [
        {
            "person": {
                # Person object
            },
            "company": {
                # Company object
            } | null,
            "interactionCount": "int",
            "lastInteraction": "datetime | null"
        }
    ],
    "companies": [
        # Company objects
    ],
    "interactions": [
        # Interaction objects
    ],
    "summary": {
        "totalContacts": "int",
        "totalCompanies": "int",
        "totalInteractions": "int",
        "lastInteractionDate": "datetime | null",
        "daysSinceLastInteraction": "int",
        "daysInCurrentStage": "int"
    }
}
```

**Business Logic**:
- Fetch deal and stage information
- Fetch all related people and companies
- Fetch interactions for people/companies on deal
- Calculate summary statistics

---

### 3. findRelationships

**Purpose**: Find relationships between two entities.

**Input Parameters**:
```python
{
    "entity1": {
        "type": "person | company | deal",
        "id": "uuid"
    },
    "entity2": {
        "type": "person | company | deal",
        "id": "uuid"
    }
}
```

**Output**:
```python
{
    "relationships": [
        {
            "type": "works_at | involved_in_deal | shared_deal | shared_company | interaction",
            "description": "string",
            "relatedEntities": [
                # Person, Company, or Deal objects
            ] | null
        }
    ],
    "degreesOfSeparation": "int"  # 0 = direct, 1 = one hop, etc.
}
```

**Business Logic**:
- Find direct relationships:
  - Person works at Company
  - Person/Company involved in Deal
  - Shared deals or companies
  - Direct interactions
- Find indirect relationships (multiple hops)
- Calculate degrees of separation
- Generate human-readable descriptions

---

### 4. getRelationshipNetwork

**Purpose**: Get relationship network around an entity.

**Input Parameters**:
```python
{
    "entityType": "person | company | deal",  # Required
    "entityId": "uuid",  # Required
    "depth": "int | null"  # Default: 1 (direct connections only)
}
```

**Output**:
```python
{
    "center": {
        # Person, Company, or Deal object
    },
    "connections": [
        {
            "entity": {
                # Person, Company, or Deal object
            },
            "relationshipType": "string",
            "strength": "float",  # 0-1, based on interaction count, recency
            "sharedEntities": [
                # Person, Company, or Deal objects
            ] | null
        }
    ]
}
```

**Business Logic**:
- Start with center entity
- Find all direct connections (depth=1)
- Optionally expand to depth=2, 3, etc.
- Calculate relationship strength based on:
  - Number of shared entities
  - Interaction frequency
  - Recency of interactions
- Return network graph

---

## Utility Query Functions

### 1. getWorkspaceSummary

**Purpose**: Get high-level workspace statistics.

**Input Parameters**:
```python
{
    "workspaceId": "uuid"  # Required
}
```

**Output**:
```python
{
    "people": {
        "total": "int",
        "addedThisMonth": "int",
        "withInteractions": "int"
    },
    "companies": {
        "total": "int",
        "addedThisMonth": "int",
        "withDeals": "int"
    },
    "deals": {
        "total": "int",
        "active": "int",
        "won": "int",
        "lost": "int",
        "totalValue": "float"
    },
    "interactions": {
        "total": "int",
        "thisWeek": "int",
        "thisMonth": "int",
        "byType": {
            # InteractionType -> count
        }
    }
}
```

**Business Logic**:
- Count all people, companies, deals, interactions
- Calculate monthly additions
- Count people with interactions
- Count companies with deals
- Calculate deal statistics (requires status determination)
- Calculate interaction statistics by type and time period

---

### 2. getBulkEntities

**Purpose**: Get multiple entities by IDs in a single call (optimization function).

**Input Parameters**:
```python
{
    "people": "list[uuid] | null",
    "companies": "list[uuid] | null",
    "deals": "list[uuid] | null",
    "interactions": "list[uuid] | null"
}
```

**Output**:
```python
{
    "people": {
        # uuid -> Person object
    },
    "companies": {
        # uuid -> Company object
    },
    "deals": {
        # uuid -> Deal object
    },
    "interactions": {
        # uuid -> Interaction object
    }
}
```

**Business Logic**:
- Fetch all requested entities in parallel queries
- Return as dictionary keyed by ID
- Useful for batch operations

---

## Implementation Notes for Python

### Database Access

1. **ORM/Query Builder**: Use SQLAlchemy, Prisma (Python port), or raw SQL with parameterized queries
2. **Connection Pooling**: Implement connection pooling for efficiency
3. **Transactions**: Use transactions for complex queries involving multiple tables
4. **Query Optimization**: Use indexes on frequently queried fields (workspaceId, createdAt, etc.)

### Error Handling

1. **Validation**: Validate all input parameters (UUIDs, dates, enums)
2. **Not Found**: Return appropriate errors when entities not found
3. **Permissions**: Verify workspace access before querying
4. **Rate Limiting**: Implement rate limiting for expensive queries

### Performance

1. **Pagination**: Always implement pagination for list queries
2. **Selective Loading**: Only load requested related data (use include flags)
3. **Caching**: Cache frequently accessed data (workspace summaries, etc.)
4. **Batch Queries**: Use batch queries where possible (getBulkEntities pattern)

### Data Formatting

1. **Dates**: Return dates as ISO 8601 strings
2. **UUIDs**: Return as strings
3. **Nulls**: Use None/null consistently
4. **Enums**: Return as strings matching the enum values

### Testing

1. **Unit Tests**: Test each function with various input combinations
2. **Integration Tests**: Test with real database
3. **Edge Cases**: Test with empty results, large datasets, invalid inputs
4. **Performance Tests**: Test query performance with large datasets

---

## Example Python Function Signature

```python
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

def search_people(
    query: Optional[str] = None,
    email: Optional[str] = None,
    job_title: Optional[str] = None,
    company_id: Optional[UUID] = None,
    group_id: Optional[UUID] = None,
    tags: Optional[List[str]] = None,
    has_interactions_since: Optional[datetime] = None,
    sort_by: Optional[str] = None,  # "name" | "createdAt" | "lastInteraction" | "interactionCount"
    sort_order: Optional[str] = None,  # "asc" | "desc"
    limit: Optional[int] = None,  # Default: 20, max: 100
    offset: Optional[int] = None,  # Default: 0
    context: Dict[str, Any] = None  # Contains workspaceId, userId, etc.
) -> Dict[str, Any]:
    """
    Search for people by various criteria.
    
    Returns:
        {
            "results": List[Person],
            "total": int,
            "hasMore": bool
        }
    """
    # Implementation here
    pass
```

---

## LLM Function Calling Format

For LLM integration, each function should be described in OpenAI function calling format:

```python
{
    "type": "function",
    "function": {
        "name": "search_people",
        "description": "Search for people by name, email, job title, company, group, or other criteria. Returns paginated results with total count.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term for name, email, or job title (case-insensitive)"
                },
                "email": {
                    "type": "string",
                    "description": "Exact email address to match"
                },
                "job_title": {
                    "type": "string",
                    "description": "Filter by job title (case-insensitive contains)"
                },
                "company_id": {
                    "type": "string",
                    "description": "Filter by company UUID"
                },
                "group_id": {
                    "type": "string",
                    "description": "Filter by group UUID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 20, max: 100)",
                    "minimum": 1,
                    "maximum": 100
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default: 0)",
                    "minimum": 0
                }
            },
            "required": []
        }
    }
}
```

---

## Conclusion

This specification provides comprehensive details for implementing all AI Analyst tools in Python. Each function is designed to be:

- **Self-contained**: Clear input/output contracts
- **Efficient**: Supports filtering, pagination, selective loading
- **Flexible**: Supports various query patterns and use cases
- **LLM-friendly**: Can be easily converted to function calling format

Use this specification as a blueprint for Python implementation, ensuring all business logic, data models, and query patterns are accurately translated.

