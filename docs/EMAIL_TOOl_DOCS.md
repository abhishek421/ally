# Analyst Feature: Email Interactions Fetching from DynamoDB

## Architecture Overview

The SoftSync application uses a **dual-database architecture**:
- **DynamoDB**: Stores all email content and email interactions
- **PostgreSQL**: Stores general interactions (calls, meetings, notes) and powers AI analyst queries

**Important**: Email interactions are exclusively stored in DynamoDB, NOT in PostgreSQL.

---

## Environment Variables

```python
# Required Environment Variables
DYNAMODB_TABLE = "prod-softsync"  # or from env: os.getenv("DYNAMODB_TABLE")
AWS_REGION = "eu-north-1"  # or from env: os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID=REDACTED
AWS_SECRET_ACCESS_KEY=REDACTED
```

---

## DynamoDB Table Structure

### Table Name
- **Table Name**: Value from `DYNAMODB_TABLE` environment variable (e.g., `"prod-softsync"`)

### Key Schema

**Primary Key (PK) - Partition Key:**
- Pattern: `WORKSPACE#{workspaceId}#PERSON#{personId}` (for person-centric emails)
- Pattern: `WORKSPACE#{workspaceId}#COMPANY#{companyId}` (for company-centric emails)

**Sort Key (SK):**
- Pattern: `{isoDate}#{messageId}` 
- Example: `2024-01-15T10:30:00Z#msg-123-abc`
- Sorted chronologically (newest first when `ScanIndexForward: false`)

**Global Secondary Index (GSI1):**
- **GSI1PK**: `WORKSPACE#{workspaceId}#EMAIL#{messageId}` (for reverse lookup by messageId)
- **GSI1SK**: `{isoDate}#{messageId}`

---

## Pseudocode: Fetching Email Interactions for Analyst

### Step 1: Initialize DynamoDB Client

```python
import boto3
from boto3.dynamodb.conditions import Key
import json
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime

# Initialize DynamoDB client
dynamodb_client = boto3.client(
    'dynamodb',
    region_name=AWS_REGION,
AWS_ACCESS_KEY_ID=REDACTED
AWS_SECRET_ACCESS_KEY=REDACTED
)

# Initialize DynamoDB Document Client (for easier JSON handling)
dynamodb_doc_client = boto3.resource(
    'dynamodb',
    region_name=AWS_REGION,
AWS_ACCESS_KEY_ID=REDACTED
AWS_SECRET_ACCESS_KEY=REDACTED
).meta.client
```

---

### Step 2: Fetch Emails for a Person

```python
def get_person_emails(
    person_id: str,
    workspace_id: str,
    limit: int = 20,
    next_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch emails for a specific person from DynamoDB.
    
    Args:
        person_id: UUID of the person (e.g., "123e4567-e89b-12d3-a456-426614174000")
        workspace_id: UUID of the workspace (e.g., "123e4567-e89b-12d3-a456-426614174001")
        limit: Maximum number of emails to return (default: 20, max: 100)
        next_token: Base64-encoded pagination token for next page
        
    Returns:
        Dictionary with:
        - items: List of email dictionaries
        - next_token: Base64-encoded token for next page (if more results exist)
    """
    
    # Construct partition key
    partition_key = f"WORKSPACE#{workspace_id}#PERSON#{person_id}"
    
    # Build query parameters
    query_params = {
        'TableName': DYNAMODB_TABLE,
        'KeyConditionExpression': 'PK = :pk',
        'ExpressionAttributeValues': {
            ':pk': partition_key
        },
        'ScanIndexForward': False,  # Latest emails first (reverse chronological)
        'Limit': min(limit, 100)  # Cap at 100 for performance
    }
    
    # Handle pagination token
    if next_token:
        # Decode base64 token to get DynamoDB LastEvaluatedKey
        try:
            decoded_token = base64.b64decode(next_token).decode('utf-8')
            exclusive_start_key = json.loads(decoded_token)
            query_params['ExclusiveStartKey'] = exclusive_start_key
        except Exception as e:
            raise ValueError(f"Invalid pagination token: {e}")
    
    # Execute query
    response = dynamodb_doc_client.query(**query_params)
    
    # Extract items
    items = response.get('Items', [])
    
    # Get pagination token if more results exist
    last_evaluated_key = response.get('LastEvaluatedKey')
    next_token_encoded = None
    if last_evaluated_key:
        # Encode LastEvaluatedKey as base64 for next request
        token_json = json.dumps(last_evaluated_key)
        next_token_encoded = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')
    
    # Map DynamoDB items to email data structure
    emails = [map_dynamo_item_to_email(item) for item in items]
    
    return {
        'items': emails,
        'next_token': next_token_encoded
    }
```

---

### Step 3: Fetch Emails for a Company

```python
def get_company_emails(
    company_id: str,
    workspace_id: str,
    limit: int = 20,
    next_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch emails for a specific company from DynamoDB.
    
    Args:
        company_id: UUID of the company
        workspace_id: UUID of the workspace
        limit: Maximum number of emails to return
        next_token: Base64-encoded pagination token
        
    Returns:
        Dictionary with items and next_token
    """
    
    # Construct partition key (company-centric)
    partition_key = f"WORKSPACE#{workspace_id}#COMPANY#{company_id}"
    
    # Build query parameters (same structure as person emails)
    query_params = {
        'TableName': DYNAMODB_TABLE,
        'KeyConditionExpression': 'PK = :pk',
        'ExpressionAttributeValues': {
            ':pk': partition_key
        },
        'ScanIndexForward': False,  # Latest first
        'Limit': min(limit, 100)
    }
    
    # Handle pagination
    if next_token:
        decoded_token = base64.b64decode(next_token).decode('utf-8')
        query_params['ExclusiveStartKey'] = json.loads(decoded_token)
    
    # Execute query
    response = dynamodb_doc_client.query(**query_params)
    
    # Process results
    items = response.get('Items', [])
    emails = [map_dynamo_item_to_email(item) for item in items]
    
    # Get next token
    last_evaluated_key = response.get('LastEvaluatedKey')
    next_token_encoded = None
    if last_evaluated_key:
        token_json = json.dumps(last_evaluated_key)
        next_token_encoded = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')
    
    return {
        'items': emails,
        'next_token': next_token_encoded
    }
```

---

### Step 4: Map DynamoDB Item to Email Data Structure

```python
def map_dynamo_item_to_email(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DynamoDB item to email data structure.
    
    Args:
        item: Raw DynamoDB item dictionary
        
    Returns:
        Email data dictionary with standardized structure
    """
    
    source = item.get('source', 'EMAIL_SYNC')
    
    # Handle manual interaction events
    if source == 'MANUAL_EVENT':
        return {
            'messageId': item.get('interactionId'),
            'subject': item.get('eventName'),
            'from': '',
            'to': [],
            'direction': item.get('direction', 'received'),
            'body': item.get('description'),
            'htmlBody': None,
            'date': datetime.fromisoformat(item.get('dateTime').replace('Z', '+00:00')),
            'threadId': None,
            'participants': [],
            'workspaceId': item.get('workspaceId'),
            'userId': item.get('createdById'),
            'processed': item.get('processed', True),
            'createdAt': datetime.fromisoformat(item.get('createdAt').replace('Z', '+00:00')),
            'updatedAt': datetime.fromisoformat(item.get('updatedAt').replace('Z', '+00:00')),
            'deleted': item.get('isDeleted', False),
            'labels': [],
            'source': 'MANUAL_EVENT',
            'interactionType': item.get('interactionType'),
            'eventName': item.get('eventName'),
            'description': item.get('description'),
            'dateTime': datetime.fromisoformat(item.get('dateTime').replace('Z', '+00:00')),
            'duration': item.get('duration'),
            'personId': item.get('personId'),
            'companyId': item.get('companyId'),
            'createdById': item.get('createdById')
        }
    
    # Handle synced email messages
    raw_html = item.get('htmlBody')
    raw_body = item.get('body')
    
    # Derive text preview from HTML or use body
    body_text = derive_text_preview(raw_html, raw_body)
    
    return {
        'messageId': item.get('messageId'),
        'subject': item.get('subject'),
        'from': item.get('from', ''),
        'to': item.get('to', []) if isinstance(item.get('to'), list) else [item.get('to')] if item.get('to') else [],
        'direction': item.get('direction', 'received'),
        'body': body_text,
        'htmlBody': raw_html,
        'date': datetime.fromisoformat(item.get('date').replace('Z', '+00:00')),
        'threadId': item.get('threadId'),
        'participants': item.get('participants', []),
        'workspaceId': item.get('workspaceId'),
        'userId': item.get('userId'),
        'processed': item.get('processed', False),
        'createdAt': datetime.fromisoformat(item.get('createdAt').replace('Z', '+00:00')),
        'updatedAt': datetime.fromisoformat(item.get('updatedAt').replace('Z', '+00:00')),
        'deleted': item.get('deleted', False),
        'labels': item.get('labels', []),
        'source': 'EMAIL_SYNC'
    }

def derive_text_preview(html: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """
    Extract text preview from HTML or use fallback text.
    Clamps to 16KB to avoid size limits.
    """
    import re
    
    source = ''
    if html:
        # Strip HTML tags
        source = re.sub(r'<script[\s\S]*?>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
        source = re.sub(r'<style[\s\S]*?>[\s\S]*?</style>', '', source, flags=re.IGNORECASE)
        source = re.sub(r'<[^>]+>', '', source)
        source = source.replace('&nbsp;', ' ').replace('&amp;', '&').strip()
    elif fallback:
        source = fallback.strip()
    
    if not source:
        return None
    
    # Clamp to 16KB
    MAX_PREVIEW_BYTES = 16000
    if len(source.encode('utf-8')) <= MAX_PREVIEW_BYTES:
        return source
    
    # Truncate if too large
    end = len(source)
    while len(source[:end].encode('utf-8')) > MAX_PREVIEW_BYTES and end > 0:
        end = int(end * 0.8)
    
    return source[:end]
```

---

### Step 5: Apply Privacy Filtering

```python
def apply_privacy_filtering(
    emails: List[Dict[str, Any]],
    current_user_id: str,
    workspace_id: str,
    user_privacy_levels: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Filter emails based on privacy settings.
    
    Privacy Levels:
    - PRIVATE: Only visible to creator (filter out for non-owners)
    - SUBJECT_ONLY: Show subject and metadata, hide body
    - FULL_ACCESS: Show everything
    
    Args:
        emails: List of email dictionaries
        current_user_id: ID of the current user viewing emails
        workspace_id: Workspace ID
        user_privacy_levels: Dictionary mapping user_id -> privacy_level
        
    Returns:
        Filtered list of emails
    """
    
    filtered = []
    
    for email in emails:
        email_user_id = email.get('userId') or email.get('createdById')
        is_own = email_user_id == current_user_id
        
        # Owner always sees their own emails in full
        if is_own:
            email['ownerPrivacyLevel'] = user_privacy_levels.get(email_user_id, 'PRIVATE')
            filtered.append(email)
            continue
        
        # Get privacy level for email owner
        owner_privacy = user_privacy_levels.get(email_user_id, 'PRIVATE')
        
        # Apply privacy rules
        if owner_privacy == 'PRIVATE':
            # Hide completely from non-owners
            continue
        elif owner_privacy == 'SUBJECT_ONLY':
            # Show subject and metadata, hide body
            email['body'] = None
            email['htmlBody'] = None
            email['ownerPrivacyLevel'] = owner_privacy
            filtered.append(email)
        elif owner_privacy == 'FULL_ACCESS':
            # Show everything
            email['ownerPrivacyLevel'] = owner_privacy
            filtered.append(email)
        else:
            # Unknown privacy level, default to private
            continue
    
    return filtered
```

---

### Step 6: Complete Flow for Analyst Feature

```python
def get_contact_emails_for_analyst(
    contact_id: str,
    contact_type: str,  # 'people' or 'companies'
    workspace_id: str,
    current_user_id: str,
    limit: int = 20,
    next_token: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None,
    direction: Optional[str] = None  # 'sent', 'received', or 'both'
) -> Dict[str, Any]:
    """
    Complete flow for fetching emails for analyst feature.
    
    Args:
        contact_id: Person ID or Company ID
        contact_type: 'people' or 'companies'
        workspace_id: Workspace UUID
        current_user_id: Current user UUID
        limit: Maximum results (default: 20, max: 50)
        next_token: Pagination token
        date_range: Optional dict with 'start' and 'end' ISO date strings
        direction: Optional filter for 'sent' or 'received'
        
    Returns:
        Dictionary with emails, metadata, and pagination info
    """
    
    # Step 1: Fetch raw emails from DynamoDB
    if contact_type == 'people':
        result = get_person_emails(contact_id, workspace_id, limit, next_token)
    elif contact_type == 'companies':
        result = get_company_emails(contact_id, workspace_id, limit, next_token)
    else:
        raise ValueError(f"Invalid contact_type: {contact_type}")
    
    emails = result['items']
    
    # Step 2: Get user privacy levels (query PostgreSQL or cache)
    # This is a simplified version - in reality, you'd query PostgreSQL
    # to get privacy settings for all users whose emails are in the result
    user_ids = list(set([email.get('userId') or email.get('createdById') for email in emails]))
    user_privacy_levels = get_user_privacy_levels(user_ids, workspace_id)  # Implement this
    
    # Step 3: Apply privacy filtering
    filtered_emails = apply_privacy_filtering(
        emails,
        current_user_id,
        workspace_id,
        user_privacy_levels
    )
    
    # Step 4: Apply date range filter if provided
    if date_range:
        start_date = datetime.fromisoformat(date_range['start'].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(date_range['end'].replace('Z', '+00:00'))
        filtered_emails = [
            email for email in filtered_emails
            if start_date <= email['date'] <= end_date
        ]
    
    # Step 5: Apply direction filter if provided
    if direction and direction != 'both':
        filtered_emails = [
            email for email in filtered_emails
            if email['direction'] == direction
        ]
    
    # Step 6: Map to AI-friendly format
    ai_emails = []
    for email in filtered_emails:
        ai_email = {
            'messageId': email['messageId'],
            'subject': email.get('subject'),
            'from': email.get('from', ''),
            'to': email.get('to', []),
            'direction': email.get('direction'),
            'body': email.get('body'),
            'date': email['date'].isoformat(),
            'participants': [
                {
                    'email': p.get('email'),
                    'role': p.get('role'),
                    'personId': p.get('personId'),
                    'companyId': p.get('companyId')
                }
                for p in email.get('participants', [])
            ],
            'threadId': email.get('threadId'),
            'source': email.get('source', 'EMAIL_SYNC')
        }
        ai_emails.append(ai_email)
    
    return {
        'emails': ai_emails,
        'totalCount': len(ai_emails),
        'hasNextPage': result['next_token'] is not None,
        'nextToken': result['next_token'],
        'contactId': contact_id,
        'contactType': contact_type
    }
```

---

## Key Patterns and IDs

### ID Formats
- **Person ID**: UUID format (e.g., `"123e4567-e89b-12d3-a456-426614174000"`)
- **Company ID**: UUID format (e.g., `"123e4567-e89b-12d3-a456-426614174001"`)
- **Workspace ID**: UUID format
- **Message ID**: String identifier (e.g., `"msg-123-abc"` or UUID)

### Key Construction Patterns
```python
# Person-centric partition key
pk = f"WORKSPACE#{workspace_id}#PERSON#{person_id}"

# Company-centric partition key
pk = f"WORKSPACE#{workspace_id}#COMPANY#{company_id}"

# Sort key (chronological)
sk = f"{iso_date}#{message_id}"  # e.g., "2024-01-15T10:30:00Z#msg-123"

# GSI1PK for reverse lookup by messageId
gsi1pk = f"WORKSPACE#{workspace_id}#EMAIL#{message_id}"
```

---

## Pagination with NextToken

### Encoding NextToken
```python
# When you receive LastEvaluatedKey from DynamoDB:
last_evaluated_key = response.get('LastEvaluatedKey')  # Dict with PK and SK

# Encode it as base64 JSON string
token_json = json.dumps(last_evaluated_key)
next_token = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')
```

### Decoding NextToken
```python
# When you receive nextToken from client:
decoded_token = base64.b64decode(next_token).decode('utf-8')
exclusive_start_key = json.loads(decoded_token)

# Use in query
query_params['ExclusiveStartKey'] = exclusive_start_key
```

---

## Example Usage in LangGraph

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional

class AnalystState(TypedDict):
    workspace_id: str
    user_id: str
    contact_id: Optional[str]
    contact_type: Optional[str]  # 'people' or 'companies'
    emails: List[Dict[str, Any]]
    next_token: Optional[str]
    query: Optional[str]

def fetch_emails_node(state: AnalystState) -> AnalystState:
    """Node that fetches emails from DynamoDB"""
    
    if not state['contact_id'] or not state['contact_type']:
        return state
    
    result = get_contact_emails_for_analyst(
        contact_id=state['contact_id'],
        contact_type=state['contact_type'],
        workspace_id=state['workspace_id'],
        current_user_id=state['user_id'],
        limit=20,
        next_token=state.get('next_token')
    )
    
    state['emails'] = result['emails']
    state['next_token'] = result.get('nextToken')
    
    return state

# Build graph
workflow = StateGraph(AnalystState)
workflow.add_node("fetch_emails", fetch_emails_node)
workflow.set_entry_point("fetch_emails")
workflow.add_edge("fetch_emails", END)

app = workflow.compile()
```

---

## Summary

1. **Table Name**: From `DYNAMODB_TABLE` env variable
2. **Partition Key**: `WORKSPACE#{workspaceId}#PERSON#{personId}` or `WORKSPACE#{workspaceId}#COMPANY#{companyId}`
3. **Sort Key**: `{isoDate}#{messageId}` (chronological)
4. **Query Pattern**: Use `Query` operation with `KeyConditionExpression: PK = :pk`
5. **Pagination**: Use `LastEvaluatedKey` encoded as base64 JSON in `nextToken`
6. **Privacy**: Filter emails based on user privacy levels (PRIVATE, SUBJECT_ONLY, FULL_ACCESS)
7. **Sorting**: `ScanIndexForward: false` for newest first
8. **Limit**: Cap at 100 items per query for performance

