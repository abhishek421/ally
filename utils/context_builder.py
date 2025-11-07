"""
Enhanced Context Builder for Reference Resolution

Builds structured context from conversation history that includes:
- Entity lists with explicit ordering
- Entity types and metadata
- Most recent entity context
- Structured data from message metadata
"""
from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class EntityContext:
    """Represents entities mentioned in a conversation message"""
    
    def __init__(self):
        self.companies: List[Dict[str, Any]] = []
        self.people: List[Dict[str, Any]] = []
        self.emails: List[Dict[str, Any]] = []
        self.interactions: List[Dict[str, Any]] = []
        self.groups: List[Dict[str, Any]] = []
        self.entity_type: Optional[str] = None  # Most recent entity type
        self.timestamp: Optional[str] = None


def build_enhanced_context(
    context_messages: List[Dict[str, Any]],
    max_messages: int = 10
) -> Dict[str, Any]:
    """
    Build enhanced context with structured entity information.
    
    Args:
        context_messages: List of message dicts with 'role', 'content', and optionally 'metadata'
        max_messages: Maximum number of messages to process
        
    Returns:
        Enhanced context dictionary with:
        - messages: Original message text
        - entities: Structured entity lists by type
        - most_recent_entity_type: Type of most recently mentioned entity
        - entity_summary: Summary of all entities mentioned
    """
    if not context_messages:
        return {
            "messages": [],
            "entities": {},
            "most_recent_entity_type": None,
            "entity_summary": ""
        }
    
    # Process last N messages (most recent first)
    recent_messages = context_messages[-max_messages:]
    
    # Extract entities from messages
    all_entities = {
        "companies": [],
        "people": [],
        "emails": [],
        "interactions": [],
        "groups": []
    }
    
    most_recent_entity_type = None
    entity_contexts = []
    
    # Process messages in reverse order (oldest to newest)
    for msg in recent_messages:
        role = msg.get("role", "UNKNOWN")
        content = msg.get("content", "")
        metadata = msg.get("metadata", {})
        
        # Extract entities from metadata (structured data)
        if metadata and isinstance(metadata, dict):
            query_context = metadata.get("query_context", {})
            if query_context:
                entities = _extract_entities_from_metadata(query_context)
                if entities:
                    # Merge entities, preserving order
                    for entity_type, entity_list in entities.items():
                        if entity_list:
                            all_entities[entity_type].extend(entity_list)
                            if not most_recent_entity_type:
                                most_recent_entity_type = entity_type
        
        # Also extract entities from text (for messages without metadata)
        if role == "ASSISTANT" and content:
            text_entities = _extract_entities_from_text(content)
            if text_entities:
                for entity_type, entity_list in text_entities.items():
                    if entity_list:
                        all_entities[entity_type].extend(entity_list)
                        if not most_recent_entity_type:
                            most_recent_entity_type = entity_type
    
    # Build entity summary
    entity_summary = _build_entity_summary(all_entities, most_recent_entity_type)
    
    # Build message context (text only, for LLM)
    message_context = _build_message_context(recent_messages)
    
    return {
        "messages": message_context,
        "entities": all_entities,
        "most_recent_entity_type": most_recent_entity_type,
        "entity_summary": entity_summary
    }


def _extract_entities_from_metadata(query_context: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract entities from query context metadata.
    
    Metadata structure:
    {
        "result_summary": {
            "companies": {
                "company_ids": ["id1", "id2"],
                "count": 2,
                "company_names": ["Name1", "Name2"]  # if available
            },
            "people": {...}
        }
    }
    """
    entities = {
        "companies": [],
        "people": [],
        "emails": [],
        "interactions": [],
        "groups": []
    }
    
    result_summary = query_context.get("result_summary", {})
    if not isinstance(result_summary, dict):
        return entities
    
    # Extract companies
    if "companies" in result_summary:
        company_data = result_summary["companies"]
        company_ids = company_data.get("company_ids", [])
        company_names = company_data.get("company_names", [])
        count = company_data.get("count", len(company_ids))
        
        for i, company_id in enumerate(company_ids[:count]):
            entity = {
                "id": company_id,
                "index": i + 1,
                "name": company_names[i] if i < len(company_names) else None
            }
            entities["companies"].append(entity)
    
    # Extract people
    if "people" in result_summary:
        people_data = result_summary["people"]
        people_ids = people_data.get("people_ids", [])
        people_names = people_data.get("people_names", [])
        count = people_data.get("count", len(people_ids))
        
        for i, person_id in enumerate(people_ids[:count]):
            entity = {
                "id": person_id,
                "index": i + 1,
                "name": people_names[i] if i < len(people_names) else None
            }
            entities["people"].append(entity)
    
    # Extract emails
    if "emails" in result_summary:
        email_data = result_summary["emails"]
        email_ids = email_data.get("email_ids", [])
        count = email_data.get("count", len(email_ids))
        
        for i, email_id in enumerate(email_ids[:count]):
            entity = {
                "id": email_id,
                "index": i + 1
            }
            entities["emails"].append(entity)
    
    return entities


def _extract_entities_from_text(content: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract entities from text content using simple pattern matching.
    
    This is a fallback when metadata is not available.
    """
    entities = {
        "companies": [],
        "people": [],
        "emails": [],
        "interactions": [],
        "groups": []
    }
    
    # Look for numbered lists (1. Name, 2. Name, etc.)
    import re
    numbered_pattern = r'(\d+)\.\s+([^\n]+)'
    matches = re.findall(numbered_pattern, content)
    
    if matches:
        # Try to determine entity type from context
        content_lower = content.lower()
        entity_type = None
        
        if "compan" in content_lower:
            entity_type = "companies"
        elif "people" in content_lower or "person" in content_lower or "contact" in content_lower:
            entity_type = "people"
        elif "email" in content_lower:
            entity_type = "emails"
        elif "interaction" in content_lower or "meeting" in content_lower:
            entity_type = "interactions"
        elif "group" in content_lower:
            entity_type = "groups"
        
        if entity_type:
            for index, name in matches:
                entity = {
                    "index": int(index),
                    "name": name.strip()
                }
                entities[entity_type].append(entity)
    
    return entities


def _build_entity_summary(
    entities: Dict[str, List[Dict[str, Any]]],
    most_recent_type: Optional[str]
) -> str:
    """Build a human-readable summary of entities for LLM context."""
    summary_lines = []
    
    if most_recent_type:
        summary_lines.append(f"MOST RECENT ENTITY TYPE: {most_recent_type.upper()}")
        summary_lines.append("")
    
    # Build entity lists with explicit ordering
    for entity_type, entity_list in entities.items():
        if entity_list:
            summary_lines.append(f"{entity_type.upper()}:")
            for entity in entity_list:
                index = entity.get("index", "?")
                name = entity.get("name")
                entity_id = entity.get("id")
                
                if name:
                    summary_lines.append(f"  {index}. {name} (id: {entity_id})" if entity_id else f"  {index}. {name}")
                elif entity_id:
                    summary_lines.append(f"  {index}. [id: {entity_id}]")
            summary_lines.append("")
    
    return "\n".join(summary_lines)


def _build_message_context(messages: List[Dict[str, Any]]) -> str:
    """Build text context from messages."""
    context_lines = ["PREVIOUS CONVERSATION CONTEXT:"]
    
    for msg in messages:
        role = msg.get("role", "UNKNOWN")
        content = msg.get("content", "")
        context_lines.append(f"{role}: {content}")
    
    return "\n".join(context_lines)


def build_context_string_for_llm(enhanced_context: Dict[str, Any]) -> str:
    """
    Build a formatted context string for LLM prompts.
    
    Includes both message text and structured entity information.
    """
    parts = []
    
    # Add message context
    if enhanced_context.get("messages"):
        parts.append(enhanced_context["messages"])
    
    # Add entity summary
    if enhanced_context.get("entity_summary"):
        parts.append("\nSTRUCTURED ENTITY INFORMATION:")
        parts.append(enhanced_context["entity_summary"])
    
    # Add reference resolution instructions
    if enhanced_context.get("most_recent_entity_type"):
        entity_type = enhanced_context["most_recent_entity_type"]
        parts.append(f"\nCRITICAL INSTRUCTIONS FOR REFERENCE RESOLUTION:")
        parts.append(f"- The most recent entity type discussed is: {entity_type}")
        parts.append(f"- When resolving references like 'the first one', 'the second one', 'the last one':")
        parts.append(f"  1. Check the {entity_type} list above for the entity order")
        parts.append(f"  2. Use the EXACT name/ID from the list (do NOT abbreviate or infer)")
        parts.append(f"  3. 'the first one' = index 1, 'the second one' = index 2, 'the last one' = last index")
        parts.append(f"  4. If switching entity types, look for the most recent entity type mentioned")
    
    return "\n".join(parts)

