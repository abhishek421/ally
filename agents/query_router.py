"""
Query Router - Fast-path routing for meta queries and help requests

This router intercepts queries before they hit the full pipeline to provide
instant responses for common meta queries that don't require data extraction.

Also detects simple queries that can skip QueryOptimizer for faster execution.
"""
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate handlers based on intent

    Handles:
    - Meta queries (help, capabilities, etc.) -> instant response
    - Data queries -> full pipeline
    """

    # Meta query patterns and their responses
    META_PATTERNS = {
        "help": [
            "help",
            "how can you help",
            "what can you do",
            "how do you work",
            "what are your capabilities",
            "help me",
            "what do you do"
        ],
        "greeting": [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening"
        ]
    }

    # Pre-defined responses for meta queries
    META_RESPONSES = {
        "help": {
            "response": """I'm Analyst, an AI Business Analyst by SoftSync. I help you query and analyze your business data.

**What I can do:**
- **Search & Find**: Companies, people, emails, interactions, groups
- **Count & Analyze**: Get counts, summaries, and analytics
- **List & Browse**: View all entities of a specific type
- **Explore Relationships**: Find connections between entities

**Example queries:**
- "Find all companies in the tech industry"
- "How many people work at Acme Corp?"
- "Show me all recent interactions"
- "Show me people at Microsoft"

**What I cannot do (yet):**
- Create, update, or delete records
- Send emails or schedule meetings
- Modify your data in any way

I'm read-only and focused on helping you understand your data. Just ask me a question in natural language!""",
            "metadata": {
                "type": "meta_help",
                "fast_path": True
            }
        },
        "greeting": {
            "response": "Hello! I'm Analyst, an AI Business Analyst by SoftSync. I can help you search, analyze, and understand your business data. What would you like to know?",
            "metadata": {
                "type": "meta_greeting",
                "fast_path": True
            }
        }
    }

    def route(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Route a query - returns None if it should go to full pipeline,
        or a response dict if it can be handled instantly

        Args:
            query: User query string

        Returns:
            Response dict for meta queries, None for data queries
        """
        query_lower = query.lower().strip()

        # Check meta patterns
        for meta_type, patterns in self.META_PATTERNS.items():
            for pattern in patterns:
                if pattern in query_lower:
                    logger.info(f"Fast-path: Detected meta query type '{meta_type}'")
                    return self._create_meta_response(meta_type)

        # Not a meta query - needs full pipeline
        logger.debug("Query requires full pipeline processing")
        return None

    def _create_meta_response(self, meta_type: str) -> Dict[str, Any]:
        """
        Create a response for a meta query type

        Args:
            meta_type: Type of meta query (help, greeting, etc.)

        Returns:
            Response dictionary
        """
        if meta_type not in self.META_RESPONSES:
            logger.warning(f"Unknown meta type: {meta_type}, falling back to help")
            meta_type = "help"

        response = self.META_RESPONSES[meta_type].copy()
        response["metadata"]["fast_path_ms"] = 0  # Instant response

        return response

    def is_simple_query(self, query: str) -> bool:
        """
        Detect if a query is simple enough to skip QueryOptimizer

        Simple queries are straightforward entity lookups that don't need
        LLM-based query optimization. These can go directly to DataExtractor.

        Patterns:
        - "Show me all X"
        - "Find X"
        - "List X"
        - "Get X"
        - "Show me X"

        Args:
            query: User query string

        Returns:
            True if query is simple and can skip optimization
        """
        query_lower = query.lower().strip()

        # Remove common filler words for pattern matching
        query_clean = query_lower.replace(' me ', ' ').replace(' all ', ' ')

        # Simple patterns (regex for flexibility)
        simple_patterns = [
            r'^show\s+(all\s+)?(\w+)$',           # "show companies", "show all people"
            r'^list\s+(all\s+)?(\w+)$',           # "list companies"
            r'^get\s+(all\s+)?(\w+)$',            # "get companies"
            r'^find\s+(\w+(\s+\w+)?)$',           # "find john", "find acme corporation"
            r'^(show|get|list)\s+(my\s+)?(\w+)$', # "show my companies"
        ]

        for pattern in simple_patterns:
            if re.match(pattern, query_clean):
                logger.info(f"Simple query detected (skip optimization): {query[:50]}...")
                return True

        return False

    def needs_context(self, query: str, is_first_message: bool = False) -> bool:
        """
        Determine if conversation context retrieval is needed

        Context is only needed if:
        1. Not the first message in conversation
        2. Query contains referential terms (that, those, these, them, more, again, etc.)

        This saves 500-800ms for most queries

        Args:
            query: User query string
            is_first_message: Whether this is the first message in conversation

        Returns:
            True if context should be retrieved
        """
        # First message never needs context
        if is_first_message:
            logger.info("First message: Skipping context retrieval")
            return False

        query_lower = query.lower()

        # Referential terms that indicate query depends on previous context
        referential_terms = [
            'that', 'those', 'these', 'them',  # References
            'more', 'additional', 'other',     # Continuation
            'again', 'also', 'too',            # Repetition
            'previous', 'last', 'earlier',     # Historical reference
            'same', 'similar',                 # Comparison
            'the email', 'the company', 'the person',  # Specific references
        ]

        has_reference = any(term in query_lower for term in referential_terms)

        if has_reference:
            logger.info("Referential query: Will retrieve context")
        else:
            logger.info("Self-contained query: Skipping context retrieval")

        return has_reference
