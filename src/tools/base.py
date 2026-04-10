"""Base tool functionality and context."""

import json
import logging
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Optional

from rapidfuzz import fuzz, process
from src.graphql.client import GraphQLClient

logger = logging.getLogger(__name__)


# Data change detection for real-time frontend updates
DATA_CHANGE_MARKER = "\n__DATA_CHANGE__:"


class EntityType(str, Enum):
    """Types of entities that can be changed."""
    PERSON = "person"
    COMPANY = "company"
    GROUP = "group"
    VIEW = "view"
    REMINDER = "reminder"
    NOTE = "note"


class ChangeAction(str, Enum):
    """Types of changes that can be made."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass
class DataChange:
    """Metadata about a data change made by a tool.
    
    This is used to notify the frontend to invalidate caches.
    """
    entity_type: EntityType
    action: ChangeAction
    entity_id: Optional[str] = None
    group_id: Optional[str] = None
    
    def to_marker(self) -> str:
        """Convert to a marker string that can be appended to tool results."""
        data = {
            "entityType": self.entity_type.value,
            "action": self.action.value,
        }
        if self.entity_id:
            data["entityId"] = self.entity_id
        if self.group_id:
            data["groupId"] = self.group_id
        return DATA_CHANGE_MARKER + json.dumps(data)


def parse_data_change(result: str) -> tuple[str, Optional[dict]]:
    """Parse a tool result to extract any data change metadata.
    
    Args:
        result: The tool result string
        
    Returns:
        Tuple of (cleaned_result, change_data or None)
    """
    if DATA_CHANGE_MARKER not in result:
        return result, None
    
    parts = result.split(DATA_CHANGE_MARKER)
    cleaned_result = parts[0]
    
    try:
        change_data = json.loads(parts[1])
        return cleaned_result, change_data
    except (json.JSONDecodeError, IndexError):
        logger.warning(f"Failed to parse data change marker from result")
        return cleaned_result, None


# Fuzzy matching utilities

def fuzzy_match_entities(
    query: str,
    entities: list[dict],
    name_key: str = "name",
    threshold: float = 60.0,
    limit: int = 5,
) -> list[tuple[dict, float]]:
    """Find entities that fuzzy match the query string.
    
    Uses multiple matching strategies to handle:
    - Typos (e.g., "Gogle" → "Google")
    - Partial names (e.g., "John" → "John Smith")
    - Case differences (e.g., "ACME" → "Acme Corp")
    - Word reordering (e.g., "Smith John" → "John Smith")
    
    Args:
        query: The search query (potentially with typos)
        entities: List of entity dicts to search through
        name_key: The key in entity dict containing the name
        threshold: Minimum similarity score (0-100) to include
        limit: Maximum number of results to return
        
    Returns:
        List of (entity, score) tuples sorted by score descending
    """
    if not query or not entities:
        return []
    
    query_lower = query.lower().strip()
    
    # Build choices list - handles both simple name and compound names (firstName + lastName)
    choices = []
    for entity in entities:
        if name_key == "fullName":
            # Special case for people: combine firstName and lastName
            first = entity.get("firstName", "") or ""
            last = entity.get("lastName", "") or ""
            name = f"{first} {last}".strip()
        else:
            name = entity.get(name_key, "") or ""
        choices.append(name)
    
    # Use a combined scoring approach for best results
    results = []
    
    for i, entity in enumerate(entities):
        name = choices[i]
        if not name:
            continue
        
        name_lower = name.lower()
        
        # Calculate multiple similarity scores
        # 1. Token sort ratio - handles word reordering
        token_sort = fuzz.token_sort_ratio(query_lower, name_lower)
        
        # 2. Token set ratio - handles subset matching
        token_set = fuzz.token_set_ratio(query_lower, name_lower)
        
        # 3. Partial ratio - handles partial matches
        partial = fuzz.partial_ratio(query_lower, name_lower)
        
        # 4. Standard ratio - handles simple typos
        standard = fuzz.ratio(query_lower, name_lower)
        
        # Take the best score from all methods
        best_score = max(token_sort, token_set, partial, standard)
        
        # Boost exact prefix matches significantly
        if name_lower.startswith(query_lower):
            best_score = min(100, best_score + 20)
        
        # Boost if all query words are found in the name
        query_words = set(query_lower.split())
        name_words = set(name_lower.split())
        if query_words.issubset(name_words):
            best_score = min(100, best_score + 15)
        
        if best_score >= threshold:
            results.append((entity, best_score))
    
    # Sort by score descending and limit results
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def get_best_match(
    query: str,
    entities: list[dict],
    name_key: str = "name",
    threshold: float = 70.0,
) -> dict | None:
    """Get the single best matching entity if confidence is high enough.
    
    Args:
        query: The search query
        entities: List of entity dicts
        name_key: The key containing the name
        threshold: Minimum score to consider a confident match
        
    Returns:
        The best matching entity or None if no confident match
    """
    matches = fuzzy_match_entities(query, entities, name_key, threshold, limit=1)
    if matches and matches[0][1] >= threshold:
        return matches[0][0]
    return None


def format_fuzzy_suggestions(
    query: str,
    matches: list[tuple[dict, float]],
    name_key: str = "name",
) -> str:
    """Format fuzzy match results as suggestions for the user.
    
    Args:
        query: Original query
        matches: List of (entity, score) tuples
        name_key: Key containing the name
        
    Returns:
        Formatted suggestion string
    """
    if not matches:
        return f"No matches found for '{query}'."
    
    if len(matches) == 1 and matches[0][1] >= 90:
        entity = matches[0][0]
        if name_key == "fullName":
            name = f"{entity.get('firstName', '')} {entity.get('lastName', '')}".strip()
        else:
            name = entity.get(name_key, "Unknown")
        return f"Found: **{name}** (ID: {entity.get('id', 'N/A')})"
    
    lines = [f"Found {len(matches)} potential matches for '{query}':\n"]
    for entity, score in matches:
        if name_key == "fullName":
            name = f"{entity.get('firstName', '')} {entity.get('lastName', '')}".strip()
        else:
            name = entity.get(name_key, "Unknown")
        confidence = "high" if score >= 85 else "medium" if score >= 70 else "low"
        lines.append(f"- **{name}** (ID: {entity.get('id', 'N/A')}) - {confidence} confidence")
    
    return "\n".join(lines)


@dataclass
class ToolContext:
    """Context passed to tools containing auth and workspace info.

    Note: user_id should be the database user ID, not the Cognito sub.
    The API layer resolves the Cognito sub to the database ID before
    creating this context.
    """

    auth_token: str
    workspace_id: str
    user_id: str  # Database user ID (resolved from Cognito sub at API layer)
    session_id: str = ""
    active_url: Optional[str] = None  # Current page URL the user is viewing
    user_first_name: Optional[str] = None  # User's first name for personalization
    user_email: Optional[str] = None  # User's email for context
    workspace_instructions: Optional[str] = None  # Custom instructions for the workspace
    group_instructions: Optional[str] = None  # Custom instructions for the active group
    web_search_enabled: bool = True  # Whether the web_search tool is available for this request
    _client: Optional[GraphQLClient] = field(default=None, init=False, repr=False)

    def get_client(self) -> GraphQLClient:
        """Get a cached GraphQL client for this request context.

        Returns the same client instance on repeated calls so all tool
        invocations within a single request share one HTTP connection.
        """
        if self._client is None:
            self._client = GraphQLClient(self.auth_token, self.workspace_id, self.session_id)
        return self._client

    async def close_client(self) -> None:
        """Close the cached GraphQL client and release its connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None


class BaseTool:
    """Base class for Ally tools."""
    
    def __init__(self, context: ToolContext):
        """Initialize the tool with context.
        
        Args:
            context: Tool context with auth and workspace info
        """
        self.context = context
        self.client = context.get_client()
    
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement execute()")
    
    async def close(self):
        """Close any resources."""
        await self.client.close()


# ---------------------------------------------------------------------------
# List-view limits — single constant controls all list tools.
# Lowering this number reduces tool-result tokens on every listing call.
# Detail views (get_company_by_id, etc.) are unaffected.
# ---------------------------------------------------------------------------
LIST_MAX_RESULTS = 25


def format_company_compact(company: dict) -> str:
    """Single-line company summary for list views (tokens-friendly).

    Example: "Acme Corp — acme@example.com"
    Full detail is available via get_company_by_id.
    """
    name = company.get("name", "Unknown")
    parts = [name]

    emails = company.get("emails") or []
    primary_email = next(
        (e.get("value") for e in emails if e.get("isPrimary") and e.get("value")),
        next((e.get("value") for e in emails if e.get("value")), None),
    )
    if primary_email:
        parts.append(primary_email)

    desc = company.get("description", "")
    if desc:
        # Truncate long descriptions so they don't bloat list output
        parts.append(desc[:60] + "…" if len(desc) > 60 else desc)

    return "- " + " — ".join(parts)


def format_person_compact(person: dict) -> str:
    """Single-line person summary for list views (tokens-friendly).

    Example: "John Smith, Engineer — john@example.com"
    Full detail is available via get_person_by_id.
    """
    name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip() or "Unknown"
    parts = [name]

    job = person.get("jobTitle", "")
    if job:
        parts[0] = f"{name}, {job}"

    emails = person.get("emails") or []
    primary_email = next(
        (e.get("value") for e in emails if e.get("isPrimary") and e.get("value")),
        next((e.get("value") for e in emails if e.get("value")), None),
    )
    if primary_email:
        parts.append(primary_email)

    companies = person.get("companyMetaData") or []
    if companies:
        company_names = [
            c.get("company", {}).get("name", "")
            for c in companies
            if c.get("company", {}).get("name")
        ]
        if company_names:
            parts.append(f"@ {', '.join(company_names[:2])}")

    return "- " + " — ".join(parts)


def format_group_compact(group: dict) -> str:
    """Single-line group summary for list views (tokens-friendly).

    Example: "📁 Prospects (COMPANIES)"
    """
    emoji = group.get("emoji", "")
    name = group.get("name", "Unknown")
    group_type = group.get("type", "")
    label = f"{emoji} {name}".strip() if emoji else name
    return f"- {label} ({group_type})" if group_type else f"- {label}"


def format_company(company: dict) -> str:
    """Format a company dict for display.
    
    Args:
        company: Company data from GraphQL
        
    Returns:
        Formatted string representation
    """
    lines = [f"**{company.get('name', 'Unknown')}** (ID: {company.get('id', 'N/A')})"]
    
    if company.get('description'):
        lines.append(f"  Description: {company['description']}")
    
    emails = company.get('emails', [])
    if emails:
        email_str = ", ".join(e.get('value', '') for e in emails if e.get('value'))
        if email_str:
            lines.append(f"  Emails: {email_str}")
    
    phones = company.get('phoneNumbers', [])
    if phones:
        phone_str = ", ".join(p.get('value', '') for p in phones if p.get('value'))
        if phone_str:
            lines.append(f"  Phone: {phone_str}")
    
    return "\n".join(lines)


def format_person(person: dict) -> str:
    """Format a person dict for display.
    
    Args:
        person: Person data from GraphQL
        
    Returns:
        Formatted string representation
    """
    name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip() or "Unknown"
    lines = [f"**{name}** (ID: {person.get('id', 'N/A')})"]
    
    if person.get('jobTitle'):
        lines.append(f"  Job Title: {person['jobTitle']}")
    
    if person.get('description'):
        lines.append(f"  Description: {person['description']}")
    
    emails = person.get('emails', [])
    if emails:
        email_str = ", ".join(e.get('value', '') for e in emails if e.get('value'))
        if email_str:
            lines.append(f"  Emails: {email_str}")
    
    phones = person.get('phoneNumbers', [])
    if phones:
        phone_str = ", ".join(p.get('value', '') for p in phones if p.get('value'))
        if phone_str:
            lines.append(f"  Phone: {phone_str}")
    
    companies = person.get('companyMetaData', [])
    if companies:
        company_names = [
            c.get('company', {}).get('name', '') 
            for c in companies 
            if c.get('company', {}).get('name')
        ]
        if company_names:
            lines.append(f"  Companies: {', '.join(company_names)}")
    
    return "\n".join(lines)


def format_email(email: dict) -> str:
    """Format an email/interaction dict for display.
    
    Args:
        email: Email interaction data from GraphQL
        
    Returns:
        Formatted string representation
    """
    subject = email.get('subject') or '(No subject)'
    direction = email.get('direction', 'unknown')
    direction_icon = "📤" if direction == "sent" else "📥"
    
    lines = [f"{direction_icon} **{subject}**"]
    
    # Date
    date = email.get('date', '')
    if date:
        # Format date nicely if it's a string
        if isinstance(date, str):
            lines.append(f"  Date: {date[:10] if len(date) >= 10 else date}")
        else:
            lines.append(f"  Date: {date}")
            
    # IDs (for tool use)
    msg_id = email.get('messageId')
    if msg_id:
        lines.append(f"  Message ID: {msg_id}")
        
    thread_id = email.get('threadId')
    if thread_id:
        lines.append(f"  Thread ID: {thread_id}")
    
    # From/To
    from_addr = email.get('from', '')
    if from_addr:
        lines.append(f"  From: {from_addr}")
    
    to_addrs = email.get('to', [])
    if to_addrs:
        lines.append(f"  To: {', '.join(to_addrs[:3])}" + (" ..." if len(to_addrs) > 3 else ""))
    
    # Interaction type (for manual interactions)
    interaction_type = email.get('interactionType')
    if interaction_type:
        lines.append(f"  Type: {interaction_type}")
    
    event_name = email.get('eventName')
    if event_name:
        lines.append(f"  Event: {event_name}")
    
    # Body preview (first 150 chars)
    body = email.get('body', '')
    if body:
        preview = body[:150].replace('\n', ' ').strip()
        if len(body) > 150:
            preview += "..."
        lines.append(f"  Preview: {preview}")
    
    return "\n".join(lines)


def format_group(group: dict) -> str:
    """Format a group dict for display.
    
    Args:
        group: Group data from GraphQL
        
    Returns:
        Formatted string representation
    """
    emoji = group.get('emoji', '')
    name = group.get('name', 'Unknown')
    lines = [f"**{emoji} {name}** (ID: {group.get('id', 'N/A')})"]
    
    if group.get('description'):
        lines.append(f"  Description: {group['description']}")
    
    group_type = group.get('type', 'Unknown')
    lines.append(f"  Type: {group_type}")
    
    is_private = group.get('isPrivate', False)
    lines.append(f"  Private: {'Yes' if is_private else 'No'}")
    
    views = group.get('views', [])
    if views:
        view_names = [v.get('name', '') for v in views if v.get('name')]
        if view_names:
            lines.append(f"  Views: {', '.join(view_names)}")
    
    return "\n".join(lines)

