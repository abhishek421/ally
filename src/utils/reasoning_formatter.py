"""Utility to format technical reasoning steps into user-friendly messages."""

import re
from typing import List, Dict, Any, Tuple


def format_reasoning_step(step: str) -> str:
    """
    Transform a technical reasoning step into a user-friendly message.
    
    Following the "Glass Box" principle from Ally Vision:
    - Show thinking in a natural, conversational way
    - Hide implementation details
    - Focus on intent and outcomes
    
    Args:
        step: Raw reasoning step from the LLM
        
    Returns:
        User-friendly formatted reasoning step
    """
    # Skip empty steps
    if not step or not step.strip():
        return ""
    
    step = step.strip()
    
    # Pattern: ACTION: use_tool TOOL: xxx PARAMS: {...}
    tool_match = re.search(
        r'ACTION:\s*use_tool\s+TOOL:\s*(\w+)\s+PARAMS:\s*(\{[^}]*\})?',
        step,
        re.IGNORECASE | re.DOTALL
    )
    if tool_match:
        tool_name = tool_match.group(1)
        return _format_tool_action(tool_name, tool_match.group(2))
    
    # Pattern: ACTION: answer ANSWER: xxx
    answer_match = re.search(r'ACTION:\s*answer\s+ANSWER:', step, re.IGNORECASE)
    if answer_match:
        return "📝 Preparing my response..."
    
    # Pattern: Tool xxx called with params...
    tool_called_match = re.search(
        r'Tool\s+(\w+)\s+called\s+with\s+params',
        step,
        re.IGNORECASE
    )
    if tool_called_match:
        tool_name = tool_called_match.group(1)
        return _format_tool_result(tool_name)
    
    # Pattern: Looking for specific data patterns
    if "workspace_id" in step.lower() and "your_workspace" in step.lower():
        return "🔍 Searching your workspace..."
    
    # Pattern: Contains JSON-like structures - summarize intent
    if step.count('{') > 0 and step.count('}') > 0:
        # Try to extract intent from surrounding text
        intent = _extract_intent(step)
        if intent:
            return intent
        return "🔄 Processing request..."
    
    # Pattern: Error messages
    if "error" in step.lower():
        return "⚠️ Encountered an issue, trying another approach..."
    
    # Pattern: Technical thinking that should be simplified
    if any(keyword in step.lower() for keyword in ['params', 'query:', 'result:', 'json']):
        intent = _extract_intent(step)
        if intent:
            return intent
        return "💭 Analyzing the data..."
    
    # If it's already a reasonably user-friendly message, keep it
    # But clean up any remaining technical artifacts
    cleaned = _clean_technical_artifacts(step)
    
    # Add appropriate emoji if not present
    if cleaned and not any(cleaned.startswith(e) for e in ['🔍', '💭', '📝', '✅', '⚠️', '🔄', '📊', '👥', '🏢', '💼']):
        cleaned = f"💭 {cleaned}"
    
    return cleaned


def _format_tool_action(tool_name: str, params_str: str = None) -> str:
    """Format a tool action into a friendly message."""
    tool_messages = {
        # People tools
        'search_people': '👥 Searching for people...',
        'get_person_by_id': '👤 Looking up person details...',
        'get_person_companies': '🏢 Finding companies for this person...',
        'get_person_deals': '💼 Checking deals for this person...',
        'get_person_interactions': '📧 Reviewing interactions...',
        'get_person_timeline': '📅 Building timeline...',
        
        # Company tools
        'search_companies': '🏢 Searching for companies...',
        'get_company_by_id': '🏢 Looking up company details...',
        'get_company_people': '👥 Finding people at this company...',
        'get_company_deals': '💼 Checking company deals...',
        'get_company_interactions': '📧 Reviewing company interactions...',
        'get_company_timeline': '📅 Building company timeline...',
        
        # Deal tools
        'search_deals': '💼 Searching for deals...',
        'get_deal_by_id': '💼 Looking up deal details...',
        'get_deal_people': '👥 Finding people on this deal...',
        'get_deal_companies': '🏢 Finding companies on this deal...',
        'get_deal_interactions': '📧 Reviewing deal interactions...',
        
        # Interaction tools
        'search_interactions': '📧 Searching interactions...',
        'get_interaction_by_id': '📧 Looking up interaction...',
        
        # Group tools
        'get_workspace_groups': '📁 Looking up your groups...',
        'get_group_by_id': '📁 Getting group details...',
        'get_group_members': '👥 Finding group members...',
        
        # Analytics tools
        'get_activity_summary': '📊 Analyzing activity...',
        'analyze_contact_growth': '📈 Analyzing growth trends...',
        'analyze_pipeline': '📊 Analyzing pipeline...',
        
        # Context tools
        'get_account_context': '🔍 Gathering account context...',
        'get_deal_context': '🔍 Gathering deal context...',
        'find_relationships': '🔗 Finding relationships...',
        'get_relationship_network': '🕸️ Mapping relationship network...',
        
        # Creation/Write tools
        'create_person': '✨ Creating new person...',
        'create_company': '✨ Creating new company...',
        'create_group': '✨ Creating new group...',
        'add_person_to_company': '🔗 Linking person to company...',
        'add_person_to_group': '➕ Adding person to group...',
        'add_company_to_group': '➕ Adding company to group...',
        'add_multiple_people_to_group': '➕ Adding people to group...',
        'add_multiple_companies_to_group': '➕ Adding companies to group...',
        'find_relationships': '🔗 Finding relationships...',
        'get_relationship_network': '🕸️ Mapping relationship network...',
        
        # Utility tools
        'get_workspace_summary': '📊 Getting workspace overview...',
        'get_bulk_entities': '📦 Fetching multiple records...',
    }
    
    # Get friendly message or generate one
    if tool_name in tool_messages:
        return tool_messages[tool_name]
    
    # Generate a generic message for unknown tools
    friendly_name = tool_name.replace('_', ' ').title()
    return f"🔄 {friendly_name}..."


def _format_tool_result(tool_name: str) -> str:
    """Format a tool result notification."""
    tool_result_messages = {
        'search_people': '✅ Found people matching your criteria',
        'search_companies': '✅ Found companies matching your criteria',
        'search_deals': '✅ Found deals matching your criteria',
        'search_interactions': '✅ Found relevant interactions',
        'get_workspace_groups': '✅ Retrieved your groups',
        'get_company_people': '✅ Found people at this company',
    }
    
    if tool_name in tool_result_messages:
        return tool_result_messages[tool_name]
    
    return f"✅ Retrieved {tool_name.replace('_', ' ')} data"


def _extract_intent(step: str) -> str:
    """Try to extract the user-facing intent from a technical step."""
    # Common patterns and their friendly translations
    patterns = [
        (r'search.*people', '👥 Searching for people...'),
        (r'search.*compan', '🏢 Searching for companies...'),
        (r'search.*deal', '💼 Searching for deals...'),
        (r'get.*group', '📁 Looking up groups...'),
        (r'find.*relationship', '🔗 Finding connections...'),
        (r'analyz', '📊 Analyzing data...'),
        (r'count', '🔢 Counting records...'),
        (r'filter', '🔍 Filtering results...'),
        (r'sort', '📑 Sorting results...'),
    ]
    
    step_lower = step.lower()
    for pattern, message in patterns:
        if re.search(pattern, step_lower):
            return message
    
    return None


def _clean_technical_artifacts(step: str) -> str:
    """Remove technical artifacts from a reasoning step."""
    # Remove JSON objects
    step = re.sub(r'\{[^}]*\}', '', step)
    
    # Remove common technical prefixes
    step = re.sub(r'^(ACTION:|TOOL:|PARAMS:|ANSWER:)\s*', '', step, flags=re.IGNORECASE)
    
    # Remove workspace_id, user_id mentions
    step = re.sub(r'workspace_id["\']?\s*[:=]\s*["\']?[\w-]+["\']?', '', step, flags=re.IGNORECASE)
    step = re.sub(r'user_id["\']?\s*[:=]\s*["\']?[\w-]+["\']?', '', step, flags=re.IGNORECASE)
    
    # Remove UUIDs
    step = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '', step, flags=re.IGNORECASE)
    
    # Remove empty quotes and brackets
    step = re.sub(r'["\'][\s]*["\']', '', step)
    step = re.sub(r'\[\s*\]', '', step)
    step = re.sub(r'\(\s*\)', '', step)
    
    # Clean up multiple spaces and newlines
    step = re.sub(r'\s+', ' ', step)
    
    # Remove trailing punctuation artifacts
    step = re.sub(r'[,;:]+\s*$', '', step)
    
    return step.strip()


def format_reasoning_steps(steps: List[str]) -> List[str]:
    """
    Format a list of reasoning steps into user-friendly messages.
    
    Args:
        steps: List of raw reasoning steps
        
    Returns:
        List of formatted, user-friendly reasoning steps
    """
    formatted = []
    seen_messages = set()  # Avoid duplicates
    
    for step in steps:
        formatted_step = format_reasoning_step(step)
        
        # Skip empty or duplicate messages
        if formatted_step and formatted_step not in seen_messages:
            formatted.append(formatted_step)
            seen_messages.add(formatted_step)
    
    return formatted


def format_tool_call_for_display(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a tool call record for user-friendly display.
    
    Args:
        tool_call: Raw tool call record with tool, params, result
        
    Returns:
        Formatted tool call with user-friendly descriptions
    """
    tool_name = tool_call.get('tool', 'unknown')
    
    # Friendly tool names
    friendly_names = {
        # Read tools
        'search_people': 'Search People',
        'search_companies': 'Search Companies',
        'search_deals': 'Search Deals',
        'get_person_by_id': 'Get Person Details',
        'get_company_by_id': 'Get Company Details',
        'get_company_people': 'Find Company Contacts',
        'get_workspace_groups': 'List Groups',
        'get_group_by_id': 'Get Group Details',
        'get_workspace_summary': 'Workspace Overview',
        'analyze_pipeline': 'Analyze Pipeline',
        # Write/Creation tools
        'create_person': 'Create Person',
        'create_company': 'Create Company',
        'create_group': 'Create Group',
        'add_person_to_company': 'Link Person to Company',
        'add_person_to_group': 'Add to Group',
        'add_company_to_group': 'Add to Group',
        'add_multiple_people_to_group': 'Add People to Group',
        'add_multiple_companies_to_group': 'Add Companies to Group',
    }
    
    return {
        'tool': friendly_names.get(tool_name, tool_name.replace('_', ' ').title()),
        'tool_id': tool_name,  # Keep original for technical use
        'params': _sanitize_params(tool_call.get('params', {})),
        'status': 'completed' if tool_call.get('result') else 'calling',
    }


def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive or technical params from display."""
    # Keys to hide from user display
    hidden_keys = {'workspace_id', 'user_id'}
    
    return {
        k: v for k, v in params.items()
        if k not in hidden_keys and v is not None
    }


def clean_final_answer(answer: str) -> str:
    """
    Clean the final answer from technical artifacts that users shouldn't see.
    
    This removes:
    - UUIDs (company IDs, person IDs, etc.)
    - Technical parameter mentions
    - Internal identifiers
    
    Args:
        answer: Raw answer from the LLM
        
    Returns:
        Cleaned, user-friendly answer
    """
    if not answer:
        return answer
    
    # Remove standalone UUIDs (with optional surrounding quotes)
    # Pattern: UUID possibly surrounded by quotes, parentheses, or as part of "ID is UUID"
    answer = re.sub(
        r'\b[Tt]he\s+(?:company|person|group|deal|interaction)\s+ID\s+is\s+["\']?[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}["\']?\.?',
        '',
        answer,
        flags=re.IGNORECASE
    )
    
    # Remove "with ID <uuid>" patterns
    answer = re.sub(
        r'\s+with\s+(?:an?\s+)?ID\s+(?:of\s+)?["\']?[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}["\']?',
        '',
        answer,
        flags=re.IGNORECASE
    )
    
    # Remove "(ID: <uuid>)" patterns
    answer = re.sub(
        r'\s*\(ID:\s*[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\)',
        '',
        answer,
        flags=re.IGNORECASE
    )
    
    # Remove "ID <uuid>" at end of sentences
    answer = re.sub(
        r'\s+ID\s+[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
        '',
        answer,
        flags=re.IGNORECASE
    )
    
    # Remove any remaining standalone UUIDs
    answer = re.sub(
        r'["\']?[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}["\']?',
        '',
        answer,
        flags=re.IGNORECASE
    )
    
    # Remove workspace_id and user_id mentions
    answer = re.sub(
        r'\s*(?:workspace_id|user_id|workspace ID|user ID)[:\s]+["\']?[\w-]+["\']?',
        '',
        answer,
        flags=re.IGNORECASE
    )
    
    # Clean up artifacts from removal
    # Double periods
    answer = re.sub(r'\.\.+', '.', answer)
    # Double spaces
    answer = re.sub(r'\s{2,}', ' ', answer)
    # Space before punctuation
    answer = re.sub(r'\s+([.,!?])', r'\1', answer)
    # Empty parentheses
    answer = re.sub(r'\(\s*\)', '', answer)
    # Sentence starting with lowercase after cleanup
    answer = re.sub(r'\.\s+([a-z])', lambda m: '. ' + m.group(1).upper(), answer)
    # Leading/trailing whitespace
    answer = answer.strip()
    
    return answer

