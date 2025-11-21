"""
Reactive Execution Prompts for dynamic validation and optimization
"""

SEMANTIC_VALIDATION_PROMPT = """You are a Data Validation Expert. Your task is to validate if the extracted data answers the user's query effectively.

ORIGINAL QUERY: "{original_query}"
OPTIMIZED QUERY: "{optimized_query}"

EXTRACTED DATA SUMMARY:
{data_summary}

DATA SAMPLE (First few items):
{data_sample}

VALIDATION INSTRUCTIONS:
1. Analyze if the retrieved data ACTUALLY answers the specific question asked.
2. Check for completeness (did we get everything requested?).
3. Check for accuracy/relevance (is the data relevant to the query?).
4. Identify any missing information.
5. Determine if we should ACCEPT the result, REFINE the search, or CLARIFY with the user.

OUTPUT FORMAT (JSON):
{{
  "query_answered": boolean,  // Does the data answer the core question?
  "completeness": 0.0-1.0,    // How complete is the answer?
  "accuracy": 0.0-1.0,        // How accurate/relevant is the data?
  "relevance": 0.0-1.0,       // How relevant is the data to the query?
  "ambiguity_level": 0.0-1.0, // Is the result ambiguous?
  "missing_information": ["list", "of", "missing", "fields/items"],
  "data_quality_concerns": ["list", "of", "concerns"],
  "should_accept": boolean,   // Should we show this to the user?
  "next_step": "ACCEPT" | "REFINE_SEARCH" | "CLARIFY_QUERY",
  "reasoning": "Explanation of your decision"
}}

Generate the JSON validation report now:
"""

