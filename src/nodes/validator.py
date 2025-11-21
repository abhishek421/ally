"""
Validator node for the LangGraph agent pipeline.

This module exports the validator_node function, which is responsible for:
1. Detecting user confirmations of pending actions
2. Converting write operations into pending confirmation flows
3. Validating task arguments and constraints
4. Ensuring safety rules before execution

The validator sits between the planner and executor in the pipeline:
    User Input → Planner → Validator → Executor

The validator does NOT execute tools or call the LLM. It performs pure Python
validation logic and may modify the plan before returning it to the executor.

Safety Rules:
- All write operations (create, update, delete) require user confirmation
- Users must explicitly confirm pending actions before execution
- XOR constraints are enforced (e.g., personId XOR companyId for interactions)
- Required fields are validated before allowing execution
- Invalid plans are rejected with clear error messages

Pending Action Workflow:
1. Planner suggests a write operation (e.g., createPerson)
2. Validator converts it to a pending_action and sets decision_type to CONFIRMATION_REQUIRED
3. Agent sends pending_action to frontend for user review
4. User confirms (or edits) the action
5. Validator detects confirmation and converts pending_action back to executable task
6. Executor performs the actual operation

Mutation Confirmation Workflow:
When the validator detects a mutating operation:
- Extracts the first mutation from planned tasks
- Converts it to a pending_action with human-readable description
- Clears all tasks (to prevent execution without confirmation)
- Sets decision_type to CONFIRMATION_REQUIRED
- Returns modified plan to agent for user confirmation
"""

import re
from typing import Dict, Any, Set

from src.memory.state import AgentState
from src.utils.types import PlannerDecisionType
from src.config.logger import logger


# ========================================
# Constants
# ========================================

# Set of tools that mutate data and require user confirmation
MUTATING_TOOLS: Set[str] = {
    # Company mutations
    "create_company",
    "update_company",
    "delete_companies",
    
    # Person mutations
    "create_person",
    "update_person",
    "delete_people",
    
    # Interaction mutations
    "create_interaction",
    "update_interaction",
    "delete_interaction",
    
    # Group mutations
    "create_group",
    "update_group",
    "delete_group",
    
    # Group membership mutations
    "add_company_to_group",
    "remove_company_from_group",
    "add_person_to_group",
    "remove_person_from_group",
}

# Affirmative confirmation patterns
CONFIRMATION_PATTERNS = [
    r'\byes\b',
    r'\byep\b',
    r'\byeah\b',
    r'\bconfirm\b',
    r'\bgo ahead\b',
    r'\bdo it\b',
    r'\bproceed\b',
    r'\bok\b',
    r'\bokay\b',
    r'\bapprove\b',
    r'\bapproved\b',
    r'\bsure\b',
    r'\bcorrect\b',
    r'\bright\b',
    r'\bexactly\b',
]


# ========================================
# Helper Functions
# ========================================


def _is_confirmation(message: str) -> bool:
    """
    Check if a user message is an affirmative confirmation.
    
    Uses regex patterns to detect common confirmation phrases like
    "yes", "confirm", "go ahead", "do it", "proceed", etc.
    
    Args:
        message: User message text to check
    
    Returns:
        True if message contains confirmation language, False otherwise
    
    Example:
        >>> _is_confirmation("yes, go ahead")
        True
        >>> _is_confirmation("no, cancel that")
        False
    """
    message_lower = message.lower().strip()
    
    for pattern in CONFIRMATION_PATTERNS:
        if re.search(pattern, message_lower):
            logger.debug(f"Detected confirmation pattern: {pattern}")
            return True
    
    return False


def _has_mutating_tasks(plan: Dict[str, Any]) -> bool:
    """
    Check if a plan contains any mutating (write) operations.
    
    Args:
        plan: Plan dictionary with 'tasks' key
    
    Returns:
        True if any task is a mutating operation, False otherwise
    """
    tasks = plan.get("tasks", [])
    
    for task in tasks:
        tool_name = task.get("tool", "")
        if tool_name in MUTATING_TOOLS:
            return True
    
    return False


def _get_first_mutation(plan: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Extract the first mutating task from a plan.
    
    Args:
        plan: Plan dictionary with 'tasks' key
    
    Returns:
        First mutating task dictionary or None if no mutations found
    """
    tasks = plan.get("tasks", [])
    
    for task in tasks:
        tool_name = task.get("tool", "")
        if tool_name in MUTATING_TOOLS:
            return task
    
    return None


def _generate_action_description(tool_name: str, args: Dict[str, Any]) -> str:
    """
    Generate a human-readable description for a pending action.
    
    Creates user-friendly descriptions like:
    - "Create a new person: John Smith (PUBLIC)"
    - "Delete 3 companies"
    - "Update group 'Sales Team' privacy settings"
    
    Args:
        tool_name: Name of the tool/action
        args: Arguments for the action
    
    Returns:
        Human-readable description string
    """
    # Company actions
    if tool_name == "create_company":
        name = args.get("input", {}).get("name", "Unknown")
        privacy = args.get("input", {}).get("privacyLevel", "PRIVATE")
        return f"Create a new company: {name} ({privacy})"
    
    elif tool_name == "update_company":
        company_id = args.get("input", {}).get("id", "unknown")
        return f"Update company {company_id}"
    
    elif tool_name == "delete_companies":
        count = len(args.get("company_ids", []))
        return f"Delete {count} {'company' if count == 1 else 'companies'}"
    
    # Person actions
    elif tool_name == "create_person":
        input_data = args.get("input", {})
        first_name = input_data.get("firstName", "Unknown")
        last_name = input_data.get("lastName", "")
        full_name = f"{first_name} {last_name}".strip()
        privacy = input_data.get("privacyLevel", "PRIVATE")
        return f"Create a new person: {full_name} ({privacy})"
    
    elif tool_name == "update_person":
        person_id = args.get("input", {}).get("id", "unknown")
        return f"Update person {person_id}"
    
    elif tool_name == "delete_people":
        count = len(args.get("people_ids", []))
        return f"Delete {count} {'person' if count == 1 else 'people'}"
    
    # Interaction actions
    elif tool_name == "create_interaction":
        interaction_type = args.get("interaction_type", "interaction")
        event_name = args.get("event_name", "")
        return f"Create {interaction_type}: {event_name}"
    
    elif tool_name == "update_interaction":
        return f"Update interaction {args.get('interaction_id', 'unknown')}"
    
    elif tool_name == "delete_interaction":
        return f"Delete interaction {args.get('interaction_id', 'unknown')}"
    
    # Group actions
    elif tool_name == "create_group":
        name = args.get("input", {}).get("name", "Unknown")
        group_type = args.get("input", {}).get("type", "group")
        return f"Create a new group: {name} ({group_type})"
    
    elif tool_name == "update_group":
        return f"Update group {args.get('group_id', 'unknown')}"
    
    elif tool_name == "delete_group":
        return f"Delete group {args.get('group_id', 'unknown')}"
    
    # Group membership actions
    elif tool_name == "add_company_to_group":
        return f"Add company to group"
    
    elif tool_name == "remove_company_from_group":
        return f"Remove company from group"
    
    elif tool_name == "add_person_to_group":
        return f"Add person to group"
    
    elif tool_name == "remove_person_from_group":
        return f"Remove person from group"
    
    # Default fallback
    return f"Execute {tool_name}"


def _validate_task_args(task: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate arguments for a single task.
    
    Performs validation checks:
    1. Task has 'tool' and 'args' fields
    2. Args is a dictionary
    3. XOR constraint for create_interaction (personId XOR companyId)
    4. Update operations have required 'id' field
    5. Create operations have required fields (workspace_id, etc.)
    
    Args:
        task: Task dictionary to validate
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
        If valid, error_message is empty string
    """
    # Check basic structure
    if "tool" not in task:
        return False, "Task missing 'tool' field"
    
    if "args" not in task:
        return False, f"Task '{task['tool']}' missing 'args' field"
    
    tool_name = task["tool"]
    args = task["args"]
    
    if not isinstance(args, dict):
        return False, f"Task '{tool_name}' args must be a dictionary"
    
    # Validate create_interaction XOR constraint
    if tool_name == "create_interaction":
        person_id = args.get("person_id") or args.get("personId")
        company_id = args.get("company_id") or args.get("companyId")
        
        if person_id and company_id:
            return False, "create_interaction cannot have both person_id and company_id"
        
        if not person_id and not company_id:
            return False, "create_interaction must have either person_id or company_id"
    
    # Validate update operations have id
    update_tools = {
        "update_company", "update_person", "update_interaction", "update_group"
    }
    if tool_name in update_tools:
        # Check for id in args or in input sub-dict
        has_id = (
            "id" in args or
            "interaction_id" in args or
            "group_id" in args or
            ("input" in args and isinstance(args["input"], dict) and "id" in args["input"])
        )
        if not has_id:
            return False, f"{tool_name} requires an id field"
    
    # Validate create operations have required fields
    create_tools = {
        "create_company", "create_person", "create_interaction", "create_group"
    }
    if tool_name in create_tools:
        # Most create operations need workspace_id
        if tool_name == "create_interaction":
            if "workspace_id" not in args:
                return False, f"{tool_name} requires workspace_id"
        else:
            # For others, workspace_id is usually in input sub-dict
            if "input" in args:
                input_data = args["input"]
                if isinstance(input_data, dict):
                    if "workspaceId" not in input_data and "workspace_id" not in input_data:
                        return False, f"{tool_name} requires workspaceId in input"
    
    # All validations passed
    return True, ""


# ========================================
# Main Validator Node
# ========================================


async def validator_node(
    state: AgentState
) -> Dict[str, Any]:
    """
    Validate and potentially modify an execution plan.
    
    This is the validator node in the LangGraph pipeline. It sits between
    the planner and executor, performing safety checks and enforcing
    business rules before any tools are executed.
    
    The validator performs four main checks:
    
    A. User Confirmation Detection
       - Checks if user is confirming a pending_action
       - Converts confirmed pending_action into executable task
       - Clears pending_action from state
    
    B. Mutation Detection and Conversion
       - Identifies write operations (create, update, delete)
       - Converts mutations into pending_action for user review
       - Prevents accidental data modifications
    
    C. Argument Validation
       - Validates task structure (tool, args)
       - Enforces XOR constraints (e.g., personId XOR companyId)
       - Checks required fields for create/update operations
       - Rejects invalid plans with detailed error messages
    
    D. Reasoning Logging
       - Adds transparent reasoning steps to state
       - Helps users understand validation decisions
       - Useful for debugging and auditing
    
    Args:
        state: Current agent state with conversation context and plan
    
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
    """
    try:
        logger.info("Validating plan...")
        
        # Get the plan from state
        plan = state.plan
        if not plan:
            logger.warning("No plan in state for validator")
            return {"plan": {
                "decision_type": PlannerDecisionType.NONE.value,
                "tasks": [],
                "pending_action": None,
                "summary": "No plan generated.",
                "confidence": 0.0
            }}
        
        # Get the last user message for confirmation detection
        last_message = state.messages[-1].content if state.messages else ""
        
        # ========================================
        # A. Check for User Confirmation
        # ========================================
        
        if state.pending_action is not None:
            logger.debug("Pending action exists, checking for user confirmation")
            
            if _is_confirmation(last_message):
                logger.info("User confirmed pending action")
                
                # Convert pending_action to executable task
                pending = state.pending_action
                task = {
                    "tool": pending.action,
                    "args": pending.payload
                }
                
                # Create new plan with single task
                validated_plan = {
                    "decision_type": PlannerDecisionType.SEQUENTIAL.value,
                    "tasks": [task],
                    "pending_action": None,
                    "summary": f"Executing confirmed action: {pending.action}",
                    "confidence": plan.get("confidence", 0.9)
                }
                
                # Clear pending_action from state
                state.pending_action = None
                
                # Add reasoning
                state.add_reasoning(
                    f"Validator: User confirmed pending action '{pending.action}'"
                )
                state.add_reasoning("Validator: Converted to executable task")
                
                logger.info(f"Converted pending action to executable task: {pending.action}")
                
                return {"plan": validated_plan}
            else:
                logger.debug("User message is not a confirmation")
                # Let the planner handle the new request
                # But keep the pending_action in state for later
        
        # ========================================
        # B. Check for Mutating Tasks
        # ========================================
        
        decision_type = plan.get("decision_type", "NONE")
        
        # If plan already marked for confirmation, pass it through
        if decision_type == PlannerDecisionType.CONFIRMATION_REQUIRED.value:
            logger.debug("Plan already marked as CONFIRMATION_REQUIRED")
            state.add_reasoning("Validator: Plan requires confirmation")
            return {"plan": plan}
        
        # Check if plan contains mutations
        if _has_mutating_tasks(plan):
            logger.info("Plan contains mutating tasks, converting to pending confirmation")
            
            # Extract first mutation
            mutation_task = _get_first_mutation(plan)
            
            if mutation_task:
                tool_name = mutation_task["tool"]
                args = mutation_task["args"]
                
                # Generate human-readable description
                description = _generate_action_description(tool_name, args)
                
                # Create pending_action
                pending_action = {
                    "action_id": f"action_{state.conversation_id}_{len(state.messages)}",
                    "action": tool_name,
                    "payload": args,
                    "description": description,
                    "requires_confirmation": True
                }
                
                # Create modified plan
                validated_plan = {
                    "decision_type": PlannerDecisionType.CONFIRMATION_REQUIRED.value,
                    "tasks": [],  # Clear tasks to prevent execution without confirmation
                    "pending_action": pending_action,
                    "summary": f"Ready to execute after confirmation: {description}",
                    "confidence": plan.get("confidence", 0.8)
                }
                
                # Add reasoning
                state.add_reasoning(
                    f"Validator: Converting '{tool_name}' into pending confirmation"
                )
                state.add_reasoning(f"Validator: {description}")
                
                logger.info(
                    f"Converted mutation to pending_action: {tool_name} - {description}"
                )
                
                return {"plan": validated_plan}
        
        # ========================================
        # C. Validate Task Arguments
        # ========================================
        
        tasks = plan.get("tasks", [])
        validation_errors = []
        
        for i, task in enumerate(tasks):
            is_valid, error_message = _validate_task_args(task)
            
            if not is_valid:
                validation_errors.append(f"Task {i+1}: {error_message}")
                logger.warning(f"Validation failed for task {i+1}: {error_message}")
        
        # If validation errors found, reject the plan
        if validation_errors:
            logger.warning(f"Plan validation failed with {len(validation_errors)} errors")
            
            error_summary = "I need more details: " + "; ".join(validation_errors)
            
            # Create rejected plan
            validated_plan = {
                "decision_type": PlannerDecisionType.NONE.value,
                "tasks": [],
                "pending_action": None,
                "summary": error_summary,
                "confidence": 0.0
            }
            
            # Add reasoning
            state.add_reasoning("Validator: Plan validation failed")
            for error in validation_errors:
                state.add_reasoning(f"Validator: {error}")
            
            return {"plan": validated_plan}
        
        # ========================================
        # D. Plan is Valid - Pass Through
        # ========================================
        
        logger.info(f"Plan validated successfully with {len(tasks)} task(s)")
        
        # Add reasoning
        state.add_reasoning(
            f"Validator: Approved plan with {len(tasks)} task(s)"
        )
        
        if tasks:
            task_names = [t.get("tool", "unknown") for t in tasks]
            state.add_reasoning(f"Validator: Tasks approved: {', '.join(task_names)}")
        
        return {"plan": plan}
    
    except Exception as e:
        # Catch-all error handler - reject plan on any error
        logger.error(f"Error in validator_node: {e}", exc_info=True)
        
        # Add error reasoning
        state.add_reasoning(f"Validator: Error during validation: {str(e)}")
        
        # Return rejected plan
        return {"plan": {
            "decision_type": PlannerDecisionType.NONE.value,
            "tasks": [],
            "pending_action": None,
            "summary": f"Validation error: {str(e)}. Please try again.",
            "confidence": 0.0
        }}

