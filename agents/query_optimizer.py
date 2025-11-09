"""
QueryOptimizerAgent - Converts user queries to more defined and structured queries
"""
from typing import Dict, Optional, List, Any
import logging
import time
from datetime import datetime, timedelta
from adapters.llm_provider import LLMProvider
from config.settings import QUERY_OPTIMIZATION_TEMPLATE
from services.conversation_state import ConversationState


class QueryOptimizerAgent:
    """Optimizes and structures user queries for better data extraction"""
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize QueryOptimizerAgent
        
        Args:
            llm_provider: LLM provider instance (injected dependency)
                         If None, will be created from config
        """
        self.template = QUERY_OPTIMIZATION_TEMPLATE
        self._current_date = datetime.now()
        
        # logger initialization kept lightweight to avoid overriding app-level config
        self._logger = logging.getLogger(__name__)
        if not self._logger.handlers and not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
            )
        
        # Set LLM provider (injected or created from config)
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from adapters.provider_factory import LLMProviderFactory
            from config.settings import get_agent_config
            # Get config using ConfigManager (will fall back to env if not initialized)
            agent_config = get_agent_config("query_optimizer")
            self.llm_provider = LLMProviderFactory.create(agent_config)
            self._logger.info(f"QueryOptimizerAgent using {agent_config.get('provider', 'unknown')}/{agent_config.get('model', 'unknown')}")
        
        self._logger.debug(f"QueryOptimizerAgent initialized with provider: {self.llm_provider}")
    
    def optimize(self, user_query: str, context_messages: List[Dict[str, Any]] = None,
                 conversation_state: Optional[ConversationState] = None) -> str:
        """
        Optimize a user query to make it more structured and actionable

        Args:
            user_query: Natural language query from the user
            context_messages: Previous conversation messages for context
            conversation_state: Conversation state for reference resolution

        Returns:
            Optimized query with clear intent and structure
        """

        self._logger.info("Optimizing query")
        self._logger.debug("User query received: %s", user_query)

        # Resolve references in query using conversation state
        resolved_query = user_query
        if conversation_state:
            resolved_query = self._resolve_references(user_query, conversation_state)
            if resolved_query != user_query:
                self._logger.info(f"Resolved references: '{user_query}' -> '{resolved_query}'")

        # Build context if available
        context_str = ""
        if context_messages:
            self._logger.info(f"Using {len(context_messages)} context messages")
            context_str = self._build_context_string(context_messages)

        # Add conversation state context summary
        if conversation_state:
            context_summary = conversation_state.get_context_summary()
            if context_summary != "No entities tracked yet":
                context_str = f"Context: {context_summary}\n\n{context_str}" if context_str else f"Context: {context_summary}"
                self._logger.debug(f"Added conversation context: {context_summary}")

        # for LLM-based optimization with exact date replacements
        start_time = time.time()
        optimized = self._llm_optimization(resolved_query, context_str)
        elapsed_ms = int((time.time() - start_time) * 1000)
        self._logger.info("Query optimized in %d ms", elapsed_ms)
        self._logger.debug("Optimized query: %s", optimized)

        return optimized

    def _resolve_references(self, user_query: str, conversation_state: ConversationState) -> str:
        """
        Resolve references in the user query using conversation state

        Args:
            user_query: Original user query
            conversation_state: Conversation state with tracked entities

        Returns:
            Query with references replaced by actual entity names
        """
        # Check if query contains reference words
        reference_words = ["first", "second", "third", "that", "it", "them", "this", "those", "these"]
        query_lower = user_query.lower()

        has_reference = any(word in query_lower for word in reference_words)
        if not has_reference:
            return user_query

        # Try to resolve the reference
        resolved = conversation_state.resolve_reference(user_query)
        if resolved and resolved.get("name"):
            entity_name = resolved["name"]
            entity_type = resolved.get("type", "")

            # Replace common reference patterns with the actual name
            import re
            patterns = [
                (r'\bthe first one\b', entity_name),
                (r'\bfirst one\b', entity_name),
                (r'\bthe second one\b', entity_name),
                (r'\bsecond one\b', entity_name),
                (r'\bthe third one\b', entity_name),
                (r'\bthird one\b', entity_name),
                (r'\bthat company\b', entity_name),
                (r'\bthat person\b', entity_name),
                (r'\bthat one\b', entity_name),
                (r'\bthis one\b', entity_name),
                (r'\bit\b', entity_name),
                (r'\btheir\b', entity_name + "'s"),
            ]

            resolved_query = user_query
            for pattern, replacement in patterns:
                resolved_query = re.sub(pattern, replacement, resolved_query, flags=re.IGNORECASE)

            return resolved_query

        return user_query

    def _build_context_string(self, context_messages: List[Dict[str, Any]]) -> str:
        """Build a formatted string from context messages with enhanced entity information"""
        if not context_messages:
            return ""
        
        # Use enhanced context builder if available
        try:
            from utils.context_builder import build_enhanced_context, build_context_string_for_llm
            
            enhanced_context = build_enhanced_context(context_messages, max_messages=10)
            context_str = build_context_string_for_llm(enhanced_context)
            
            self._logger.debug(f"Built enhanced context with {len(enhanced_context.get('entities', {}))} entity types")
            return context_str
            
        except ImportError:
            # Fallback to basic context building if enhanced builder not available
            self._logger.warning("Enhanced context builder not available, using basic context")
            return self._build_basic_context_string(context_messages)
    
    def _build_basic_context_string(self, context_messages: List[Dict[str, Any]]) -> str:
        """Build basic context string (fallback method)"""
        context_lines = ["PREVIOUS CONVERSATION CONTEXT (for reference resolution):"]
        for msg in context_messages[-5:]:  # Last 5 messages for context
            role = msg.get("role", "UNKNOWN")
            content = msg.get("content", "")
            context_lines.append(f"{role}: {content}")
        
        context_str = "\n".join(context_lines)
        context_str += "\n\nCRITICAL INSTRUCTIONS FOR REFERENCE RESOLUTION:"
        context_str += "\n- If the current query contains references like 'the first one', 'that company', 'the second one', 'it', 'them', etc.:"
        context_str += "\n  1. Find the ASSISTANT response in the context above that contains the data"
        context_str += "\n  2. Look for numbered lists (1., 2., etc.) or explicit mentions of company/people names"
        context_str += "\n  3. Extract the EXACT name as it appears in the context (do NOT abbreviate or infer)"
        context_str += "\n  4. If the context says '1. Acme Corporation, 2. Tech Solutions Inc', then 'the second one' refers to 'Tech Solutions Inc' (exact name)"
        context_str += "\n  5. Use the EXACT name/ID from the context in your optimized query - do NOT use abbreviations or inferred names"
        context_str += "\n  6. In the 'optimized_query' field, replace references with the EXACT names from context"
        context_str += "\n  7. In the 'entities' field, use the EXACT names/IDs from context, not the references"
        
        return context_str
    
    def _get_current_date_context(self) -> str:
        """
        Get current date context for LLM to use in replacements
        """
        now = datetime.now()
        last_month = (now.replace(day=1) - timedelta(days=1))
        
        context = f"""
            - Today is: {now.strftime('%B %d, %Y')}
            - Current Month: {now.strftime('%B %Y')}
            - Last Month: {last_month.strftime('%B %Y')}
            - Current Year: {now.year}
            - Last Year: {now.year - 1}
            - Yesterday: {(now - timedelta(days=1)).strftime('%B %d, %Y')}
            - Last Week: {(now - timedelta(weeks=1)).strftime('%B %d, %Y')} to {now.strftime('%B %d, %Y')}
        """
        self._logger.debug("Date context generated")
        return context
    
    def _llm_optimization(self, user_query: str, context_str: str = "") -> str:
        """
        Use LLM to optimize the query with exact date replacements and conversation context
        """
        self._logger.info(f"Calling LLM for optimization (provider={self.llm_provider})")
        
        # Get current date context
        date_context = self._get_current_date_context()
        
        # Build full query with context
        full_query = user_query
        if context_str:
            full_query = f"{context_str}\n\nCurrent query: {user_query}"
        
        # Format template with both date_context and user_query
        prompt = self.template.format(
            date_context=date_context,
            user_query=full_query
        )
        self._logger.debug("Prompt prepared (length=%d)", len(prompt))
        
        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": "You are a QueryOptimizer that replaces relative dates with exact values."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            call_start = time.time()
            optimized = self.llm_provider.chat(messages, temperature=0.3)
            call_elapsed_ms = int((time.time() - call_start) * 1000)
            self._logger.info("LLM call completed in %d ms", call_elapsed_ms)
            return optimized
        except Exception as exc:
            self._logger.exception("LLM optimization failed: %s", str(exc))
            raise


# Convenience function
def optimize_query(query: str) -> str:
    """Convenience function to optimize a query"""
    agent = QueryOptimizerAgent()
    return agent.optimize(query)

