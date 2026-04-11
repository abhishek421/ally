"""Reminder tools for creating, reading, updating, and deleting reminders."""

import logging
from datetime import datetime as dt
from langchain_core.tools import tool

from src.tools.context_var import get_tool_context
from src.tools.base import EntityType, ChangeAction, DataChange

try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    GraphInterrupt = None

logger = logging.getLogger(__name__)


def normalize_duedate(duedate: str) -> str | None:
    """Normalize various date formats to ISO 8601 format."""
    logger.info(f"Normalizing duedate: {duedate}")

    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]

    for fmt in formats_to_try:
        try:
            parsed_date = dt.strptime(duedate, fmt)
            normalized = parsed_date.strftime("%Y-%m-%dT%H:%M:%S")
            logger.info(f"Normalized duedate to: {normalized}")
            return normalized
        except ValueError:
            continue

    if "T" in duedate and len(duedate) >= 16:
        normalized = duedate.split(".")[0]
        logger.info(f"Using duedate as-is (looks like ISO): {normalized}")
        return normalized

    logger.warning(f"Could not parse duedate format: {duedate}")
    return None


def format_reminder(reminder: dict) -> str:
    """Format a reminder dict for display."""
    title = reminder.get("title", "Unknown Reminder")
    id_str = reminder.get("id", "N/A")
    duedate = reminder.get("duedate", "N/A")

    lines = [f"⏰ **{title}** (ID: {id_str})"]
    lines.append(f"  Due: {duedate}")

    if reminder.get("timezone"):
        lines.append(f"  Timezone: {reminder['timezone']}")

    if reminder.get("recurring") and reminder["recurring"] != "NONE":
        lines.append(f"  Recurring: {reminder['recurring']}")

    visibility = reminder.get("reminderVisibility")
    if visibility:
        lines.append(f"  Visibility: {visibility}")

    links = []
    if reminder.get("peopleId"):
        links.append(f"Person: {reminder['peopleId']}")
    if reminder.get("companyId"):
        links.append(f"Company: {reminder['companyId']}")

    if links:
        lines.append(f"  Linked to: {', '.join(links)}")

    return "\n".join(lines)


def get_reminder_tools() -> list:
    """Get all reminder-related tools."""

    _LIST_QUERY = """
    query Reminders($workspaceId: String!, $input: ListRemindersInput) {
        reminders(workspaceId: $workspaceId, input: $input) {
            items {
                id title duedate timezone recurring
                reminderVisibility peopleId companyId createdAt
            }
            totalCount
        }
    }
    """

    async def _find_reminder_by_title(client, workspace_id: str, title_search: str) -> tuple[dict | None, list]:
        """Fetch reminders and find the best title match. Returns (matched, all_items)."""
        result = await client.query(_LIST_QUERY, {
            "workspaceId": workspace_id,
            "input": {"limit": 50},
        })
        items = result.get("reminders", {}).get("items", [])
        search_lower = title_search.lower()
        matched = next((r for r in items if search_lower in r.get("title", "").lower()), None)
        return matched, items

    @tool
    async def create_reminder(
        title: str,
        duedate: str,
        timezone: str = "UTC",
        recurring: str = "NONE",
        reminder_visibility: str = "PRIVATE",
        people_name: str | None = None,
        company_name: str | None = None,
    ) -> str:
        """Create a new reminder in the workspace.

        Args:
            title: Title of the reminder
            duedate: Due date and time in ISO format e.g. '2024-03-25T15:00:00'. Calculate from current date.
            timezone: Timezone (default: UTC)
            recurring: "NONE", "DAILY", "WEEKLY", "MONTHLY", or "YEARLY" (default: NONE)
            reminder_visibility: "PRIVATE", "WORKSPACE", or "PUBLIC" (default: PRIVATE)
            people_name: Optional name of a person to link the reminder to
            company_name: Optional name of a company to link the reminder to
        """
        normalized_duedate = normalize_duedate(duedate)
        if not normalized_duedate:
            return f"Error: Invalid date format '{duedate}'. Use ISO format like '2024-03-25T15:00:00'."

        context = get_tool_context()
        client = context.get_client()

        try:
            people_id: str | None = None
            company_id: str | None = None

            # Resolve person name → ID
            if people_name:
                res = await client.query("""
                query GetWorkspacePeople($workspaceId: ID!, $search: String, $limit: Int) {
                    getWorkspacePeople(workspaceId: $workspaceId, search: $search, limit: $limit) {
                        data { id firstName lastName }
                    }
                }
                """, {"workspaceId": context.workspace_id, "search": people_name, "limit": 5})
                people = res.get("getWorkspacePeople", {}).get("data", [])
                if not people:
                    return f"No person found matching '{people_name}'."
                people_id = people[0]["id"]

            # Resolve company name → ID
            if company_name:
                res = await client.query("""
                query GetWorkspaceCompany($workspaceId: ID!, $search: String, $limit: Int) {
                    getWorkspaceCompany(workspaceId: $workspaceId, search: $search, limit: $limit) {
                        data { id name }
                    }
                }
                """, {"workspaceId": context.workspace_id, "search": company_name, "limit": 5})
                companies = res.get("getWorkspaceCompany", {}).get("data", [])
                if not companies:
                    return f"No company found matching '{company_name}'."
                company_id = companies[0]["id"]

            mutation = """
            mutation CreateReminder($input: CreateReminderInput!, $workspaceId: String!) {
                createReminder(input: $input, workspaceId: $workspaceId) {
                    id title duedate timezone recurring reminderVisibility
                    peopleId companyId createdAt updatedAt
                }
            }
            """
            input_data: dict = {
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

            result = await client.mutate(mutation, {
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            reminder = result.get("createReminder", {})

            change = DataChange(
                entity_type=EntityType.REMINDER,
                action=ChangeAction.CREATED,
                entity_id=reminder.get("id"),
            )
            return f"✅ Reminder created successfully!\n\n{format_reminder(reminder)}{change.to_marker()}"
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error creating reminder: {type(e).__name__}: {e}")
            return f"Error creating reminder: {str(e)}"
        finally:
            await client.close()

    async def list_reminders(
        entity_name: str | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> str:
        """List reminders in the workspace, optionally filtered by a linked person or company name.

        Args:
            entity_name: Optional name of a person or company to filter reminders by
            entity_type: "PEOPLE" or "COMPANY" — required if entity_name is provided
            limit: Maximum number of reminders to return (default: 10)
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            # If filtering by entity, resolve the entity ID first
            entity_id: str | None = None
            entity_filter_key: str | None = None

            if entity_name and entity_type:
                entity_type_upper = entity_type.upper()
                if entity_type_upper in ("PEOPLE", "PERSON"):
                    search_query = """
                    query GetWorkspacePeople($workspaceId: ID!, $search: String, $limit: Int) {
                        getWorkspacePeople(workspaceId: $workspaceId, search: $search, limit: $limit) {
                            data { id firstName lastName }
                        }
                    }
                    """
                    res = await client.query(search_query, {
                        "workspaceId": context.workspace_id,
                        "search": entity_name,
                        "limit": 5,
                    })
                    entities = res.get("getWorkspacePeople", {}).get("data", [])
                    if not entities:
                        return f"No person found matching '{entity_name}'."
                    entity_id = entities[0]["id"]
                    entity_filter_key = "peopleId"
                elif entity_type_upper == "COMPANY":
                    search_query = """
                    query GetWorkspaceCompany($workspaceId: ID!, $search: String, $limit: Int) {
                        getWorkspaceCompany(workspaceId: $workspaceId, search: $search, limit: $limit) {
                            data { id name }
                        }
                    }
                    """
                    res = await client.query(search_query, {
                        "workspaceId": context.workspace_id,
                        "search": entity_name,
                        "limit": 5,
                    })
                    entities = res.get("getWorkspaceCompany", {}).get("data", [])
                    if not entities:
                        return f"No company found matching '{entity_name}'."
                    entity_id = entities[0]["id"]
                    entity_filter_key = "companyId"

            input_data: dict = {"limit": limit}
            if entity_id and entity_filter_key:
                input_data[entity_filter_key] = entity_id

            result = await client.query(_LIST_QUERY, {
                "workspaceId": context.workspace_id,
                "input": input_data,
            })

            reminders_data = result.get("reminders", {})
            items = reminders_data.get("items", [])
            total = reminders_data.get("totalCount", 0)

            if not items:
                return "No reminders found."

            lines = [f"Found {total} reminder(s):\n"]
            for reminder in items:
                lines.append(format_reminder(reminder))
                lines.append("")
            return "\n".join(lines)

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error listing reminders: {type(e).__name__}: {e}")
            return f"Error listing reminders: {str(e)}"
        finally:
            await client.close()

    async def get_reminder(title_search: str) -> str:
        """Get a reminder by searching its title.

        Args:
            title_search: Part of the reminder title to search for
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            matched, all_items = await _find_reminder_by_title(client, context.workspace_id, title_search)

            if not matched:
                if not all_items:
                    return "No reminders found in your workspace."
                previews = "\n".join(f"- {r['title']}" for r in all_items[:10])
                return f"No reminder found matching '{title_search}'.\nExisting reminders:\n{previews}"

            # Fetch full details
            query = """
            query Reminder($id: String!, $workspaceId: String!) {
                reminder(id: $id, workspaceId: $workspaceId) {
                    id title duedate timezone recurring reminderVisibility
                    peopleId companyId createdAt updatedAt
                }
            }
            """
            result = await client.query(query, {"id": matched["id"], "workspaceId": context.workspace_id})
            reminder = result.get("reminder")
            if not reminder:
                return f"Reminder '{title_search}' not found."
            return format_reminder(reminder)

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error getting reminder: {type(e).__name__}: {e}")
            return f"Error getting reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_reminder(
        title_search: str,
        title: str | None = None,
        duedate: str | None = None,
        timezone: str | None = None,
        recurring: str | None = None,
        reminder_visibility: str | None = None,
        people_id: str | None = None,
        company_id: str | None = None,
    ) -> str:
        """Update an existing reminder by searching its title.

        Args:
            title_search: Part of the current reminder title to find it
            title: New title (optional)
            duedate: New due date in ISO format (optional)
            timezone: New timezone (optional)
            recurring: New recurring pattern - "NONE", "DAILY", "WEEKLY", "MONTHLY", "YEARLY" (optional)
            reminder_visibility: New visibility - "PRIVATE", "WORKSPACE", "PUBLIC" (optional)
            people_id: New person ID to link to (optional)
            company_id: New company ID to link to (optional)
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            matched, all_items = await _find_reminder_by_title(client, context.workspace_id, title_search)

            if not matched:
                if not all_items:
                    return "No reminders found in your workspace."
                previews = "\n".join(f"- {r['title']}" for r in all_items[:10])
                return f"No reminder found matching '{title_search}'.\nExisting reminders:\n{previews}"

            reminder_id = matched["id"]

            update_input: dict = {}
            if title is not None:
                update_input["title"] = title
            if duedate is not None:
                normalized_duedate = normalize_duedate(duedate)
                if not normalized_duedate:
                    return f"Error: Invalid date format '{duedate}'. Use ISO format like '2024-03-25T15:00:00'."
                update_input["duedate"] = normalized_duedate
            if timezone is not None:
                update_input["timezone"] = timezone
            if recurring is not None:
                update_input["recurring"] = recurring
            if reminder_visibility is not None:
                update_input["reminderVisibility"] = reminder_visibility
            if people_id is not None:
                update_input["peopleId"] = people_id
            if company_id is not None:
                update_input["companyId"] = company_id

            if not update_input:
                return "No changes specified. Please provide at least one field to update."

            mutation = """
            mutation UpdateReminder($id: String!, $input: UpdateReminderInput!, $workspaceId: String!) {
                updateReminder(id: $id, input: $input, workspaceId: $workspaceId) {
                    id title duedate timezone recurring reminderVisibility
                    peopleId companyId updatedAt
                }
            }
            """
            result = await client.mutate(mutation, {
                "id": reminder_id,
                "input": update_input,
                "workspaceId": context.workspace_id,
            })

            updated = result.get("updateReminder", {})
            change = DataChange(
                entity_type=EntityType.REMINDER,
                action=ChangeAction.UPDATED,
                entity_id=reminder_id,
            )
            return f"✅ Reminder updated successfully!\n\n{format_reminder(updated)}{change.to_marker()}"

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating reminder: {type(e).__name__}: {e}")
            return f"Error updating reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_reminder(title_search: str) -> str:
        """Delete a reminder by searching its title.

        Args:
            title_search: Part of the reminder title to find which one to delete
        """
        context = get_tool_context()
        client = context.get_client()

        try:
            matched, all_items = await _find_reminder_by_title(client, context.workspace_id, title_search)

            if not matched:
                if not all_items:
                    return "No reminders found in your workspace."
                previews = "\n".join(f"- {r['title']}" for r in all_items[:10])
                return f"No reminder found matching '{title_search}'.\nExisting reminders:\n{previews}"

            reminder_id = matched["id"]
            reminder_title = matched.get("title", title_search)

            mutation = """
            mutation DeleteReminder($id: String!, $workspaceId: String!) {
                deleteReminder(id: $id, workspaceId: $workspaceId)
            }
            """
            await client.mutate(mutation, {
                "id": reminder_id,
                "workspaceId": context.workspace_id,
            })

            change = DataChange(
                entity_type=EntityType.REMINDER,
                action=ChangeAction.DELETED,
                entity_id=reminder_id,
            )
            return f"✅ Reminder '{reminder_title}' deleted successfully.{change.to_marker()}"

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error deleting reminder: {type(e).__name__}: {e}")
            return f"Error deleting reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_reminders(
        entity_name: str | None = None,
        entity_type: str | None = None,
        search_title: str | None = None,
        limit: int = 10,
    ) -> str:
        """Fetch reminders, with optional filtering by linked entity or title search.

        Replaces both list_reminders and get_reminder.

        Args:
            entity_name: Optional person or company name to filter by.
            entity_type: "PEOPLE" or "COMPANY" — required if entity_name is given.
            search_title: Optional title snippet to find a specific reminder.
            limit: Max reminders to return (default: 10).
        """
        if search_title and not entity_name:
            # Title-based lookup — delegate to helper
            context = get_tool_context()
            client = context.get_client()
            try:
                matched, all_items = await _find_reminder_by_title(client, context.workspace_id, search_title)
                if not matched:
                    if not all_items:
                        return "No reminders found in your workspace."
                    previews = "\n".join(f"- {r['title']}" for r in all_items[:10])
                    return f"No reminder found matching '{search_title}'.\nExisting reminders:\n{previews}"
                return format_reminder(matched)
            finally:
                await client.close()

        # Entity-filtered list (or unfiltered)
        return await list_reminders(entity_name=entity_name, entity_type=entity_type, limit=limit)

    @tool
    async def get_upcoming_reminders(limit: int = 10) -> str:
        """Get upcoming reminders sorted by due date (soonest first).

        Use when the user asks "what do I have coming up?", "what's due this week?",
        or "show me my upcoming reminders".

        Args:
            limit: Maximum number of reminders to return (default: 10, max: 50).
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query UpcomingReminders($workspaceId: String!, $limit: Int) {
            upcomingReminders(workspaceId: $workspaceId, limit: $limit) {
                items {
                    id title duedate timezone recurring
                    reminderVisibility peopleId companyId createdAt
                }
                totalCount
            }
        }
        """
        variables = {
            "workspaceId": context.workspace_id,
            "limit": min(limit, 50),
        }

        try:
            result = await client.execute(query, variables)
            data = result.get("data", {}).get("upcomingReminders", {})
            items = data.get("items", [])
            total = data.get("totalCount", 0)

            if not items:
                return "No upcoming reminders found."

            lines = [f"Upcoming reminders ({total} total, showing {len(items)}):"]
            lines.append("")
            for reminder in items:
                lines.append(format_reminder(reminder))
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error fetching upcoming reminders: {e}")
            return f"Error fetching upcoming reminders: {str(e)}"
        finally:
            await client.close()

    return [
        create_reminder,
        get_reminders,
        update_reminder,
        delete_reminder,
        get_upcoming_reminders,
    ]
