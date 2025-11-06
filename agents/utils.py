"""
Utility functions for reactive execution and validation

These utilities support data analysis, summarization, and decision-making
in the reactive tool calling system.
"""
import json
from typing import Dict, Any, List, Optional
from tools.base_tool import ToolResult


def count_results(tool_result: ToolResult) -> int:
    """
    Count items in tool result

    Args:
        tool_result: ToolResult object

    Returns:
        Count of items in result
    """
    if not tool_result.success or not tool_result.data:
        return 0

    data = tool_result.data

    # Check common list keys
    for key in ['companies', 'people', 'emails', 'interactions', 'groups']:
        if key in data and isinstance(data[key], list):
            return len(data[key])

    # Single object result
    if isinstance(data, dict) and 'id' in data:
        return 1

    # List result
    if isinstance(data, list):
        return len(data)

    return 0


def summarize_tool_result(tool_result: ToolResult, max_items: int = 3) -> str:
    """
    Create human-readable summary of tool result

    Used by OBSERVE phase to understand what was returned.

    Args:
        tool_result: ToolResult object
        max_items: Maximum number of sample items to include

    Returns:
        Human-readable summary string
    """
    if not tool_result.success:
        return f"❌ Tool failed: {tool_result.error}"

    if not tool_result.data:
        return "ℹ️ No data returned"

    count = count_results(tool_result)
    data = tool_result.data

    summary_parts = [f"✅ Retrieved {count} item(s)"]

    # Add sample of data
    if isinstance(data, dict):
        for key in ['companies', 'people', 'emails', 'interactions', 'groups']:
            if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                items = data[key][:max_items]
                summary_parts.append(f"\n{key.capitalize()}: {len(data[key])} total")

                for item in items:
                    if isinstance(item, dict):
                        # Try to get a meaningful identifier
                        name = (
                            item.get('name') or
                            item.get('email') or
                            item.get('subject') or
                            item.get('id', 'Unknown')
                        )
                        summary_parts.append(f"  • {name}")

                if len(data[key]) > max_items:
                    summary_parts.append(f"  ... and {len(data[key]) - max_items} more")

    return "\n".join(summary_parts)


def summarize_collected_data(collected_data: Dict[str, Any]) -> str:
    """
    Summarize all collected data so far

    Used by THINK phase to understand current state.

    Args:
        collected_data: Dictionary of collected data

    Returns:
        Summary string
    """
    if not collected_data:
        return "No data collected yet"

    summary_parts = []

    for key, value in collected_data.items():
        if key.startswith('_'):
            continue

        if isinstance(value, list):
            if len(value) > 0:
                summary_parts.append(f"- {key}: {len(value)} items")
        elif value is not None:
            summary_parts.append(f"- {key}: present")

    return "\n".join(summary_parts) if summary_parts else "No meaningful data collected"


def detect_query_type(query: str) -> str:
    """
    Detect query type from natural language

    Args:
        query: Natural language query string

    Returns:
        Query type: COUNT, LIST, SINGLE, ANALYTICS, RELATIONSHIP, or UNKNOWN
    """
    query_lower = query.lower()

    # Count queries
    if any(word in query_lower for word in ['how many', 'count', 'number of', 'total']):
        return "COUNT"

    # Relationship queries
    if any(word in query_lower for word in ['related to', 'connected to', 'who knows', 'relationship']):
        return "RELATIONSHIP"

    # List queries
    if any(word in query_lower for word in ['list', 'show', 'get all', 'find all', 'display']):
        return "LIST"

    # Single entity queries
    if any(word in query_lower for word in ['who is', 'what is', 'show me the', 'get the']):
        return "SINGLE"

    # Analytical queries
    if any(word in query_lower for word in ['analyze', 'analytics', 'metrics', 'statistics', 'trend']):
        return "ANALYTICS"

    return "UNKNOWN"


def detect_data_type(data: Dict[str, Any]) -> str:
    """
    Detect what type of data was returned

    Args:
        data: Data dictionary from tool results

    Returns:
        Data type: EMPTY, LIST, ANALYTICS, SINGLE, or UNKNOWN
    """
    if not data:
        return "EMPTY"

    # Check if it's a list of items
    list_keys = ['companies', 'people', 'emails', 'interactions', 'groups']
    for key in list_keys:
        if key in data and isinstance(data[key], list) and len(data[key]) > 0:
            return "LIST"

    # Check if it's analytics/aggregate data
    if any(key in data for key in ['total_count', 'metrics', 'analytics', 'aggregated']):
        return "ANALYTICS"

    # Check if it's a single entity
    if 'id' in data and not any(key in data for key in list_keys):
        return "SINGLE"

    return "UNKNOWN"


def create_data_summary(data: Dict[str, Any], max_length: int = 1000) -> str:
    """
    Create abbreviated summary of data for LLM prompts

    This is used to pass data context to LLM without overwhelming token limits.

    Args:
        data: Data dictionary
        max_length: Maximum length of summary

    Returns:
        JSON string summary
    """
    summary = {
        "data_types": [],
        "counts": {},
        "sample_data": {}
    }

    for key, value in data.items():
        if key.startswith("_"):
            continue

        if isinstance(value, list):
            summary["data_types"].append(key)
            summary["counts"][key] = len(value)

            # Add sample (first 2 items)
            if len(value) > 0:
                sample = value[0] if len(value) == 1 else value[:2]
                # Simplify sample to just key fields
                if isinstance(sample, list):
                    summary["sample_data"][key] = [
                        _simplify_item(item) for item in sample
                    ]
                else:
                    summary["sample_data"][key] = _simplify_item(sample)

        elif value is not None:
            summary["data_types"].append(key)
            summary["sample_data"][key] = _simplify_item(value)

    # Convert to JSON and truncate if needed
    json_str = json.dumps(summary, indent=2, default=str)
    if len(json_str) > max_length:
        json_str = json_str[:max_length] + "\n... (truncated)"

    return json_str


def _simplify_item(item: Any) -> Any:
    """
    Simplify a data item to key fields only

    Args:
        item: Data item (dict or other)

    Returns:
        Simplified version with key fields only
    """
    if not isinstance(item, dict):
        return item

    # Key fields to keep
    key_fields = ['id', 'name', 'email', 'subject', 'company_id', 'person_id', 'type', 'status']

    simplified = {}
    for field in key_fields:
        if field in item:
            simplified[field] = item[field]

    # If no key fields found, return first 3 fields
    if not simplified:
        for i, (k, v) in enumerate(item.items()):
            if i >= 3:
                break
            simplified[k] = v

    return simplified


def score_reasoning_quality(reasoning_traces: List) -> float:
    """
    Score quality of reasoning traces

    Good reasoning shows:
    - Increasing confidence over iterations
    - Clear decision-making
    - Learning from observations

    Args:
        reasoning_traces: List of reasoning trace objects

    Returns:
        Quality score 0.0-1.0
    """
    if not reasoning_traces:
        return 0.5  # Neutral if no traces

    # Extract confidence values
    confidences = []
    for trace in reasoning_traces:
        if hasattr(trace, 'confidence'):
            confidences.append(trace.confidence)
        elif isinstance(trace, dict) and 'confidence' in trace:
            confidences.append(trace['confidence'])

    if len(confidences) < 2:
        return 0.7  # Not enough data, return default

    # Check if confidence improved (learning)
    if confidences[-1] > confidences[0]:
        return 0.9  # Good - learned and improved

    # Check if maintained high confidence
    if all(c > 0.7 for c in confidences):
        return 0.8  # Good - consistently confident

    # Check if declining confidence
    if confidences[-1] < confidences[0] * 0.7:
        return 0.4  # Poor - losing confidence

    return 0.6  # Okay - neither improving nor degrading


def score_data_quantity(data: Dict[str, Any]) -> float:
    """
    Score data quantity (not too little, not too much)

    Optimal range: 1-20 items
    Good range: 21-50 items
    Too many: >50 items

    Args:
        data: Data dictionary

    Returns:
        Quantity score 0.0-1.0
    """
    if not data:
        return 0.0

    total_items = 0
    for key, value in data.items():
        if key.startswith('_'):
            continue
        if isinstance(value, list):
            total_items += len(value)
        elif value is not None:
            total_items += 1

    # Optimal range: 1-20 items
    if 1 <= total_items <= 20:
        return 1.0

    # Good range: 21-50 items
    elif 21 <= total_items <= 50:
        return 0.8

    # Too many: >50 items (might be too broad)
    elif total_items > 50:
        # Gradually decrease score as items increase
        score = max(0.3, 0.8 - (total_items - 50) * 0.01)
        return score

    # No results
    else:
        return 0.3


def extract_entity_mentions(query: str) -> Dict[str, List[str]]:
    """
    Extract entity mentions from query

    This is a simple heuristic-based extraction. Could be enhanced with NER.

    Args:
        query: Natural language query

    Returns:
        Dictionary of entity types to mentions
    """
    query_lower = query.lower()
    entities = {
        "companies": [],
        "people": [],
        "emails": [],
        "dates": []
    }

    # Simple pattern matching (can be enhanced)
    # Company indicators
    if any(word in query_lower for word in ['company', 'corp', 'inc', 'ltd']):
        # Extract quoted company names
        import re
        quoted = re.findall(r'"([^"]+)"', query)
        entities["companies"].extend(quoted)

    # People indicators
    if any(word in query_lower for word in ['person', 'john', 'jane', 'from', 'to']):
        # Extract potential names (capitalized words)
        import re
        # Simple: words that start with capital letter
        potential_names = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', query)
        entities["people"].extend(potential_names)

    # Email patterns
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, query)
    entities["emails"].extend(emails)

    # Date patterns (simple)
    date_keywords = ['last month', 'last week', 'yesterday', 'today', 'this year']
    for keyword in date_keywords:
        if keyword in query_lower:
            entities["dates"].append(keyword)

    return entities


def format_observations_for_prompt(observations: List) -> str:
    """
    Format observations into readable text for LLM prompts

    Args:
        observations: List of Observation objects

    Returns:
        Formatted string
    """
    if not observations:
        return "No observations yet"

    formatted = []
    for i, obs in enumerate(observations, 1):
        if hasattr(obs, 'tool'):
            formatted.append(f"\nObservation {i} ({obs.tool}):")
            formatted.append(f"  Success: {obs.success}")
            formatted.append(f"  Result count: {obs.result_count}")
            formatted.append(f"  Confidence: {obs.confidence_score:.2f}")

            if obs.learned:
                formatted.append(f"  Learned: {', '.join(obs.learned[:3])}")

            if obs.still_missing:
                formatted.append(f"  Still missing: {', '.join(obs.still_missing[:3])}")
        elif isinstance(obs, dict):
            formatted.append(f"\nObservation {i}:")
            formatted.append(f"  {json.dumps(obs, indent=2)}")

    return "\n".join(formatted)


def is_query_ambiguous(query: str, result_count: int) -> bool:
    """
    Heuristic to detect if query is ambiguous based on results

    Args:
        query: Original query
        result_count: Number of results returned

    Returns:
        True if likely ambiguous
    """
    query_lower = query.lower()

    # Very generic queries with many results
    if result_count > 50:
        generic_terms = ['all', 'any', 'everything', 'list']
        if any(term in query_lower for term in generic_terms):
            return True

    # Mentions person/company name without specifics and got many results
    if result_count > 10:
        if any(word in query_lower for word in ['john', 'jane', 'smith', 'company']):
            # Check if there are qualifying details
            has_details = any(word in query_lower for word in [
                'at', 'in', 'from', '@', 'who works', 'located'
            ])
            if not has_details:
                return True

    return False


def calculate_progress_score(current_iteration: int, observations: List, max_iterations: int) -> float:
    """
    Calculate progress score for REFLECT phase

    Args:
        current_iteration: Current iteration number
        observations: List of observations so far
        max_iterations: Maximum allowed iterations

    Returns:
        Progress score 0.0-1.0
    """
    if not observations:
        return 0.0

    # Check if we're finding useful data
    useful_observations = sum(
        1 for obs in observations
        if (hasattr(obs, 'result_count') and obs.result_count > 0) or
           (isinstance(obs, dict) and obs.get('result_count', 0) > 0)
    )

    data_finding_rate = useful_observations / len(observations) if observations else 0

    # Check if we're running out of iterations
    iteration_progress = 1.0 - (current_iteration / max_iterations)

    # Combine scores
    progress = (data_finding_rate * 0.7) + (iteration_progress * 0.3)

    return progress
