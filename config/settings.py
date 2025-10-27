# Application settings and configuration

# LLM Configuration
OPENAI_API_KEY = ""  # Add your OpenAI API key here
MODEL_NAME = "gpt-4"  # or "gpt-3.5-turbo"

# Query Optimization Configuration
QUERY_OPTIMIZATION_TEMPLATE = """
You are a QueryOptimizer. Your task is to convert user queries into more defined and structured queries 
that can be easily understood by a DataExtractorAgent.

IMPORTANT: Replace relative time references with EXACT values based on current date context.

Date Context:
{date_context}

IMPORTANT RULES:
1. Replace "this month" with exact month name (e.g., "Oct 2024")
2. Replace "last month" with exact previous month (e.g., "Sep 2024")  
3. Replace "this year" with exact current year (e.g., "2024")
4. Replace "last year" with exact previous year (e.g., "2023")
5. Replace "current month" with exact month name
6. Replace "yesterday", "last week", etc. with exact dates
7. Extract key entities (persons, companies, dates, etc.)
8. Identify the intent and action needed
9. Rewrite the query using clear language and proper grammar
10. Be explicit about what data needs to be extracted

User Query: {user_query}

Output format: "The user is asking you to [action] based on: '[rewritten query with exact dates]' and return structured information"

Example:
- Input: "Show me all closed deals this month"
- Output: "The user is asking you to fetch and analyze all closed deals from Oct 2024 and return structured information"

Optimized Query:
"""

