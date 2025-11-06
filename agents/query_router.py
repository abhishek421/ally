"""
Query Router - Fast-path routing for meta queries and help requests

This router intercepts queries before they hit the full pipeline to provide
instant responses for common meta queries that don't require data extraction.
"""
import logging
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
            "response": """I'm an AI Analyst that helps you query and analyze your business data. Here's what I can do:

**Search & Find:**
- Find companies, people, emails, interactions, and groups
- Search by name, domain, tags, or other attributes
- Example: "Find all companies in the tech industry"

**Count & Analyze:**
- Count entities matching your criteria
- Get analytics and summaries
- Example: "How many people work at Acme Corp?"

**List & Browse:**
- List all entities of a type
- Browse through your data
- Example: "Show me all recent interactions"

**Relationships:**
- Find connections between entities
- Explore related data
- Example: "Show me people at Microsoft"

Just ask me a question in natural language, and I'll fetch the data for you!""",
            "metadata": {
                "type": "meta_help",
                "fast_path": True
            }
        },
        "greeting": {
            "response": "Hello! I'm your AI Analyst. I can help you search, analyze, and understand your business data. What would you like to know?",
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
