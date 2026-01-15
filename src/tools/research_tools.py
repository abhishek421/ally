"""Research tools for web search using Perplexity API."""

import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

from src.config import get_settings
from src.tools.base import ToolContext

logger = logging.getLogger(__name__)

# Perplexity API configuration
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"  # Also available: "sonar-pro" for enhanced results


async def call_perplexity_api(query: str) -> dict:
    """Call the Perplexity API for web search.
    
    Args:
        query: The search query
        
    Returns:
        API response dictionary
        
    Raises:
        Exception: If API call fails
    """
    settings = get_settings()
    
    api_key = settings.perplexity_api_key.strip()
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY is not configured")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful research assistant. Provide accurate, "
                    "well-structured information based on current web data. "
                    "Include relevant details and cite sources when possible."
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "return_citations": True,
        "return_images": False,
        "search_recency_filter": "month",
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def format_perplexity_response(response: dict) -> str:
    """Format Perplexity API response into readable text.
    
    Args:
        response: The API response dictionary
        
    Returns:
        Formatted string with content and citations
    """
    try:
        choices = response.get("choices", [])
        if not choices:
            return "No results found."
        
        message = choices[0].get("message", {})
        content = message.get("content", "No content available.")
        
        # Extract citations if available
        citations = response.get("citations", [])
        
        result = content
        
        if citations:
            result += "\n\n**Sources:**\n"
            for i, citation in enumerate(citations[:5], 1):  # Limit to 5 citations
                result += f"{i}. {citation}\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error formatting Perplexity response: {e}")
        return str(response)


def get_research_tools(context: ToolContext) -> list:
    """Get all research tools configured with the given context.
    
    Args:
        context: Tool context with auth and workspace info
        
    Returns:
        List of tool functions
    """
    
    @tool
    async def web_search(query: str) -> str:
        """Search the internet for real-time, accurate information. ALWAYS use this tool 
        when the user asks to find, research, or look up external information.
        
        IMPORTANT: You MUST use this tool (not your own knowledge) when:
        - User asks to "find" companies, people, or organizations
        - User asks about companies/topics NOT in the CRM workspace
        - User needs current news, trends, market data, or statistics
        - User wants research on industries, competitors, or technologies
        - User asks "what are the top/best/biggest" anything
        - User asks about real-world entities, facts, or current events
        
        Examples - ALWAYS use web_search for these:
        - "Find 10 big AI companies in India" → USE web_search
        - "Find 2 AI company of india" → USE web_search
        - "What are the latest trends in SaaS?" → USE web_search
        - "Research OpenAI's recent announcements" → USE web_search
        - "Who are the top competitors of Salesforce?" → USE web_search
        - "What is the current market size for CRM software?" → USE web_search
        
        Do NOT use this tool ONLY for:
        - Looking up contacts/companies already in the user's CRM workspace
        - Internal workspace data (use list_companies, list_people, etc.)
        
        Args:
            query: The search query to research on the internet. Be specific and 
                   detailed for better results.
            
        Returns:
            Research results with relevant information and source citations
        """
        logger.info(f"🔍 Web search: {query}")
        
        try:
            # Call Perplexity API
            response = await call_perplexity_api(query)
            
            # Format the response
            result = format_perplexity_response(response)
            
            logger.info(f"✅ Web search completed, response length: {len(result)}")
            return result
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Web search API error: {e.response.status_code}"
            logger.error(f"❌ {error_msg}: {e.response.text}")
            return f"Error performing web search: {error_msg}. Please try again."
            
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            return f"Web search is not configured: {str(e)}"
            
        except Exception as e:
            logger.error(f"❌ Web search error: {e}")
            return f"Error performing web search: {str(e)}. Please try again."
    
    # Return all research tools
    return [web_search]

