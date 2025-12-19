"""Human-in-the-loop confirmation utilities for Ally agent."""

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Optional

from langgraph.types import interrupt

logger = logging.getLogger(__name__)


class ConfirmationType(str, Enum):
    """Types of confirmation requests."""
    CONFIRM_ACTION = "confirm_action"      # Simple yes/no confirmation
    SELECT_ONE = "select_one"              # Radio buttons - select one option
    SELECT_MANY = "select_many"            # Checkboxes - select multiple options
    CONFIRM_WITH_EDIT = "confirm_with_edit"  # Confirm with optional modifications


@dataclass
class ConfirmationOption:
    """An option for SELECT_ONE or SELECT_MANY confirmations."""
    id: str
    label: str
    description: Optional[str] = None
    confidence: Optional[str] = None  # "high", "medium", "low"
    metadata: Optional[dict] = None  # Additional data for display


@dataclass
class ConfirmationRequest:
    """Request for user confirmation before proceeding with an action.
    
    Attributes:
        type: The type of confirmation needed
        title: Short title for the confirmation dialog
        message: Detailed message explaining what needs confirmation
        options: List of options for SELECT_ONE/SELECT_MANY types
        draft_data: Preview data for create/update confirmations
        allow_cancel_feedback: Whether to show feedback input on cancel
        entity_type: Type of entity being operated on (for UI hints)
        action_label: Custom label for the confirm button
    """
    type: ConfirmationType
    title: str
    message: str
    options: Optional[list[ConfirmationOption]] = None
    draft_data: Optional[dict] = None
    allow_cancel_feedback: bool = True
    entity_type: Optional[str] = None  # "person", "company", "group"
    action_label: Optional[str] = None  # Custom confirm button label

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "confirmation_type": self.type.value,
            "title": self.title,
            "message": self.message,
            "allow_cancel_feedback": self.allow_cancel_feedback,
        }
        
        if self.options:
            result["options"] = [
                {
                    "id": opt.id,
                    "label": opt.label,
                    "description": opt.description,
                    "confidence": opt.confidence,
                    "metadata": opt.metadata,
                }
                for opt in self.options
            ]
        
        if self.draft_data:
            result["draft_data"] = self.draft_data
        
        if self.entity_type:
            result["entity_type"] = self.entity_type
        
        if self.action_label:
            result["action_label"] = self.action_label
        
        return result


@dataclass
class ConfirmationResponse:
    """Response from user after confirmation request.
    
    Attributes:
        confirmed: Whether the user confirmed the action
        selected_id: Selected option ID for SELECT_ONE
        selected_ids: Selected option IDs for SELECT_MANY
        feedback: Optional feedback message from user (on cancel)
        modified_data: Modified data for CONFIRM_WITH_EDIT
    """
    confirmed: bool = False
    selected_id: Optional[str] = None
    selected_ids: Optional[list[str]] = None
    feedback: Optional[str] = None
    modified_data: Optional[dict] = None


def request_confirmation(request: ConfirmationRequest) -> ConfirmationResponse:
    """Pause agent execution and request user confirmation.
    
    This function uses LangGraph's interrupt() to pause the agent,
    save state to the checkpointer, and wait for user input.
    
    Args:
        request: The confirmation request with details about what to confirm
        
    Returns:
        ConfirmationResponse with the user's decision
        
    Example:
        >>> response = request_confirmation(ConfirmationRequest(
        ...     type=ConfirmationType.CONFIRM_ACTION,
        ...     title="Create Company",
        ...     message="I'll create Acme Corp with the following details:",
        ...     draft_data={"name": "Acme Corp", "email": "info@acme.com"},
        ... ))
        >>> if response.confirmed:
        ...     # proceed with creation
        ... else:
        ...     # handle cancellation
    """
    logger.info(f"Requesting confirmation: {request.title}")
    
    # Interrupt the agent and wait for user response
    # The interrupt value will be sent to the frontend as confirmation_required event
    # When the user responds, the agent will resume with the response value
    response_data = interrupt(request.to_dict())
    
    # Parse the response from the user
    if isinstance(response_data, dict):
        return ConfirmationResponse(
            confirmed=response_data.get("confirmed", False),
            selected_id=response_data.get("selected_id"),
            selected_ids=response_data.get("selected_ids"),
            feedback=response_data.get("feedback"),
            modified_data=response_data.get("modified_data"),
        )
    
    # If response is not a dict, treat as cancellation
    logger.warning(f"Unexpected confirmation response type: {type(response_data)}")
    return ConfirmationResponse(confirmed=False)


def request_entity_selection(
    entity_type: str,
    name_query: str,
    matches: list[tuple[dict, float]],
    name_key: str = "name",
) -> ConfirmationResponse:
    """Request user to select from multiple matching entities.
    
    Convenience function for disambiguation when multiple entities match a name.
    
    Args:
        entity_type: Type of entity ("person", "company", "group")
        name_query: The original name query from user
        matches: List of (entity_dict, score) tuples from fuzzy matching
        name_key: Key to use for the entity name (or "fullName" for people)
        
    Returns:
        ConfirmationResponse with selected_id set if user confirmed
    """
    options = []
    for entity, score in matches:
        if name_key == "fullName":
            label = f"{entity.get('firstName', '')} {entity.get('lastName', '')}".strip()
        else:
            label = entity.get(name_key, "Unknown")
        
        # Build description from available fields
        description_parts = []
        if entity.get("jobTitle"):
            description_parts.append(entity["jobTitle"])
        if entity.get("description"):
            desc = entity["description"][:50]
            if len(entity["description"]) > 50:
                desc += "..."
            description_parts.append(desc)
        
        options.append(ConfirmationOption(
            id=entity.get("id", ""),
            label=label,
            description=" • ".join(description_parts) if description_parts else None,
            confidence="high" if score >= 85 else "medium" if score >= 70 else "low",
            metadata={"score": score},
        ))
    
    entity_label = entity_type.replace("_", " ").title()
    
    return request_confirmation(ConfirmationRequest(
        type=ConfirmationType.SELECT_ONE,
        title=f"Multiple {entity_label}s Found",
        message=f"Which '{name_query}' did you mean?",
        options=options,
        entity_type=entity_type,
        action_label="Select",
    ))


def request_create_confirmation(
    entity_type: str,
    draft_data: dict,
    message: Optional[str] = None,
) -> ConfirmationResponse:
    """Request confirmation before creating an entity.
    
    Args:
        entity_type: Type of entity ("person", "company", "group")
        draft_data: Dictionary with the entity data to be created
        message: Optional custom message
        
    Returns:
        ConfirmationResponse with confirmed=True if user approved
    """
    entity_label = entity_type.replace("_", " ").title()
    
    return request_confirmation(ConfirmationRequest(
        type=ConfirmationType.CONFIRM_ACTION,
        title=f"Create {entity_label}",
        message=message or f"I'll create the following {entity_type}:",
        draft_data=draft_data,
        entity_type=entity_type,
        action_label=f"Create {entity_label}",
    ))


def request_update_confirmation(
    entity_type: str,
    entity_name: str,
    changes: dict,
    message: Optional[str] = None,
) -> ConfirmationResponse:
    """Request confirmation before updating an entity.
    
    Args:
        entity_type: Type of entity ("person", "company", "group")
        entity_name: Name of the entity being updated
        changes: Dictionary showing the changes (field -> new_value)
        message: Optional custom message
        
    Returns:
        ConfirmationResponse with confirmed=True if user approved
    """
    entity_label = entity_type.replace("_", " ").title()
    
    return request_confirmation(ConfirmationRequest(
        type=ConfirmationType.CONFIRM_ACTION,
        title=f"Update {entity_label}",
        message=message or f"I'll update '{entity_name}' with the following changes:",
        draft_data=changes,
        entity_type=entity_type,
        action_label=f"Update {entity_label}",
    ))


def request_delete_confirmation(
    entity_type: str,
    entity_name: str,
    context: Optional[str] = None,
) -> ConfirmationResponse:
    """Request confirmation before a destructive action.
    
    Args:
        entity_type: Type of entity or action
        entity_name: Name of the entity being affected
        context: Additional context about the action
        
    Returns:
        ConfirmationResponse with confirmed=True if user approved
    """
    return request_confirmation(ConfirmationRequest(
        type=ConfirmationType.CONFIRM_ACTION,
        title=f"Confirm Removal",
        message=context or f"Are you sure you want to remove '{entity_name}'?",
        entity_type=entity_type,
        action_label="Remove",
        allow_cancel_feedback=True,
    ))


def request_column_update_confirmation(
    entity_type: str,
    entity_name: str,
    column_name: str,
    current_value: Optional[str],
    new_value: str,
    group_name: Optional[str] = None,
    current_value_color: Optional[str] = None,
    new_value_color: Optional[str] = None,
) -> ConfirmationResponse:
    """Request confirmation before updating a column value (e.g., status change).
    
    This is specifically designed for status/column value updates where we want
    to show a clear visual "old → new" transition.
    
    Args:
        entity_type: Type of entity ("person", "company")
        entity_name: Name of the entity being updated
        column_name: Human-readable column name (e.g., "Status")
        current_value: Current value label (or None if not set)
        new_value: New value label
        group_name: Name of the group context (optional)
        current_value_color: Color of the current value badge (optional)
        new_value_color: Color of the new value badge (optional)
        
    Returns:
        ConfirmationResponse with confirmed=True if user approved
    """
    logger.info(f"request_column_update_confirmation called: entity={entity_name}, column={column_name}, current={current_value}, new={new_value}")
    
    entity_label = entity_type.replace("_", " ").title()
    
    # Build the message
    if group_name:
        message = f"Change {column_name} for '{entity_name}' in {group_name}"
    else:
        message = f"Change {column_name} for '{entity_name}'"
    
    # Build draft_data with status change info
    draft_data = {
        "entity": entity_name,
        "column": column_name,
        "current_value": current_value or "(not set)",
        "new_value": new_value,
        "_is_status_change": True,  # Flag for frontend to render special UI
    }
    
    if group_name:
        draft_data["group_name"] = group_name
    
    if current_value_color:
        draft_data["current_value_color"] = current_value_color
    
    if new_value_color:
        draft_data["new_value_color"] = new_value_color
    
    return request_confirmation(ConfirmationRequest(
        type=ConfirmationType.CONFIRM_ACTION,
        title=f"Update {column_name}",
        message=message,
        draft_data=draft_data,
        entity_type=entity_type,
        action_label="Confirm Change",
        allow_cancel_feedback=True,
    ))

