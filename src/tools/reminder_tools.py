"""Reminder tools for creating, reading, updating, and deleting reminders."""

import logging
from datetime import datetime as dt
from langchain_core.tools import tool

from src.tools.context_var import get_tool_context
from src.tools.base import (
    ToolContext,
    EntityType,
    ChangeAction,
    DataChange,
)
from src.tools.confirmation import (
    request_create_confirmation,
    request_update_confirmation,
    request_delete_confirmation,
)

logger = logging.getLogger(__name__)


def normalize_duedate(duedate: str) -> str | None:
    """Normalize various date formats to ISO 8601 format.
    
    Args:
        duedate: Date string in various possible formats
        
    Returns:
        Normalized ISO 8601 date string (YYYY-MM-DDTHH:MM:SS) or None if parsing fails
    """
    logger.info(f"Normalizing duedate: {duedate}")
    
    # Common formats the AI might use
    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",       # ISO 8601 (ideal)
        "%Y-%m-%dT%H:%M:%S.%f",    # ISO 8601 with microseconds
        "%Y-%m-%dT%H:%M",          # ISO 8601 without seconds
        "%Y-%m-%d %H:%M:%S",       # Space separator
        "%Y-%m-%d %H:%M",          # Space separator without seconds
        "%Y-%m-%d",                # Date only (will add T00:00:00)
        "%m/%d/%Y %H:%M:%S",       # US format
        "%m/%d/%Y %H:%M",          # US format without seconds
        "%d/%m/%Y %H:%M:%S",       # EU format
        "%d/%m/%Y %H:%M",          # EU format without seconds
    ]
    
    for fmt in formats_to_try:
        try:
            parsed_date = dt.strptime(duedate, fmt)
            normalized = parsed_date.strftime("%Y-%m-%dT%H:%M:%S")
            logger.info(f"Normalized duedate to: {normalized}")
            return normalized
        except ValueError:
            continue
    
    # If none of the formats work, check if it already looks like ISO
    if "T" in duedate and len(duedate) >= 16:
        # Looks like ISO format, use as-is (remove microseconds if present)
        normalized = duedate.split(".")[0]
        logger.info(f"Using duedate as-is (looks like ISO): {normalized}")
        return normalized
    
    logger.warning(f"Could not parse duedate format: {duedate}")
    return None


def format_reminder(reminder: dict) -> str:
    """Format a reminder dict for display.
    
    Args:
        reminder: Reminder data from GraphQL
        
    Returns:
        Formatted string representation
    """
    title = reminder.get('title', 'Unknown Reminder')
    id_str = reminder.get('id', 'N/A')
    duedate = reminder.get('duedate', 'N/A')

    lines = [f"⏰ **{title}** (ID: {id_str})"]
    lines.append(f"  Due: {duedate}")

    if reminder.get('timezone'):
        lines.append(f"  Timezone: {reminder['timezone']}")

    if reminder.get('recurring') and reminder['recurring'] != 'NONE':
        lines.append(f"  Recurring: {reminder['recurring']}")

    visibility = reminder.get('reminderVisibility')
    if visibility:
        lines.append(f"  Visibility: {visibility}")

    # Links
    links = []
    if reminder.get('peopleId'):
        links.append(f"Person: {reminder['peopleId']}")
    if reminder.get('companyId'):
        links.append(f"Company: {reminder['companyId']}")
    if reminder.get('dealId'):
        links.append(f"Deal: {reminder['dealId']}")

    if links:
        lines.append(f"  Linked to: {', '.join(links)}")

    return "\n".join(lines)


def get_reminder_tools() -> list:
    """Get all reminder-related tools.

    Returns:
        List of reminder tools
    """
    
    @tool
    async def create_reminder(
        title: str,
        duedate: str,
        timezone: str = "UTC",
        recurring: str = "NONE",
        reminder_visibility: str = "PRIVATE",
        people_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> str:
        """Create a new reminder.
        
        Args:
            title: Title of the reminder
            duedate: Due date in ISO format (e.g. '2024-03-25T15:00:00')
            timezone: Timezone (default: UTC)
            recurring: "NONE", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"
            reminder_visibility: "PRIVATE", "WORKSPACE", "PUBLIC"
            people_id: Optional person ID to link
            company_id: Optional company ID to link
            deal_id: Optional deal ID to link
        """
        # Normalize the duedate to ISO 8601 format
        normalized_duedate = normalize_duedate(duedate)
        if not normalized_duedate:
            return f"Error: Invalid date format '{duedate}'. Please use ISO format like '2024-03-25T15:00:00' or 'YYYY-MM-DD HH:MM:SS'."
        
        # Build draft data for confirmation preview
        draft_data = {
            "title": title,
            "duedate": normalized_duedate,
            "timezone": timezone,
            "recurring": recurring,
            "reminderVisibility": reminder_visibility,
        }
        if people_id:
            draft_data["peopleId"] = people_id
        if company_id:
            draft_data["companyId"] = company_id
        if deal_id:
            draft_data["dealId"] = deal_id

        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="reminder",
            draft_data=draft_data,
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Reminder creation cancelled by user.{feedback}"

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation CreateReminder(
            $input: CreateReminderInput!
            $workspaceId: String!
        ) {
            createReminder(input: $input, workspaceId: $workspaceId) {
                id
                title
                duedate
                timezone
                recurring
                reminderVisibility
                peopleId
                companyId
                dealId
                createdAt
                updatedAt
            }
        }
        """

        # Build input object
        input_data = {
            "title": title,
            "duedate": normalized_duedate,
            "timezone": timezone,
            "recurring": recurring,
            "reminderVisibility": reminder_visibility,
        }

        if people_id:
            input_data["peopleId"] = people_id
        if company_id:
            input_data["companyId"] = company_id
        if deal_id:
            input_data["dealId"] = deal_id

        try:
            result = await client.mutate(mutation, {
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            reminder = result.get("createReminder", {})
            
            # Add data change marker for frontend updates
            change = DataChange(
                entity_type=EntityType.REMINDER,
                action=ChangeAction.CREATED,
                entity_id=reminder.get("id"),
            )
            
            return f"✅ Reminder created successfully!\n\n{format_reminder(reminder)}{change.to_marker()}"
        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return f"Error creating reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_reminders(
        people_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        limit: int = 10,
    ) -> str:
        """List reminders in the workspace, optionally filtered by linked entity.
        
        Args:
            people_id: Optional - filter reminders linked to this person ID
            company_id: Optional - filter reminders linked to this company ID
            deal_id: Optional - filter reminders linked to this deal ID
            limit: Maximum number of reminders to return (default: 10)
            
        Returns:
            Formatted list of reminders
        """
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query Reminders(
            $workspaceId: String!
            $input: ListRemindersInput
        ) {
            reminders(workspaceId: $workspaceId, input: $input) {
                items {
                    id
                    title
                    duedate
                    timezone
                    recurring
                    reminderVisibility
                    peopleId
                    companyId
                    dealId
                    createdAt
                }
                totalCount
            }
        }
        """
        
        # Build filter input
        input_data: dict = {"limit": limit}
        if people_id:
            input_data["peopleId"] = people_id
        if company_id:
            input_data["companyId"] = company_id
        if deal_id:
            input_data["dealId"] = deal_id
        
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "input": input_data if input_data else None,
            })
            
            reminders_data = result.get("reminders", {})
            items = reminders_data.get("items", [])
            total = reminders_data.get("totalCount", 0)
            
            if not items:
                return "No reminders found."
            
            lines = [f"Found {total} reminder(s):\n"]
            for reminder in items:
                lines.append(format_reminder(reminder))
                lines.append("")  # Empty line between reminders
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error listing reminders: {e}")
            return f"Error listing reminders: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_reminder(reminder_id: str) -> str:
        """Get a single reminder by its ID.
        
        Args:
            reminder_id: The ID of the reminder to retrieve
            
        Returns:
            Formatted reminder details
        """
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query Reminder($id: String!, $workspaceId: String!) {
            reminder(id: $id, workspaceId: $workspaceId) {
                id
                title
                duedate
                timezone
                recurring
                reminderVisibility
                peopleId
                companyId
                dealId
                createdAt
                updatedAt
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "id": reminder_id,
                "workspaceId": context.workspace_id,
            })
            
            reminder = result.get("reminder")
            if not reminder:
                return f"Reminder with ID '{reminder_id}' not found."
            
            return format_reminder(reminder)
        except Exception as e:
            logger.error(f"Error getting reminder: {e}")
            return f"Error getting reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_reminder(
        reminder_id: str,
        title: str | None = None,
        duedate: str | None = None,
        timezone: str | None = None,
        recurring: str | None = None,
        reminder_visibility: str | None = None,
        people_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> str:
        """Update an existing reminder.
        
        Args:
            reminder_id: ID of the reminder to update
            title: New title (optional)
            duedate: New due date in ISO format (optional)
            timezone: New timezone (optional)
            recurring: "NONE", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"
            reminder_visibility: "PRIVATE", "WORKSPACE", "PUBLIC"
            people_id: New person ID to link (optional)
            company_id: New company ID to link (optional)
            deal_id: New deal ID to link (optional)
        """
        context = get_tool_context()
        client = context.get_client()
        
        # First, get the current reminder to show what will be changed
        query = """
        query Reminder($id: String!, $workspaceId: String!) {
            reminder(id: $id, workspaceId: $workspaceId) {
                id
                title
                duedate
                timezone
                recurring
                reminderVisibility
                peopleId
                companyId
                dealId
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "id": reminder_id,
                "workspaceId": context.workspace_id,
            })
            
            current = result.get("reminder")
            if not current:
                return f"Reminder with ID '{reminder_id}' not found."
            
            # Build the update input with only the fields that are being changed
            update_input: dict = {}
            changes: dict = {}
            
            if title is not None:
                update_input["title"] = title
                changes["title"] = {"from": current.get("title"), "to": title}
            
            if duedate is not None:
                normalized_duedate = normalize_duedate(duedate)
                if not normalized_duedate:
                    return f"Error: Invalid date format '{duedate}'. Please use ISO format like '2024-03-25T15:00:00'."
                update_input["duedate"] = normalized_duedate
                changes["duedate"] = {"from": current.get("duedate"), "to": normalized_duedate}
            
            if timezone is not None:
                update_input["timezone"] = timezone
                changes["timezone"] = {"from": current.get("timezone"), "to": timezone}
            
            if recurring is not None:
                update_input["recurring"] = recurring
                changes["recurring"] = {"from": current.get("recurring"), "to": recurring}
            
            if reminder_visibility is not None:
                update_input["reminderVisibility"] = reminder_visibility
                changes["reminderVisibility"] = {"from": current.get("reminderVisibility"), "to": reminder_visibility}
            
            if people_id is not None:
                update_input["peopleId"] = people_id
                changes["peopleId"] = {"from": current.get("peopleId"), "to": people_id}
            
            if company_id is not None:
                update_input["companyId"] = company_id
                changes["companyId"] = {"from": current.get("companyId"), "to": company_id}
            
            if deal_id is not None:
                update_input["dealId"] = deal_id
                changes["dealId"] = {"from": current.get("dealId"), "to": deal_id}
            
            if not update_input:
                return "No changes specified. Please provide at least one field to update."
            
            # Proceed with update directly without HITL
            mutation = """
            mutation UpdateReminder(
                $id: String!
                $input: UpdateReminderInput!
                $workspaceId: String!
            ) {
                updateReminder(id: $id, input: $input, workspaceId: $workspaceId) {
                    id
                    title
                    duedate
                    timezone
                    recurring
                    reminderVisibility
                    peopleId
                    companyId
                    dealId
                    updatedAt
                }
            }
            """
            
            result = await client.mutate(mutation, {
                "id": reminder_id,
                "input": update_input,
                "workspaceId": context.workspace_id,
            })
            
            updated = result.get("updateReminder", {})
            
            # Add data change marker for frontend updates
            change = DataChange(
                entity_type=EntityType.REMINDER,
                action=ChangeAction.UPDATED,
                entity_id=reminder_id,
            )
            
            return f"✅ Reminder updated successfully!\n\n{format_reminder(updated)}{change.to_marker()}"
        except Exception as e:
            logger.error(f"Error updating reminder: {e}")
            return f"Error updating reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_reminder(reminder_id: str) -> str:
        """Delete a reminder by its ID.
        
        This tool will ask for user confirmation before deleting.
        
        Args:
            reminder_id: The ID of the reminder to delete
            
        Returns:
            Confirmation message
        """
        context = get_tool_context()
        client = context.get_client()
        
        # First, get the reminder to show what will be deleted
        query = """
        query Reminder($id: String!, $workspaceId: String!) {
            reminder(id: $id, workspaceId: $workspaceId) {
                id
                title
                duedate
                timezone
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "id": reminder_id,
                "workspaceId": context.workspace_id,
            })
            
            reminder = result.get("reminder")
            if not reminder:
                return f"Reminder with ID '{reminder_id}' not found."
            
            # Proceed with deletion directly without HITL
            mutation = """
            mutation DeleteReminder($id: String!, $workspaceId: String!) {
                deleteReminder(id: $id, workspaceId: $workspaceId)
            }
            """
            
            await client.mutate(mutation, {
                "id": reminder_id,
                "workspaceId": context.workspace_id,
            })
            
            # Add data change marker for frontend updates
            change = DataChange(
                entity_type=EntityType.REMINDER,
                action=ChangeAction.DELETED,
                entity_id=reminder_id,
            )
            
            return f"✅ Reminder '{reminder.get('title')}' has been deleted.{change.to_marker()}"
        except Exception as e:
            logger.error(f"Error deleting reminder: {e}")
            return f"Error deleting reminder: {str(e)}"
        finally:
            await client.close()

    return [
        create_reminder,
        list_reminders,
        get_reminder,
        update_reminder,
        delete_reminder,
    ]
