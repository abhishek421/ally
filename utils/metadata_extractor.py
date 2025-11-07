"""
Utility for extracting compact metadata from tool results for conversation storage.

This module prevents data duplication by storing only IDs and references
instead of full data objects that already exist in the database.
"""
from typing import Dict, Any, List, Optional


def extract_compact_query_context(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract compact query context from pipeline result.

    Stores only:
    - Tool names that were executed
    - Entity IDs and names (company_id, person_id, etc.)
    - Result counts and pagination info
    - Record IDs (email_ids, deal_ids, etc.) - NOT full records

    Does NOT store:
    - Full email bodies, HTML content
    - Complete deal/contact/company objects
    - Large data structures that exist in DB

    Args:
        result: Pipeline result containing response, data, and metadata

    Returns:
        Compact query context dictionary suitable for metadata storage

    Example:
        Input:
        {
            "response": "# Emails from Acme...",
            "data": {
                "emails": {
                    "emails": [{"messageId": "msg-1", "body": "..."}, ...],
                    "total_count": 3,
                    "company_id": "comp-123"
                }
            },
            "metadata": {"processing_time_ms": 1250}
        }

        Output:
        {
            "tools_executed": ["emails"],
            "result_summary": {
                "emails": {
                    "email_ids": ["msg-1", "msg-2", "msg-3"],
                    "count": 3,
                    "company_id": "comp-123",
                    "has_more": false
                }
            }
        }
    """
    if not isinstance(result, dict):
        return {}

    extracted_data = result.get("data", {})
    if not isinstance(extracted_data, dict):
        return {}

    query_context = {
        "tools_executed": list(extracted_data.keys()),
        "result_summary": {}
    }

    # Extract compact summaries for each tool result
    for tool_name, tool_data in extracted_data.items():
        if not isinstance(tool_data, dict):
            continue

        summary = _extract_tool_summary(tool_name, tool_data)
        if summary:
            query_context["result_summary"][tool_name] = summary

    return query_context


def _extract_tool_summary(tool_name: str, tool_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract compact summary from a single tool's result.

    Args:
        tool_name: Name of the tool (e.g., "emails", "deals")
        tool_data: Tool result data

    Returns:
        Compact summary with IDs, counts, and entity references
    """
    summary = {}

    # Extract counts and pagination
    if "total_count" in tool_data:
        summary["count"] = tool_data["total_count"]
    if "has_more" in tool_data:
        summary["has_more"] = tool_data["has_more"]
    if "next_token" in tool_data and tool_data["next_token"]:
        summary["has_next_page"] = True

    # Extract entity references (company, person, etc.)
    _extract_entity_references(tool_data, summary)

    # Extract record IDs based on tool type
    _extract_record_ids(tool_name, tool_data, summary)

    # Extract filter information
    _extract_filters(tool_data, summary)

    return summary if summary else None


def _extract_entity_references(tool_data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract entity IDs and names from tool data."""
    entity_fields = [
        ("company_id", "company_id"),
        ("company_name", "company_name"),
        ("person_id", "person_id"),
        ("person_name", "person_name"),
        ("deal_id", "deal_id"),
        ("contact_id", "contact_id"),
    ]

    for source_field, target_field in entity_fields:
        if source_field in tool_data and tool_data[source_field]:
            summary[target_field] = tool_data[source_field]


def _extract_record_ids(tool_name: str, tool_data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """
    Extract record IDs from tool results.

    Stores only IDs, not full records. This prevents data duplication
    while maintaining conversation context for follow-up queries.
    """
    # Email tool results
    if "emails" in tool_data:
        emails = tool_data["emails"]
        if isinstance(emails, list) and emails:
            summary["email_ids"] = [
                email.get("messageId")
                for email in emails
                if isinstance(email, dict) and email.get("messageId")
            ]
            summary["count"] = len(emails)

    # Deal tool results
    elif "deals" in tool_data:
        deals = tool_data["deals"]
        if isinstance(deals, list) and deals:
            summary["deal_ids"] = [
                deal.get("id")
                for deal in deals
                if isinstance(deal, dict) and deal.get("id")
            ]
            summary["count"] = len(deals)

    # Contact/People tool results
    elif "contacts" in tool_data or "people" in tool_data:
        people_data = tool_data.get("contacts") or tool_data.get("people", [])
        if isinstance(people_data, list) and people_data:
            summary["people_ids"] = [
                person.get("id")
                for person in people_data
                if isinstance(person, dict) and person.get("id")
            ]
            # Extract people names for better context resolution
            summary["people_names"] = [
                person.get("name")
                for person in people_data
                if isinstance(person, dict) and person.get("name")
            ]
            summary["count"] = len(people_data)

    # Company tool results
    elif "companies" in tool_data:
        companies = tool_data["companies"]
        if isinstance(companies, list) and companies:
            summary["company_ids"] = [
                company.get("id")
                for company in companies
                if isinstance(company, dict) and company.get("id")
            ]
            # Extract company names for better context resolution
            summary["company_names"] = [
                company.get("name")
                for company in companies
                if isinstance(company, dict) and company.get("name")
            ]
            summary["count"] = len(companies)

    # Single email result (get_by_id, get_latest)
    elif "email" in tool_data:
        email = tool_data["email"]
        if isinstance(email, dict) and email.get("messageId"):
            summary["email_id"] = email.get("messageId")
            summary["count"] = 1

    # Single deal result
    elif "deal" in tool_data:
        deal = tool_data["deal"]
        if isinstance(deal, dict) and deal.get("id"):
            summary["deal_id"] = deal.get("id")
            summary["count"] = 1

    # Thread information
    if "thread_id" in tool_data:
        summary["thread_id"] = tool_data["thread_id"]


def _extract_filters(tool_data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract filter information that was applied to the query."""
    filters = {}

    # Direction filter (sent/received)
    if "direction_filter" in tool_data:
        filters["direction"] = tool_data["direction_filter"]

    # Date filters
    if "date_from" in tool_data:
        filters["date_from"] = tool_data["date_from"]
    if "date_to" in tool_data:
        filters["date_to"] = tool_data["date_to"]

    # Privacy filtering info
    if "privacy_filtered" in tool_data:
        summary["privacy_filtered_count"] = tool_data["privacy_filtered"]

    # Limit/pagination
    if "limit" in tool_data:
        filters["limit"] = tool_data["limit"]

    if filters:
        summary["filters_applied"] = filters


def extract_performance_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract performance metadata from pipeline result.

    Args:
        result: Pipeline result containing metadata

    Returns:
        Performance metrics dictionary
    """
    if not isinstance(result, dict):
        return {}

    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        return {}

    performance = {}

    # Extract relevant performance metrics
    perf_fields = [
        "processing_time_ms",
        "llm_call_time_ms",
        "response_length",
        "data_sources_count"
    ]

    for field in perf_fields:
        if field in metadata:
            performance[field] = metadata[field]

    return performance
