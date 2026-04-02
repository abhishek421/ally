"""CREATE tools for creating companies, people, groups, and views."""

import logging
from typing import Optional

from langchain_core.tools import tool
from langgraph.errors import GraphInterrupt

from src.tools.context_var import get_tool_context
from src.tools.base import (
    ToolContext,
    format_company,
    format_person,
    format_group,
    DataChange,
    EntityType,
    ChangeAction,
)
from src.tools.reminder_tools import format_reminder
from src.tools.note_tools import format_note
from src.tools.confirmation import (
    request_create_confirmation,
    request_bulk_create_confirmation,
)

logger = logging.getLogger(__name__)


def get_create_tools() -> list:
    """Get all CREATE tools.

    Returns:
        List of tool functions
    """

    @tool
    async def create_company(
        name: str,
        description: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> str:
        """Create a new company. Shows confirmation preview. Use defaults for unspecified optional fields."""
        # Build draft data for confirmation preview
        draft_data = {"name": name, "_draft_id": "draft-0"}
        if description:
            draft_data["description"] = description
        if email:
            draft_data["email"] = email
        if phone:
            draft_data["phone"] = phone
        if website:
            draft_data["website"] = website
        if group_id:
            draft_data["group_id"] = group_id

        # Use bulk confirmation so a draft row appears in the table
        confirmation = request_bulk_create_confirmation(
            entities=[draft_data],
            entity_type="company",
            group_id=group_id,
        )

        if not confirmation.confirmed:
            return f"Company creation cancelled by user. [CANCELLED - stop here, do not retry or reattempt]"

        # Check if the single entity was accepted
        accepted_ids = confirmation.accepted_ids
        if accepted_ids is not None and "draft-0" not in accepted_ids:
            return f"Company creation cancelled by user. [CANCELLED - stop here, do not retry or reattempt]"

        # Apply any inline edits made during confirmation
        final = {**draft_data}
        final.pop("_draft_id", None)
        final.pop("group_id", None)
        if confirmation.edited_entities and "draft-0" in confirmation.edited_entities:
            final.update(confirmation.edited_entities["draft-0"])

        # Extract (possibly edited) values
        name = final.get("name", name)
        description = final.get("description", description)
        email = final.get("email", email)
        phone = final.get("phone", phone)
        website = final.get("website", website)

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation CreateCompany(
            $input: CreateCompanyInput!
            $groupId: ID
        ) {
            createCompany(input: $input, groupId: $groupId) {
                id
                name
                description
                emails { id value type isPrimary }
                phoneNumbers { id value type isPrimary }
                urls { id label value isPrimary }
            }
        }
        """

        # Build input object
        input_data = {
            "name": name,
            "workspaceId": context.workspace_id,
        }

        if description:
            input_data["description"] = description

        if email:
            input_data["emails"] = [{"value": email, "type": "work", "isPrimary": True}]

        if phone:
            input_data["phoneNumbers"] = [{"value": phone, "type": "work", "isPrimary": True}]

        if website:
            input_data["urls"] = [{"value": website, "label": "Website", "isPrimary": True}]
        
        try:
            result = await client.mutate(mutation, {
                "input": input_data,
                "groupId": group_id,
            })

            company = result.get("createCompany")
            
            if company:
                group_msg = f" and added to group" if group_id else ""
                result = f"Successfully created company{group_msg}:\n\n{format_company(company)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.CREATED,
                    entity_id=company.get("id"),
                    group_id=group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to create company - no data returned."
                
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error creating company: {e}")
            return f"Error creating company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def create_person(
        first_name: str,
        last_name: Optional[str] = None,
        job_title: Optional[str] = None,
        description: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> str:
        """Create a new contact/person. Shows confirmation preview. Use defaults for unspecified optional fields."""
        # Build draft data for confirmation preview
        draft_data = {"first_name": first_name, "_draft_id": "draft-0"}
        if last_name:
            draft_data["last_name"] = last_name
        if job_title:
            draft_data["job_title"] = job_title
        if description:
            draft_data["description"] = description
        if email:
            draft_data["email"] = email
        if phone:
            draft_data["phone"] = phone
        if group_id:
            draft_data["group_id"] = group_id

        # Use bulk confirmation so a draft row appears in the table
        confirmation = request_bulk_create_confirmation(
            entities=[draft_data],
            entity_type="person",
            group_id=group_id,
        )

        if not confirmation.confirmed:
            return f"Person creation cancelled by user. [CANCELLED - stop here, do not retry or reattempt]"

        # Check if the single entity was accepted
        accepted_ids = confirmation.accepted_ids
        if accepted_ids is not None and "draft-0" not in accepted_ids:
            return f"Person creation cancelled by user. [CANCELLED - stop here, do not retry or reattempt]"

        # Apply any inline edits made during confirmation
        final = {**draft_data}
        final.pop("_draft_id", None)
        final.pop("group_id", None)
        if confirmation.edited_entities and "draft-0" in confirmation.edited_entities:
            final.update(confirmation.edited_entities["draft-0"])

        # Extract (possibly edited) values
        first_name = final.get("first_name", first_name)
        last_name = final.get("last_name", last_name)
        job_title = final.get("job_title", job_title)
        description = final.get("description", description)
        email = final.get("email", email)
        phone = final.get("phone", phone)

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation CreatePerson(
            $input: CreatePeopleInput!
            $groupId: ID
        ) {
            createPerson(input: $input, groupId: $groupId) {
                id
                firstName
                lastName
                jobTitle
                description
                emails { id value type isPrimary }
                phoneNumbers { id value type isPrimary }
            }
        }
        """

        # Build input object
        input_data = {
            "firstName": first_name,
            "workspaceId": context.workspace_id,
        }

        if last_name:
            input_data["lastName"] = last_name

        if job_title:
            input_data["jobTitle"] = job_title

        if description:
            input_data["description"] = description

        if email:
            input_data["emails"] = [{"value": email, "type": "work", "isPrimary": True}]

        if phone:
            input_data["phoneNumbers"] = [{"value": phone, "type": "mobile", "isPrimary": True}]
        
        try:
            result = await client.mutate(mutation, {
                "input": input_data,
                "groupId": group_id,
            })

            person = result.get("createPerson")
            
            if person:
                group_msg = f" and added to group" if group_id else ""
                result = f"Successfully created person{group_msg}:\n\n{format_person(person)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.CREATED,
                    entity_id=person.get("id"),
                    group_id=group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to create person - no data returned."
                
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error creating person: {e}")
            return f"Error creating person: {str(e)}"
        finally:
            await client.close()

    @tool
    async def create_group(
        name: str,
        group_type: str = "PEOPLE",
        description: Optional[str] = None,
        emoji: str = "📁",
        is_private: bool = True,
    ) -> str:
        """Create a new group. Shows confirmation preview. Defaults: type=PEOPLE, is_private=true."""
        # Validate group type
        valid_types = ["PEOPLE", "COMPANY"]
        if group_type.upper() not in valid_types:
            return f"Invalid group type '{group_type}'. Must be one of: {', '.join(valid_types)}"
        
        # Build draft data for confirmation preview
        draft_data = {
            "name": name,
            "type": group_type.upper(),
            "is_private": is_private,
            "emoji": emoji,
        }
        if description:
            draft_data["description"] = description
        
        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="group",
            draft_data=draft_data,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Group creation cancelled by user.{feedback} [CANCELLED - stop here, do not retry or reattempt]"
        
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation CreateGroup($input: CreateGroupRequest!) {
            createGroup(input: $input) {
                id
                name
                type
                description
                emoji
                isPrivate
                isFavourite
                views {
                    id
                    name
                    type
                }
            }
        }
        """
        
        try:
            input_data = {
                "name": name,
                "workspaceId": context.workspace_id,
                "type": group_type.upper(),
                "isPrivate": is_private,
                "createdBy": context.user_id,
                "emoji": emoji,
            }

            if description:
                input_data["description"] = description
            
            result = await client.mutate(mutation, {"input": input_data})
            
            # createGroup returns an array of groups, get the first one
            groups = result.get("createGroup", [])
            
            if groups and len(groups) > 0:
                group = groups[0]
                result = f"Successfully created group:\n\n{format_group(group)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.GROUP,
                    action=ChangeAction.CREATED,
                    entity_id=group.get("id"),
                )
                return result + change.to_marker()
            else:
                return "Failed to create group - no data returned."
                
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error creating group: {e}")
            return f"Error creating group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def create_view_in_group(
        group_id: str,
        name: str,
        view_type: str = "TABLE",
        target_entity: Optional[str] = None,
    ) -> str:
        """Create a new view inside a group."""
        context = get_tool_context()
        client = context.get_client()
        
        # First, get the group to determine target entity if not provided
        group_query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                type
            }
        }
        """
        
        try:
            group_result = await client.query(group_query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = group_result.get("getGroups", [])
            group = next((g for g in groups if g.get("id") == group_id), None)
            
            if not group:
                return f"Group with ID {group_id} not found."
            
            # Determine target entity from group type
            entity = target_entity
            if not entity:
                group_type = group.get("type", "PEOPLE")
                entity = group_type  # PEOPLE or COMPANY
            
            mutation = """
            mutation CreateView($input: CreateViewRequest!) {
                createView(input: $input) {
                    id
                    name
                    type
                    targetEntity
                    isDefault
                    groupId
                }
            }
            """
            
            # Validate view type
            valid_types = ["TABLE", "PIPELINE"]
            if view_type.upper() not in valid_types:
                return f"Invalid view type '{view_type}'. Must be one of: {', '.join(valid_types)}"
            
            input_data = {
                "name": name,
                "type": view_type.upper(),
                "targetEntity": entity.upper(),
                "groupId": group_id,
                "workspaceId": context.workspace_id,
            }
            
            result = await client.mutate(mutation, {"input": input_data})
            
            view = result.get("createView")
            
            if view:
                result = (
                    f"Successfully created view:\n\n"
                    f"- **{view.get('name', 'Unknown')}** (ID: {view.get('id', 'N/A')})\n"
                    f"  Type: {view.get('type', 'Unknown')}\n"
                    f"  Target: {view.get('targetEntity', 'Unknown')}\n"
                    f"  Group ID: {view.get('groupId', 'N/A')}"
                )
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.VIEW,
                    action=ChangeAction.CREATED,
                    entity_id=view.get("id"),
                    group_id=view.get("groupId") or group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to create view - no data returned."
                
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error creating view: {e}")
            return f"Error creating view: {str(e)}"
        finally:
            await client.close()

    # @tool
    # async def create_reminder(
    #     title: str,
    #     due_date: str,
    #     timezone: Optional[str] = None,
    #     recurring: str = "OFF",
    #     visibility: str = "PRIVATE",
    #     people_id: Optional[str] = None,
    #     company_id: Optional[str] = None,
    #     deal_id: Optional[str] = None,
    # ) -> str:
    #     """Create a new reminder in the workspace.
        
    #     Args:
    #         title: Title of the reminder (required)
    #         due_date: Due date and time in ISO format or natural language (required)
    #         timezone: Timezone for the reminder (optional, defaults to user's local timezone)
    #         recurring: Recurring pattern like "OFF", "DAILY", "WEEKLY", "MONTHLY" (default: OFF)
    #         visibility: Visibility setting "PRIVATE", "WORKSPACE", or "PUBLIC" (default: PRIVATE)
    #         people_id: ID of a related person (optional)
    #         company_id: ID of a related company (optional)
    #         deal_id: ID of a related deal (optional)
            
    #     Returns:
    #         Confirmation message with the created reminder details
    #     """
    #     # Resolve timezone: use provided, context, or fallback
    #     tz = timezone or context.timezone or "UTC"
        
    #     # Build draft data for confirmation preview
    #     draft_data = {
    #         "title": title,
    #         "due_date": due_date,
    #         "timezone": tz,
    #         "recurring": recurring,
    #         "visibility": visibility,
    #     }
    #     if people_id: draft_data["people_id"] = people_id
    #     if company_id: draft_data["company_id"] = company_id
        
    #     # Request user confirmation
    #     confirmation = request_create_confirmation(
    #         entity_type="reminder",
    #         draft_data=draft_data,
    #     )
        
    #     if not confirmation.confirmed:
    #         feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
    #         return f"Reminder creation cancelled by user.{feedback} [CANCELLED - stop here, do not retry or reattempt]"
        
    #     client = context.get_client()
        
    #     mutation = """
    #     mutation CreateReminder($input: CreateReminderInput!, $workspaceId: String!) {
    #         createReminder(input: $input, workspaceId: $workspaceId) {
    #             id
    #             title
    #             duedate
    #             timezone
    #             recurring
    #             reminderVisibility
    #             createdBy
    #             workspaceId
    #             peopleId
    #             companyId
    #         }
    #     }
    #     """
        
    #     input_data = {
    #         "title": title,
    #         "duedate": due_date,
    #         "timezone": tz,
    #         "recurring": recurring,
    #         "reminderVisibility": visibility.upper(),
    #     }
    #     if people_id: input_data["peopleId"] = people_id
    #     if company_id: input_data["companyId"] = company_id
    #     if deal_id: input_data["dealId"] = deal_id
        
    #     try:
    #         result = await client.mutate(mutation, {
    #             "input": input_data,
    #             "workspaceId": context.workspace_id,
    #         })
            
    #         reminder = result.get("createReminder")
            
    #         if reminder:
    #             result_msg = f"Successfully created reminder:\n\n{format_reminder(reminder)}"
    #             # Add change metadata for frontend cache invalidation
    #             change = DataChange(
    #                 entity_type=EntityType.PERSON if people_id else EntityType.COMPANY if company_id else EntityType.PERSON, # Fallback to person
    #                 action=ChangeAction.CREATED,
    #                 entity_id=reminder.get("id"),
    #             )
    #             # Note: Reminders might need their own entity type in DataChange, but for now we'll use PERSON/COMPANY 
    #             # or just return the result if it doesn't map perfectly.
    #             return result_msg
    #         else:
    #             return "Failed to create reminder - no data returned."
                
    #     except Exception as e:
    #         logger.error(f"Error creating reminder: {e}")
    #         return f"Error creating reminder: {str(e)}"
    #     finally:
    #         await client.close()

    @tool
    async def create_note(
        entity_id: str,
        entity_type: str,
        content: str,
        is_private: bool = False,
    ) -> str:
        """Create a note attached to an entity."""
        # Validate entity type
        valid_types = ["PEOPLE", "COMPANY"]
        if entity_type.upper() not in valid_types:
            return f"Invalid entity type '{entity_type}'. Must be one of: {', '.join(valid_types)}"
        
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation CreateNote($input: CreateNoteInput!, $workspaceId: String!) {
            createNote(input: $input, workspaceId: $workspaceId) {
                id
                content
                entityType
                entityId
                isPrivate
                createdAt
            }
        }
        """
        
        input_data = {
            "entityType": entity_type.upper(),
            "entityId": entity_id,
            "content": content,
            "isPrivate": is_private,
        }
        
        try:
            result = await client.mutate(mutation, {
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            
            note = result.get("createNote")
            
            if note:
                # Use the user's requested phrasing for streamlined experience
                result_text = f"okay your note is created \"{note.get('content')}\""
                
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.NOTE,
                    action=ChangeAction.CREATED,
                    entity_id=note.get("id"),
                )
                return result_text + change.to_marker()
            else:
                return "Failed to create note - no data returned."
                
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error creating note: {e}")
            return f"Error creating note: {str(e)}"
        finally:
            await client.close()

    @tool
    async def bulk_create_companies(
        companies: list[dict],
        group_id: Optional[str] = None,
    ) -> str:
        """Create multiple companies at once in a single confirmed action.

        Use this tool instead of create_company when the user wants to create
        2 or more companies. The user reviews all companies before any are created.
        They can uncheck individual companies to exclude them or edit fields inline.

        Args:
            companies: List of company dicts. Each dict should have at minimum
                       {"name": str} and optionally {"description": str,
                       "email": str, "phone": str, "website": str}.
            group_id: ID of the group to add all created companies to (optional).

        Returns:
            Summary of how many companies were created.
        """
        if not companies:
            return "No companies provided to create."

        # Assign temp draft IDs for frontend tracking
        for i, company in enumerate(companies):
            company["_draft_id"] = f"draft-{i}"

        confirmation = request_bulk_create_confirmation(
            entities=companies,
            entity_type="company",
            group_id=group_id,
        )

        if not confirmation.confirmed:
            return "Bulk company creation cancelled. [CANCELLED - stop here, do not retry or reattempt]"

        accepted_ids = confirmation.accepted_ids  # None = accept all
        edited_entities = confirmation.edited_entities or {}

        items_to_create = []
        for company in companies:
            draft_id = company["_draft_id"]
            if accepted_ids is not None and draft_id not in accepted_ids:
                continue
            final = {**company}
            if draft_id in edited_entities:
                final.update(edited_entities[draft_id])
            final.pop("_draft_id", None)
            items_to_create.append(final)

        if not items_to_create:
            return "No companies were selected for creation."

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation BulkCreateCompanies($input: BulkCreateCompaniesInput!) {
            bulkCreateCompanies(input: $input) {
                count
                created {
                    id
                    name
                    workspaceId
                }
            }
        }
        """

        input_items = []
        for company in items_to_create:
            item: dict = {"name": company["name"], "workspaceId": context.workspace_id}
            if company.get("description"):
                item["description"] = company["description"]
            if company.get("email"):
                item["emails"] = [{"value": company["email"], "type": "work", "isPrimary": True}]
            if company.get("phone"):
                item["phoneNumbers"] = [{"value": company["phone"], "type": "work", "isPrimary": True}]
            if company.get("website"):
                item["urls"] = [{"value": company["website"], "label": "Website", "isPrimary": True}]
            input_items.append(item)

        try:
            result = await client.mutate(mutation, {
                "input": {"items": input_items, "groupId": group_id},
            })
            bulk_result = result.get("bulkCreateCompanies", {})
            count = bulk_result.get("count", 0)
            created = bulk_result.get("created", [])

            markers = ""
            for company in created:
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.CREATED,
                    entity_id=company.get("id"),
                    group_id=group_id,
                )
                markers += change.to_marker()

            return f"Created {count} {'company' if count == 1 else 'companies'}." + markers

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error bulk creating companies: {e}")
            return f"Error creating companies: {str(e)}"
        finally:
            await client.close()

    @tool
    async def bulk_create_people(
        people: list[dict],
        group_id: Optional[str] = None,
    ) -> str:
        """Create multiple people (contacts) at once in a single confirmed action.

        Use this tool instead of create_person when the user wants to create
        2 or more people. The user reviews all contacts before any are created.
        They can uncheck individual contacts to exclude them or edit fields inline.

        Args:
            people: List of person dicts. Each dict should have at minimum
                    {"first_name": str} and optionally {"last_name": str,
                    "job_title": str, "email": str, "phone": str,
                    "description": str}.
            group_id: ID of the group to add all created contacts to (optional).

        Returns:
            Summary of how many people were created.
        """
        if not people:
            return "No people provided to create."

        for i, person in enumerate(people):
            person["_draft_id"] = f"draft-{i}"

        confirmation = request_bulk_create_confirmation(
            entities=people,
            entity_type="person",
            group_id=group_id,
        )

        if not confirmation.confirmed:
            return "Bulk people creation cancelled. [CANCELLED - stop here, do not retry or reattempt]"

        accepted_ids = confirmation.accepted_ids
        edited_entities = confirmation.edited_entities or {}

        items_to_create = []
        for person in people:
            draft_id = person["_draft_id"]
            if accepted_ids is not None and draft_id not in accepted_ids:
                continue
            final = {**person}
            if draft_id in edited_entities:
                final.update(edited_entities[draft_id])
            final.pop("_draft_id", None)
            items_to_create.append(final)

        if not items_to_create:
            return "No people were selected for creation."

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation BulkCreatePeople($input: BulkCreatePeopleInput!) {
            bulkCreatePeople(input: $input) {
                count
                created {
                    id
                    firstName
                    lastName
                    workspaceId
                }
            }
        }
        """

        input_items = []
        for person in items_to_create:
            item: dict = {
                "firstName": person.get("first_name") or person.get("firstName", ""),
                "workspaceId": context.workspace_id,
            }
            if person.get("last_name") or person.get("lastName"):
                item["lastName"] = person.get("last_name") or person.get("lastName")
            if person.get("job_title") or person.get("jobTitle"):
                item["jobTitle"] = person.get("job_title") or person.get("jobTitle")
            if person.get("description"):
                item["description"] = person["description"]
            if person.get("email"):
                item["emails"] = [{"value": person["email"], "type": "work", "isPrimary": True}]
            if person.get("phone"):
                item["phoneNumbers"] = [{"value": person["phone"], "type": "mobile", "isPrimary": True}]
            input_items.append(item)

        try:
            result = await client.mutate(mutation, {
                "input": {"items": input_items, "groupId": group_id},
            })
            bulk_result = result.get("bulkCreatePeople", {})
            count = bulk_result.get("count", 0)
            created = bulk_result.get("created", [])

            markers = ""
            for person in created:
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.CREATED,
                    entity_id=person.get("id"),
                    group_id=group_id,
                )
                markers += change.to_marker()

            return f"Created {count} {'person' if count == 1 else 'people'}." + markers

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error bulk creating people: {e}")
            return f"Error creating people: {str(e)}"
        finally:
            await client.close()

    return [
        create_company,
        create_person,
        create_group,
        create_view_in_group,
        create_note,
        bulk_create_companies,
        bulk_create_people,
    ]

