"""
Reusable async GraphQL client for CRM backend communication.

This module provides a low-level HTTP layer for executing GraphQL queries and
mutations against the CRM backend API. All tool modules use this client to
communicate with the backend.

This file contains only the HTTP transport layer - no business logic or
specific tool implementations.

Features:
- Async httpx client for high performance
- Automatic authentication header injection
- Retry logic with exponential backoff
- Structured logging with query names and timing
- Error handling and response parsing

Usage:
    from src.tools.graphql_client import gql_request
    
    query = '''
        query GetCompany($id: ID!) {
            company(id: $id) {
                id
                name
            }
        }
    '''
    
    result = await gql_request(query, {"id": "company-123"})
    company = result["company"]
"""

# ========================================
# 1. Imports
# ========================================

import httpx
import json
import asyncio
import time
import re
from typing import Dict, Any, Optional

from src.config.logger import logger
from src.config.settings import settings


# ========================================
# 2. Module-level Async HTTP Client
# ========================================

# Global async client with reasonable timeout
# Reused across all GraphQL requests for connection pooling
client = httpx.AsyncClient(
    timeout=15.0,
    headers={
        "Content-Type": "application/json"
    }
)


# ========================================
# 5. Helper Functions
# ========================================


def extract_query_name(query: str) -> str:
    """
    Extract the operation name from a GraphQL query for logging purposes.
    
    Attempts to parse the query/mutation name from the first line of the
    GraphQL string. Falls back to "UnnamedQuery" if parsing fails.
    
    Args:
        query: GraphQL query string
    
    Returns:
        Extracted operation name or "UnnamedQuery"
    
    Examples:
        >>> extract_query_name("query GetPerson($id: ID!) { ... }")
        'GetPerson'
        
        >>> extract_query_name("mutation CreateCompany { ... }")
        'CreateCompany'
        
        >>> extract_query_name("{ companies { id } }")
        'UnnamedQuery'
    """
    try:
        # Look for pattern like "query Name" or "mutation Name"
        match = re.search(r'(?:query|mutation)\s+(\w+)', query)
        if match:
            return match.group(1)
        
        # Fallback for unnamed queries
        return "UnnamedQuery"
    except Exception:
        return "UnnamedQuery"


# ========================================
# 3. Main GraphQL Request Function
# ========================================


async def gql_request(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a GraphQL query or mutation against the CRM backend.
    
    This function handles:
    - Building the GraphQL POST request payload
    - Merging authentication headers from settings
    - Sending the HTTP request to the GraphQL endpoint
    - Parsing and validating the response
    - Retrying on network errors or 5xx responses (up to 3 attempts)
    - Structured logging with timing and error details
    
    Authentication:
    The auth_token parameter takes precedence. If not provided, falls back to
    settings.GRAPHQL_AUTH_TOKEN. The token is included as a Bearer token in
    the Authorization header.
    
    Error Handling:
    - Network errors trigger retries with exponential backoff
    - GraphQL errors in the response raise an exception with error details
    - HTTP 5xx errors trigger retries
    - HTTP 4xx errors raise an exception immediately (no retry)
    
    Args:
        query: GraphQL query or mutation string
        variables: Variables to pass to the GraphQL operation (default: {})
        headers: Additional HTTP headers to include in the request
        auth_token: Optional authentication token (takes precedence over settings)
    
    Returns:
        The "data" field from the GraphQL response
    
    Raises:
        Exception: If the request fails after retries or if GraphQL errors occur
        httpx.HTTPError: For HTTP-level errors
    
    Example:
        query = '''
            query SearchCompanies($name: String!) {
                companies(filter: { name: $name }) {
                    id
                    name
                }
            }
        '''
        
        data = await gql_request(query, {"name": "Acme Corp"})
        companies = data["companies"]
    """
    # Extract query name for logging
    query_name = extract_query_name(query)
    
    # Build GraphQL payload
    payload = {
        "query": query,
        "variables": variables or {}
    }
    
    # Merge headers
    request_headers = {
        "Content-Type": "application/json"
    }
    
    # Add authentication - prefer auth_token parameter, fallback to settings
    token = auth_token or getattr(settings, "GRAPHQL_AUTH_TOKEN", None)
    if token:
        request_headers["Authorization"] = f"{token}"
    
    # Merge any additional headers provided by caller
    if headers:
        request_headers.update(headers)
    
    # Get GraphQL endpoint from settings
    endpoint = getattr(settings, "GRAPHQL_ENDPOINT")
    
    # Retry configuration
    max_retries = 3
    base_delay = 0.5  # Initial delay in seconds
    
    # Attempt the request with retry logic
    for attempt in range(max_retries):
        start_time = time.time()
        
        try:
            logger.debug(
                f"Executing GraphQL query '{query_name}' (attempt {attempt + 1}/{max_retries})"
            )
            
            # Execute POST request
            response = await client.post(
                endpoint,
                json=payload,
                headers=request_headers
            )
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Check HTTP status
            if response.status_code >= 500:
                # Server error - retry
                logger.warning(
                    f"GraphQL query '{query_name}' returned {response.status_code}. "
                    f"Retrying... (attempt {attempt + 1}/{max_retries})"
                )
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    raise Exception(
                        f"GraphQL query '{query_name}' failed after {max_retries} attempts: "
                        f"HTTP {response.status_code}"
                    )
            
            # Raise for 4xx errors (don't retry client errors)
            if response.status_code >= 400:
                error_text = response.text
                logger.error(
                    f"GraphQL query '{query_name}' failed with HTTP {response.status_code}: "
                    f"{error_text}"
                )
                raise Exception(
                    f"GraphQL query '{query_name}' failed: HTTP {response.status_code} - {error_text}"
                )
            
            # Parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse JSON response for query '{query_name}': {e}"
                )
                raise Exception(f"Invalid JSON response from GraphQL endpoint: {e}")
            
            # Check for GraphQL errors
            if "errors" in response_data:
                errors = response_data["errors"]
                error_summary = "; ".join([
                    err.get("message", str(err)) for err in errors
                ])
                
                logger.error(
                    f"GraphQL query '{query_name}' returned errors: {error_summary}"
                )
                
                raise Exception(
                    f"GraphQL query '{query_name}' failed: {error_summary}"
                )
            
            # Success - extract data field
            data = response_data.get("data")
            
            logger.info(
                f"GraphQL query '{query_name}' completed successfully "
                f"in {execution_time:.2f}s"
            )
            
            return data
        
        except httpx.HTTPError as e:
            # Network error - retry
            logger.warning(
                f"Network error executing GraphQL query '{query_name}': {e}. "
                f"Retrying... (attempt {attempt + 1}/{max_retries})"
            )
            
            if attempt < max_retries - 1:
                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            else:
                # Final attempt failed
                logger.error(
                    f"GraphQL query '{query_name}' failed after {max_retries} attempts: {e}"
                )
                raise Exception(
                    f"GraphQL query '{query_name}' failed after {max_retries} attempts: {e}"
                )
        
        except Exception as e:
            # Non-retryable error - raise immediately
            if "GraphQL query" in str(e):
                # Already logged and formatted
                raise
            else:
                # Unexpected error
                logger.error(
                    f"Unexpected error executing GraphQL query '{query_name}': {e}"
                )
                raise Exception(
                    f"GraphQL query '{query_name}' failed unexpectedly: {e}"
                )


# ========================================
# 4. Cleanup Method
# ========================================


async def close_client() -> None:
    """
    Close the global HTTP client and clean up connections.
    
    This should be called during application shutdown to ensure all
    HTTP connections are properly closed and resources are released.
    
    Example:
        # In server shutdown handler
        await close_client()
    """
    await client.aclose()
    logger.info("GraphQL client closed")

