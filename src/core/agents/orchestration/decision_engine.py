"""
DecisionEngine - Intelligent query routing and agent selection

This engine analyzes queries and decides:
1. Can we respond directly without agents?
2. Which agents are needed?
3. In what order should they execute?
4. What parameters should be used?
"""
import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ExecutionDecision:
    """
    Decision about how to handle a query

    Three types of decisions:
    1. DIRECT: Respond immediately without agents
    2. SIMPLE: Use minimal agents (no optimization/validation)
    3. COMPLEX: Use full agent pipeline with validation
    """
    strategy: str  # "direct", "simple", "complex"
    agents_needed: List[str]  # List of agent names to use
    reasoning: str  # Why this decision was made
    estimated_cost: str  # "zero", "low", "medium", "high"
    confidence: float  # Confidence in this decision (0-1)

    # Execution parameters
    skip_optimization: bool = False
    skip_validation: bool = False
    use_reactive: bool = False  # Use reactive vs static extractor
    max_retries: int = 0
    meta_type: Optional[str] = None  # "greeting", "help", "introduction" for meta queries


class DecisionEngine:
    """
    Intelligent decision engine for query routing

    Makes decisions based on:
    - Query patterns (regex matching)
    - Query complexity (word count, structure)
    - Query intent (meta, data, analytical)
    - Historical performance (optional future feature)
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)

        # Pattern-based rules for quick decisions
        self._meta_patterns = [
            (r'^(hi|hello|hey|greetings?)$', "greeting"),
            (r'(what can you do|help|capabilities|how do you work)', "help"),
            (r'(who are you|what are you|introduce yourself)', "introduction"),
        ]

        self._simple_patterns = [
            (r'^(show|list|get|find|display)\s+(all\s+)?(companies|people|emails?|interactions?|groups?|workspaces?)$', "list_all"),
            (r'^(show|get|find)\s+me\s+(companies|people|emails?|interactions?|groups?)$', "list_all"),
        ]

        self._complex_indicators = [
            "aggregate", "sum", "average", "count", "total",
            "group by", "compare", "analyze", "trend",
            "where", "with", "that have", "filter by"
        ]

    def decide(
        self,
        query: str,
        context_messages: Optional[List[Dict]] = None,
        is_first_message: bool = False
    ) -> ExecutionDecision:
        """
        Analyze query and decide execution strategy

        Args:
            query: User query
            context_messages: Previous conversation messages
            is_first_message: Whether this is the first message

        Returns:
            ExecutionDecision with strategy and agent list
        """
        query_lower = query.lower().strip()
        self._logger.info(f"Analyzing query: {query[:100]}")

        # Step 1: Check for meta queries (greeting, help, etc.)
        meta_type = self._detect_meta_query(query_lower)
        if meta_type:
            self._logger.info(f"Decision: DIRECT response (meta query: {meta_type})")
            return ExecutionDecision(
                strategy="direct",
                agents_needed=[],  # No agents needed - orchestrator handles directly
                reasoning=f"Meta query detected ({meta_type}) - instant response",
                estimated_cost="zero",
                confidence=0.95,
                skip_optimization=True,
                skip_validation=True,
                meta_type=meta_type
            )

        # Step 2: Check if query has referential terms needing context
        has_reference = self._has_referential_terms(query_lower)
        if has_reference and not context_messages:
            # References but no context - might need clarification
            self._logger.info("Query has references but no context available")

        # Step 3: Detect if query needs data extraction
        needs_data = self._needs_data_extraction(query_lower)
        if not needs_data:
            self._logger.info("Decision: DIRECT response (no data needed)")
            return ExecutionDecision(
                strategy="direct",
                agents_needed=[],  # No agents needed
                reasoning="Query doesn't require data extraction",
                estimated_cost="zero",
                confidence=0.85
            )

        # Step 4: Classify query complexity
        complexity = self._classify_complexity(query_lower, query)

        # Step 5: Check if query is clear and unambiguous
        is_ambiguous = self._is_ambiguous(query_lower, has_reference, context_messages)

        # Step 6: Decide strategy based on complexity and clarity
        if complexity == "simple" and not is_ambiguous:
            # SIMPLE strategy: Direct extraction, no optimization/validation
            self._logger.info("Decision: SIMPLE strategy (clear + simple)")
            return ExecutionDecision(
                strategy="simple",
                agents_needed=["data_extractor"],
                reasoning="Simple, clear query - direct extraction",
                estimated_cost="low",
                confidence=0.90,
                skip_optimization=True,
                skip_validation=True,
                max_retries=0
            )

        elif complexity == "simple" and is_ambiguous:
            # SIMPLE: Even if ambiguous, LLM can handle it
            self._logger.info("Decision: SIMPLE strategy (LLM handles ambiguity)")
            return ExecutionDecision(
                strategy="simple",
                agents_needed=["data_extractor"],
                reasoning="Simple query - LLM handles ambiguity directly",
                estimated_cost="low",
                confidence=0.85,
                skip_optimization=True,
                skip_validation=True,
                max_retries=0
            )

        elif complexity == "medium":
            # STANDARD strategy: Extraction + Validation (no optimizer)
            self._logger.info("Decision: STANDARD strategy (medium complexity)")
            return ExecutionDecision(
                strategy="complex",
                agents_needed=["data_extractor", "result_validator"],
                reasoning="Medium complexity - extraction with validation",
                estimated_cost="medium",
                confidence=0.80,
                skip_optimization=True,
                skip_validation=False,
                max_retries=1
            )

        else:  # complex
            # COMPLEX strategy: Extraction with validation (no optimizer)
            self._logger.info("Decision: COMPLEX strategy (high complexity)")
            return ExecutionDecision(
                strategy="complex",
                agents_needed=["data_extractor", "result_validator"],
                reasoning="Complex query - extraction with validation",
                estimated_cost="medium",
                confidence=0.80,
                skip_optimization=True,
                skip_validation=False,
                use_reactive=False,
                max_retries=2
            )

    def _detect_meta_query(self, query_lower: str) -> Optional[str]:
        """
        Detect if query is a meta query (help, greeting, etc.)

        Returns:
            Meta type string, or None if not a meta query
        """
        for pattern, meta_type in self._meta_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return meta_type
        return None

    def _needs_data_extraction(self, query_lower: str) -> bool:
        """
        Determine if query requires data extraction

        Returns:
            True if data extraction is needed
        """
        # Keywords indicating data queries
        data_keywords = [
            "show", "find", "get", "list", "search",
            "who", "what", "where", "which",
            "company", "companies", "people", "person",
            "email", "interaction", "meeting", "group",
            "how many", "count", "number"
        ]

        # If query contains any data keywords, it needs extraction
        return any(keyword in query_lower for keyword in data_keywords)

    def _classify_complexity(self, query_lower: str, query_original: str) -> str:
        """
        Classify query complexity: simple, medium, or complex

        Returns:
            "simple", "medium", or "complex"
        """
        complexity_score = 0

        # Check for complex indicators
        for indicator in self._complex_indicators:
            if indicator in query_lower:
                complexity_score += 2

        # Check for multiple entities
        entities = ["company", "companies", "people", "person", "email", "interaction", "group"]
        entities_mentioned = sum(1 for entity in entities if entity in query_lower)
        if entities_mentioned > 2:
            complexity_score += 1

        # Check for filters/conditions
        filter_words = ["where", "with", "that", "having", "contains"]
        filters_present = sum(1 for word in filter_words if word in query_lower)
        if filters_present >= 2:
            complexity_score += 1

        # Check query length
        word_count = len(query_original.split())
        if word_count > 15:
            complexity_score += 1

        # Classify based on score
        if complexity_score == 0:
            return "simple"
        elif complexity_score <= 2:
            return "medium"
        else:
            return "complex"

    def _is_ambiguous(
        self,
        query_lower: str,
        has_reference: bool,
        context_messages: Optional[List[Dict]]
    ) -> bool:
        """
        Check if query is ambiguous or unclear

        Returns:
            True if query is ambiguous
        """
        # References without context are ambiguous
        if has_reference and not context_messages:
            return True

        # Very short queries might be ambiguous
        word_count = len(query_lower.split())
        if word_count <= 2:
            return True

        # Vague terms indicate ambiguity
        vague_terms = ["some", "few", "several", "various", "certain", "stuff", "things"]
        if any(term in query_lower for term in vague_terms):
            return True

        return False

    def _has_referential_terms(self, query_lower: str) -> bool:
        """
        Check if query contains referential terms (that, those, it, them)

        Returns:
            True if referential terms are present
        """
        referential_terms = [
            'that', 'those', 'these', 'them', 'it',
            'the first', 'the second', 'the last',
            'above', 'previous', 'earlier',
            'same', 'similar'
        ]

        return any(term in query_lower for term in referential_terms)
