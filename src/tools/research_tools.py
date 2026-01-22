"""Research tools for web search using Perplexity Search API."""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from langchain_core.tools import tool

from src.config import get_settings
from src.tools.base import ToolContext

logger = logging.getLogger(__name__)

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"


@dataclass
class SearchResult:
    """A single search result from Perplexity."""

    title: str
    url: str
    snippet: str
    date: str
    last_updated: str


@dataclass
class SearchResponse:
    """Response from Perplexity Search API."""

    results: list[SearchResult]


async def call_perplexity_search(
    query: str,
    max_results: int = 10,
    search_recency_filter: Optional[str] = None,
    country: Optional[str] = None,
) -> SearchResponse:
    """Call the Perplexity Search API.

    Args:
        query: The search query
        max_results: Maximum number of results to return (1-20)
        search_recency_filter: Filter by recency ("day", "week", "month", "year")
        country: Country code to filter results (e.g., "US", "GB")

    Returns:
        SearchResponse with list of results

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPStatusError: If API call fails
    """
    settings = get_settings()

    api_key = settings.perplexity_api_key.strip()
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "query": query,
        "max_results": min(max(max_results, 1), 20),
    }

    if search_recency_filter and search_recency_filter in ("day", "week", "month", "year"):
        payload["search_recency_filter"] = search_recency_filter

    if country:
        payload["country"] = country

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            PERPLEXITY_SEARCH_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    results = [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("snippet", ""),
            date=r.get("date", ""),
            last_updated=r.get("last_updated", ""),
        )
        for r in data.get("results", [])
    ]

    return SearchResponse(results=results)


def format_search_results(response: SearchResponse) -> str:
    """Format search results into readable text.

    Args:
        response: The SearchResponse object

    Returns:
        Formatted string with results
    """
    if not response.results:
        return "No results found."

    lines: list[str] = []
    for i, result in enumerate(response.results, 1):
        lines.append(f"**{i}. {result.title}**")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        if result.last_updated:
            lines.append(f"   Last updated: {result.last_updated}")
        lines.append("")

    return "\n".join(lines)


def get_research_tools(context: ToolContext) -> list:
    """Get all research tools configured with the given context.

    Args:
        context: Tool context with auth and workspace info

    Returns:
        List of tool functions
    """

    @tool
    async def web_search(
        query: str,
        max_results: int = 10,
        recency: Optional[str] = None,
    ) -> str:
        """Search the web for real-time information about companies, people, industries, news, or market data.

        USE THIS TOOL when user asks to find/research external information NOT in the CRM.
        DO NOT USE for CRM data lookups (use list_companies, list_people instead).

        QUERY FORMAT - Structure your query with these components:
        1. WHAT: The specific entity/topic (company names, industry, technology)
        2. WHERE: Geographic scope if relevant (country, region, city)
        3. CRITERIA: Size, funding, revenue, employee count, or other qualifiers
        4. CONTEXT: Industry vertical, use case, or domain focus

        GOOD query examples:
        - "Top 10 B2B SaaS companies in India with Series B+ funding in enterprise software"
        - "AI startups in healthcare sector Germany founded after 2020 with 50+ employees"
        - "Latest funding rounds and valuations for CRM software companies Q4 2024"
        - "Competitors of Salesforce in small business CRM market with pricing under $50/user"

        BAD query examples (too vague):
        - "AI companies" → Missing location, size, industry focus
        - "Find startups" → No criteria, geography, or domain specified

        Args:
            query: A detailed, structured search query. Include: entity type, geography,
                   size/funding criteria, and industry context. More specific = better results.
            max_results: Results to return (1-20). Use 5-10 for focused searches, 15-20 for broad research.
            recency: Time filter - "day" (breaking news), "week" (recent), "month", "year".

        Returns:
            Ranked results with title, URL, snippet, and last updated date.
        """
        logger.info(f"🔍 Web search: {query} (max_results={max_results}, recency={recency})")

        try:
            response = await call_perplexity_search(
                query=query,
                max_results=max_results,
                search_recency_filter=recency,
            )

            result = format_search_results(response)

            logger.info(f"✅ Web search completed, found {len(response.results)} results")
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

    return [web_search]
