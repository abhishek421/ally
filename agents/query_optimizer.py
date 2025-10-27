"""
QueryOptimizerAgent - Converts user queries to more defined and structured queries
"""
from typing import Dict
from datetime import datetime, timedelta
from config.settings import (
    OPENAI_API_KEY,
    MODEL_NAME,
    QUERY_OPTIMIZATION_TEMPLATE
)


class QueryOptimizerAgent:
    """Optimizes and structures user queries for better data extraction"""
    
    def __init__(self):
        self.template = QUERY_OPTIMIZATION_TEMPLATE
        self._current_date = datetime.now()
        # Note: In production, you'd initialize the LLM client here
        # from openai import OpenAI
        # self.client = OpenAI(api_key=OPENAI_API_KEY)
    
    def optimize(self, user_query: str) -> str:
        """
        Optimize a user query to make it more structured and actionable
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            Optimized query with clear intent and structure
        """
        
        # for LLM-based optimization with exact date replacements
        optimized = self._llm_optimization(user_query)
        
        return optimized
    
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
        return context
    
    def _llm_optimization(self, user_query: str) -> str:
        """
        Use LLM to optimize the query with exact date replacements
        """
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Get current date context
        date_context = self._get_current_date_context()
        
        # Format template with both date_context and user_query
        prompt = self.template.format(
            date_context=date_context,
            user_query=user_query
        )
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a QueryOptimizer that replaces relative dates with exact values."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()


# Convenience function
def optimize_query(query: str) -> str:
    """Convenience function to optimize a query"""
    agent = QueryOptimizerAgent()
    return agent.optimize(query)

