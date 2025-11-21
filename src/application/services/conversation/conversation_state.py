"""
Conversation State Management

Tracks entities (companies, people, emails) across conversation turns to enable
reference resolution like "the first one", "that company", etc.
"""
from typing import Dict, List, Any, Optional
from collections import deque
from threading import Lock
from datetime import datetime
import logging
import json


class ConversationState:
    """
    Manages conversation state across multiple turns.

    Tracks recently mentioned entities and provides reference resolution
    for pronouns and ordinal references.
    """

    MAX_ENTITIES = 10  # Keep last 10 of each entity type

    def __init__(self):
        """Initialize conversation state with empty entity tracking."""
        self.companies: deque = deque(maxlen=self.MAX_ENTITIES)
        self.people: deque = deque(maxlen=self.MAX_ENTITIES)
        self.emails: deque = deque(maxlen=self.MAX_ENTITIES)
        self.last_query: str = ""
        self.current_turn: int = 0
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)

    def update_from_results(self, results: Dict[str, Any]) -> None:
        """
        Extract and store entities from query results.

        Args:
            results: Dictionary containing query results with possible keys:
                    - companies: List of company dicts with id, name
                    - people: List of people dicts with id, name
                    - emails: List of email dicts with message_id, subject

        Example:
            results = {
                "companies": [{"id": "123", "name": "Acme Corp"}],
                "people": [{"id": "456", "name": "John Smith"}]
            }
            state.update_from_results(results)
        """
        with self._lock:
            self.current_turn += 1

            # Extract companies
            if "companies" in results and isinstance(results["companies"], list):
                for company in results["companies"]:
                    if isinstance(company, dict) and "name" in company:
                        self.companies.append({
                            "id": company.get("id"),
                            "name": company.get("name"),
                            "turn_number": self.current_turn
                        })

            # Extract people
            if "people" in results and isinstance(results["people"], list):
                for person in results["people"]:
                    if isinstance(person, dict) and "name" in person:
                        self.people.append({
                            "id": person.get("id"),
                            "name": person.get("name"),
                            "turn_number": self.current_turn
                        })

            # Extract emails
            if "emails" in results and isinstance(results["emails"], list):
                for email in results["emails"]:
                    if isinstance(email, dict):
                        self.emails.append({
                            "message_id": email.get("message_id") or email.get("id"),
                            "subject": email.get("subject", ""),
                            "turn_number": self.current_turn
                        })

    def resolve_reference(self, reference: str) -> Optional[Dict[str, str]]:
        """
        Resolve natural language references to specific entities.

        Args:
            reference: Reference string like "the first one", "that company", "them"

        Returns:
            Dictionary with type, id, and name of referenced entity, or None if unresolvable

        Examples:
            >>> state.resolve_reference("the first one")
            {"type": "company", "id": "123", "name": "Acme Corp"}

            >>> state.resolve_reference("the second one")
            {"type": "company", "id": "456", "name": "TechCorp"}

            >>> state.resolve_reference("that company")
            {"type": "company", "id": "789", "name": "StartupXYZ"}
        """
        with self._lock:
            reference_lower = reference.lower().strip()

            # Get most recent entities from current turn
            current_turn_entities = self._get_current_turn_entities()

            # Handle ordinal references: "the first one", "first", "1st"
            if any(x in reference_lower for x in ["first", "1st", "one"]) and not "second" in reference_lower:
                if current_turn_entities:
                    entity = current_turn_entities[0]
                    return {
                        "type": entity["type"],
                        "id": str(entity.get("id", "")),
                        "name": entity.get("name", "")
                    }

            # Handle "the second one", "second", "2nd"
            if any(x in reference_lower for x in ["second", "2nd", "two"]):
                if len(current_turn_entities) >= 2:
                    entity = current_turn_entities[1]
                    return {
                        "type": entity["type"],
                        "id": str(entity.get("id", "")),
                        "name": entity.get("name", "")
                    }

            # Handle "the third one", "third", "3rd"
            if any(x in reference_lower for x in ["third", "3rd", "three"]):
                if len(current_turn_entities) >= 3:
                    entity = current_turn_entities[2]
                    return {
                        "type": entity["type"],
                        "id": str(entity.get("id", "")),
                        "name": entity.get("name", "")
                    }

            # Handle specific entity type references
            if "company" in reference_lower or "companies" in reference_lower:
                if self.companies:
                    latest = self.companies[-1]
                    return {
                        "type": "company",
                        "id": str(latest.get("id", "")),
                        "name": latest.get("name", "")
                    }

            if "person" in reference_lower or "people" in reference_lower:
                if self.people:
                    latest = self.people[-1]
                    return {
                        "type": "person",
                        "id": str(latest.get("id", "")),
                        "name": latest.get("name", "")
                    }

            if "email" in reference_lower or "message" in reference_lower:
                if self.emails:
                    latest = self.emails[-1]
                    return {
                        "type": "email",
                        "id": str(latest.get("message_id", "")),
                        "name": latest.get("subject", "")
                    }

            # Handle generic references: "it", "that", "this"
            if reference_lower in ["it", "that", "this", "that one", "this one"]:
                if current_turn_entities:
                    entity = current_turn_entities[-1]  # Most recent
                    return {
                        "type": entity["type"],
                        "id": str(entity.get("id", "")),
                        "name": entity.get("name", "")
                    }

            # Handle plural: "them", "those", "these"
            if reference_lower in ["them", "those", "these"]:
                # Return the most recent entity type with multiple entries
                if len(current_turn_entities) > 1:
                    # Return first entity but indicate it's part of a group
                    entity = current_turn_entities[0]
                    return {
                        "type": entity["type"],
                        "id": "multiple",
                        "name": f"multiple {entity['type']}s"
                    }

            return None

    def get_context_summary(self) -> str:
        """
        Generate human-readable summary of current conversation state.

        Returns:
            String summary of recently mentioned entities

        Example:
            "Recent entities: 3 companies (Acme Corp, TechCorp, StartupXYZ), 2 people (John Smith, Jane Doe)"
        """
        with self._lock:
            parts = []

            if self.companies:
                company_names = [c["name"] for c in list(self.companies)[-5:]]  # Last 5
                parts.append(f"{len(self.companies)} companies ({', '.join(company_names)})")

            if self.people:
                people_names = [p["name"] for p in list(self.people)[-5:]]
                parts.append(f"{len(self.people)} people ({', '.join(people_names)})")

            if self.emails:
                email_subjects = [e["subject"][:30] for e in list(self.emails)[-3:]]  # Last 3, truncated
                parts.append(f"{len(self.emails)} emails")

            if parts:
                return f"Recent entities: {', '.join(parts)}"
            else:
                return "No entities tracked yet"

    def _get_current_turn_entities(self) -> List[Dict[str, Any]]:
        """
        Get all entities from the current turn in order they were added.

        Returns:
            List of entity dicts with type, id, name, turn_number
        """
        entities = []

        # Collect all entities from current turn
        for company in self.companies:
            if company["turn_number"] == self.current_turn:
                entities.append({
                    "type": "company",
                    "id": company.get("id"),
                    "name": company.get("name"),
                    "turn_number": company["turn_number"]
                })

        for person in self.people:
            if person["turn_number"] == self.current_turn:
                entities.append({
                    "type": "person",
                    "id": person.get("id"),
                    "name": person.get("name"),
                    "turn_number": person["turn_number"]
                })

        for email in self.emails:
            if email["turn_number"] == self.current_turn:
                entities.append({
                    "type": "email",
                    "id": email.get("message_id"),
                    "name": email.get("subject"),
                    "turn_number": email["turn_number"]
                })

        return entities

    def clear(self) -> None:
        """Clear all tracked entities and reset state."""
        with self._lock:
            self.companies.clear()
            self.people.clear()
            self.emails.clear()
            self.last_query = ""
            self.current_turn = 0

    def set_last_query(self, query: str) -> None:
        """
        Store the last user query.

        Args:
            query: The user's query string
        """
        with self._lock:
            self.last_query = query

    def rebuild_from_messages(self, messages: List[Dict[str, Any]]) -> None:
        """
        Rebuild conversation state from previous conversation messages.

        Args:
            messages: List of conversation messages with role, blocks, and metadata
                     Messages should be in chronological order (oldest first)

        Example:
            messages = [
                {
                    "role": "USER",
                    "blocks": [...],
                    "metadata": None
                },
                {
                    "role": "ASSISTANT",
                    "blocks": [...],
                    "metadata": {"query_context": {"result_summary": {...}}}
                }
            ]
            state.rebuild_from_messages(messages)
        """
        with self._lock:
            # Clear existing state
            self.companies.clear()
            self.people.clear()
            self.emails.clear()
            self.current_turn = 0

            # Process each assistant message to extract entities
            for msg in messages:
                # Only process assistant messages
                if msg.get("role") != "ASSISTANT":
                    continue

                # Increment turn for each assistant message
                self.current_turn += 1

                # Method 1: Extract from ENTITY_LIST blocks (preferred - most accurate)
                blocks = msg.get("blocks", [])
                for block in blocks:
                    if block.get("block_type") == "ENTITY_LIST":
                        content = block.get("content", "")
                        metadata = block.get("metadata", {})
                        entity_type = metadata.get("entity_type", "")
                        
                        # Parse NDJSON
                        try:
                            for line in content.strip().split('\n'):
                                if line:
                                    entity = json.loads(line)
                                    entity_id = entity.get("id", "")
                                    entity_name = entity.get("name", "")
                                    
                                    if entity_type == "companies":
                                        self.companies.append({
                                            "id": entity_id,
                                            "name": entity_name,
                                            "turn_number": self.current_turn
                                        })
                                    elif entity_type == "people":
                                        self.people.append({
                                            "id": entity_id,
                                            "name": entity_name,
                                            "turn_number": self.current_turn
                                        })
                        except Exception as e:
                            self._logger.warning(f"Failed to parse ENTITY_LIST for state rebuild: {e}")

                # Method 2: Fallback to metadata (for backwards compatibility or TABLE blocks)
                metadata = msg.get("metadata") or {}
                query_context = metadata.get("query_context", {})
                result_summary = query_context.get("result_summary", {})

                if result_summary:
                    # Extract entities from result_summary
                    for tool_name, tool_summary in result_summary.items():
                        if not isinstance(tool_summary, dict):
                            continue

                        # Extract companies (only if not already extracted from ENTITY_LIST)
                        if "company_names" in tool_summary and "company_ids" in tool_summary:
                            company_names = tool_summary["company_names"]
                            company_ids = tool_summary["company_ids"]
                            # Check if we already have companies from this turn
                            turn_companies = [c for c in self.companies if c["turn_number"] == self.current_turn]
                            if not turn_companies:
                                for idx, name in enumerate(company_names):
                                    company_id = company_ids[idx] if idx < len(company_ids) else None
                                    self.companies.append({
                                        "id": company_id,
                                        "name": name,
                                        "turn_number": self.current_turn
                                    })

                        # Extract people (only if not already extracted from ENTITY_LIST)
                        if "people_names" in tool_summary and "people_ids" in tool_summary:
                            people_names = tool_summary["people_names"]
                            people_ids = tool_summary["people_ids"]
                            # Check if we already have people from this turn
                            turn_people = [p for p in self.people if p["turn_number"] == self.current_turn]
                            if not turn_people:
                                for idx, name in enumerate(people_names):
                                    person_id = people_ids[idx] if idx < len(people_ids) else None
                                    self.people.append({
                                        "id": person_id,
                                        "name": name,
                                        "turn_number": self.current_turn
                                    })

                        # Extract emails
                        if "email_ids" in tool_summary:
                            email_ids = tool_summary["email_ids"]
                            for email_id in email_ids:
                                self.emails.append({
                                    "message_id": email_id,
                                    "subject": "",  # Subject not stored in compact metadata
                                    "turn_number": self.current_turn
                                })

            # Log rebuild results
            self._logger.info(
                f"Rebuilt conversation state: {len(self.companies)} companies, "
                f"{len(self.people)} people, {len(self.emails)} emails from {len(messages)} messages"
            )
            if self.companies:
                company_names = [c["name"] for c in list(self.companies)[:5]]
                self._logger.info(f"Companies in state: {company_names}")
            if self.people:
                people_names = [p["name"] for p in list(self.people)[:5]]
                self._logger.info(f"People in state: {people_names}")
