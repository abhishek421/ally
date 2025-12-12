"""UPDATE tools for modifying companies, people, and groups."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.base import (
    ToolContext,
    format_company,
    format_person,
    format_group,
    DataChange,
    EntityType,
    ChangeAction,
)

logger = logging.getLogger(__name__)


def get_update_tools(context: ToolContext) -> list:
    """Get all UPDATE tools configured with the given context.
    
    Args:
        context: Tool context with auth and workspace info
        
    Returns:
        List of tool functions
    """

    @tool
    async def add_company_to_group(company_id: str, group_id: str) -> str:
        """Add a company to a group.
        
        Args:
            company_id: ID of the company to add
            group_id: ID of the group to add the company to
            
        Returns:
            Confirmation message
        """
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
            logger.error(f"Error adding company to group: {e}")
            return f"Error adding company to group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_company_from_group(company_id: str, group_id: str) -> str:
        """Remove a company from a group.
        
        Args:
            company_id: ID of the company to remove
            group_id: ID of the group to remove the company from
            
        Returns:
            Confirmation message
        """
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
                result = f"Successfully removed company {company_id} from group {group_id}."
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
            logger.error(f"Error removing company from group: {e}")
            return f"Error removing company from group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def add_person_to_group(person_id: str, group_id: str) -> str:
        """Add a person to a group.
        
        Args:
            person_id: ID of the person to add
            group_id: ID of the group to add the person to
            
        Returns:
            Confirmation message
        """
        client = context.get_client()
        
        mutation = """
        mutation CreateGroupPeople($input: CreateGroupPeopleInput!, $userId: String!) {
            createGroupPeople(input: $input, userId: $userId) {
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
                "userId": context.user_id,
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
            logger.error(f"Error adding person to group: {e}")
            return f"Error adding person to group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_person_from_group(person_id: str, group_id: str) -> str:
        """Remove a person from a group.
        
        Args:
            person_id: ID of the person to remove
            group_id: ID of the group to remove the person from
            
        Returns:
            Confirmation message
        """
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
                result = f"Successfully removed person {person_id} from group {group_id}."
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
            logger.error(f"Error removing person from group: {e}")
            return f"Error removing person from group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def add_person_to_company(person_id: str, company_id: str) -> str:
        """Add a person to a company (associate/link them).
        
        This creates a relationship between a person and a company,
        useful for tracking which contacts work at which companies.
        
        Args:
            person_id: ID of the person to add
            company_id: ID of the company to add the person to
            
        Returns:
            Confirmation message
        """
        client = context.get_client()
        
        mutation = """
        mutation AddPersonToCompany($peopleId: ID!, $companyId: ID!) {
            addPersonToCompany(peopleId: $peopleId, companyId: $companyId)
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
            logger.error(f"Error adding person to company: {e}")
            return f"Error adding person to company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_person_from_company(person_id: str, company_id: str) -> str:
        """Remove a person from a company (unlink them).
        
        This removes the relationship between a person and a company.
        
        Args:
            person_id: ID of the person to remove
            company_id: ID of the company to remove the person from
            
        Returns:
            Confirmation message
        """
        client = context.get_client()
        
        mutation = """
        mutation RemovePersonFromCompany($peopleId: ID!, $companyId: ID!) {
            removePersonFromCompany(peopleId: $peopleId, companyId: $companyId)
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
            logger.error(f"Error removing person from company: {e}")
            return f"Error removing person from company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_company(
        company_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Update a company's information.
        
        Args:
            company_id: ID of the company to update (required)
            name: New company name (optional)
            description: New company description (optional)
            
        Returns:
            Confirmation message with updated company details
        """
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
        
        if len(input_data) == 1:
            return "No updates specified. Please provide at least one field to update (name, description)."
        
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
            logger.error(f"Error updating company: {e}")
            return f"Error updating company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_person(
        person_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        job_title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Update a person's information.
        
        Args:
            person_id: ID of the person to update (required)
            first_name: New first name (optional)
            last_name: New last name (optional)
            job_title: New job title (optional)
            description: New description (optional)
            
        Returns:
            Confirmation message with updated person details
        """
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
        
        if len(input_data) == 1:
            return "No updates specified. Please provide at least one field to update (first_name, last_name, job_title, description)."
        
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
        """Update a group's information.
        
        Args:
            group_id: ID of the group to update (required)
            name: New group name (optional)
            description: New group description (optional)
            emoji: New emoji icon (optional)
            is_private: Whether the group should be private (optional)
            
        Returns:
            Confirmation message with updated group details
        """
        client = context.get_client()
        
        mutation = """
        mutation UpdateGroup($input: UpdateGroupRequest!) {
            updateGroup(input: $input) {
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
        
        # Build input - only include fields that are being updated
        input_data = {"id": group_id}
        
        if name is not None:
            input_data["name"] = name
        
        if description is not None:
            input_data["description"] = description
        
        if emoji is not None:
            input_data["emoji"] = emoji
        
        if is_private is not None:
            input_data["isPrivate"] = is_private
        
        if len(input_data) == 1:
            return "No updates specified. Please provide at least one field to update (name, description, emoji, is_private)."
        
        try:
            result = await client.mutate(mutation, {"input": input_data})
            
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
            logger.error(f"Error updating group: {e}")
            return f"Error updating group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_company_column_value(
        company_id: str,
        group_id: str,
        column_id: str,
        value: Optional[str] = None,
        select_option_id: Optional[str] = None,
    ) -> str:
        """Update a company's column value within a group.
        
        Use this tool to update group-specific fields like Status, Priority, etc.
        For SELECT/MULTISELECT columns, use select_option_id.
        For TEXT/NUMBER columns, use value.
        
        Example: "Move company Acme Corp to Followup status in Leads group" would require:
        1. First resolve the company name to get company_id
        2. Resolve the group name to get group_id  
        3. Get group columns to find the Status column_id
        4. Get column options to find the Followup option's select_option_id
        5. Call this tool with company_id, group_id, column_id, and select_option_id
        
        Args:
            company_id: ID of the company to update (required)
            group_id: ID of the group context for the update (required for cache invalidation)
            column_id: ID of the column to update (required)
            value: New value for TEXT/NUMBER columns (optional)
            select_option_id: ID of the select option for SELECT/MULTISELECT columns (optional)
            
        Returns:
            Confirmation message
        """
        if not value and not select_option_id:
            return "Please provide either 'value' (for TEXT/NUMBER columns) or 'select_option_id' (for SELECT/MULTISELECT columns)."
        
        client = context.get_client()
        
        try:
            if select_option_id:
                # Use saveSelectOptionSelectedValue for SELECT columns
                mutation = """
                mutation SaveSelectOptionValue($input: SelectOptionValueModel!) {
                    saveSelectOptionSelectedValue(selectOptionValueModel: $input) {
                        id
                        value
                        color
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
                    result_msg = f"Successfully updated company column to '{option.get('value', 'Unknown')}'."
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
                    result_msg = f"Successfully updated company column value to '{value}'."
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
            logger.error(f"Error updating company column value: {e}")
            return f"Error updating company column value: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_person_column_value(
        person_id: str,
        group_id: str,
        column_id: str,
        value: Optional[str] = None,
        select_option_id: Optional[str] = None,
    ) -> str:
        """Update a person's column value within a group.
        
        Use this tool to update group-specific fields like Status, Priority, etc.
        For SELECT/MULTISELECT columns, use select_option_id.
        For TEXT/NUMBER columns, use value.
        
        Example: "Move person John Smith to Qualified status in Contacts group" would require:
        1. First resolve the person name to get person_id
        2. Resolve the group name to get group_id
        3. Get group columns to find the Status column_id
        4. Get column options to find the Qualified option's select_option_id
        5. Call this tool with person_id, group_id, column_id, and select_option_id
        
        Args:
            person_id: ID of the person to update (required)
            group_id: ID of the group context for the update (required for cache invalidation)
            column_id: ID of the column to update (required)
            value: New value for TEXT/NUMBER columns (optional)
            select_option_id: ID of the select option for SELECT/MULTISELECT columns (optional)
            
        Returns:
            Confirmation message
        """
        if not value and not select_option_id:
            return "Please provide either 'value' (for TEXT/NUMBER columns) or 'select_option_id' (for SELECT/MULTISELECT columns)."
        
        client = context.get_client()
        
        try:
            if select_option_id:
                # Use saveSelectOptionSelectedValue for SELECT columns
                mutation = """
                mutation SaveSelectOptionValue($input: SelectOptionValueModel!) {
                    saveSelectOptionSelectedValue(selectOptionValueModel: $input) {
                        id
                        value
                        color
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
                    result_msg = f"Successfully updated person column to '{option.get('value', 'Unknown')}'."
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
                    result_msg = f"Successfully updated person column value to '{value}'."
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
            logger.error(f"Error updating person column value: {e}")
            return f"Error updating person column value: {str(e)}"
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
    ]

