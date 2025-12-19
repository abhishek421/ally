"""CREATE tools for creating companies, people, groups, and views."""

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
from src.tools.confirmation import (
    request_create_confirmation,
)

logger = logging.getLogger(__name__)


def get_create_tools(context: ToolContext) -> list:
    """Get all CREATE tools configured with the given context.
    
    Args:
        context: Tool context with auth and workspace info
        
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
        """Create a new company in the workspace.
        
        This tool will ask for user confirmation before creating the company,
        showing a preview of the data to be created.
        
        Args:
            name: Company name (required)
            description: Company description (optional)
            email: Primary email address (optional)
            phone: Primary phone number (optional)
            website: Company website URL (optional)
            group_id: ID of a group to add the company to (optional)
            
        Returns:
            Confirmation message with the created company details
        """
        # Build draft data for confirmation preview
        draft_data = {"name": name}
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
        
        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="company",
            draft_data=draft_data,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Company creation cancelled by user.{feedback}"
        
        client = context.get_client()
        
        mutation = """
        mutation CreateCompany(
            $input: CreateCompanyInput!
            $userId: ID!
            $groupId: ID
        ) {
            createCompany(input: $input, userId: $userId, groupId: $groupId) {
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
                "userId": context.user_id,
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
        """Create a new person (contact) in the workspace.
        
        This tool will ask for user confirmation before creating the person,
        showing a preview of the data to be created.
        
        Args:
            first_name: First name (required)
            last_name: Last name (optional)
            job_title: Job title (optional)
            description: Description or notes (optional)
            email: Primary email address (optional)
            phone: Primary phone number (optional)
            group_id: ID of a group to add the person to (optional)
            
        Returns:
            Confirmation message with the created person details
        """
        # Build draft data for confirmation preview
        draft_data = {"first_name": first_name}
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
        
        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="person",
            draft_data=draft_data,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Person creation cancelled by user.{feedback}"
        
        client = context.get_client()
        
        mutation = """
        mutation CreatePerson(
            $input: CreatePeopleInput!
            $userId: ID!
            $groupId: ID
        ) {
            createPerson(input: $input, userId: $userId, groupId: $groupId) {
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
                "userId": context.user_id,
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
        emoji: Optional[str] = None,
        is_private: bool = True,
    ) -> str:
        """Create a new group in the workspace.
        
        This tool will ask for user confirmation before creating the group,
        showing a preview of the data to be created.
        
        Args:
            name: Group name (required)
            group_type: Type of group - "PEOPLE" or "COMPANY" (default: PEOPLE)
            description: Group description (optional)
            emoji: Emoji icon for the group (optional)
            is_private: Whether the group is private (default: True)
            
        Returns:
            Confirmation message with the created group details
        """
        # Validate group type
        valid_types = ["PEOPLE", "COMPANY"]
        if group_type.upper() not in valid_types:
            return f"Invalid group type '{group_type}'. Must be one of: {', '.join(valid_types)}"
        
        # Build draft data for confirmation preview
        draft_data = {
            "name": name,
            "type": group_type.upper(),
            "is_private": is_private,
        }
        if description:
            draft_data["description"] = description
        if emoji:
            draft_data["emoji"] = emoji
        
        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="group",
            draft_data=draft_data,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Group creation cancelled by user.{feedback}"
        
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
            }
            
            if description:
                input_data["description"] = description
            
            if emoji:
                input_data["emoji"] = emoji
            
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
        """Create a new view in an existing group.
        
        Args:
            group_id: ID of the group to create the view in (required)
            name: Name of the view (required)
            view_type: Type of view - "TABLE" or "PIPELINE" (default: TABLE)
            target_entity: Entity type - "PEOPLE", "COMPANY", or "DEAL" (optional, inferred from group)
            
        Returns:
            Confirmation message with the created view details
        """
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
                
        except Exception as e:
            logger.error(f"Error creating view: {e}")
            return f"Error creating view: {str(e)}"
        finally:
            await client.close()

    return [
        create_company,
        create_person,
        create_group,
        create_view_in_group,
    ]

