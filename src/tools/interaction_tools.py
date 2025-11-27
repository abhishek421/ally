"""Interaction query tools for CRM."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access
from .database import get_db_session
from .models import Interaction

logger = get_logger(__name__)


class SearchInteractionsTool(Tool):
    """Search for interactions by content, type, date, or related entities."""

    @property
    def name(self) -> str:
        return "search_interactions"

    @property
    def description(self) -> str:
        return "Search for interactions by content, type, date, or related entities. Returns paginated results with summary."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "query": {"type": "string", "description": "Search in subject and content"},
                "type": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "EMAIL",
                            "CALENDAR",
                            "CALL",
                            "MEETING",
                            "NOTE",
                            "SMS",
                            "LINKEDIN_MESSAGE",
                            "SOCIAL_MEDIA",
                        ],
                    },
                    "description": "Filter by interaction types",
                },
                "direction": {
                    "type": "string",
                    "enum": ["INBOUND", "OUTBOUND", "both"],
                    "description": "Filter by direction (default: both)",
                },
                "person_id": {"type": "string", "description": "Filter by person UUID"},
                "company_id": {"type": "string", "description": "Filter by company UUID"},
                "created_by": {"type": "string", "description": "Filter by creator UUID"},
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "Start date (ISO format)"},
                        "end": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "description": "Filter by date range",
                },
                "has_content": {
                    "type": "boolean",
                    "description": "Only interactions with content (default: false)",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["date", "createdAt"],
                    "description": "Field to sort by",
                },
                "sort_order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order"},
                "limit": {"type": "integer", "description": "Maximum number of results (default: 20, max: 100)"},
                "offset": {"type": "integer", "description": "Offset for pagination (default: 0)"},
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        if not workspace_id:
            raise ValueError("workspace_id is required")

        logger.info("Searching interactions", workspace_id=workspace_id, query=kwargs.get("query"))

        # Parse date range if provided
        date_range = kwargs.get("date_range")
        parsed_date_range = None
        if date_range:
            parsed_date_range = {}
            if date_range.get("start"):
                parsed_date_range["start"] = datetime.fromisoformat(date_range["start"].replace("Z", "+00:00"))
            if date_range.get("end"):
                parsed_date_range["end"] = datetime.fromisoformat(date_range["end"].replace("Z", "+00:00"))

        data_access = get_data_access()
        return data_access.search_interactions(
            workspace_id=workspace_id,
            query=kwargs.get("query"),
            type=kwargs.get("type"),
            direction=kwargs.get("direction"),
            person_id=kwargs.get("person_id"),
            company_id=kwargs.get("company_id"),
            created_by=kwargs.get("created_by"),
            date_range=parsed_date_range,
            has_content=kwargs.get("has_content"),
            sort_by=kwargs.get("sort_by"),
            sort_order=kwargs.get("sort_order"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
        )


class GetInteractionByIdTool(Tool):
    """Get complete interaction details."""

    @property
    def name(self) -> str:
        return "get_interaction_by_id"

    @property
    def description(self) -> str:
        return "Get complete interaction details with optional related person, company, and deals."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "interaction_id": {"type": "string", "description": "Interaction UUID (required)"},
                "include": {
                    "type": "object",
                    "properties": {
                        "person": {"type": "boolean", "description": "Include related person"},
                        "company": {"type": "boolean", "description": "Include related company"},
                        "related_deals": {"type": "boolean", "description": "Include related deals"},
                    },
                    "description": "Optional data to include",
                },
            },
            "required": ["workspace_id", "interaction_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        interaction_id = kwargs.get("interaction_id")
        include = kwargs.get("include")

        if not workspace_id or not interaction_id:
            raise ValueError("workspace_id and interaction_id are required")

        logger.info("Getting interaction by ID", workspace_id=workspace_id, interaction_id=interaction_id)

        data_access = get_data_access()
        return data_access.get_interaction_by_id(
            workspace_id=workspace_id,
            interaction_id=interaction_id,
            include=include,
        )


class CreateNoteTool(Tool):
    """Create a note for a person or company."""

    @property
    def name(self) -> str:
        return "create_note"

    @property
    def description(self) -> str:
        return "Create a note for a person or company. Notes are a type of interaction that records important information, observations, or reminders about contacts."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "user_id": {"type": "string", "description": "User ID creating the note (required)"},
                "content": {"type": "string", "description": "The note content/body (required)"},
                "subject": {"type": "string", "description": "Optional subject/title for the note"},
                "person_id": {"type": "string", "description": "Person UUID to attach the note to"},
                "company_id": {"type": "string", "description": "Company UUID to attach the note to"},
            },
            "required": ["workspace_id", "user_id", "content"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        user_id = kwargs.get("user_id")
        content = kwargs.get("content")
        subject = kwargs.get("subject")
        person_id = kwargs.get("person_id")
        company_id = kwargs.get("company_id")

        if not workspace_id or not user_id or not content:
            raise ValueError("workspace_id, user_id, and content are required")

        if not person_id and not company_id:
            raise ValueError("Either person_id or company_id must be provided")

        logger.info(
            "Creating note",
            workspace_id=workspace_id,
            person_id=person_id,
            company_id=company_id,
        )

        try:
            with get_db_session() as session:
                note = Interaction(
                    workspaceId=UUID(workspace_id),
                    createdById=UUID(user_id),
                    type="NOTE",
                    direction="OUTBOUND",  # Notes are always outbound (created by user)
                    subject=subject,
                    content=content,
                    date=datetime.utcnow(),
                    peopleId=UUID(person_id) if person_id else None,
                    companyId=UUID(company_id) if company_id else None,
                    isDeleted=False,
                )
                session.add(note)
                session.commit()
                session.refresh(note)

                # Get the person/company name for the response
                entity_name = None
                if person_id and note.person:
                    entity_name = f"{note.person.firstName} {note.person.lastName or ''}".strip()
                elif company_id and note.company:
                    entity_name = note.company.name

                return {
                    "success": True,
                    "note_id": str(note.id),
                    "message": f"Note created successfully" + (f" for {entity_name}" if entity_name else ""),
                    "subject": note.subject,
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                    "created_at": note.createdAt.isoformat() if note.createdAt else None,
                }

        except Exception as e:
            logger.error("Failed to create note", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


class GetNotesTool(Tool):
    """Get notes for a person or company."""

    @property
    def name(self) -> str:
        return "get_notes"

    @property
    def description(self) -> str:
        return "Get all notes for a specific person or company. Returns notes sorted by date (most recent first)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "person_id": {"type": "string", "description": "Person UUID to get notes for"},
                "company_id": {"type": "string", "description": "Company UUID to get notes for"},
                "limit": {"type": "integer", "description": "Maximum number of notes to return (default: 20, max: 100)"},
                "offset": {"type": "integer", "description": "Offset for pagination (default: 0)"},
            },
            "required": ["workspace_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        person_id = kwargs.get("person_id")
        company_id = kwargs.get("company_id")
        limit = min(kwargs.get("limit", 20), 100)
        offset = kwargs.get("offset", 0)

        if not workspace_id:
            raise ValueError("workspace_id is required")

        if not person_id and not company_id:
            raise ValueError("Either person_id or company_id must be provided")

        logger.info(
            "Getting notes",
            workspace_id=workspace_id,
            person_id=person_id,
            company_id=company_id,
        )

        try:
            with get_db_session() as session:
                query = session.query(Interaction).filter(
                    Interaction.workspaceId == UUID(workspace_id),
                    Interaction.type == "NOTE",
                    Interaction.isDeleted == False,
                )

                if person_id:
                    query = query.filter(Interaction.peopleId == UUID(person_id))
                if company_id:
                    query = query.filter(Interaction.companyId == UUID(company_id))

                # Get total count
                total = query.count()

                # Get paginated results
                notes = query.order_by(Interaction.date.desc()).offset(offset).limit(limit).all()

                results = []
                for note in notes:
                    results.append({
                        "id": str(note.id),
                        "subject": note.subject,
                        "content": note.content,
                        "date": note.date.isoformat() if note.date else None,
                        "created_at": note.createdAt.isoformat() if note.createdAt else None,
                        "person_id": str(note.peopleId) if note.peopleId else None,
                        "company_id": str(note.companyId) if note.companyId else None,
                    })

                return {
                    "results": results,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(results) < total,
                }

        except Exception as e:
            logger.error("Failed to get notes", error=str(e))
            return {
                "results": [],
                "total": 0,
                "error": str(e),
            }


class UpdateNoteTool(Tool):
    """Update an existing note."""

    @property
    def name(self) -> str:
        return "update_note"

    @property
    def description(self) -> str:
        return "Update the content or subject of an existing note."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "note_id": {"type": "string", "description": "Note/Interaction UUID to update (required)"},
                "content": {"type": "string", "description": "New content for the note"},
                "subject": {"type": "string", "description": "New subject/title for the note"},
            },
            "required": ["workspace_id", "note_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        note_id = kwargs.get("note_id")
        content = kwargs.get("content")
        subject = kwargs.get("subject")

        if not workspace_id or not note_id:
            raise ValueError("workspace_id and note_id are required")

        if not content and subject is None:
            raise ValueError("At least one of content or subject must be provided")

        logger.info("Updating note", workspace_id=workspace_id, note_id=note_id)

        try:
            with get_db_session() as session:
                note = session.query(Interaction).filter(
                    Interaction.id == UUID(note_id),
                    Interaction.workspaceId == UUID(workspace_id),
                    Interaction.type == "NOTE",
                    Interaction.isDeleted == False,
                ).first()

                if not note:
                    return {
                        "success": False,
                        "error": "Note not found",
                    }

                if content is not None:
                    note.content = content
                if subject is not None:
                    note.subject = subject
                note.updatedAt = datetime.utcnow()

                session.commit()

                return {
                    "success": True,
                    "message": "Note updated successfully",
                    "note_id": str(note.id),
                    "subject": note.subject,
                    "content_preview": note.content[:100] + "..." if note.content and len(note.content) > 100 else note.content,
                }

        except Exception as e:
            logger.error("Failed to update note", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


class DeleteNoteTool(Tool):
    """Delete a note (soft delete)."""

    @property
    def name(self) -> str:
        return "delete_note"

    @property
    def description(self) -> str:
        return "Delete a note. This performs a soft delete, marking the note as deleted."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "note_id": {"type": "string", "description": "Note/Interaction UUID to delete (required)"},
            },
            "required": ["workspace_id", "note_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        note_id = kwargs.get("note_id")

        if not workspace_id or not note_id:
            raise ValueError("workspace_id and note_id are required")

        logger.info("Deleting note", workspace_id=workspace_id, note_id=note_id)

        try:
            with get_db_session() as session:
                note = session.query(Interaction).filter(
                    Interaction.id == UUID(note_id),
                    Interaction.workspaceId == UUID(workspace_id),
                    Interaction.type == "NOTE",
                    Interaction.isDeleted == False,
                ).first()

                if not note:
                    return {
                        "success": False,
                        "error": "Note not found",
                    }

                # Soft delete
                note.isDeleted = True
                note.updatedAt = datetime.utcnow()

                session.commit()

                return {
                    "success": True,
                    "message": "Note deleted successfully",
                }

        except Exception as e:
            logger.error("Failed to delete note", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

