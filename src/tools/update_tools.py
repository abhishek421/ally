"""UPDATE tools for modifying companies, people, and groups."""

import logging
from typing import Optional

from langchain_core.tools import tool

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
from src.tools.confirmation import (
    request_update_confirmation,
    request_delete_confirmation,
    request_column_update_confirmation,
    request_entity_selection,
    ConfirmationType,
    ConfirmationRequest,
    request_confirmation,
)

try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    GraphInterrupt = None

logger = logging.getLogger(__name__)


def get_update_tools() -> list:
    """Get all UPDATE tools.

    Returns:
        List of tool functions
    """

    @tool
    async def add_company_to_group(company_id: str, group_id: str) -> str:
        """Add a company to a group."""
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation CreateGroupCompany($input: CreateGroupCompanyInput!, $userId: String!) {
            createGroupCompany(input: $input, userId: $userId) {
                groupId
                companyId
            }
        }
        """
        
        try:
            result = await client.mutate(mutation, {
                "input": {
                    "groupId": group_id,
                    "companyId": company_id,
                },
                "userId": context.user_id,
            })
            
            data = result.get("createGroupCompany")
            
            if data:
                result = f"Successfully added company {company_id} to group {group_id}."
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=company_id,
                    group_id=group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to add company to group - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error adding company to group: {e}")
            return f"Error adding company to group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_company_from_group(
        company_id: str,
        group_id: str,
        company_name: str,
        group_name: str,
    ) -> str:
        """Remove a company from a group (asks for confirmation)."""
        # Request user confirmation for this destructive action
        confirmation = request_delete_confirmation(
            entity_type="company",
            entity_name=company_name,
            context=f"Remove '{company_name}' from group '{group_name}'?",
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Removal cancelled by user.{feedback}"
        
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation DeleteGroupCompany($groupId: ID!, $companyId: ID!) {
            deleteGroupCompany(groupId: $groupId, companyId: $companyId) {
                groupId
                companyId
            }
        }
        """
        
        try:
            result = await client.mutate(mutation, {
                "groupId": group_id,
                "companyId": company_id,
            })
            
            data = result.get("deleteGroupCompany")
            
            if data:
                result = f"Successfully removed '{company_name}' from group '{group_name}'."
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=company_id,
                    group_id=group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to remove company from group - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error removing company from group: {e}")
            return f"Error removing company from group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def add_person_to_group(person_id: str, group_id: str) -> str:
        """Add a person to a group."""
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation CreateGroupPeople($input: CreateGroupPeopleInput!) {
            createGroupPeople(input: $input) {
                groupId
                peopleId
            }
        }
        """

        try:
            result = await client.mutate(mutation, {
                "input": {
                    "groupId": group_id,
                    "peopleId": person_id,
                },
            })
            
            data = result.get("createGroupPeople")
            
            if data:
                result = f"Successfully added person {person_id} to group {group_id}."
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.UPDATED,
                    entity_id=person_id,
                    group_id=group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to add person to group - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error adding person to group: {e}")
            return f"Error adding person to group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_person_from_group(
        person_id: str,
        group_id: str,
        person_name: str,
        group_name: str,
    ) -> str:
        """Remove a person from a group (asks for confirmation)."""
        # Request user confirmation for this destructive action
        confirmation = request_delete_confirmation(
            entity_type="person",
            entity_name=person_name,
            context=f"Remove '{person_name}' from group '{group_name}'?",
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Removal cancelled by user.{feedback}"
        
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation DeleteGroupPeople($groupId: ID!, $peopleId: ID!) {
            deleteGroupPeople(groupId: $groupId, peopleId: $peopleId) {
                groupId
                peopleId
            }
        }
        """
        
        try:
            result = await client.mutate(mutation, {
                "groupId": group_id,
                "peopleId": person_id,
            })
            
            data = result.get("deleteGroupPeople")
            
            if data:
                result = f"Successfully removed '{person_name}' from group '{group_name}'."
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.UPDATED,
                    entity_id=person_id,
                    group_id=group_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to remove person from group - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error removing person from group: {e}")
            return f"Error removing person from group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def add_person_to_company(person_id: str, company_id: str) -> str:
        """Link a person to a company."""
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation AddPersonToCompany($peopleId: ID!, $companyId: ID!) {
            addPersonToCompany(peopleId: $peopleId, companyId: $companyId) {
                id
            }
        }
        """
        
        try:
            result = await client.mutate(mutation, {
                "peopleId": person_id,
                "companyId": company_id,
            })
            
            success = result.get("addPersonToCompany")
            
            if success:
                result = f"Successfully added person {person_id} to company {company_id}."
                # Add change metadata for frontend cache invalidation (affects both person and company)
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.UPDATED,
                    entity_id=person_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to add person to company."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error adding person to company: {e}")
            return f"Error adding person to company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_person_from_company(person_id: str, company_id: str) -> str:
        """Unlink a person from a company."""
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation RemovePersonFromCompany($peopleId: ID!, $companyId: ID!) {
            removePersonFromCompany(peopleId: $peopleId, companyId: $companyId) {
                id
            }
        }
        """
        
        try:
            result = await client.mutate(mutation, {
                "peopleId": person_id,
                "companyId": company_id,
            })
            
            success = result.get("removePersonFromCompany")
            
            if success:
                result = f"Successfully removed person {person_id} from company {company_id}."
                # Add change metadata for frontend cache invalidation (affects both person and company)
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.UPDATED,
                    entity_id=person_id,
                )
                return result + change.to_marker()
            else:
                return "Failed to remove person from company."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error removing person from company: {e}")
            return f"Error removing person from company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_company(
        company_id: str,
        company_name: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Update a company's name or description (asks for confirmation)."""
        # Build changes dict for confirmation preview
        changes = {}
        if name is not None:
            changes["name"] = name
        if description is not None:
            changes["description"] = description
        
        if not changes:
            return "No updates specified. Please provide at least one field to update (name, description)."
        
        # Request user confirmation before updating
        confirmation = request_update_confirmation(
            entity_type="company",
            entity_name=company_name,
            changes=changes,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Company update cancelled by user.{feedback}"
        
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation UpdateCompany($input: UpdateCompanyInput!) {
            updateCompany(input: $input) {
                id
                name
                description
                emails { id value type isPrimary }
                phoneNumbers { id value type isPrimary }
            }
        }
        """
        
        # Build input - only include fields that are being updated
        input_data = {"id": company_id}
        
        if name is not None:
            input_data["name"] = name
        
        if description is not None:
            input_data["description"] = description
        
        try:
            result = await client.mutate(mutation, {"input": input_data})
            
            company = result.get("updateCompany")
            
            if company:
                result = f"Successfully updated company:\n\n{format_company(company)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=company.get("id"),
                )
                return result + change.to_marker()
            else:
                return "Failed to update company - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating company: {e}")
            return f"Error updating company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_person(
        person_id: str,
        person_name: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        job_title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Update a person's name, job title, or description (asks for confirmation)."""
        # Build changes dict for confirmation preview
        changes = {}
        if first_name is not None:
            changes["first_name"] = first_name
        if last_name is not None:
            changes["last_name"] = last_name
        if job_title is not None:
            changes["job_title"] = job_title
        if description is not None:
            changes["description"] = description
        
        if not changes:
            return "No updates specified. Please provide at least one field to update (first_name, last_name, job_title, description)."
        
        # Request user confirmation before updating
        confirmation = request_update_confirmation(
            entity_type="person",
            entity_name=person_name,
            changes=changes,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Person update cancelled by user.{feedback}"
        
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation UpdatePerson($input: UpdatePeopleInput!) {
            updatePerson(input: $input) {
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
        
        # Build input - only include fields that are being updated
        input_data = {"id": person_id}
        
        if first_name is not None:
            input_data["firstName"] = first_name
        
        if last_name is not None:
            input_data["lastName"] = last_name
        
        if job_title is not None:
            input_data["jobTitle"] = job_title
        
        if description is not None:
            input_data["description"] = description
        
        try:
            result = await client.mutate(mutation, {"input": input_data})
            
            person = result.get("updatePerson")
            
            if person:
                result = f"Successfully updated person:\n\n{format_person(person)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.UPDATED,
                    entity_id=person.get("id"),
                )
                return result + change.to_marker()
            else:
                return "Failed to update person - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating person: {e}")
            return f"Error updating person: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_group(
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emoji: Optional[str] = None,
        is_private: Optional[bool] = None,
    ) -> str:
        """Update a group's name, description, emoji, or privacy setting."""
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation UpdateGroup($input: UpdateGroupRequest!, $id: String!) {
            updateGroup(input: $input, id: $id) {
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

        # Build input - only include fields that are being updated (id is a separate arg)
        input_data = {}

        if name is not None:
            input_data["name"] = name

        if description is not None:
            input_data["description"] = description

        if emoji is not None:
            input_data["emoji"] = emoji

        if is_private is not None:
            input_data["isPrivate"] = is_private

        if not input_data:
            return "No updates specified. Please provide at least one field to update (name, description, emoji, is_private)."

        try:
            result = await client.mutate(mutation, {"input": input_data, "id": group_id})
            
            group = result.get("updateGroup")
            
            if group:
                result = f"Successfully updated group:\n\n{format_group(group)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.GROUP,
                    action=ChangeAction.UPDATED,
                    entity_id=group.get("id"),
                )
                return result + change.to_marker()
            else:
                return "Failed to update group - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating group: {e}")
            return f"Error updating group: {str(e)}"
        finally:
            await client.close()

    async def _get_current_select_option_value(
        client, 
        column_id: str, 
        company_id: Optional[str] = None, 
        person_id: Optional[str] = None
    ) -> tuple[Optional[str], Optional[str]]:
        """Fetch the current selected option value for a company or person.
        
        Returns:
            Tuple of (value_label, color) or (None, None) if not set
        """
        try:
            # Query the company/person to see which option is selected
            if company_id:
                entity_query = """
                query GetCompanyColumnValue($companyId: ID!) {
                    getOneCompany(companyId: $companyId) {
                        columnValueSelectOption {
                            columnId
                            selectOptionId
                            selectOption {
                                id
                                value
                                color
                            }
                        }
                    }
                }
                """
                entity_result = await client.query(entity_query, {"companyId": company_id})
                entity = entity_result.get("getOneCompany", {})
                selected_options = entity.get("columnValueSelectOption", []) if entity else []
            elif person_id:
                entity_query = """
                query GetPersonColumnValue($peopleId: ID!) {
                    getPerson(peopleId: $peopleId) {
                        columnValueSelectOption {
                            columnId
                            selectOptionId
                            selectOption {
                                id
                                value
                                color
                            }
                        }
                    }
                }
                """
                entity_result = await client.query(entity_query, {"peopleId": person_id})
                entity = entity_result.get("getPerson", {})
                selected_options = entity.get("columnValueSelectOption", []) if entity else []
            else:
                return None, None
            
            # Find the selected option for this column
            for selected in selected_options:
                if selected.get("columnId") == column_id:
                    option = selected.get("selectOption", {})
                    if option:
                        return option.get("value"), option.get("color")
            
            return None, None
            
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.warning(f"Could not fetch current column value: {e}")
            return None, None

    @tool
    async def update_company_column_value(
        company_id: str,
        group_id: str,
        column_id: str,
        company_name: str,
        column_name: str,
        new_value_label: str,
        value: Optional[str] = None,
        select_option_id: Optional[str] = None,
        group_name: Optional[str] = None,
        new_value_color: Optional[str] = None,
    ) -> str:
        """Update a company's column value (Status, Priority, etc.) within a group.

        Requires: resolve entity/group names first, then get_group_columns → get_column_options.
        Pass all IDs + display names so the confirmation UI shows "Old → New".

        Args:
            company_id: Company ID
            group_id: Group ID
            column_id: Column ID
            company_name: Company display name (for confirmation UI)
            column_name: Column display name e.g. "Status"
            new_value_label: New value label e.g. "Lead"
            value: New value for TEXT/NUMBER columns
            select_option_id: Option ID for SELECT/MULTISELECT columns
            group_name: Group display name (for confirmation UI)
            new_value_color: Color of new value badge
        """
        if not value and not select_option_id:
            return "Please provide either 'value' (for TEXT/NUMBER columns) or 'select_option_id' (for SELECT/MULTISELECT columns)."
        
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # Fetch the current value before showing confirmation
            current_value_label = None
            current_value_color = None
            if select_option_id:
                current_value_label, current_value_color = await _get_current_select_option_value(
                    client, column_id, company_id=company_id
                )
            
            # Request user confirmation before updating
            confirmation = request_column_update_confirmation(
                entity_type="company",
                entity_name=company_name,
                column_name=column_name,
                current_value=current_value_label,
                new_value=new_value_label,
                group_name=group_name,
                current_value_color=current_value_color,
                new_value_color=new_value_color,
            )
            
            if not confirmation.confirmed:
                feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
                return f"Column update cancelled by user.{feedback}"
            
            if select_option_id:
                # Use saveSelectOptionSelectedValue for SELECT columns
                mutation = """
                mutation SaveSelectOptionValue($input: SelectOptionValueModel!) {
                    saveSelectOptionSelectedValue(selectOptionValueModel: $input) {
                        id
                        selectOptionId
                        selectOption { id value color }
                    }
                }
                """

                result = await client.mutate(mutation, {
                    "input": {
                        "columnId": column_id,
                        "companyId": company_id,
                        "selectOptionId": select_option_id,
                    }
                })

                option = result.get("saveSelectOptionSelectedValue")

                if option:
                    option_value = option.get("selectOption", {}).get("value", new_value_label)
                    result_msg = f"Successfully updated {column_name} for '{company_name}' to '{option_value}'."
                    change = DataChange(
                        entity_type=EntityType.COMPANY,
                        action=ChangeAction.UPDATED,
                        entity_id=company_id,
                        group_id=group_id,
                    )
                    return result_msg + change.to_marker()
                else:
                    return "Failed to update column value - no data returned."
            else:
                # Use upsertColumnValue for TEXT/NUMBER columns
                mutation = """
                mutation UpsertColumnValue($input: UpsertColumnValueInput!) {
                    upsertColumnValue(input: $input) {
                        id
                        value
                        columnId
                    }
                }
                """
                
                result = await client.mutate(mutation, {
                    "input": {
                        "columnId": column_id,
                        "companyId": company_id,
                        "value": value,
                    }
                })
                
                column_value = result.get("upsertColumnValue")
                
                if column_value:
                    result_msg = f"Successfully updated {column_name} for '{company_name}' to '{value}'."
                    change = DataChange(
                        entity_type=EntityType.COMPANY,
                        action=ChangeAction.UPDATED,
                        entity_id=company_id,
                        group_id=group_id,
                    )
                    return result_msg + change.to_marker()
                else:
                    return "Failed to update column value - no data returned."
                    
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating company column value: {e}")
            return f"Error updating company column value: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_person_column_value(
        person_id: str,
        group_id: str,
        column_id: str,
        person_name: str,
        column_name: str,
        new_value_label: str,
        value: Optional[str] = None,
        select_option_id: Optional[str] = None,
        group_name: Optional[str] = None,
        new_value_color: Optional[str] = None,
    ) -> str:
        """Update a person's column value (Status, Priority, etc.) within a group.

        Requires: resolve entity/group names first, then get_group_columns → get_column_options.
        Pass all IDs + display names so the confirmation UI shows "Old → New".

        Args:
            person_id: Person ID
            group_id: Group ID
            column_id: Column ID
            person_name: Person display name (for confirmation UI)
            column_name: Column display name e.g. "Status"
            new_value_label: New value label e.g. "Qualified"
            value: New value for TEXT/NUMBER columns
            select_option_id: Option ID for SELECT/MULTISELECT columns
            group_name: Group display name (for confirmation UI)
            new_value_color: Color of new value badge
        """
        if not value and not select_option_id:
            return "Please provide either 'value' (for TEXT/NUMBER columns) or 'select_option_id' (for SELECT/MULTISELECT columns)."
        
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # Fetch the current value before showing confirmation
            current_value_label = None
            current_value_color = None
            if select_option_id:
                current_value_label, current_value_color = await _get_current_select_option_value(
                    client, column_id, person_id=person_id
                )
            
            # Request user confirmation before updating
            confirmation = request_column_update_confirmation(
                entity_type="person",
                entity_name=person_name,
                column_name=column_name,
                current_value=current_value_label,
                new_value=new_value_label,
                group_name=group_name,
                current_value_color=current_value_color,
                new_value_color=new_value_color,
            )
            
            if not confirmation.confirmed:
                feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
                return f"Column update cancelled by user.{feedback}"
            
            if select_option_id:
                # Use saveSelectOptionSelectedValue for SELECT columns
                mutation = """
                mutation SaveSelectOptionValue($input: SelectOptionValueModel!) {
                    saveSelectOptionSelectedValue(selectOptionValueModel: $input) {
                        id
                        selectOptionId
                        selectOption { id value color }
                    }
                }
                """

                result = await client.mutate(mutation, {
                    "input": {
                        "columnId": column_id,
                        "peopleId": person_id,
                        "selectOptionId": select_option_id,
                    }
                })

                option = result.get("saveSelectOptionSelectedValue")

                if option:
                    option_value = option.get("selectOption", {}).get("value", new_value_label)
                    result_msg = f"Successfully updated {column_name} for '{person_name}' to '{option_value}'."
                    change = DataChange(
                        entity_type=EntityType.PERSON,
                        action=ChangeAction.UPDATED,
                        entity_id=person_id,
                        group_id=group_id,
                    )
                    return result_msg + change.to_marker()
                else:
                    return "Failed to update column value - no data returned."
            else:
                # Use upsertColumnValue for TEXT/NUMBER columns
                mutation = """
                mutation UpsertColumnValue($input: UpsertColumnValueInput!) {
                    upsertColumnValue(input: $input) {
                        id
                        value
                        columnId
                    }
                }
                """
                
                result = await client.mutate(mutation, {
                    "input": {
                        "columnId": column_id,
                        "peopleId": person_id,
                        "value": value,
                    }
                })
                
                column_value = result.get("upsertColumnValue")
                
                if column_value:
                    result_msg = f"Successfully updated {column_name} for '{person_name}' to '{value}'."
                    change = DataChange(
                        entity_type=EntityType.PERSON,
                        action=ChangeAction.UPDATED,
                        entity_id=person_id,
                        group_id=group_id,
                    )
                    return result_msg + change.to_marker()
                else:
                    return "Failed to update column value - no data returned."
                    
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating person column value: {e}")
            return f"Error updating person column value: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_person_status(
        person_name: str,
        group_name: str,
        new_status: str,
    ) -> str:
        """Update a person's status column in a group (handles name resolution and confirmation)."""
        from src.tools.base import fuzzy_match_entities

        context = get_tool_context()
        client = context.get_client()

        # Variables to hold resolved data
        person_id = None
        resolved_person_name = None
        group_id = None
        resolved_group_name = None
        status_column = None
        option_id = None
        option_value = None
        option_color = None
        current_value = None
        current_color = None

        # Step 1-5: Lookup and resolve all entities (in try block)
        try:
            # Step 1: Find the person using getWorkspacePeople with search
            search_query = """
            query GetWorkspacePeople($workspaceId: ID!, $limit: Int, $search: String) {
                getWorkspacePeople(workspaceId: $workspaceId, limit: $limit, search: $search) {
                    data { id firstName lastName }
                }
            }
            """

            person_result = await client.query(search_query, {
                "workspaceId": context.workspace_id,
                "limit": 10,
                "search": person_name,
            })

            raw_people = person_result.get("getWorkspacePeople", {}).get("data", [])
            # Normalize people to have 'name' field
            people = [{**p, "name": f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()} for p in raw_people]
            if not people:
                await client.close()
                return f"Could not find any person matching '{person_name}'."

            # Fuzzy match to find best person
            person_matches = fuzzy_match_entities(person_name, people, name_key="name", threshold=50.0, limit=3)
            if not person_matches:
                await client.close()
                return f"Could not find a person matching '{person_name}'."

            # Auto-select best match (disambiguation handled separately if needed)
            person = person_matches[0][0]
            person_id = person["id"]
            resolved_person_name = person["name"]

            # Step 2: Find the group
            groups_query = """
            query GetGroups($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    emoji
                    peopleColumns { id name dataType type }
                }
            }
            """

            groups_result = await client.query(groups_query, {"workspaceId": context.workspace_id})
            groups = groups_result.get("getGroups", [])

            if not groups:
                await client.close()
                return "No groups found in this workspace."

            # Fuzzy match to find best group
            group_matches = fuzzy_match_entities(group_name, groups, name_key="name", threshold=50.0, limit=3)
            if not group_matches:
                available = [f"{g.get('emoji', '')} {g['name']}".strip() for g in groups[:5]]
                await client.close()
                return f"Could not find a group matching '{group_name}'. Available: {', '.join(available)}"

            group = group_matches[0][0]
            group_id = group["id"]
            resolved_group_name = f"{group.get('emoji', '')} {group['name']}".strip()

            # Step 3: Find the Status column
            columns = group.get("peopleColumns", [])
            for col in columns:
                if col["name"].lower() == "status" and col["dataType"] in ["SELECT", "MULTISELECT"]:
                    status_column = col
                    break

            if not status_column:
                for col in columns:
                    if "status" in col["name"].lower() and col["dataType"] in ["SELECT", "MULTISELECT"]:
                        status_column = col
                        break

            if not status_column:
                col_names = [c["name"] for c in columns if c["dataType"] in ["SELECT", "MULTISELECT"]]
                await client.close()
                return f"No Status column found in group '{resolved_group_name}'. Available select columns: {', '.join(col_names) or 'None'}"

            # Step 4: Get status options and find matching option
            options_query = """
            query GetSelectOptions($columnId: String!) {
                getSelectOptionsByColumnId(columnId: $columnId) { id value color order }
            }
            """

            options_result = await client.query(options_query, {"columnId": status_column["id"]})
            options = options_result.get("getSelectOptionsByColumnId", [])

            if not options:
                await client.close()
                return f"No status options found for the Status column."

            # Fuzzy match the status value
            status_matches = fuzzy_match_entities(new_status, options, name_key="value", threshold=50.0, limit=3)
            if not status_matches:
                available = [opt["value"] for opt in options]
                await client.close()
                return f"Could not match status '{new_status}'. Available options: {', '.join(available)}"

            selected_option = status_matches[0][0]
            option_id = selected_option["id"]
            option_value = selected_option["value"]
            option_color = selected_option.get("color")

            # Step 5: Get current value for confirmation display
            current_value, current_color = await _get_current_select_option_value(
                client, status_column["id"], person_id=person_id
            )

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error looking up person status data: {e}")
            await client.close()
            return f"Error looking up data: {str(e)}"

        # Step 6: Request confirmation (OUTSIDE try block so interrupt propagates)
        confirmation = request_column_update_confirmation(
            entity_type="person",
            entity_name=resolved_person_name,
            column_name="Status",
            current_value=current_value,
            new_value=option_value,
            group_name=resolved_group_name,
            current_value_color=current_color,
            new_value_color=option_color,
        )

        if not confirmation.confirmed:
            await client.close()
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Status update cancelled.{feedback}"

        # Step 7: Apply the update (in try block)
        try:
            mutation = """
            mutation SaveSelectOptionValue($input: SelectOptionValueModel!) {
                saveSelectOptionSelectedValue(selectOptionValueModel: $input) {
                    id
                    selectOptionId
                    selectOption { id value color }
                }
            }
            """

            result = await client.mutate(mutation, {
                "input": {
                    "columnId": status_column["id"],
                    "peopleId": person_id,
                    "selectOptionId": option_id,
                }
            })

            saved = result.get("saveSelectOptionSelectedValue")
            if saved:
                saved_value = saved.get("selectOption", {}).get("value", option_value)
                result_msg = f"Successfully updated status for '{resolved_person_name}' to '{saved_value}' in {resolved_group_name}."
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.UPDATED,
                    entity_id=person_id,
                    group_id=group_id,
                )
                return result_msg + change.to_marker()
            else:
                return "Failed to update status - no data returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating person status: {e}")
            return f"Error updating person status: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_company_status(
        company_name: str,
        group_name: str,
        new_status: str,
    ) -> str:
        """Update a company's status column in a group (handles name resolution and confirmation)."""
        from src.tools.base import fuzzy_match_entities

        context = get_tool_context()
        client = context.get_client()

        # Variables to hold resolved data
        company_id = None
        resolved_company_name = None
        group_id = None
        resolved_group_name = None
        status_column = None
        option_id = None
        option_value = None
        option_color = None
        current_value = None
        current_color = None

        # Step 1-5: Lookup and resolve all entities (in try block)
        try:
            # Step 1: Find the company using getWorkspaceCompany with search
            search_query = """
            query GetWorkspaceCompany($workspaceId: ID!, $limit: Int, $search: String) {
                getWorkspaceCompany(workspaceId: $workspaceId, limit: $limit, search: $search) {
                    data { id name }
                }
            }
            """

            company_result = await client.query(search_query, {
                "workspaceId": context.workspace_id,
                "limit": 10,
                "search": company_name,
            })

            companies = company_result.get("getWorkspaceCompany", {}).get("data", [])
            if not companies:
                await client.close()
                return f"Could not find any company matching '{company_name}'."

            # Fuzzy match to find best company
            company_matches = fuzzy_match_entities(company_name, companies, name_key="name", threshold=50.0, limit=3)
            if not company_matches:
                await client.close()
                return f"Could not find a company matching '{company_name}'."

            # Auto-select best match
            company = company_matches[0][0]
            company_id = company["id"]
            resolved_company_name = company["name"]

            # Step 2: Find the group
            groups_query = """
            query GetGroups($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    emoji
                    companyColumns { id name dataType type }
                }
            }
            """

            groups_result = await client.query(groups_query, {"workspaceId": context.workspace_id})
            groups = groups_result.get("getGroups", [])

            if not groups:
                await client.close()
                return "No groups found in this workspace."

            # Fuzzy match to find best group
            group_matches = fuzzy_match_entities(group_name, groups, name_key="name", threshold=50.0, limit=3)
            if not group_matches:
                available = [f"{g.get('emoji', '')} {g['name']}".strip() for g in groups[:5]]
                await client.close()
                return f"Could not find a group matching '{group_name}'. Available: {', '.join(available)}"

            group = group_matches[0][0]
            group_id = group["id"]
            resolved_group_name = f"{group.get('emoji', '')} {group['name']}".strip()

            # Step 3: Find the Status column
            columns = group.get("companyColumns", [])
            for col in columns:
                if col["name"].lower() == "status" and col["dataType"] in ["SELECT", "MULTISELECT"]:
                    status_column = col
                    break

            if not status_column:
                for col in columns:
                    if "status" in col["name"].lower() and col["dataType"] in ["SELECT", "MULTISELECT"]:
                        status_column = col
                        break

            if not status_column:
                col_names = [c["name"] for c in columns if c["dataType"] in ["SELECT", "MULTISELECT"]]
                await client.close()
                return f"No Status column found in group '{resolved_group_name}'. Available select columns: {', '.join(col_names) or 'None'}"

            # Step 4: Get status options and find matching option
            options_query = """
            query GetSelectOptions($columnId: String!) {
                getSelectOptionsByColumnId(columnId: $columnId) { id value color order }
            }
            """

            options_result = await client.query(options_query, {"columnId": status_column["id"]})
            options = options_result.get("getSelectOptionsByColumnId", [])

            if not options:
                await client.close()
                return f"No status options found for the Status column."

            # Fuzzy match the status value
            status_matches = fuzzy_match_entities(new_status, options, name_key="value", threshold=50.0, limit=3)
            if not status_matches:
                available = [opt["value"] for opt in options]
                await client.close()
                return f"Could not match status '{new_status}'. Available options: {', '.join(available)}"

            selected_option = status_matches[0][0]
            option_id = selected_option["id"]
            option_value = selected_option["value"]
            option_color = selected_option.get("color")

            # Step 5: Get current value for confirmation display
            current_value, current_color = await _get_current_select_option_value(
                client, status_column["id"], company_id=company_id
            )

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error looking up company status data: {e}")
            await client.close()
            return f"Error looking up data: {str(e)}"

        # Step 6: Request confirmation (OUTSIDE try block so interrupt propagates)
        confirmation = request_column_update_confirmation(
            entity_type="company",
            entity_name=resolved_company_name,
            column_name="Status",
            current_value=current_value,
            new_value=option_value,
            group_name=resolved_group_name,
            current_value_color=current_color,
            new_value_color=option_color,
        )

        if not confirmation.confirmed:
            await client.close()
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Status update cancelled.{feedback}"

        # Step 7: Apply the update (in try block)
        try:
            mutation = """
            mutation SaveSelectOptionValue($input: SelectOptionValueModel!) {
                saveSelectOptionSelectedValue(selectOptionValueModel: $input) {
                    id
                    selectOptionId
                    selectOption { id value color }
                }
            }
            """

            result = await client.mutate(mutation, {
                "input": {
                    "columnId": status_column["id"],
                    "companyId": company_id,
                    "selectOptionId": option_id,
                }
            })

            saved = result.get("saveSelectOptionSelectedValue")
            if saved:
                saved_value = saved.get("selectOption", {}).get("value", option_value)
                result_msg = f"Successfully updated status for '{resolved_company_name}' to '{saved_value}' in {resolved_group_name}."
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=company_id,
                    group_id=group_id,
                )
                return result_msg + change.to_marker()
            else:
                return "Failed to update status - no data returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating company status: {e}")
            return f"Error updating company status: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_reminder(
        id: str,
        title: Optional[str] = None,
        due_date: Optional[str] = None,
        timezone: Optional[str] = None,
        recurring: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> str:
        """Update an existing reminder.
        
        Args:
            id: ID of the reminder to update (required)
            title: New title (optional)
            due_date: New due date in ISO format or natural language (optional)
            timezone: New timezone (optional)
            recurring: New recurring pattern (optional)
            visibility: New visibility setting "PRIVATE", "WORKSPACE", "PUBLIC" (optional)
            
        Returns:
            Confirmation message with updated reminder details
        """
        changes = {}
        if title: changes["title"] = title
        if due_date: changes["due_date"] = due_date
        if timezone: changes["timezone"] = timezone
        if recurring: changes["recurring"] = recurring
        if visibility: changes["visibility"] = visibility
        
        if not changes:
            return "No updates specified. Please provide at least one field to update."
            
        # Request user confirmation
        confirmation = request_update_confirmation(
            entity_type="reminder",
            entity_name=title or id,
            changes=changes,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Reminder update cancelled by user.{feedback}"
            
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation UpdateReminder($id: ID!, $input: UpdateReminderInput!, $workspaceId: String!) {
            updateReminder(id: $id, input: $input, workspaceId: $workspaceId) {
                id
                title
                duedate
                timezone
                recurring
                reminderVisibility
            }
        }
        """
        
        input_data = {}
        if title: input_data["title"] = title
        if due_date: input_data["duedate"] = due_date
        if timezone: input_data["timezone"] = timezone
        if recurring: input_data["recurring"] = recurring
        if visibility: input_data["reminderVisibility"] = visibility.upper()
        
        try:
            result = await client.mutate(mutation, {
                "id": id,
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            
            reminder = result.get("updateReminder")
            
            if reminder:
                return f"Successfully updated reminder:\n\n{format_reminder(reminder)}"
            else:
                return "Failed to update reminder - no data returned."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating reminder: {e}")
            return f"Error updating reminder: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_reminder(id: str, title: Optional[str] = None) -> str:
        """Delete a reminder.
        
        Args:
            id: ID of the reminder to delete (required)
            title: Title of the reminder (optional, for confirmation UI)
            
        Returns:
            Confirmation message
        """
        # Request user confirmation
        confirmation = request_delete_confirmation(
            entity_type="reminder",
            entity_name=title or id,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Deletion cancelled by user.{feedback}"
            
        context = get_tool_context()
        client = context.get_client()
        
        mutation = """
        mutation DeleteReminder($id: ID!, $workspaceId: String!) {
            deleteReminder(id: $id, workspaceId: $workspaceId)
        }
        """
        
        try:
            result = await client.mutate(mutation, {
                "id": id,
                "workspaceId": context.workspace_id,
            })
            
            success = result.get("deleteReminder")
            
            if success:
                return f"Successfully deleted reminder '{title or id}'."
            else:
                return "Failed to delete reminder."
                
        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error deleting reminder: {e}")
            return f"Error deleting reminder: {str(e)}"
        finally:
            await client.close()

    return [
        # Group membership tools
        add_company_to_group,
        remove_company_from_group,
        add_person_to_group,
        remove_person_from_group,
        # Company-person relationship tools
        add_person_to_company,
        remove_person_from_company,
        # Entity update tools
        update_company,
        update_person,
        update_group,
        # Group column value update tools
        update_company_column_value,
        update_person_column_value,
        # Simplified status update tools
        update_person_status,
        update_company_status,
        # Reminder tools
        update_reminder,
        delete_reminder,
    ]

