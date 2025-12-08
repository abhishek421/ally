"""Write/Creation tools for CRM - Create and manipulate entities."""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_

from ..utils.logger import get_logger
from .base import Tool
from .database import get_db_session
from .models import (
    Person,
    Company,
    Group,
    GroupPeople,
    GroupCompany,
    MetaData,
    Email,
    PhoneNumber,
    CustomField,
    View,
    ColumnViewSetting,
    SelectOption,
    SelectOptionSetting,
    DefaultColumn,
    ProfileColumnViewSetting,
)

logger = get_logger(__name__)


# ==================== Person Creation Tools ====================

class CreatePersonTool(Tool):
    """Create a new person in the CRM."""

    @property
    def name(self) -> str:
        return "create_person"

    @property
    def description(self) -> str:
        return (
            "Create a new person/contact in the CRM. "
            "Requires first name. Can optionally include last name, job title, "
            "description, email, and phone number."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is creating this person (required)",
                },
                "first_name": {
                    "type": "string",
                    "description": "Person's first name (required)",
                },
                "last_name": {
                    "type": "string",
                    "description": "Person's last name (optional)",
                },
                "job_title": {
                    "type": "string",
                    "description": "Person's job title (optional)",
                },
                "description": {
                    "type": "string",
                    "description": "Description or notes about the person (optional)",
                },
                "email": {
                    "type": "string",
                    "description": "Person's primary email address (optional)",
                },
                "phone": {
                    "type": "string",
                    "description": "Person's primary phone number (optional)",
                },
                "privacy_level": {
                    "type": "string",
                    "enum": ["PRIVATE", "PUBLIC"],
                    "description": "Privacy level (default: PRIVATE)",
                },
            },
            "required": ["workspace_id", "user_id", "first_name"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        first_name = kwargs.get("first_name")

        if not workspace_id or not user_id or not first_name:
            raise ValueError("workspace_id, user_id, and first_name are required")

        logger.info(
            "Creating person",
            workspace_id=workspace_id,
            first_name=first_name,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)

            with get_db_session() as session:
                # Create person
                person = Person(
                    id=uuid4(),
                    firstName=first_name,
                    lastName=kwargs.get("last_name"),
                    jobTitle=kwargs.get("job_title"),
                    description=kwargs.get("description"),
                    privacyLevel=kwargs.get("privacy_level", "PRIVATE"),
                    workspaceId=workspace_uuid,
                    createdBy=user_uuid,
                )
                session.add(person)
                session.flush()  # Get the ID

                person_id = str(person.id)

                # Add email if provided
                if kwargs.get("email"):
                    email = Email(
                        id=uuid4(),
                        value=kwargs["email"],
                        type="work",
                        isPrimary=True,
                        personId=person.id,
                    )
                    session.add(email)

                # Add phone if provided
                if kwargs.get("phone"):
                    phone = PhoneNumber(
                        id=uuid4(),
                        value=kwargs["phone"],
                        type="work",
                        isPrimary=True,
                        personId=person.id,
                    )
                    session.add(phone)

                session.commit()

                return {
                    "success": True,
                    "person_id": person_id,
                    "message": f"Successfully created person: {first_name} {kwargs.get('last_name', '')}".strip(),
                    "person": {
                        "id": person_id,
                        "firstName": first_name,
                        "lastName": kwargs.get("last_name"),
                        "jobTitle": kwargs.get("job_title"),
                        "email": kwargs.get("email"),
                        "phone": kwargs.get("phone"),
                    },
                }

        except Exception as e:
            logger.error("Failed to create person", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create person: {str(e)}",
            }


# ==================== Company Creation Tools ====================

class CreateCompanyTool(Tool):
    """Create a new company in the CRM."""

    @property
    def name(self) -> str:
        return "create_company"

    @property
    def description(self) -> str:
        return (
            "Create a new company/organization in the CRM. "
            "Requires company name. Can optionally include description, email, and phone."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is creating this company (required)",
                },
                "name": {
                    "type": "string",
                    "description": "Company name (required)",
                },
                "description": {
                    "type": "string",
                    "description": "Description or notes about the company (optional)",
                },
                "email": {
                    "type": "string",
                    "description": "Company's primary email address (optional)",
                },
                "phone": {
                    "type": "string",
                    "description": "Company's primary phone number (optional)",
                },
                "privacy_level": {
                    "type": "string",
                    "enum": ["PRIVATE", "PUBLIC"],
                    "description": "Privacy level (default: PRIVATE)",
                },
            },
            "required": ["workspace_id", "user_id", "name"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        name = kwargs.get("name")

        if not workspace_id or not user_id or not name:
            raise ValueError("workspace_id, user_id, and name are required")

        logger.info(
            "Creating company",
            workspace_id=workspace_id,
            name=name,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)

            with get_db_session() as session:
                # Create company
                company = Company(
                    id=uuid4(),
                    name=name,
                    description=kwargs.get("description"),
                    privacyLevel=kwargs.get("privacy_level", "PRIVATE"),
                    workspaceId=workspace_uuid,
                    createdBy=user_uuid,
                )
                session.add(company)
                session.flush()

                company_id = str(company.id)

                # Add email if provided
                if kwargs.get("email"):
                    email = Email(
                        id=uuid4(),
                        value=kwargs["email"],
                        type="work",
                        isPrimary=True,
                        companyId=company.id,
                    )
                    session.add(email)

                # Add phone if provided
                if kwargs.get("phone"):
                    phone = PhoneNumber(
                        id=uuid4(),
                        value=kwargs["phone"],
                        type="work",
                        isPrimary=True,
                        companyId=company.id,
                    )
                    session.add(phone)

                session.commit()

                return {
                    "success": True,
                    "company_id": company_id,
                    "message": f"Successfully created company: {name}",
                    "company": {
                        "id": company_id,
                        "name": name,
                        "description": kwargs.get("description"),
                        "email": kwargs.get("email"),
                        "phone": kwargs.get("phone"),
                    },
                }

        except Exception as e:
            logger.error("Failed to create company", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create company: {str(e)}",
            }


# ==================== Group Creation Tools ====================

class CreateGroupTool(Tool):
    """Create a new group in the CRM."""

    @property
    def name(self) -> str:
        return "create_group"

    @property
    def description(self) -> str:
        return (
            "Create a new group to organize people or companies. "
            "Groups can be of type PEOPLE or COMPANY. "
            "Use this to create lists, segments, or collections."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is creating this group (required)",
                },
                "name": {
                    "type": "string",
                    "description": "Group name (required)",
                },
                "type": {
                    "type": "string",
                    "enum": ["PEOPLE", "COMPANY"],
                    "description": "Type of entities this group will contain (required)",
                },
                "description": {
                    "type": "string",
                    "description": "Description of the group's purpose (optional)",
                },
                "emoji": {
                    "type": "string",
                    "description": "Emoji icon for the group (optional)",
                },
                "is_private": {
                    "type": "boolean",
                    "description": "Whether the group is private (default: true)",
                },
            },
            "required": ["workspace_id", "user_id", "name", "type"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        name = kwargs.get("name")
        group_type = kwargs.get("type")

        if not workspace_id or not user_id or not name or not group_type:
            raise ValueError("workspace_id, user_id, name, and type are required")

        if group_type not in ["PEOPLE", "COMPANY"]:
            raise ValueError("type must be either 'PEOPLE' or 'COMPANY'")

        logger.info(
            "Creating group",
            workspace_id=workspace_id,
            name=name,
            type=group_type,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)

            with get_db_session() as session:
                # Create the group
                group = Group(
                    id=uuid4(),
                    name=name,
                    type=group_type,
                    description=kwargs.get("description"),
                    emoji=kwargs.get("emoji"),
                    isPrivate=kwargs.get("is_private", True),
                    isFavourite=False,
                    isDeleted=False,
                    isCollapse=True,
                    workspaceId=workspace_uuid,
                    createdBy=user_uuid,
                    favouriteOrder=0,
                    privateOrder=0,
                    publicOrder=0,
                )
                session.add(group)
                session.flush()  # Flush to get the group ID

                # Get default columns for this group type
                default_columns = session.query(DefaultColumn).filter(
                    DefaultColumn.type == group_type
                ).order_by(DefaultColumn.order).all()

                if not default_columns:
                    logger.warning(f"No default columns found for group type {group_type}")

                # Create Status column
                status_column = CustomField(
                    id=uuid4(),
                    name="Status",
                    description=f"Status of {group_type}",
                    dataType="SELECT",
                    type=group_type,
                    isDefault=False,
                    isDeleted=False,
                    groupId=group.id,
                    dealId=None,
                    selectOptions=None,
                )
                session.add(status_column)
                session.flush()

                # Create select options for Status column
                status_options = [
                    {"value": "No Status", "color": "#c378fd", "order": 1, "pipelineOrder": 1},
                    {"value": "Lead", "color": "#50fdac", "order": 2, "pipelineOrder": 2},
                    {"value": "Qualified", "color": "#ff5361", "order": 3, "pipelineOrder": 3},
                    {"value": "Follow-up", "color": "#fdcb22", "order": 4, "pipelineOrder": 4},
                    {"value": "Closed-lost", "color": "#ffffff", "order": 5, "pipelineOrder": 5},
                    {"value": "Closed-won", "color": "#fd62c8", "order": 6, "pipelineOrder": 6},
                ]

                for option_data in status_options:
                    select_option = SelectOption(
                        id=uuid4(),
                        value=option_data["value"],
                        color=option_data["color"],
                        order=option_data["order"],
                        pipelineOrder=option_data["pipelineOrder"],
                        columnId=status_column.id,
                    )
                    session.add(select_option)

                # Determine view names based on group type
                if group_type == "PEOPLE":
                    table_view_name = "All People"
                    target_entity = "PEOPLE"
                else:  # COMPANY
                    table_view_name = "All Company"
                    target_entity = "COMPANY"

                # Create views: Pipeline and Table
                views_to_create = [
                    {"name": "Pipeline", "type": "PIPELINE", "groupBy": str(status_column.id)},
                    {"name": table_view_name, "type": "TABLE", "groupBy": None},
                ]

                created_views = []
                for view_data in views_to_create:
                    view = View(
                        id=uuid4(),
                        name=view_data["name"],
                        type=view_data["type"],
                        isDefault=True,
                        groupId=group.id,
                        workspaceId=workspace_uuid,
                        targetEntity=target_entity,
                        groupBy=view_data["groupBy"],
                        order=100,
                        dealColumnId=None,
                        isDeleted=False,
                        condition=None,
                        aggregateType=None,
                        groupColumnId=None,
                    )
                    session.add(view)
                    session.flush()
                    created_views.append(view)

                    # Create column view settings for each view
                    # Add default columns
                    for default_col in default_columns:
                        col_view_setting = ColumnViewSetting(
                            id=uuid4(),
                            order=default_col.order,
                            isVisible=default_col.isVisible,
                            width=default_col.width,
                            columnId=None,
                            viewId=view.id,
                            defaultColumnId=default_col.id,
                            isDeleted=False,
                        )
                        session.add(col_view_setting)

                    # Add Status column
                    if default_columns:
                        last_order = max([dc.order for dc in default_columns])
                    else:
                        last_order = 0
                    
                    status_col_setting = ColumnViewSetting(
                        id=uuid4(),
                        order=last_order + 100,
                        isVisible=True,
                        width=100,
                        columnId=status_column.id,
                        viewId=view.id,
                        defaultColumnId=None,
                        isDeleted=False,
                    )
                    session.add(status_col_setting)

                    # Create select option settings for Pipeline view
                    if view_data["type"] == "PIPELINE":
                        for option_data in status_options:
                            # Find the select option we just created
                            select_option = session.query(SelectOption).filter(
                                SelectOption.columnId == status_column.id,
                                SelectOption.value == option_data["value"]
                            ).first()
                            
                            if select_option:
                                select_option_setting = SelectOptionSetting(
                                    id=uuid4(),
                                    selectOptionId=select_option.id,
                                    viewId=view.id,
                                    isVisible=True,
                                    pipelineOrder=option_data["pipelineOrder"],
                                    columnId=status_column.id,
                                )
                                session.add(select_option_setting)

                # Create profile column view settings
                # Get all default columns (without type filter for profile)
                all_default_columns = session.query(DefaultColumn).filter(
                    DefaultColumn.type == group_type
                ).order_by(DefaultColumn.order).all()

                for default_col in all_default_columns:
                    profile_setting = ProfileColumnViewSetting(
                        id=uuid4(),
                        order=default_col.order,
                        isVisible=default_col.isVisible,
                        columnId=None,
                        groupId=group.id,
                        defaultColumnId=default_col.id,
                        type=target_entity,
                    )
                    session.add(profile_setting)

                # Add Status column to profile settings
                if all_default_columns:
                    last_profile_order = max([dc.order for dc in all_default_columns])
                else:
                    last_profile_order = 0

                status_profile_setting = ProfileColumnViewSetting(
                    id=uuid4(),
                    order=last_profile_order + 100,
                    isVisible=True,
                    columnId=status_column.id,
                    groupId=group.id,
                    defaultColumnId=None,
                    type=target_entity,
                )
                session.add(status_profile_setting)

                # Commit all changes
                session.commit()

                return {
                    "success": True,
                    "group_id": str(group.id),
                    "message": f"Successfully created group: {name} with default views",
                    "group": {
                        "id": str(group.id),
                        "name": name,
                        "type": group_type,
                        "description": kwargs.get("description"),
                        "emoji": kwargs.get("emoji"),
                        "isPrivate": kwargs.get("is_private", True),
                    },
                    "views_created": [{"id": str(v.id), "name": v.name, "type": v.type} for v in created_views],
                }

        except Exception as e:
            logger.error("Failed to create group", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create group: {str(e)}",
            }


# ==================== View Creation Tools ====================

class CreateViewTool(Tool):
    """Create a new view in a group."""

    @property
    def name(self) -> str:
        return "create_view"

    @property
    def description(self) -> str:
        return (
            "Create a new view in a group. Views can be of type TABLE, PIPELINE, KANBAN, or CALENDAR. "
            "Views organize how data is displayed in a group. "
            "For PIPELINE views, you can specify a groupBy column ID to group by."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group ID where the view will be created (required)",
                },
                "name": {
                    "type": "string",
                    "description": "View name (required)",
                },
                "type": {
                    "type": "string",
                    "enum": ["TABLE", "PIPELINE", "KANBAN", "CALENDAR"],
                    "description": "Type of view (required)",
                },
                "target_entity": {
                    "type": "string",
                    "enum": ["PEOPLE", "COMPANY", "DEAL"],
                    "description": "Target entity type for the view (required)",
                },
                "is_default": {
                    "type": "boolean",
                    "description": "Whether this is the default view (default: false)",
                },
                "group_by": {
                    "type": "string",
                    "description": "Column ID to group by (optional, typically for PIPELINE views)",
                },
                "deal_column_id": {
                    "type": "string",
                    "description": "Deal column ID (optional, required for DEAL target entity)",
                },
            },
            "required": ["workspace_id", "group_id", "name", "type", "target_entity"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        group_id = kwargs.get("group_id")
        name = kwargs.get("name")
        view_type = kwargs.get("type")
        target_entity = kwargs.get("target_entity")
        is_default = kwargs.get("is_default", False)
        group_by = kwargs.get("group_by")
        deal_column_id = kwargs.get("deal_column_id")

        if not workspace_id or not group_id or not name or not view_type or not target_entity:
            raise ValueError("workspace_id, group_id, name, type, and target_entity are required")

        if view_type not in ["TABLE", "PIPELINE", "KANBAN", "CALENDAR"]:
            raise ValueError("type must be one of: TABLE, PIPELINE, KANBAN, CALENDAR")

        if target_entity not in ["PEOPLE", "COMPANY", "DEAL"]:
            raise ValueError("target_entity must be one of: PEOPLE, COMPANY, DEAL")

        if target_entity == "DEAL" and not deal_column_id:
            raise ValueError("deal_column_id is required when target_entity is DEAL")

        logger.info(
            "Creating view",
            workspace_id=workspace_id,
            group_id=group_id,
            name=name,
            type=view_type,
            target_entity=target_entity,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            group_uuid = UUID(group_id)

            with get_db_session() as session:
                # Verify group exists
                group = session.query(Group).filter(
                    Group.id == group_uuid,
                    Group.workspaceId == workspace_uuid,
                    Group.isDeleted == False
                ).first()

                if not group:
                    raise ValueError(f"Group with ID {group_id} not found in workspace {workspace_id}")

                # Create the view
                view = View(
                    id=uuid4(),
                    name=name,
                    type=view_type,
                    isDefault=is_default,
                    groupId=group_uuid,
                    workspaceId=workspace_uuid,
                    targetEntity=target_entity,
                    groupBy=group_by,
                    order=100,
                    dealColumnId=UUID(deal_column_id) if deal_column_id else None,
                    isDeleted=False,
                    condition=None,
                    aggregateType=None,
                    groupColumnId=None,
                )
                session.add(view)
                session.flush()

                # Get default columns for the target entity
                default_columns = session.query(DefaultColumn).filter(
                    DefaultColumn.type == target_entity
                ).order_by(DefaultColumn.order).all()

                if not default_columns:
                    logger.warning(f"No default columns found for target entity {target_entity}")

                # Get existing custom columns for this group and target entity
                # Note: We need to match columns by type, but CustomField.type uses group type
                # For PEOPLE/COMPANY groups, columns have type PEOPLE/COMPANY
                # For DEAL views, we need to handle differently
                existing_columns = []
                if target_entity != "DEAL":
                    existing_columns = session.query(CustomField).filter(
                        CustomField.groupId == group_uuid,
                        CustomField.type == target_entity,
                        CustomField.isDeleted == False
                    ).all()

                # Build column view settings
                column_view_settings = []

                # Add default column settings
                for default_col in default_columns:
                    col_view_setting = ColumnViewSetting(
                        id=uuid4(),
                        order=default_col.order,
                        isVisible=default_col.isVisible,
                        width=default_col.width,
                        columnId=None,
                        viewId=view.id,
                        defaultColumnId=default_col.id,
                        isDeleted=False,
                    )
                    column_view_settings.append(col_view_setting)
                    session.add(col_view_setting)

                # Add custom column settings
                if default_columns:
                    base_order = len(default_columns) * 100 + 100
                else:
                    base_order = 100

                for index, custom_col in enumerate(existing_columns):
                    col_view_setting = ColumnViewSetting(
                        id=uuid4(),
                        order=base_order + (index * 100),
                        isVisible=True,
                        width=100,  # Default width
                        columnId=custom_col.id,
                        viewId=view.id,
                        defaultColumnId=None,
                        isDeleted=False,
                    )
                    column_view_settings.append(col_view_setting)
                    session.add(col_view_setting)

                # For PIPELINE views with groupBy, create select option settings
                if view_type == "PIPELINE" and group_by:
                    try:
                        group_by_uuid = UUID(group_by)
                        # Find the groupBy column
                        group_by_column = session.query(CustomField).filter(
                            CustomField.id == group_by_uuid,
                            CustomField.groupId == group_uuid,
                            CustomField.isDeleted == False
                        ).first()

                        if group_by_column and group_by_column.dataType == "SELECT":
                            # Get all select options for this column
                            select_options = session.query(SelectOption).filter(
                                SelectOption.columnId == group_by_uuid
                            ).order_by(SelectOption.pipelineOrder).all()

                            # Create select option settings for each option
                            for select_option in select_options:
                                select_option_setting = SelectOptionSetting(
                                    id=uuid4(),
                                    selectOptionId=select_option.id,
                                    viewId=view.id,
                                    isVisible=True,
                                    pipelineOrder=select_option.pipelineOrder or select_option.order,
                                    columnId=group_by_uuid,
                                )
                                session.add(select_option_setting)
                    except (ValueError, Exception) as e:
                        logger.warning(f"Could not create select option settings for groupBy column: {e}")

                session.commit()

                return {
                    "success": True,
                    "view_id": str(view.id),
                    "message": f"Successfully created view: {name}",
                    "view": {
                        "id": str(view.id),
                        "name": name,
                        "type": view_type,
                        "targetEntity": target_entity,
                        "isDefault": is_default,
                        "groupId": group_id,
                    },
                }

        except Exception as e:
            logger.error("Failed to create view", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create view: {str(e)}",
            }


# ==================== Relationship Tools ====================

class AddPersonToCompanyTool(Tool):
    """Add a person to a company (create person-company relationship)."""

    @property
    def name(self) -> str:
        return "add_person_to_company"

    @property
    def description(self) -> str:
        return (
            "Link a person to a company, establishing an employment or association relationship. "
            "Can optionally set this as the person's primary company or the company's primary contact."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "person_id": {
                    "type": "string",
                    "description": "Person UUID to add (required)",
                },
                "company_id": {
                    "type": "string",
                    "description": "Company UUID to add person to (required)",
                },
                "is_primary_company": {
                    "type": "boolean",
                    "description": "Set this as the person's primary company (default: false)",
                },
                "is_primary_contact": {
                    "type": "boolean",
                    "description": "Set this person as the company's primary contact (default: false)",
                },
            },
            "required": ["workspace_id", "person_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        company_id = kwargs.get("company_id")

        if not workspace_id or not person_id or not company_id:
            raise ValueError("workspace_id, person_id, and company_id are required")

        logger.info(
            "Adding person to company",
            person_id=person_id,
            company_id=company_id,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            person_uuid = UUID(person_id)
            company_uuid = UUID(company_id)

            with get_db_session() as session:
                # Verify person exists in workspace
                person = session.query(Person).filter(
                    and_(
                        Person.id == person_uuid,
                        Person.workspaceId == workspace_uuid,
                    )
                ).first()
                if not person:
                    return {
                        "success": False,
                        "error": "Person not found in workspace",
                        "message": "The specified person was not found in this workspace",
                    }

                # Verify company exists in workspace
                company = session.query(Company).filter(
                    and_(
                        Company.id == company_uuid,
                        Company.workspaceId == workspace_uuid,
                    )
                ).first()
                if not company:
                    return {
                        "success": False,
                        "error": "Company not found in workspace",
                        "message": "The specified company was not found in this workspace",
                    }

                # Check if relationship already exists
                existing = session.query(MetaData).filter(
                    and_(
                        MetaData.peopleId == person_uuid,
                        MetaData.companyId == company_uuid,
                    )
                ).first()

                if existing:
                    # Update existing relationship
                    if kwargs.get("is_primary_company"):
                        existing.isPeoplePrimary = True
                    if kwargs.get("is_primary_contact"):
                        existing.isCompanyPrimary = True
                    session.commit()
                    return {
                        "success": True,
                        "message": f"Updated relationship: {person.firstName} is already linked to {company.name}",
                        "already_existed": True,
                    }

                # Create new relationship
                metadata = MetaData(
                    id=uuid4(),
                    peopleId=person_uuid,
                    companyId=company_uuid,
                    isPeoplePrimary=kwargs.get("is_primary_company", False),
                    isCompanyPrimary=kwargs.get("is_primary_contact", False),
                )
                session.add(metadata)
                session.commit()

                return {
                    "success": True,
                    "message": f"Successfully linked {person.firstName} {person.lastName or ''} to {company.name}".strip(),
                    "relationship": {
                        "person_id": person_id,
                        "person_name": f"{person.firstName} {person.lastName or ''}".strip(),
                        "company_id": company_id,
                        "company_name": company.name,
                        "is_primary_company": kwargs.get("is_primary_company", False),
                        "is_primary_contact": kwargs.get("is_primary_contact", False),
                    },
                }

        except Exception as e:
            logger.error("Failed to add person to company", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add person to company: {str(e)}",
            }


class AddPersonToGroupTool(Tool):
    """Add a person to a group."""

    @property
    def name(self) -> str:
        return "add_person_to_group"

    @property
    def description(self) -> str:
        return (
            "Add a person to a PEOPLE type group. "
            "Use this to organize contacts into lists or segments."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is adding this person (required)",
                },
                "person_id": {
                    "type": "string",
                    "description": "Person UUID to add (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group UUID to add person to (required)",
                },
            },
            "required": ["workspace_id", "user_id", "person_id", "group_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        person_id = kwargs.get("person_id")
        group_id = kwargs.get("group_id")

        if not workspace_id or not user_id or not person_id or not group_id:
            raise ValueError("workspace_id, user_id, person_id, and group_id are required")

        logger.info(
            "Adding person to group",
            person_id=person_id,
            group_id=group_id,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)
            person_uuid = UUID(person_id)
            group_uuid = UUID(group_id)

            with get_db_session() as session:
                # Verify person exists in workspace
                person = session.query(Person).filter(
                    and_(
                        Person.id == person_uuid,
                        Person.workspaceId == workspace_uuid,
                    )
                ).first()
                if not person:
                    return {
                        "success": False,
                        "error": "Person not found in workspace",
                        "message": "The specified person was not found in this workspace",
                    }

                # Verify group exists and is PEOPLE type
                group = session.query(Group).filter(
                    and_(
                        Group.id == group_uuid,
                        Group.workspaceId == workspace_uuid,
                        Group.isDeleted == False,
                    )
                ).first()
                if not group:
                    return {
                        "success": False,
                        "error": "Group not found in workspace",
                        "message": "The specified group was not found in this workspace",
                    }
                if group.type != "PEOPLE":
                    return {
                        "success": False,
                        "error": "Invalid group type",
                        "message": f"Cannot add a person to a {group.type} group. The group must be of type PEOPLE.",
                    }

                # Check if already in group
                existing = session.query(GroupPeople).filter(
                    and_(
                        GroupPeople.groupId == group_uuid,
                        GroupPeople.peopleId == person_uuid,
                    )
                ).first()

                if existing:
                    return {
                        "success": True,
                        "message": f"{person.firstName} is already in group '{group.name}'",
                        "already_existed": True,
                    }

                # Add to group
                group_people = GroupPeople(
                    groupId=group_uuid,
                    peopleId=person_uuid,
                    addedBy=user_uuid,
                )
                session.add(group_people)
                session.commit()

                return {
                    "success": True,
                    "message": f"Successfully added {person.firstName} {person.lastName or ''} to group '{group.name}'".strip(),
                    "membership": {
                        "person_id": person_id,
                        "person_name": f"{person.firstName} {person.lastName or ''}".strip(),
                        "group_id": group_id,
                        "group_name": group.name,
                    },
                }

        except Exception as e:
            logger.error("Failed to add person to group", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add person to group: {str(e)}",
            }


class AddCompanyToGroupTool(Tool):
    """Add a company to a group."""

    @property
    def name(self) -> str:
        return "add_company_to_group"

    @property
    def description(self) -> str:
        return (
            "Add a company to a COMPANY type group. "
            "Use this to organize companies into lists or segments."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is adding this company (required)",
                },
                "company_id": {
                    "type": "string",
                    "description": "Company UUID to add (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group UUID to add company to (required)",
                },
            },
            "required": ["workspace_id", "user_id", "company_id", "group_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        company_id = kwargs.get("company_id")
        group_id = kwargs.get("group_id")

        if not workspace_id or not user_id or not company_id or not group_id:
            raise ValueError("workspace_id, user_id, company_id, and group_id are required")

        logger.info(
            "Adding company to group",
            company_id=company_id,
            group_id=group_id,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)
            company_uuid = UUID(company_id)
            group_uuid = UUID(group_id)

            with get_db_session() as session:
                # Verify company exists in workspace
                company = session.query(Company).filter(
                    and_(
                        Company.id == company_uuid,
                        Company.workspaceId == workspace_uuid,
                    )
                ).first()
                if not company:
                    return {
                        "success": False,
                        "error": "Company not found in workspace",
                        "message": "The specified company was not found in this workspace",
                    }

                # Verify group exists and is COMPANY type
                group = session.query(Group).filter(
                    and_(
                        Group.id == group_uuid,
                        Group.workspaceId == workspace_uuid,
                        Group.isDeleted == False,
                    )
                ).first()
                if not group:
                    return {
                        "success": False,
                        "error": "Group not found in workspace",
                        "message": "The specified group was not found in this workspace",
                    }
                if group.type != "COMPANY":
                    return {
                        "success": False,
                        "error": "Invalid group type",
                        "message": f"Cannot add a company to a {group.type} group. The group must be of type COMPANY.",
                    }

                # Check if already in group
                existing = session.query(GroupCompany).filter(
                    and_(
                        GroupCompany.groupId == group_uuid,
                        GroupCompany.companyId == company_uuid,
                    )
                ).first()

                if existing:
                    return {
                        "success": True,
                        "message": f"{company.name} is already in group '{group.name}'",
                        "already_existed": True,
                    }

                # Add to group
                group_company = GroupCompany(
                    groupId=group_uuid,
                    companyId=company_uuid,
                    addedBy=user_uuid,
                )
                session.add(group_company)
                session.commit()

                return {
                    "success": True,
                    "message": f"Successfully added {company.name} to group '{group.name}'",
                    "membership": {
                        "company_id": company_id,
                        "company_name": company.name,
                        "group_id": group_id,
                        "group_name": group.name,
                    },
                }

        except Exception as e:
            logger.error("Failed to add company to group", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add company to group: {str(e)}",
            }


# ==================== Bulk Operations ====================

class AddMultiplePeopleToGroupTool(Tool):
    """Add multiple people to a group at once."""

    @property
    def name(self) -> str:
        return "add_multiple_people_to_group"

    @property
    def description(self) -> str:
        return (
            "Add multiple people to a PEOPLE type group in a single operation. "
            "Useful for bulk organizing contacts."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is adding these people (required)",
                },
                "person_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of person UUIDs to add (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group UUID to add people to (required)",
                },
            },
            "required": ["workspace_id", "user_id", "person_ids", "group_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        person_ids = kwargs.get("person_ids", [])
        group_id = kwargs.get("group_id")

        if not workspace_id or not user_id or not person_ids or not group_id:
            raise ValueError("workspace_id, user_id, person_ids, and group_id are required")

        if not isinstance(person_ids, list) or len(person_ids) == 0:
            raise ValueError("person_ids must be a non-empty list")

        logger.info(
            "Adding multiple people to group",
            count=len(person_ids),
            group_id=group_id,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)
            group_uuid = UUID(group_id)

            with get_db_session() as session:
                # Verify group exists and is PEOPLE type
                group = session.query(Group).filter(
                    and_(
                        Group.id == group_uuid,
                        Group.workspaceId == workspace_uuid,
                        Group.isDeleted == False,
                    )
                ).first()
                if not group:
                    return {
                        "success": False,
                        "error": "Group not found",
                        "message": "The specified group was not found in this workspace",
                    }
                if group.type != "PEOPLE":
                    return {
                        "success": False,
                        "error": "Invalid group type",
                        "message": f"Cannot add people to a {group.type} group",
                    }

                added = []
                skipped = []
                failed = []

                for pid in person_ids:
                    try:
                        person_uuid = UUID(pid)

                        # Check if person exists
                        person = session.query(Person).filter(
                            and_(
                                Person.id == person_uuid,
                                Person.workspaceId == workspace_uuid,
                            )
                        ).first()

                        if not person:
                            failed.append({"id": pid, "reason": "Person not found"})
                            continue

                        # Check if already in group
                        existing = session.query(GroupPeople).filter(
                            and_(
                                GroupPeople.groupId == group_uuid,
                                GroupPeople.peopleId == person_uuid,
                            )
                        ).first()

                        if existing:
                            skipped.append({
                                "id": pid,
                                "name": f"{person.firstName} {person.lastName or ''}".strip(),
                            })
                            continue

                        # Add to group
                        group_people = GroupPeople(
                            groupId=group_uuid,
                            peopleId=person_uuid,
                            addedBy=user_uuid,
                        )
                        session.add(group_people)
                        added.append({
                            "id": pid,
                            "name": f"{person.firstName} {person.lastName or ''}".strip(),
                        })

                    except ValueError:
                        failed.append({"id": pid, "reason": "Invalid UUID"})

                session.commit()

                return {
                    "success": True,
                    "message": f"Added {len(added)} people to group '{group.name}'",
                    "summary": {
                        "added_count": len(added),
                        "skipped_count": len(skipped),
                        "failed_count": len(failed),
                    },
                    "added": added,
                    "skipped": skipped,
                    "failed": failed,
                }

        except Exception as e:
            logger.error("Failed to add multiple people to group", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add people to group: {str(e)}",
            }


class AddMultipleCompaniesToGroupTool(Tool):
    """Add multiple companies to a group at once."""

    @property
    def name(self) -> str:
        return "add_multiple_companies_to_group"

    @property
    def description(self) -> str:
        return (
            "Add multiple companies to a COMPANY type group in a single operation. "
            "Useful for bulk organizing companies."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier (required)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID of who is adding these companies (required)",
                },
                "company_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of company UUIDs to add (required)",
                },
                "group_id": {
                    "type": "string",
                    "description": "Group UUID to add companies to (required)",
                },
            },
            "required": ["workspace_id", "user_id", "company_ids", "group_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        company_ids = kwargs.get("company_ids", [])
        group_id = kwargs.get("group_id")

        if not workspace_id or not user_id or not company_ids or not group_id:
            raise ValueError("workspace_id, user_id, company_ids, and group_id are required")

        if not isinstance(company_ids, list) or len(company_ids) == 0:
            raise ValueError("company_ids must be a non-empty list")

        logger.info(
            "Adding multiple companies to group",
            count=len(company_ids),
            group_id=group_id,
        )

        try:
            workspace_uuid = UUID(workspace_id)
            user_uuid = UUID(user_id)
            group_uuid = UUID(group_id)

            with get_db_session() as session:
                # Verify group exists and is COMPANY type
                group = session.query(Group).filter(
                    and_(
                        Group.id == group_uuid,
                        Group.workspaceId == workspace_uuid,
                        Group.isDeleted == False,
                    )
                ).first()
                if not group:
                    return {
                        "success": False,
                        "error": "Group not found",
                        "message": "The specified group was not found in this workspace",
                    }
                if group.type != "COMPANY":
                    return {
                        "success": False,
                        "error": "Invalid group type",
                        "message": f"Cannot add companies to a {group.type} group",
                    }

                added = []
                skipped = []
                failed = []

                for cid in company_ids:
                    try:
                        company_uuid = UUID(cid)

                        # Check if company exists
                        company = session.query(Company).filter(
                            and_(
                                Company.id == company_uuid,
                                Company.workspaceId == workspace_uuid,
                            )
                        ).first()

                        if not company:
                            failed.append({"id": cid, "reason": "Company not found"})
                            continue

                        # Check if already in group
                        existing = session.query(GroupCompany).filter(
                            and_(
                                GroupCompany.groupId == group_uuid,
                                GroupCompany.companyId == company_uuid,
                            )
                        ).first()

                        if existing:
                            skipped.append({"id": cid, "name": company.name})
                            continue

                        # Add to group
                        group_company = GroupCompany(
                            groupId=group_uuid,
                            companyId=company_uuid,
                            addedBy=user_uuid,
                        )
                        session.add(group_company)
                        added.append({"id": cid, "name": company.name})

                    except ValueError:
                        failed.append({"id": cid, "reason": "Invalid UUID"})

                session.commit()

                return {
                    "success": True,
                    "message": f"Added {len(added)} companies to group '{group.name}'",
                    "summary": {
                        "added_count": len(added),
                        "skipped_count": len(skipped),
                        "failed_count": len(failed),
                    },
                    "added": added,
                    "skipped": skipped,
                    "failed": failed,
                }

        except Exception as e:
            logger.error("Failed to add multiple companies to group", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add companies to group: {str(e)}",
            }

