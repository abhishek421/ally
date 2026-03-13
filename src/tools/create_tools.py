"""CREATE tools for creating companies, people, groups, and views."""

import hashlib
import json
import logging
from typing import Optional
from uuid import uuid4

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
    request_batch_create_confirmation,
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
        # Build full API-ready input for draft_data
        draft_data = {
            "name": name,
            "workspaceId": context.workspace_id,
            "description": description or None,
            "emails": [{"value": email, "type": "work", "isPrimary": True}] if email else [],
            "phoneNumbers": [{"value": phone, "type": "work", "isPrimary": True}] if phone else [],
            "urls": [{"value": website, "label": "Website", "isPrimary": True}] if website else [],
            "groupId": group_id or None,
            "userId": context.user_id,
        }

        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="company",
            draft_data=draft_data,
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Company creation cancelled by user.{feedback}"

        # Use confirmed draft_data (may have been edited by user) as source of truth
        confirmed_data = confirmation.modified_data if confirmation.modified_data else draft_data

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

        # Build input from confirmed data
        input_data = {
            "name": confirmed_data["name"],
            "workspaceId": confirmed_data["workspaceId"],
        }

        if confirmed_data.get("description"):
            input_data["description"] = confirmed_data["description"]

        if confirmed_data.get("emails"):
            input_data["emails"] = confirmed_data["emails"]

        if confirmed_data.get("phoneNumbers"):
            input_data["phoneNumbers"] = confirmed_data["phoneNumbers"]

        if confirmed_data.get("urls"):
            input_data["urls"] = confirmed_data["urls"]

        confirmed_group_id = confirmed_data.get("groupId")
        confirmed_user_id = confirmed_data.get("userId", context.user_id)

        try:
            result = await client.mutate(mutation, {
                "input": input_data,
                "userId": confirmed_user_id,
                "groupId": confirmed_group_id,
            })
            
            company = result.get("createCompany")

            if company:
                group_msg = f" and added to group" if confirmed_group_id else ""
                result = f"Successfully created company{group_msg}:\n\n{format_company(company)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.CREATED,
                    entity_id=company.get("id"),
                    group_id=confirmed_group_id,
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
        # Build full API-ready input for draft_data
        draft_data = {
            "firstName": first_name,
            "lastName": last_name or None,
            "jobTitle": job_title or None,
            "description": description or None,
            "workspaceId": context.workspace_id,
            "emails": [{"value": email, "type": "work", "isPrimary": True}] if email else [],
            "phoneNumbers": [{"value": phone, "type": "mobile", "isPrimary": True}] if phone else [],
            "groupId": group_id or None,
            "userId": context.user_id,
        }

        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="person",
            draft_data=draft_data,
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Person creation cancelled by user.{feedback}"

        # Use confirmed draft_data (may have been edited by user) as source of truth
        confirmed_data = confirmation.modified_data if confirmation.modified_data else draft_data

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

        # Build input from confirmed data
        input_data = {
            "firstName": confirmed_data["firstName"],
            "workspaceId": confirmed_data["workspaceId"],
        }

        if confirmed_data.get("lastName"):
            input_data["lastName"] = confirmed_data["lastName"]

        if confirmed_data.get("jobTitle"):
            input_data["jobTitle"] = confirmed_data["jobTitle"]

        if confirmed_data.get("description"):
            input_data["description"] = confirmed_data["description"]

        if confirmed_data.get("emails"):
            input_data["emails"] = confirmed_data["emails"]

        if confirmed_data.get("phoneNumbers"):
            input_data["phoneNumbers"] = confirmed_data["phoneNumbers"]

        confirmed_group_id = confirmed_data.get("groupId")
        confirmed_user_id = confirmed_data.get("userId", context.user_id)

        try:
            result = await client.mutate(mutation, {
                "input": input_data,
                "userId": confirmed_user_id,
                "groupId": confirmed_group_id,
            })
            
            person = result.get("createPerson")

            if person:
                group_msg = f" and added to group" if confirmed_group_id else ""
                result = f"Successfully created person{group_msg}:\n\n{format_person(person)}"
                # Add change metadata for frontend cache invalidation
                change = DataChange(
                    entity_type=EntityType.PERSON,
                    action=ChangeAction.CREATED,
                    entity_id=person.get("id"),
                    group_id=confirmed_group_id,
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
        emoji: str = "📁",
        is_private: bool = True,
    ) -> str:
        """Create a new group in the workspace.

        This tool will ask for user confirmation before creating the group,
        showing a preview of the data to be created.

        IMPORTANT: Always provide a relevant emoji that matches the group's purpose or name.
        For example:
        - "Sales Leads" -> 💰 or 🎯
        - "Engineering Team" -> 👨‍💻 or ⚙️
        - "Investors" -> 💵 or 📈
        - "Partners" -> 🤝
        - "Customers" -> 👥 or 🛒
        - "Marketing" -> 📣 or 🎨
        - "Support" -> 🎧 or 💬

        Args:
            name: Group name (required)
            group_type: Type of group - "PEOPLE" or "COMPANY" (default: PEOPLE)
            description: Group description (optional)
            emoji: Emoji icon for the group - choose one that matches the group's purpose (default: 📁)
            is_private: Whether the group is private (default: True)

        Returns:
            Confirmation message with the created group details
        """
        # Validate group type
        valid_types = ["PEOPLE", "COMPANY"]
        if group_type.upper() not in valid_types:
            return f"Invalid group type '{group_type}'. Must be one of: {', '.join(valid_types)}"
        
        # Build full API-ready input for draft_data
        draft_data = {
            "name": name,
            "workspaceId": context.workspace_id,
            "type": group_type.upper(),
            "isPrivate": is_private,
            "createdBy": context.user_id,
            "emoji": emoji,
            "description": description or None,
        }

        # Request user confirmation before creating
        confirmation = request_create_confirmation(
            entity_type="group",
            draft_data=draft_data,
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Group creation cancelled by user.{feedback}"

        # Use confirmed draft_data (may have been edited by user) as source of truth
        confirmed_data = confirmation.modified_data if confirmation.modified_data else draft_data

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
                "name": confirmed_data["name"],
                "workspaceId": confirmed_data["workspaceId"],
                "type": confirmed_data["type"],
                "isPrivate": confirmed_data["isPrivate"],
                "createdBy": confirmed_data["createdBy"],
                "emoji": confirmed_data["emoji"],
            }

            if confirmed_data.get("description"):
                input_data["description"] = confirmed_data["description"]

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

    @tool
    async def create_people_batch(
        people: list[dict],
    ) -> str:
        """Create multiple people (contacts) across one or more groups in a single batch.

        Use this tool when creating multiple people at once, or when creating people
        with specific group assignments. Each person dict can specify which group to add to.

        Args:
            people: List of person dicts. Each dict can have:
                - firstName (required): First name
                - lastName: Last name
                - jobTitle: Job title
                - description: Description or notes
                - email: Primary email address
                - phone: Primary phone number
                - groupId: ID of group to add this person to
                - groupName: Display name of the group (for UI)

        Returns:
            Summary of created people
        """
        draft_entities = []
        groups_summary = {}

        for idx, person in enumerate(people):
            # Deterministic draft ID: LangGraph re-executes tools on resume,
            # so uuid4() would produce different IDs. Use a hash of the input
            # data + index so draft IDs are stable across re-executions.
            id_seed = json.dumps({"idx": idx, "data": person}, sort_keys=True)
            draft_id = f"draft-{hashlib.sha256(id_seed.encode()).hexdigest()[:12]}"
            group_id = person.get("groupId") or person.get("group_id")
            group_name = person.get("groupName") or person.get("group_name") or ""

            draft_entities.append({
                "draft_id": draft_id,
                "group_id": group_id,
                "group_name": group_name,
                "data": {
                    "firstName": person.get("firstName") or person.get("first_name", ""),
                    "lastName": person.get("lastName") or person.get("last_name") or "",
                    "jobTitle": person.get("jobTitle") or person.get("job_title") or "",
                    "description": person.get("description") or "",
                    "emails": [{"value": person["email"], "type": "work", "isPrimary": True}] if person.get("email") else [],
                    "phoneNumbers": [{"value": person["phone"], "type": "mobile", "isPrimary": True}] if person.get("phone") else [],
                    "workspaceId": context.workspace_id,
                    "userId": context.user_id,
                    "groupId": group_id,
                },
            })

            if group_id:
                if group_id not in groups_summary:
                    groups_summary[group_id] = {"group_id": group_id, "group_name": group_name, "count": 0}
                groups_summary[group_id]["count"] += 1

        # ONE interrupt for all entities
        confirmation = request_batch_create_confirmation(
            entity_type="person",
            draft_entities=draft_entities,
            groups_summary=list(groups_summary.values()),
        )

        if not confirmation.confirmed:
            return f"Cancelled. No people were created."

        # Determine which entities to create
        accepted_ids = set()
        modified_map = {}
        if confirmation.accepted_entities:
            for ae in confirmation.accepted_entities:
                accepted_ids.add(ae["draft_id"])
                if ae.get("modified_data"):
                    modified_map[ae["draft_id"]] = ae["modified_data"]
        else:
            # If no explicit accepted_entities, accept all (simple "Accept all")
            accepted_ids = {d["draft_id"] for d in draft_entities}

        rejected_ids = set(confirmation.rejected_entity_ids or [])
        accepted_ids -= rejected_ids

        if not accepted_ids:
            return "All people were rejected. No people created."

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

        created = []
        result_parts = []
        try:
            for draft in draft_entities:
                if draft["draft_id"] not in accepted_ids:
                    continue

                entity_data = modified_map.get(draft["draft_id"]) or draft["data"]

                input_data = {
                    "firstName": entity_data["firstName"],
                    "workspaceId": entity_data.get("workspaceId", context.workspace_id),
                }
                if entity_data.get("lastName"):
                    input_data["lastName"] = entity_data["lastName"]
                if entity_data.get("jobTitle"):
                    input_data["jobTitle"] = entity_data["jobTitle"]
                if entity_data.get("description"):
                    input_data["description"] = entity_data["description"]
                if entity_data.get("emails"):
                    input_data["emails"] = entity_data["emails"]
                if entity_data.get("phoneNumbers"):
                    input_data["phoneNumbers"] = entity_data["phoneNumbers"]

                group_id = entity_data.get("groupId") or draft.get("group_id")
                user_id = entity_data.get("userId", context.user_id)

                try:
                    logger.info(f"Creating person {draft['draft_id']}: name={input_data.get('firstName')} {input_data.get('lastName', '')}, groupId={group_id}")
                    client = context.get_client()
                    res = await client.mutate(mutation, {
                        "input": input_data,
                        "userId": user_id,
                        "groupId": group_id,
                    })
                    await client.close()
                    logger.info(f"Mutation result for {draft['draft_id']}: {res}")

                    person = res.get("createPerson")
                    if person:
                        created.append(person)
                        change = DataChange(
                            entity_type=EntityType.PERSON,
                            action=ChangeAction.CREATED,
                            entity_id=person.get("id"),
                            group_id=group_id,
                            draft_id=draft["draft_id"],
                        )
                        result_parts.append(change.to_marker())
                    else:
                        logger.error(f"createPerson returned None for {draft['draft_id']}. Full response: {res}")
                except Exception as e:
                    logger.error(f"Error creating person {draft['draft_id']}: {e}", exc_info=True)

            summary = f"Successfully created {len(created)} of {len(accepted_ids)} people."
            if rejected_ids:
                summary += f" {len(rejected_ids)} were rejected."
            return summary + "".join(result_parts)

        except Exception as e:
            logger.error(f"Error in create_people_batch: {e}")
            return f"Error creating people: {str(e)}"

    @tool
    async def create_companies_batch(
        companies: list[dict],
    ) -> str:
        """Create multiple companies across one or more groups in a single batch.

        Use this tool when creating multiple companies at once, or when creating companies
        with specific group assignments.

        Args:
            companies: List of company dicts. Each dict can have:
                - name (required): Company name
                - description: Company description
                - email: Primary email address
                - phone: Primary phone number
                - website: Company website URL
                - groupId: ID of group to add this company to
                - groupName: Display name of the group (for UI)

        Returns:
            Summary of created companies
        """
        draft_entities = []
        groups_summary = {}

        for idx, company in enumerate(companies):
            # Deterministic draft ID: LangGraph re-executes tools on resume,
            # so uuid4() would produce different IDs. Use a hash of the input
            # data + index so draft IDs are stable across re-executions.
            id_seed = json.dumps({"idx": idx, "data": company}, sort_keys=True)
            draft_id = f"draft-{hashlib.sha256(id_seed.encode()).hexdigest()[:12]}"
            group_id = company.get("groupId") or company.get("group_id")
            group_name = company.get("groupName") or company.get("group_name") or ""

            draft_entities.append({
                "draft_id": draft_id,
                "group_id": group_id,
                "group_name": group_name,
                "data": {
                    "name": company.get("name", ""),
                    "description": company.get("description") or "",
                    "emails": [{"value": company["email"], "type": "work", "isPrimary": True}] if company.get("email") else [],
                    "phoneNumbers": [{"value": company["phone"], "type": "work", "isPrimary": True}] if company.get("phone") else [],
                    "urls": [{"value": company["website"], "label": "Website", "isPrimary": True}] if company.get("website") else [],
                    "workspaceId": context.workspace_id,
                    "userId": context.user_id,
                    "groupId": group_id,
                },
            })

            if group_id:
                if group_id not in groups_summary:
                    groups_summary[group_id] = {"group_id": group_id, "group_name": group_name, "count": 0}
                groups_summary[group_id]["count"] += 1

        # ONE interrupt for all entities
        logger.info(f"[BATCH] Requesting batch confirmation for {len(draft_entities)} companies")
        confirmation = request_batch_create_confirmation(
            entity_type="company",
            draft_entities=draft_entities,
            groups_summary=list(groups_summary.values()),
        )
        logger.info(f"[BATCH] Confirmation received: confirmed={confirmation.confirmed}, accepted_entities={confirmation.accepted_entities}, rejected_entity_ids={confirmation.rejected_entity_ids}")

        if not confirmation.confirmed:
            logger.info("[BATCH] Confirmation was NOT confirmed, returning cancelled")
            return f"Cancelled. No companies were created."

        # Determine which entities to create
        accepted_ids = set()
        modified_map = {}
        if confirmation.accepted_entities:
            for ae in confirmation.accepted_entities:
                accepted_ids.add(ae["draft_id"])
                if ae.get("modified_data"):
                    modified_map[ae["draft_id"]] = ae["modified_data"]
        else:
            accepted_ids = {d["draft_id"] for d in draft_entities}

        rejected_ids = set(confirmation.rejected_entity_ids or [])
        accepted_ids -= rejected_ids

        logger.info(f"[BATCH] accepted_ids={accepted_ids}, rejected_ids={rejected_ids}, draft_entity_ids={[d['draft_id'] for d in draft_entities]}")

        if not accepted_ids:
            logger.info("[BATCH] No accepted IDs, returning rejected")
            return "All companies were rejected. No companies created."

        logger.info(f"[BATCH] Proceeding to create {len(accepted_ids)} companies")
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

        created = []
        result_parts = []
        try:
            for draft in draft_entities:
                if draft["draft_id"] not in accepted_ids:
                    continue

                entity_data = modified_map.get(draft["draft_id"]) or draft["data"]

                input_data = {
                    "name": entity_data["name"],
                    "workspaceId": entity_data.get("workspaceId", context.workspace_id),
                }
                if entity_data.get("description"):
                    input_data["description"] = entity_data["description"]
                if entity_data.get("emails"):
                    input_data["emails"] = entity_data["emails"]
                if entity_data.get("phoneNumbers"):
                    input_data["phoneNumbers"] = entity_data["phoneNumbers"]
                if entity_data.get("urls"):
                    input_data["urls"] = entity_data["urls"]

                group_id = entity_data.get("groupId") or draft.get("group_id")
                user_id = entity_data.get("userId", context.user_id)

                try:
                    logger.info(f"Creating company {draft['draft_id']}: name={input_data.get('name')}, groupId={group_id}")
                    client = context.get_client()
                    res = await client.mutate(mutation, {
                        "input": input_data,
                        "userId": user_id,
                        "groupId": group_id,
                    })
                    await client.close()
                    logger.info(f"Mutation result for {draft['draft_id']}: {res}")

                    company = res.get("createCompany")
                    if company:
                        created.append(company)
                        change = DataChange(
                            entity_type=EntityType.COMPANY,
                            action=ChangeAction.CREATED,
                            entity_id=company.get("id"),
                            group_id=group_id,
                            draft_id=draft["draft_id"],
                        )
                        result_parts.append(change.to_marker())
                    else:
                        logger.error(f"createCompany returned None for {draft['draft_id']}. Full response: {res}")
                except Exception as e:
                    logger.error(f"Error creating company {draft['draft_id']}: {e}", exc_info=True)

            summary = f"Successfully created {len(created)} of {len(accepted_ids)} companies."
            if rejected_ids:
                summary += f" {len(rejected_ids)} were rejected."
            return summary + "".join(result_parts)

        except Exception as e:
            logger.error(f"Error in create_companies_batch: {e}")
            return f"Error creating companies: {str(e)}"

    return [
        create_company,
        create_person,
        create_group,
        create_view_in_group,
        create_people_batch,
        create_companies_batch,
    ]

