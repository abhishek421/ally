"""
Prompt templates for ReAct pattern execution

These prompts guide the LLM through the Think-Act-Observe-Reflect cycle.
"""

INITIAL_PLANNING_PROMPT = """
Analyze this optimized query and create a strategic execution plan.

OPTIMIZED QUERY:
{optimized_query}

{conversation_context}

YOUR TASK:
Create a strategic plan for answering this query. Do NOT plan specific tool calls yet -
just understand what we need to accomplish and set success criteria.

AVAILABLE TOOLS:
- company: Search/get companies
- people: Search/get people/contacts
- email: Search/get emails
- interaction: Search/get interactions (calls, meetings)
- group: Search/get groups/segments
- workspace: Get workspace info

Return JSON with this exact structure:
{{
    "intent": "search|get|list|analyze|aggregate",
    "primary_entity": "company|people|email|interaction|group|workspace",
    "entities_mentioned": ["entity1", "entity2"],
    "success_criteria": {{
        "min_results": 1,
        "required_fields": ["field1", "field2"],
        "answer_type": "list|count|single_entity|aggregation"
    }},
    "initial_strategy": "Brief description of approach (1-2 sentences)",
    "potential_challenges": ["challenge1", "challenge2"],
    "expected_tools": ["tool1", "tool2"]
}}

IMPORTANT:
- Be specific about success criteria
- Identify potential ambiguities
- Consider if query requires multiple steps
"""

THINK_PROMPT = """
You are executing a data extraction task using the ReAct (Reasoning + Acting) pattern.
Decide your next action based on current state.

═══════════════════════════════════════════════════════════════
ORIGINAL QUERY: {query}
═══════════════════════════════════════════════════════════════

SUCCESS CRITERIA:
{success_criteria}

CURRENT STATE:
- Iteration: {iteration}/{max_iterations}
- Data collected so far: {collected_data_keys}
- Confidence scores: {confidence_scores}

PREVIOUS OBSERVATIONS (most recent):
{recent_observations}

PREVIOUS REASONING (most recent):
{recent_reasoning}

TOOLS ALREADY EXECUTED:
{tools_executed}

CURRENT DATA SUMMARY:
{data_summary}

{refinement_feedback}

{conversation_context}

═══════════════════════════════════════════════════════════════
DECISION TIME: What should I do next?
═══════════════════════════════════════════════════════════════

THINK CAREFULLY:
1. Do I have enough data to answer the query?
2. Is the data I have relevant and sufficient?
3. What information is still missing?
4. Am I stuck in a loop (repeating same actions)?
5. Is the query ambiguous and needs clarification?

OPTIONS:
1. SUFFICIENT - I have enough data to answer the query confidently
2. EXECUTE_TOOL - I need to execute another tool to get more data
3. CLARIFY - The query is ambiguous, I need user clarification

GUIDELINES:
- If I have ZERO results, try a different approach or ask for clarification
- If I have ambiguous results (e.g., 50+ matching "John"), refine or clarify
- If I successfully answered the query, STOP (choose SUFFICIENT)
- If I'm repeating the same tool with no new info, ask for clarification
- If data type doesn't match what query asks for, refine approach
- Consider if I'm at max iterations - may need to stop even if not perfect

Return JSON with this exact structure:
{{
    "decision": "SUFFICIENT|EXECUTE_TOOL|CLARIFY",
    "reasoning": "Detailed step-by-step explanation of this decision (3-5 sentences)",
    "confidence": 0.0-1.0,

    // ONLY if decision is EXECUTE_TOOL:
    "tool_spec": {{
        "tool": "company|people|email|interaction|group|workspace",
        "query_type": "search|get_by_id|list|analytics",
        "params": {{
            // Include necessary parameters
            // Can reference previous results: "<person_id_from_previous_call>"
        }},
        "expected_outcome": "What I hope to achieve with this tool call",
        "fallback_plan": "What to do if this tool returns no results"
    }},

    // ONLY if decision is CLARIFY:
    "clarification_question": "Clear, specific question to ask the user",
    "clarification_reason": "Why I need this information to proceed"
}}

Return ONLY valid JSON, no additional text.
"""

OBSERVE_PROMPT = """
Analyze this tool execution result in the context of our goal.

ORIGINAL QUERY: {query}
EXPECTED OUTCOME: {expected_outcome}

TOOL EXECUTED: {tool_name} ({query_type})
PARAMETERS USED: {params}

RESULT SUMMARY:
{result_summary}

═══════════════════════════════════════════════════════════════
ANALYSIS QUESTIONS:
═══════════════════════════════════════════════════════════════

1. WHAT DID WE LEARN?
   - What specific facts did this result tell us?
   - Does this match what we expected?

2. RELEVANCE
   - Is this result relevant to answering the original query?
   - Rate relevance: 0.0 (not relevant) to 1.0 (highly relevant)

3. WHAT'S MISSING?
   - What information is still needed to answer the query?
   - Are there gaps in the data?

4. NEW QUESTIONS
   - Did this result raise any new questions?
   - Do we need to fetch related data?

5. DATA QUALITY
   - Are there any quality issues? (missing fields, errors, etc.)
   - Is the data trustworthy?

Return JSON with this exact structure:
{{
    "learned": ["specific fact 1", "specific fact 2"],
    "relevance_to_query": 0.0-1.0,
    "still_missing": ["missing piece 1", "missing piece 2"],
    "new_questions": ["question 1", "question 2"],
    "data_quality_issues": ["issue 1", "issue 2"]
}}

Be specific and factual. Focus on what the data tells us about answering the query.
Return ONLY valid JSON, no additional text.
"""

REFLECT_PROMPT = """
Reflect on our progress towards answering the query.

ORIGINAL QUERY: {query}
SUCCESS CRITERIA: {success_criteria}

PROGRESS SO FAR:
- Iterations used: {iteration}/{max_iterations}
- Tools executed: {tool_count}
- Data collected: {data_keys}

RECENT OBSERVATIONS:
{recent_observations}

CONFIDENCE SCORES:
{confidence_scores}

═══════════════════════════════════════════════════════════════
REFLECTION QUESTIONS:
═══════════════════════════════════════════════════════════════

1. QUERY ANSWERED?
   - Have we successfully gathered information to answer the original query?
   - Is the answer complete or partial?

2. DATA QUALITY
   - Is the data we collected reliable and relevant?
   - Are there any major gaps?

3. PROGRESS ASSESSMENT
   - Are we making good progress?
   - Are we stuck (repeating same actions with no new information)?
   - Are we close to max iterations?

4. SHOULD WE CONTINUE?
   - Yes if: We're making progress and haven't answered the query
   - No if: We've answered the query, OR we're stuck, OR at max iterations

Return JSON with this exact structure:
{{
    "should_continue": true/false,
    "reason": "Clear explanation of why we should continue or stop (2-3 sentences)",
    "progress_assessment": "good|ok|poor|stuck",
    "next_recommendations": ["recommendation 1", "recommendation 2"]
}}

Be honest about our progress. It's okay to stop if we're not making progress.
Return ONLY valid JSON, no additional text.
"""

SEMANTIC_VALIDATION_PROMPT = """
You are validating if extracted data successfully answers a user query.

═══════════════════════════════════════════════════════════════
ORIGINAL USER QUERY: {original_query}
OPTIMIZED QUERY: {optimized_query}
═══════════════════════════════════════════════════════════════

EXTRACTED DATA SUMMARY:
{data_summary}

SAMPLE DATA (first few items):
{data_sample}

═══════════════════════════════════════════════════════════════
VALIDATION CHECKLIST:
═══════════════════════════════════════════════════════════════

1. QUERY ANSWERED?
   - Does the extracted data contain information needed to answer the query?
   - Rate: YES (fully answered) | PARTIAL (some info) | NO (not answered)

2. COMPLETENESS (0.0-1.0)
   - Is all requested information present?
   - What specific information is missing (if any)?
   - Is the data depth sufficient (not just IDs, but actual useful content)?

3. ACCURACY & RELEVANCE (0.0-1.0)
   - Does the data seem relevant to what the user asked?
   - Are there obvious accuracy concerns?
   - Is the data type correct for the question?
     Example: User asks "how many?" but we returned a list instead of count

4. AMBIGUITY LEVEL (0.0-1.0)
   - Is the answer clear and unambiguous?
   - Could there be multiple valid interpretations?
   - Did we get too many results indicating query was too broad?
   - Example: Asked for "emails from John" but got 100 different Johns

5. DATA QUALITY
   - Are there empty results when we expected data?
   - Are there errors or warnings in the data?
   - Is any data truncated or incomplete?

6. FINAL DECISION
   - Should we accept this answer? (YES/NO)
   - If NO, what's the best next step?
     * REFINE_SEARCH: Try different search parameters
     * CLARIFY_QUERY: Ask user for more specific information
     * FETCH_MORE_DATA: Need to get additional related data

Return JSON with this exact structure:
{{
    "query_answered": true/false,
    "completeness": 0.0-1.0,
    "accuracy": 0.0-1.0,
    "relevance": 0.0-1.0,
    "ambiguity_level": 0.0-1.0,
    "missing_information": ["specific item 1", "specific item 2"],
    "data_quality_concerns": ["concern 1", "concern 2"],
    "should_accept": true/false,
    "next_step": "ACCEPT|REFINE_SEARCH|CLARIFY_QUERY|FETCH_MORE_DATA",
    "reasoning": "Detailed explanation of validation decision (3-5 sentences)"
}}

Be thorough but honest. It's okay to say we didn't fully answer the query.
Return ONLY valid JSON, no additional text.
"""

# Example few-shot examples for THINK phase
THINK_EXAMPLES = """
EXAMPLES OF GOOD THINKING:

Example 1 - First Iteration:
Query: "Show me companies in San Francisco"
Data collected: None yet
Decision: EXECUTE_TOOL
Reasoning: "This is the first iteration and we haven't collected any data yet. The query clearly asks for companies with a location filter. I should use the company tool with a search query_type, filtering by city='San Francisco'. Expected outcome: Get a list of companies located in San Francisco."

Example 2 - Found Data, Should Stop:
Query: "Show me companies in San Francisco"
Data collected: companies: 5 items
Confidence: 0.85
Decision: SUFFICIENT
Reasoning: "We successfully retrieved 5 companies located in San Francisco. The data is relevant and the result count is reasonable. The confidence score is 0.85 which is high. We have successfully answered the query and should stop."

Example 3 - No Results, Need Clarification:
Query: "Show me emails from John"
Data collected: people: 50 items (all named "John")
Confidence: 0.3
Decision: CLARIFY
Reasoning: "We found 50 people named John in the system. The query is too ambiguous - we don't know which John the user is referring to. Rather than guessing or returning all emails from all Johns, we should ask the user to be more specific (last name, company, email address, etc.)."
Clarification question: "I found 50 people named John. Could you please provide more details like last name, company, or email address?"

Example 4 - Multi-Step Query:
Query: "Get emails from John at TechCorp"
Data collected: None yet
Decision: EXECUTE_TOOL
Reasoning: "This query requires two steps: first find John at TechCorp (person search), then get their emails. I should start by searching for people with first_name='John' and company matching 'TechCorp'. Then in the next iteration, I'll use the person_id to fetch emails."

Example 5 - Stuck, Need to Stop:
Query: "Find company XYZ123"
Data collected: companies: 0 items (tried 3 times)
Iteration: 4/5
Decision: CLARIFY
Reasoning: "We've searched for company 'XYZ123' three times with no results. We're at iteration 4 out of 5. Continuing to search with the same parameters won't help. The company either doesn't exist or has a different name. We should ask the user to verify the company name."
Clarification question: "I couldn't find a company named 'XYZ123'. Could you please verify the company name or provide additional details?"
"""
