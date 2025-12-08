"""Planning-related prompts."""

PLAN_GENERATION_INSTRUCTIONS = """Generate a step-by-step plan to answer the user's request using available tools.

Analyze the user's request and the available tools. Create a numbered list of steps 
to solve the problem efficiently. Do not execute the tools, just plan the steps.
The plan should be logical, efficient, and directly address the user's goal.

CRITICAL RULES FOR PLANNING:
1. FRESHNESS: If the user asks for "all", "new", "list", or a quantity different from previous turns,
   you MUST generate a plan to fetch FRESH data using tools. Do NOT rely on data from conversation history.
2. NO ASSUMPTIONS: Do not assume the previous search results found "everything". Always search again 
   if the user's scope is broader (e.g. "give me ALL" vs previous "give me 3").
3. COMPLETENESS: If the user asks for multiple types of entities (e.g. "companies AND people"), 
   ensure the plan includes steps to fetch BOTH."""


PLAN_FALLBACK_PROMPT_TEMPLATE = """You are a planner.
Context: {context}
Question: {question}

Create a numbered list of steps to solve this request using the available tools.
CRITICAL: If the user asks for 'all' items or new data, you MUST plan to search again. Do not reuse old results.
PLAN:
"""

