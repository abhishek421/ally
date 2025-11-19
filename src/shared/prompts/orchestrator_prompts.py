"""
Prompts for OrchestratorAgent

These prompts guide the orchestrator through:
1. Query analysis (complexity, intent, clarity)
2. Execution planning (strategy selection)
"""

# ============================================================================
# QUERY ANALYSIS PROMPT
# ============================================================================

ORCHESTRATOR_ANALYZE_PROMPT = """You are analyzing a user query to determine execution strategy.

USER QUERY:
{user_query}

CONVERSATION CONTEXT (if any):
{context}

Your task is to analyze this query and return a structured analysis in JSON format.

ANALYSIS CRITERIA:

1. COMPLEXITY:
   - SIMPLE: Single entity, no filters, straightforward (e.g., "list all companies")
   - MEDIUM: Multiple entities OR complex filters (e.g., "companies in SF with >5 employees")
   - COMPLEX: Multi-step, aggregations, dependencies, relationships (e.g., "companies we emailed last month that haven't responded")

2. INTENT:
   - SEARCH: Find entities matching criteria
   - COUNT: Count matching entities
   - ANALYTICS: Compute aggregations or metrics
   - GET_BY_ID: Retrieve specific entity by ID/name
   - LIST: List all entities (no filters)
   - RELATIONSHIP: Find relationships between entities

3. ENTITIES MENTIONED:
   - List all entity types mentioned: companies, people, emails, interactions, groups, workspace

4. FILTERS DETECTED:
   - List all filters/conditions mentioned (location, date range, status, etc.)

5. CLARITY SCORE (0.0-1.0):
   - 1.0: Perfectly clear, unambiguous
   - 0.7-0.9: Mostly clear, minor ambiguity
   - 0.4-0.6: Somewhat ambiguous
   - 0.0-0.3: Very ambiguous or unclear

6. REQUIRES OPTIMIZATION:
   - true: Query needs to be refined/optimized for better execution
   - false: Query is already clear and well-formed

7. ESTIMATED STEPS:
   - Number of tool calls / operations needed (1-5+)

Return your analysis in this JSON format:
{{
  "complexity": "simple|medium|complex",
  "intent": "search|count|analytics|get_by_id|list|relationship",
  "entities_mentioned": ["company", "people", ...],
  "filters_detected": ["location:SF", "employee_count:>5", ...],
  "clarity_score": 0.85,
  "requires_optimization": true,
  "estimated_steps": 2,
  "reasoning": "Explanation of your analysis"
}}

EXAMPLES:

Query: "List all companies"
{{
  "complexity": "simple",
  "intent": "list",
  "entities_mentioned": ["company"],
  "filters_detected": [],
  "clarity_score": 1.0,
  "requires_optimization": false,
  "estimated_steps": 1,
  "reasoning": "Straightforward list query with no filters or complexity"
}}

Query: "Find companies in San Francisco with more than 5 employees that we emailed last month"
{{
  "complexity": "complex",
  "intent": "search",
  "entities_mentioned": ["company", "email"],
  "filters_detected": ["location:San Francisco", "employee_count:>5", "email_date:last_month"],
  "clarity_score": 0.9,
  "requires_optimization": true,
  "estimated_steps": 3,
  "reasoning": "Multi-step query requiring: 1) email lookup for last month, 2) company search with filters, 3) join results. High complexity with multiple filters and entity relationships."
}}

Query: "Show me that thing"
{{
  "complexity": "simple",
  "intent": "get_by_id",
  "entities_mentioned": [],
  "filters_detected": [],
  "clarity_score": 0.2,
  "requires_optimization": true,
  "estimated_steps": 1,
  "reasoning": "Very ambiguous - unclear what 'thing' refers to. Needs context or clarification."
}}

Now analyze the user query above and return your JSON response.
"""


# ============================================================================
# EXECUTION PLANNING PROMPT (Optional - can also use rule-based)
# ============================================================================

ORCHESTRATOR_PLAN_PROMPT = """You are creating an execution plan based on query analysis.

QUERY ANALYSIS:
{analysis}

AVAILABLE STRATEGIES:

1. EXTRACTOR STRATEGY:
   - STATIC: Use DataExtractor (predictable, fast, good for simple queries)
   - REACTIVE: Use ReActiveDataExtractor (adaptive, thorough, good for complex/ambiguous queries)
   - HYBRID: Start with static, fallback to reactive if needed

2. VALIDATION LEVEL:
   - NONE: Skip validation (save time/cost for high-confidence queries)
   - HEURISTIC: Fast rule-based validation only
   - SEMANTIC: Deep LLM-based validation (thorough but slower/costlier)

3. OTHER PARAMETERS:
   - should_optimize_query: Whether to run QueryOptimizer
   - max_retries: Maximum retry attempts (0-3)
   - confidence_threshold: Minimum confidence to accept (0.0-1.0)

DECISION GUIDELINES:

SIMPLE QUERIES (clarity > 0.8):
- Extractor: STATIC
- Validation: NONE or HEURISTIC
- Optimize: false (save time)
- Max retries: 0
- Threshold: 0.7

MEDIUM QUERIES:
- Extractor: STATIC
- Validation: HEURISTIC
- Optimize: true
- Max retries: 1
- Threshold: 0.7

COMPLEX QUERIES or LOW CLARITY (< 0.5):
- Extractor: REACTIVE
- Validation: SEMANTIC
- Optimize: true
- Max retries: 2
- Threshold: 0.8

Return your plan in this JSON format:
{{
  "should_optimize_query": true,
  "extractor_strategy": "static|reactive|hybrid",
  "validation_level": "none|heuristic|semantic",
  "max_retries": 1,
  "confidence_threshold": 0.7,
  "reasoning": "Explanation of your decisions",
  "estimated_cost": "low|medium|high"
}}

Create the optimal execution plan now.
"""


# ============================================================================
# FALLBACK / CLARIFICATION PROMPTS
# ============================================================================

ORCHESTRATOR_CLARIFICATION_PROMPT = """The query is too ambiguous to execute confidently.

QUERY: {query}
CLARITY SCORE: {clarity_score}
ISSUES: {issues}

Generate a helpful clarification question to ask the user.

Return JSON:
{{
  "clarification_question": "What specific information are you looking for?",
  "suggestions": ["Option 1", "Option 2", "Option 3"],
  "reasoning": "Why clarification is needed"
}}
"""
