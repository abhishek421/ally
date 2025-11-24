"""
Planner node for the LangGraph agent pipeline.

This module exports the planner_node function, which is responsible for:
1. Analyzing user input and conversation context
2. Calling the LLM to generate an execution plan
3. Parsing and validating the LLM's response
4. Returning a structured plan for the executor node

The planner does NOT execute tools or perform side effects. It only:
- Reads from the state
- Calls the LLM for planning
- Validates the plan structure
- Adds reasoning steps to state
- Returns the plan as a dictionary

Expected LLM Output Format (JSON):
{
    "decision_type": "PARALLEL" | "SEQUENTIAL" | "CONFIRMATION_REQUIRED" | "NONE",
    "tasks": [
        {
            "tool": "tool_name",
            "args": {
                "arg1": "value1",
                "workspace_id": "ws-123",
                ...
            }
        },
        ...
    ],
    "pending_action": {
        "action": "createCompany",
        "payload": {...},
        "description": "Create Acme Corp with these details"
    } | null,
    "summary": "Human-readable summary of the plan",
    "confidence": 0.95  // Optional confidence score
}

Example Plans:

1. Simple read query:
{
    "decision_type": "SEQUENTIAL",
    "tasks": [
        {
            "tool": "search_companies",
            "args": {"workspace_id": "ws-123", "user_id": "user-456", "search": "Acme"}
        }
    ],
    "pending_action": null,
    "summary": "Searching for companies matching 'Acme'",
    "confidence": 0.9
}

2. Write operation requiring confirmation:
{
    "decision_type": "CONFIRMATION_REQUIRED",
    "tasks": [],
    "pending_action": {
        "action": "createPerson",
        "payload": {
            "firstName": "John",
            "lastName": "Smith",
            "workspaceId": "ws-123",
            "privacyLevel": "PUBLIC"
        },
        "description": "Create a new person: John Smith (PUBLIC)"
    },
    "summary": "Ready to create person after confirmation",
    "confidence": 0.85
}
"""

import json
import re
from typing import Dict, Any, Optional
from datetime import datetime

from src.memory.state import AgentState
from src.interfaces.schemas import UserMessageInput
from src.utils.types import (
    Message,
    Role,
    PlannerDecisionType,
    ToolRegistry,
)
from src.config.logger import logger
from src.llm.model import call_planner
from src.llm.prompts import PLANNER_SYSTEM_PROMPT

# Placeholder for tool registry injection
# TODO: This will be injected at graph build time by graph.py
TOOL_REGISTRY: Optional[ToolRegistry] = None


# ========================================
# Helper Functions
# ========================================


def parse_planner_output(text: str) -> Dict[str, Any]:
    """
    Parse LLM output text into a structured plan dictionary.
    
    This function attempts to extract and parse JSON from the LLM response.
    It handles various cases:
    1. Direct JSON response
    2. JSON wrapped in markdown code blocks
    3. JSON embedded in text
    4. Malformed or missing JSON (returns safe fallback)
    
    This is exported as a separate function for unit testing.
    
    Args:
        text: Raw text response from the LLM
    
    Returns:
        Dictionary containing the parsed plan with keys:
        - decision_type: str
        - tasks: list
        - pending_action: dict or None
        - summary: str
        - confidence: float (optional)
    
    Example:
        >>> text = '{"decision_type": "SEQUENTIAL", "tasks": [], "summary": "test"}'
        >>> plan = parse_planner_output(text)
        >>> plan["decision_type"]
        'SEQUENTIAL'
    """
    # Default fallback plan
    fallback_plan = {
        "decision_type": "NONE",
        "tasks": [],
        "pending_action": None,
        "summary": "I couldn't plan automatically; please clarify your request.",
        "confidence": 0.0
    }
    
    try:
        # Try direct JSON parsing first
        plan = json.loads(text)
        logger.debug("Successfully parsed planner output as direct JSON")
        return plan
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying regex extraction")
    
    # Try extracting JSON from markdown code blocks
    # Pattern 1: ```json ... ```
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    
    if match:
        try:
            plan = json.loads(match.group(1))
            logger.debug("Successfully extracted JSON from code block")
            return plan
        except json.JSONDecodeError:
            logger.warning("Found code block but JSON parsing failed")
    
    # Pattern 2: Find any JSON object in the text
    json_object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.finditer(json_object_pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            plan = json.loads(match.group(0))
            # Verify it looks like a valid plan
            if "decision_type" in plan or "tasks" in plan:
                logger.debug("Successfully extracted JSON object from text")
                return plan
        except json.JSONDecodeError:
            continue
    
    # All parsing attempts failed
    logger.warning("Failed to parse planner output, returning fallback plan")
    return fallback_plan


def _validate_task(task: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
    """
    Validate and enhance a single planned task.
    
    Performs the following validations:
    1. Ensures tool name is a string and exists in registry
    2. Ensures args is a dictionary
    3. Adds workspace_id to args if missing
    4. Validates XOR constraint for interaction tasks (personId XOR companyId)
    
    Args:
        task: Task dictionary with 'tool' and 'args' keys
        state: Current agent state for context
    
    Returns:
        Validated and potentially modified task dictionary
    """
    validated_task = task.copy()
    
    # Validate tool name
    tool_name = task.get("tool")
    if not isinstance(tool_name, str):
        logger.warning(f"Invalid tool name type: {type(tool_name)}")
        validated_task["tool"] = "UNKNOWN_TOOL"
        validated_task["validation_error"] = "Tool name must be a string"
    elif TOOL_REGISTRY and tool_name not in TOOL_REGISTRY:
        logger.warning(f"Unknown tool: {tool_name}")
        validated_task["validation_error"] = f"Tool '{tool_name}' not found in registry"
    
    # Validate args
    args = task.get("args", {})
    if not isinstance(args, dict):
        logger.warning(f"Invalid args type for tool {tool_name}: {type(args)}")
        validated_task["args"] = {}
        validated_task["validation_error"] = "Args must be a dictionary"
    else:
        validated_task["args"] = args
        # Normalize camelCase to snake_case for known arguments
        value = args.pop("workspaceId", None)
        if value is not None:
            args.setdefault("workspace_id", value)
        value = args.pop("userId", None)
        if value is not None:
            args.setdefault("user_id", value)

        def _override_with_context(arg_name: str, context_value: Optional[str]) -> None:
            """
            Ensure workspace and user context always align with current state,
            overriding any LLM-provided placeholders.
            """
            if not context_value:
                return
            existing_value = args.get(arg_name)
            if existing_value and existing_value != context_value:
                logger.debug(
                    f"Overriding {arg_name} for tool {tool_name}: "
                    f"{existing_value} -> {context_value}"
                )
            args[arg_name] = context_value
            validated_task["args"][arg_name] = context_value

        # Always enforce workspace/user context to avoid placeholder IDs
        _override_with_context("workspace_id", state.workspace_id)
        _override_with_context("user_id", state.user_id)
        
        # Log final validated args for debugging
        logger.debug(f"Planner validated task '{tool_name}' with args: {validated_task['args']}")

        # Special validation for interaction creation tasks
        if tool_name == "create_interaction":
            person_id = args.get("person_id") or args.get("personId")
            company_id = args.get("company_id") or args.get("companyId")
            
            # XOR constraint: exactly one must be present
            if (person_id and company_id) or (not person_id and not company_id):
                validated_task["validation_error"] = (
                    "create_interaction requires exactly ONE of person_id or company_id"
                )
                logger.warning(
                    f"XOR validation failed for create_interaction: "
                    f"person_id={person_id}, company_id={company_id}"
                )
    
    return validated_task


def _build_tool_descriptions() -> str:
    """
    Build a concise list of available tools for the LLM prompt.
    
    Returns:
        String containing tool names and brief descriptions
    """
    if not TOOL_REGISTRY:
        return "No tools available (registry not initialized)"
    
    tool_lines = []
    for tool_name, tool_spec in TOOL_REGISTRY.items():
        # Prefer explicit description attribute, fallback to docstring
        description = getattr(tool_spec, 'description', None) or getattr(tool_spec, '__doc__', "No description")
        
        # Clean up description (take first paragraph or sentence)
        if description and description != "No description":
            # Remove leading/trailing whitespace
            description = description.strip()
            # Take first paragraph (split by double newline)
            # Use regex to handle spaces between newlines
            parts = re.split(r'\n\s*\n', description)
            description = parts[0]
            # Normalize whitespace
            description = ' '.join(description.split())
            
        tool_lines.append(f"- {tool_name}: {description}")
    
    return "\n".join(tool_lines)


def _build_memory_context(state: AgentState) -> str:
    """
    Build a context string from retrieved long-term memories.
    
    Args:
        state: Current agent state containing retrieved_memories
    
    Returns:
        Formatted string of memory items (up to 3)
    """
    if not state.retrieved_memories:
        return ""
    
    memory_lines = ["Relevant context from past conversations:"]
    for i, memory in enumerate(state.retrieved_memories[:3], 1):
        # Memory format depends on vector store implementation
        content = memory.get("content", memory.get("text", str(memory)))
        memory_lines.append(f"{i}. {content}")
    
    return "\n".join(memory_lines)


# ========================================
# Main Planner Node
# ========================================


async def planner_node(
    state: AgentState
) -> Dict[str, Any]:
    """
    Generate an execution plan based on user input and conversation context.
    
    This is the planner node in the LangGraph pipeline. It analyzes the user's
    message along with conversation history and determines what actions should
    be taken to fulfill the request.
    
    The planner:
    1. Builds a prompt with system instructions, tools list, and context
    2. Calls the LLM to generate a structured plan
    3. Parses the LLM response (expected JSON format)
    4. Validates planned tasks (tool existence, args structure, constraints)
    5. Adds reasoning steps to state for transparency
    6. Returns the plan for the executor node
    
    Decision Types:
    - PARALLEL: Execute all tasks concurrently
    - SEQUENTIAL: Execute tasks one after another
    - CONFIRMATION_REQUIRED: Need user approval before execution
    - NONE: No actionable plan (clarification needed)
    
    Args:
        state: Current agent state with conversation history and context
    
    Returns:
        Dictionary containing state update:
        {
            "plan": {
                "decision_type": str,
                "tasks": List[Dict],
                "pending_action": Dict or None,
                "summary": str,
                "confidence": float (optional)
            }
        }
    
    Raises:
        Does not raise exceptions - returns safe fallback plan on errors
    """
    try:
        # Get the last user message
        if not state.messages:
            logger.warning("No messages in state for planner")
            return {"plan": {
                "decision_type": "NONE",
                "tasks": [],
                "pending_action": None,
                "summary": "No message to process.",
                "confidence": 0.0
            }}
            
        last_message = state.messages[-1]
        message_content = last_message.content
        
        logger.info(f"Planning for message: {message_content[:100]}...")
        
        # Quick check: Is this just a greeting/chitchat? Skip planning entirely
        greeting_keywords = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "thanks", "thank you", "bye", "goodbye"]
        message_lower = message_content.lower().strip()
        is_greeting = any(message_lower.startswith(kw) for kw in greeting_keywords) or message_lower in greeting_keywords
        
        if is_greeting and len(message_content.split()) <= 5:
            logger.info("Detected greeting/chitchat - skipping planning")
            return {"plan": {
                "decision_type": "NONE",
                "tasks": [],
                "pending_action": None,
                "summary": "User is greeting. Respond warmly.",
                "confidence": 1.0
            }}
        
        # Build LLM prompt context
        system_prompt = PLANNER_SYSTEM_PROMPT
        
        # Get recent message history (last 8 messages)
        recent_messages = state.messages[-8:] if state.messages else []
        message_context = "\n".join([
            f"{msg.role.value}: {msg.content}"
            for msg in recent_messages
        ])
        
        # Build tool descriptions
        tools_context = _build_tool_descriptions()
        
        # Build memory context
        memory_context = _build_memory_context(state)
        
        # Build previous results context (CRITICAL for intelligent behavior)
        previous_results_context = ""
        if state.aggregated_result:
            merged_results = state.aggregated_result.get("merged_results", {})
            if merged_results:
                import json
                # Show what data we already have
                result_summary = []
                for category, data in merged_results.items():
                    if isinstance(data, list):
                        result_summary.append(f"- {category}: {len(data)} items")
                    elif isinstance(data, dict) and "data" in data:
                        data_list = data.get("data", [])
                        total = data.get("meta", {}).get("total", len(data_list))
                        result_summary.append(f"- {category}: {len(data_list)} items (total: {total})")
                
                if result_summary:
                    previous_results_context = f"""
Previous Tool Results (from recent turns):
{chr(10).join(result_summary)}

**IMPORTANT**: Check if the user's question can be answered FULLY using these previous results.
1. If YES (e.g. filtering existing list, counting items): Use decision_type: "NONE" and explain in summary.
2. If NO (e.g. user wants DETAILS not in the list like email, phone, address): YOU MUST CALL A TOOL (like get_company or search_companies).
3. Do not assume you have details that are not explicitly shown in the summary above."""
        
        # Construct full prompt
        prompt = f"""{system_prompt}

Available Tools:
{tools_context}

{memory_context}

{previous_results_context}

Recent Conversation:
{message_context}

Current Request: {message_content}

Generate a plan as JSON with:
- decision_type: PARALLEL, SEQUENTIAL, CONFIRMATION_REQUIRED, or NONE
- tasks: array of {{tool, args}} objects
- pending_action: null or {{action, payload, description}} for confirmations
- summary: brief explanation
- confidence: 0-1 score (optional)
"""
        
        # Call LLM
        logger.debug("Calling LLM for planning...")
        
        llm_response = await call_planner(prompt, max_tokens=512)
        
        logger.debug(f"LLM response received: {llm_response[:200]}...")
        
        # Parse LLM response
        plan = parse_planner_output(llm_response)
        
        # Validate decision type
        decision_type = plan.get("decision_type", "NONE")
        if decision_type not in ["PARALLEL", "SEQUENTIAL", "CONFIRMATION_REQUIRED", "NONE"]:
            logger.warning(f"Invalid decision_type: {decision_type}, defaulting to NONE")
            plan["decision_type"] = "NONE"
        
        # Validate and enhance tasks
        tasks = plan.get("tasks", [])
        validated_tasks = []
        validation_issues = []
        
        for i, task in enumerate(tasks):
            validated_task = _validate_task(task, state)
            validated_tasks.append(validated_task)
            
            if "validation_error" in validated_task:
                validation_issues.append(
                    f"Task {i+1} ({validated_task.get('tool', 'unknown')}): "
                    f"{validated_task['validation_error']}"
                )
        
        plan["tasks"] = validated_tasks
        
        # Add reasoning steps to state
        state.add_reasoning(f"Analyzed request: {message_content[:100]}")
        
        if validation_issues:
            state.add_reasoning(f"Plan validation issues: {'; '.join(validation_issues)}")
        
        summary = plan.get("summary", "Plan generated")
        state.add_reasoning(f"Plan: {summary}")
        
        if plan["decision_type"] == "CONFIRMATION_REQUIRED":
            state.add_reasoning("This action requires user confirmation before execution")
        elif len(validated_tasks) > 0:
            task_names = [t.get("tool", "unknown") for t in validated_tasks]
            state.add_reasoning(f"Will execute {len(validated_tasks)} task(s): {', '.join(task_names)}")
        
        logger.info(
            f"Plan generated: {plan['decision_type']} with {len(validated_tasks)} task(s)"
        )
        
        return {"plan": plan}
        
    except Exception as e:
        # Catch-all error handler - return safe fallback plan
        logger.error(f"Error in planner_node: {e}", exc_info=True)
        
        # Add error reasoning to state
        state.add_reasoning(f"Planning error: {str(e)}")
        state.add_reasoning("Returning safe fallback - please rephrase your request")
        
        # Return safe fallback plan
        return {"plan": {
            "decision_type": "NONE",
            "tasks": [],
            "pending_action": None,
            "summary": f"I encountered an error while planning: {str(e)}. Please try rephrasing your request.",
            "confidence": 0.0
        }}

