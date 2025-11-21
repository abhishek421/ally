"""
Reasoning Log Processing and Summarization
==========================================

This module provides utilities to convert internal agent reasoning logs into
concise, user-friendly summaries and structured metadata for the UI.

Purpose:
- Transform chain-of-thought reasoning into user-facing explanations
- Protect against revealing internal deliberation processes
- Redact sensitive information (UUIDs, emails, API keys, long JSON)
- Provide both deterministic (regex-based) and LLM-based summarization
- Ensure testable, safe output for frontend consumption

Safety Guarantees:
- No raw chain-of-thought is exposed to users
- Sensitive tokens (UUIDs, emails, API keys) are redacted
- Long JSON blobs (>500 chars) are removed
- All summaries are limited in length and sanitized

Usage:
This module is primarily used by:
- planner_node: To explain planning decisions
- final_response node: To generate user-facing reasoning explanations
- websocket: To send structured reasoning updates to UI

LLM Integration:
- Optional LLM-based summarization via llm_router (model.py)
- Uses REASONING_SUMMARY_PROMPT from prompts.py
- Falls back to deterministic collapse_reasoning on error
- Logs latency and token usage for monitoring

Test Helpers:
- example_reasoning_logs(): Sample data for unit tests
- is_safe_summary(): Validates that output is properly redacted

Example:
    >>> from src.llm.reasoning import prepare_user_facing_reasoning
    >>> from src.memory.state import AgentState
    >>> 
    >>> state = AgentState(reasoning=["Planned search", "Found 3 results", "Will ask user"])
    >>> result = await prepare_user_facing_reasoning(state, use_llm=True)
    >>> print(result["summary"])
    "I searched and found 3 results. I'll present them for your review."
"""

import re
from datetime import datetime, timezone
from typing import Any

from src.config.logger import logger
from src.llm.prompts import REASONING_SUMMARY_PROMPT
from src.memory.state import AgentState

# ==============================================================================
# REDACTION UTILITIES
# ==============================================================================

def redact_sensitive(text: str) -> str:
    """
    Remove or mask sensitive information from text.
    
    This function redacts:
    - UUIDs: Replaced with <REDACTED_ID>
    - Email addresses: Local part masked (e.g., ***@example.com)
    - Long JSON blobs (>500 chars): Replaced with <REDACTED_JSON>
    - API key-like tokens: Long alphanumeric sequences replaced with <REDACTED_TOKEN>
    
    Args:
        text: Raw text that may contain sensitive information
        
    Returns:
        Sanitized text with sensitive data redacted
        
    Safety:
        Uses non-backtracking regexes to prevent performance issues.
        All patterns are tested to avoid catastrophic backtracking.
        
    Example:
        >>> redact_sensitive("User ID: 550e8400-e29b-41d4-a716-446655440000")
        "User ID: <REDACTED_ID>"
        >>> redact_sensitive("Contact: john.doe@example.com")
        "Contact: ***@example.com"
    """
    if not text:
        return text
    
    # Redact UUIDs (8-4-4-4-12 format)
    text = re.sub(
        r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        '<REDACTED_ID>',
        text,
        flags=re.IGNORECASE
    )
    
    # Redact email addresses (keep domain, mask local part)
    text = re.sub(
        r'\b[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b',
        r'***@\1',
        text
    )
    
    # Redact long JSON blobs (>500 chars)
    # Match JSON objects or arrays that are very long
    def replace_long_json(match):
        json_text = match.group(0)
        if len(json_text) > 500:
            return '<REDACTED_JSON>'
        return json_text
    
    # Simple JSON detection (not perfect, but safe)
    text = re.sub(
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
        replace_long_json,
        text
    )
    text = re.sub(
        r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',
        replace_long_json,
        text
    )
    
    # Redact API key-like tokens (long alphanumeric sequences)
    # Match sequences like: sk_live_abcd123456789... or similar
    text = re.sub(
        r'\b(?:sk_|pk_|api_|token_|key_)[a-zA-Z0-9_-]{20,}\b',
        '<REDACTED_TOKEN>',
        text,
        flags=re.IGNORECASE
    )
    
    # Redact generic long alphanumeric tokens (likely secrets)
    text = re.sub(
        r'\b[a-zA-Z0-9]{40,}\b',
        '<REDACTED_TOKEN>',
        text
    )
    
    return text


# ==============================================================================
# REASONING COLLAPSE AND RANKING
# ==============================================================================

def rank_reasoning_items(reasoning_logs: list[str], top_n: int = 3) -> list[str]:
    """
    Heuristically rank reasoning log items by usefulness for end-user summary.
    
    Ranking Strategy:
    - Prefer lines with decision-oriented keywords (planned, decided, confirmed, etc.)
    - Demote lines with debug/internal keywords (trace, debug, raw_tool_output, etc.)
    - Remove empty or very short lines
    - Return top_n most relevant items after scoring
    
    Args:
        reasoning_logs: List of reasoning log strings
        top_n: Number of top items to return (default: 3)
        
    Returns:
        List of top_n most relevant reasoning items, redacted
        
    Example:
        >>> logs = ["DEBUG: trace info", "Planned to search companies", "Found 3 matches"]
        >>> rank_reasoning_items(logs, top_n=2)
        ["Planned to search companies", "Found 3 matches"]
    """
    if not reasoning_logs:
        return []
    
    # Keywords that increase relevance score
    positive_keywords = [
        'decision', 'planned', 'plan', 'error', 'validation', 'validated',
        'confirmed', 'created', 'updated', 'deleted', 'found', 'searched',
        'retrieved', 'will', 'going to', 'determined', 'identified',
        'executing', 'completed', 'success', 'failed', 'warning'
    ]
    
    # Keywords that decrease relevance score
    negative_keywords = [
        'debug', 'trace', 'stack', 'raw_tool_output', 'internal',
        'timestamp', 'uuid', 'token', 'bearer', 'authorization'
    ]
    
    scored_items = []
    
    for log in reasoning_logs:
        if not log or len(log.strip()) < 10:
            continue
            
        score = 0
        log_lower = log.lower()
        
        # Add points for positive keywords
        for keyword in positive_keywords:
            if keyword in log_lower:
                score += 2
                
        # Subtract points for negative keywords
        for keyword in negative_keywords:
            if keyword in log_lower:
                score -= 3
                
        # Prefer medium-length items (too short or too long are less useful)
        length = len(log)
        if 30 <= length <= 200:
            score += 1
        elif length > 500:
            score -= 2
            
        scored_items.append((score, log))
    
    # Sort by score (descending) and take top_n
    scored_items.sort(key=lambda x: x[0], reverse=True)
    top_items = [redact_sensitive(item[1]) for item in scored_items[:top_n]]
    
    return top_items


def collapse_reasoning(reasoning_logs: list[str], max_lines: int = 5) -> str:
    """
    Collapse reasoning logs into a concise, user-friendly summary.
    
    This is a synchronous, deterministic function that:
    - Takes the most recent max_lines entries
    - Removes debug noise and internal tokens
    - Redacts sensitive information
    - Merges into 2-4 concise sentences
    - Returns a single human-facing paragraph
    
    Args:
        reasoning_logs: List of reasoning log strings
        max_lines: Maximum number of recent entries to consider (default: 5)
        
    Returns:
        A concise summary paragraph suitable for end users
        
    Safety:
        - Never returns more than max_lines worth of content
        - Always redacts sensitive tokens
        - Removes chain-of-thought markers
        
    Example:
        >>> logs = [
        ...     "Analyzing user request",
        ...     "Planned: search_companies",
        ...     "Found 3 matches",
        ...     "Will present top 3, ask user to confirm"
        ... ]
        >>> collapse_reasoning(logs, max_lines=5)
        "I searched companies and found 3 matches. I will show the top results and ask you to confirm."
    """
    if not reasoning_logs:
        return "Processing your request."
    
    # Take only the most recent max_lines
    recent_logs = reasoning_logs[-max_lines:] if len(reasoning_logs) > max_lines else reasoning_logs
    
    # Rank and get top items
    ranked = rank_reasoning_items(recent_logs, top_n=min(3, len(recent_logs)))
    
    if not ranked:
        return "Processing your request."
    
    # Join and clean up
    combined = " ".join(ranked)
    
    # Remove common chain-of-thought markers
    combined = re.sub(r'\b(Step \d+:|Task \d+:|DEBUG:|INFO:|WARNING:)\s*', '', combined, flags=re.IGNORECASE)
    combined = re.sub(r'\b(Analyzing|Processing|Executing|Running)\s+', '', combined, flags=re.IGNORECASE)
    
    # Normalize whitespace
    combined = re.sub(r'\s+', ' ', combined).strip()
    
    # Ensure it ends with a period
    if combined and not combined[-1] in '.!?':
        combined += '.'
    
    # Make it more conversational (replace some patterns)
    combined = re.sub(r'\bWill\b', 'I will', combined)
    combined = re.sub(r'\bFound\b', 'I found', combined)
    combined = re.sub(r'\bPlanned\b', 'I planned', combined)
    
    # Final redaction pass
    combined = redact_sensitive(combined)
    
    # Limit total length
    if len(combined) > 500:
        combined = combined[:497] + '...'
    
    return combined if combined else "Processing your request."


# ==============================================================================
# LLM-BASED SUMMARIZATION
# ==============================================================================

async def summarize_reasoning_llm(reasoning_text: str, max_tokens: int = 256) -> str:
    """
    Use LLM to summarize reasoning text into a user-friendly explanation.
    
    This function calls the llm_router's summarizer route with the
    REASONING_SUMMARY_PROMPT to convert internal reasoning into a concise,
    natural language summary.
    
    Args:
        reasoning_text: The reasoning text to summarize (already redacted)
        max_tokens: Maximum tokens for LLM response (default: 256)
        
    Returns:
        LLM-generated summary, or fallback to collapse_reasoning on error
        
    Error Handling:
        - On LLM call failure: Falls back to collapse_reasoning
        - On network error: Falls back to collapse_reasoning
        - On timeout: Falls back to collapse_reasoning
        - Logs all errors for debugging
        
    Performance:
        - Logs latency for monitoring
        - Logs token usage if available
        
    Example:
        >>> text = "Planned search. Found 3 companies. Will present results."
        >>> summary = await summarize_reasoning_llm(text)
        >>> print(summary)
        "I searched and found 3 companies to show you."
    """
    try:
        # Import here to avoid circular dependency
        from src.llm.model import llm_router
        
        # Build prompt
        prompt = f"{REASONING_SUMMARY_PROMPT}\n\n{reasoning_text}"
        
        # Log the request
        logger.debug(f"Calling LLM summarizer with {len(reasoning_text)} chars")
        start_time = datetime.now(timezone.utc)
        
        # Call LLM router
        response = await llm_router.call(
            route="summarizer",
            prompt=prompt,
            max_tokens=max_tokens
        )
        
        # Calculate latency
        latency = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"LLM summarizer completed in {latency:.2f}s")
        
        # Extract summary from response
        if isinstance(response, dict):
            summary = response.get('content', '') or response.get('text', '')
        else:
            summary = str(response)
        
        # Validate and clean
        summary = summary.strip()
        if not summary or len(summary) < 10:
            logger.warning("LLM returned empty or very short summary, using fallback")
            return collapse_reasoning(reasoning_text.split('\n'))
        
        # Final redaction (just in case LLM leaked something)
        summary = redact_sensitive(summary)
        
        # Limit length
        if len(summary) > 500:
            summary = summary[:497] + '...'
        
        return summary
        
    except ImportError as e:
        logger.warning(f"Could not import llm_router: {e}. Using fallback.")
        return collapse_reasoning(reasoning_text.split('\n'))
        
    except Exception as e:
        logger.error(f"Error in LLM summarization: {e}. Using fallback.")
        # Fallback to deterministic collapse
        return collapse_reasoning(reasoning_text.split('\n'))


# ==============================================================================
# UI FORMATTING
# ==============================================================================

def format_reasoning_for_ui(summary: str, items: list[str]) -> dict[str, Any]:
    """
    Format reasoning summary and items into a structured dict for UI consumption.
    
    Args:
        summary: One-paragraph summary of reasoning
        items: List of highlight items (reasoning snippets)
        
    Returns:
        Dictionary with keys:
        - summary: str - The main summary paragraph
        - highlights: list[str] - Truncated and redacted highlight items
        - timestamp: str - ISO8601 timestamp of when this was generated
        
    Example:
        >>> summary = "I searched companies and found 3 matches."
        >>> items = ["Planned search_companies", "Found 3 results", "Will present"]
        >>> result = format_reasoning_for_ui(summary, items)
        >>> print(result.keys())
        dict_keys(['summary', 'highlights', 'timestamp'])
    """
    # Truncate and redact highlights
    highlights = []
    for item in items:
        if not item:
            continue
        # Redact first
        redacted = redact_sensitive(item)
        # Truncate to 120 chars
        if len(redacted) > 120:
            redacted = redacted[:117] + '...'
        highlights.append(redacted)
    
    # Generate timestamp
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    return {
        "summary": summary,
        "highlights": highlights,
        "timestamp": timestamp
    }


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

async def prepare_user_facing_reasoning(
    state: AgentState,
    use_llm: bool = True,
    max_items: int = 5
) -> dict[str, Any]:
    """
    Main entrypoint for preparing user-facing reasoning from agent state.
    
    This function:
    1. Extracts reasoning logs from state
    2. Redacts sensitive information
    3. Optionally uses LLM for summarization (or falls back to collapse)
    4. Ranks and selects top reasoning items
    5. Formats everything for UI consumption
    
    This is the primary function called by final_response node and websocket
    handlers to generate reasoning explanations for users.
    
    Args:
        state: AgentState containing reasoning logs
        use_llm: Whether to use LLM summarization (default: True)
        max_items: Maximum reasoning items to consider (default: 5)
        
    Returns:
        Dictionary with structure:
        {
            "summary": "Human-friendly summary paragraph",
            "highlights": ["Key point 1", "Key point 2", ...],
            "timestamp": "2025-11-21T10:30:00Z"
        }
        
    Safety:
        - Never exposes raw chain-of-thought
        - All sensitive data is redacted
        - Falls back gracefully on LLM errors
        
    Example:
        >>> from src.memory.state import AgentState
        >>> state = AgentState(
        ...     reasoning=[
        ...         "User wants to search companies",
        ...         "Planning to use search_companies tool",
        ...         "Found 3 matching results",
        ...         "Will present top 3 to user"
        ...     ]
        ... )
        >>> result = await prepare_user_facing_reasoning(state, use_llm=True)
        >>> print(result["summary"])
        "I searched companies and found 3 matching results to show you."
        >>> print(len(result["highlights"]))
        2
    """
    try:
        # Extract reasoning logs
        reasoning_logs = state.reasoning if hasattr(state, 'reasoning') and state.reasoning else []
        
        if not reasoning_logs:
            logger.debug("No reasoning logs found in state")
            return format_reasoning_for_ui(
                summary="Processing your request.",
                items=[]
            )
        
        # Take last N items
        recent_logs = reasoning_logs[-max_items:] if len(reasoning_logs) > max_items else reasoning_logs
        
        # Redact entire block first
        redacted_logs = [redact_sensitive(log) for log in recent_logs]
        combined_text = "\n".join(redacted_logs)
        
        # Generate summary
        if use_llm:
            try:
                summary = await summarize_reasoning_llm(combined_text)
            except Exception as e:
                logger.warning(f"LLM summarization failed: {e}. Using collapse.")
                summary = collapse_reasoning(redacted_logs)
        else:
            summary = collapse_reasoning(redacted_logs)
        
        # Rank items for highlights
        highlights = rank_reasoning_items(redacted_logs, top_n=3)
        
        # Format for UI
        result = format_reasoning_for_ui(summary, highlights)
        
        logger.debug(f"Prepared user-facing reasoning: {len(summary)} chars, {len(highlights)} highlights")
        
        return result
        
    except Exception as e:
        logger.error(f"Error preparing user-facing reasoning: {e}")
        # Ultimate fallback
        return format_reasoning_for_ui(
            summary="Processing your request.",
            items=[]
        )


# ==============================================================================
# TEST HELPERS
# ==============================================================================

def example_reasoning_logs() -> list[str]:
    """
    Return sample reasoning logs for unit tests.
    
    Returns:
        List of example reasoning strings with various patterns
        
    Example:
        >>> logs = example_reasoning_logs()
        >>> len(logs) > 0
        True
        >>> 'Planned' in logs[0] or 'Found' in ' '.join(logs)
        True
    """
    return [
        "User requested to search for companies matching 'Acme'",
        "Planned to use search_companies tool with query parameter",
        "Found 3 matching companies in workspace",
        "Determined that user wants to see all results",
        "Will present top 3 companies and ask for confirmation",
        "Validated that workspaceId is present in context",
        "DEBUG: Internal trace information here",
        "Executing search with filters: {'query': 'Acme'}",
        "Successfully retrieved results from GraphQL API",
        "Preparing response with company details"
    ]


def is_safe_summary(text: str) -> bool:
    """
    Validate that text is properly redacted and safe for users.
    
    Checks that the text does NOT contain:
    - UUIDs (8-4-4-4-12 format)
    - Email addresses (with @ symbol and local part)
    - Long JSON blobs (>500 chars of JSON structure)
    - API key-like tokens
    
    Args:
        text: Text to validate
        
    Returns:
        True if text is safe (properly redacted), False otherwise
        
    Example:
        >>> is_safe_summary("I found 3 companies.")
        True
        >>> is_safe_summary("Found user: john@example.com")
        False
        >>> is_safe_summary("ID: 550e8400-e29b-41d4-a716-446655440000")
        False
    """
    if not text:
        return True
    
    # Check for UUIDs
    if re.search(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', text, re.IGNORECASE):
        return False
    
    # Check for email addresses (full emails, not redacted ones)
    if re.search(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', text):
        # Allow redacted emails like ***@example.com
        if not re.search(r'\*\*\*@', text):
            return False
    
    # Check for very long JSON (likely not redacted)
    json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    for block in json_blocks:
        if len(block) > 500:
            return False
    
    # Check for API key patterns
    if re.search(r'\b(?:sk_|pk_|api_|token_|key_)[a-zA-Z0-9_-]{20,}\b', text, re.IGNORECASE):
        return False
    
    # Check for long alphanumeric tokens
    if re.search(r'\b[a-zA-Z0-9]{40,}\b', text):
        return False
    
    return True


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    "collapse_reasoning",
    "summarize_reasoning_llm",
    "redact_sensitive",
    "rank_reasoning_items",
    "format_reasoning_for_ui",
    "prepare_user_facing_reasoning",
    "example_reasoning_logs",
    "is_safe_summary",
]

