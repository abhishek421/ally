"""
Query Router - Fast-path routing for meta queries and help requests

This router intercepts queries before they hit the full pipeline to provide
instant responses for common meta queries that don't require data extraction.

Uses LLM-based intent classification to avoid false positives from pattern matching.
"""
import logging
import re
import json
from typing import Optional, Dict, Any, List
from config.config_manager import ConfigManager
from adapters.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate handlers based on LLM-detected intent

    Handles:
    - Meta queries (help, capabilities, greetings) -> instant response
    - Data queries -> full pipeline
    """

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

    # System prompt for intent classification
    INTENT_CLASSIFIER_PROMPT = """You are an intent classifier for a business analytics assistant.

Your task is to classify user queries into ONE of these categories:

1. **greeting** - Simple greetings (hello, hi, good morning, etc.)
   Examples: "Hi", "Hello", "Good morning"

2. **help** - Requests for help or capabilities
   Examples: "What can you do?", "Help me", "What are your capabilities?"

3. **data** - Any query asking about business data (companies, people, interactions, etc.)
   Examples: "Show me companies", "Find John Smith", "Is there any company named Nothing?"

IMPORTANT RULES:
- If the query mentions ANY business entity (company, person, email, interaction), classify as "data"
- Company/person names can be ANYTHING - don't assume patterns
- Only classify as "greeting" or "help" if the query is PURELY about that (no data requests)
- When in doubt, classify as "data" to avoid missing legitimate queries

Respond with ONLY a JSON object in this exact format:
{{
  "intent": "greeting|help|data",
  "confidence": 0.0-1.0
}}

User query: {query}"""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the QueryRouter

        Args:
            config_manager: Configuration manager for LLM setup (optional)
        """
        self.config_manager = config_manager
        self._llm_provider = None

    async def _get_llm_provider(self):
        """Get or create LLM provider for intent classification"""
        if self._llm_provider is None:
            if self.config_manager:
                # Use query_router agent config (or fall back to global)
                llm_config = await self.config_manager.get_agent_config("query_router")
                config_dict = {
                    "provider": llm_config.provider,
                    "model": llm_config.model,
                    "api_key": llm_config.api_key
                }
            else:
                # Fallback to default configuration
                import os
                config_dict = {
                    "provider": os.getenv("LLM_PROVIDER", "openai"),
                    "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),  # Fast model for classification
                    "api_key": os.getenv("OPENAI_API_KEY", "")
                }

            self._llm_provider = LLMProviderFactory.create(config_dict)
            logger.info(f"Initialized LLM provider for query routing: {self._llm_provider}")

        return self._llm_provider

    async def route(self, query: str, context_messages: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Route a query using LLM-based intent classification

        Args:
            query: User query string
            context_messages: Previous conversation messages for context (optional)

        Returns:
            Response dict for meta queries, None for data queries
        """
        # Quick length check - very short queries are likely greetings/help
        query_stripped = query.strip()
        if len(query_stripped) == 0:
            return None

        try:
            # Get intent from LLM (with context for reference resolution)
            intent_result = await self._classify_intent(query_stripped, context_messages)
            intent = intent_result.get("intent")
            confidence = intent_result.get("confidence", 0.0)

            logger.info(f"Intent classification: {intent} (confidence: {confidence:.2f})")

            # Route based on intent
            if intent in ["greeting", "help"]:
                logger.info(f"Fast-path: Detected meta query type '{intent}'")
                return self._create_meta_response(intent)
            else:
                # Data query - needs full pipeline
                logger.debug("Query requires full pipeline processing")
                return None

        except Exception as e:
            logger.error(f"Error in intent classification: {e}", exc_info=True)
            # On error, default to full pipeline to avoid breaking user queries
            logger.warning("Falling back to full pipeline due to classification error")
            return None

    async def _classify_intent(self, query: str, context_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Classify query intent using LLM

        Args:
            query: User query string
            context_messages: Previous conversation messages for context (optional)

        Returns:
            Dict with "intent" and "confidence" keys
        """
        provider = await self._get_llm_provider()

        # Build context string if available
        context_str = ""
        if context_messages and len(context_messages) > 0:
            context_lines = ["PREVIOUS CONVERSATION CONTEXT:"]
            for msg in context_messages[-3:]:  # Last 3 messages
                role = msg.get("role", "UNKNOWN")
                content = msg.get("content", "")
                context_lines.append(f"{role}: {content}")
            context_str = "\n".join(context_lines)
            context_str += "\n\nIMPORTANT: If the query contains references like 'the first one', 'that company', 'the second one', 'it', 'them', etc., it is a DATA query, not a meta query. Classify it as 'data'."

        # Build the prompt
        if context_str:
            prompt = f"{self.INTENT_CLASSIFIER_PROMPT}\n\n{context_str}"
        else:
            prompt = self.INTENT_CLASSIFIER_PROMPT.format(query=query)
        
        # Format query if not already formatted
        if "{query}" in prompt:
            prompt = prompt.format(query=query)

        messages = [
            {"role": "user", "content": prompt}
        ]

        # Call LLM with low temperature for consistent classification
        response = provider.chat(
            messages=messages,
            temperature=0.0,
            max_tokens=50
        )

        # Parse JSON response
        try:
            result = json.loads(response.strip())

            # Validate response format
            if "intent" not in result:
                raise ValueError("Missing 'intent' in LLM response")

            if result["intent"] not in ["greeting", "help", "data"]:
                logger.warning(f"Unknown intent: {result['intent']}, defaulting to 'data'")
                result["intent"] = "data"

            # Ensure confidence is present
            if "confidence" not in result:
                result["confidence"] = 1.0

            return result

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse intent classification response: {e}")
            logger.debug(f"Raw LLM response: {response}")
            # Default to data query on parse error
            return {"intent": "data", "confidence": 0.0}

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
