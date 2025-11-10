"""
Query Optimizer Prompt Template
"""
QUERY_OPTIMIZER_TEMPLATE = """
Parse this CRM query into a simple structured format.

Date Context:
{date_context}

User Query: {user_query}

Extract three things:
1. Intent - what the user wants (emails, companies, people, deals, interactions, count, or summary)
2. Filters - any specific criteria mentioned (names, statuses, etc.)
3. Time Period - convert relative dates to exact dates using the date context above

Time Conversion Rules:
- "this month" → current month (e.g., "November 2025")
- "last month" → previous month (e.g., "October 2025")
- "this year" → current year (e.g., "2025")
- "last year" → previous year (e.g., "2024")
- "yesterday", "last week", "Q1", etc. → exact date or date range

EXAMPLES:

Input: "Show me emails from John Smith last month"
Output:
Intent: emails
Filters: from=John Smith
Time Period: October 2025

Input: "How many companies do I have?"
Output:
Intent: count companies
Filters: none
Time Period: none

Input: "Find closed deals this year"
Output:
Intent: deals
Filters: stage=closed
Time Period: 2025

Input: "Show me all interactions with Acme Corp in Q1"
Output:
Intent: interactions
Filters: company=Acme Corp
Time Period: January 1, 2025 to March 31, 2025

Input: "Who did I email yesterday about the proposal?"
Output:
Intent: people
Filters: subject/content contains "proposal"
Time Period: November 8, 2025

Now parse the user query above. Return ONLY the three lines (Intent, Filters, Time Period), no additional text.
"""

