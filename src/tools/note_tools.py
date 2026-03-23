"""NOTE tools for creating, reading, updating, and deleting notes."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.context_var import get_tool_context
from src.tools.base import (
    ToolContext,
    DataChange,
    EntityType as ToolEntityType,
    ChangeAction,
)
from src.tools.confirmation import (
    request_create_confirmation,
    request_delete_confirmation,
    request_update_confirmation,
)

logger = logging.getLogger(__name__)


# Note entity type enum matching backend
NOTE_ENTITY_TYPES = ["PEOPLE", "COMPANY", "PERSON"]


def format_note(note: dict) -> str:
    """Format a note dict for display.
    
    Args:
        note: Note data from GraphQL
        
    Returns:
        Formatted string representation
    """
    note_id = note.get("id", "N/A")
    content = note.get("content", "No content")
    entity_type = note.get("entityType", "Unknown")
    is_private = note.get("isPrivate", False)
    created_at = note.get("createdAt", "Unknown")
    
    # Get creator info if available
    creator = note.get("creator", {})
    creator_name = ""
    if creator:
        first = creator.get("firstName", "")
        last = creator.get("lastName", "")
        creator_name = f"{first} {last}".strip()
    
    # Truncate long content for display
    display_content = content
    if len(content) > 200:
        display_content = content[:200] + "..."
    
    lines = [f"📝 **Note** (ID: {note_id})"]
    lines.append(f"   Content: {display_content}")
    if creator_name:
        lines.append(f"   Created by: {creator_name}")
    lines.append(f"   Type: {entity_type} | Private: {'Yes' if is_private else 'No'}")
    lines.append(f"   Created: {created_at}")
    
    # Show tags if present
    tags = note.get("tags", [])
    if tags:
        lines.append(f"   Tags: {', '.join(tags)}")
    
    return "\n".join(lines)


def get_note_tools() -> list:
    """Get all NOTE tools.

    Returns:
        List of tool functions
    """

    @tool
    async def create_note(
        entity_name: str,
        entity_type: str,
        content: str,
        is_private: bool = False,
        tags: Optional[str] = None,
    ) -> str:
        """Create a new note for a person or company in the CRM.
        
        Use this tool when the user wants to add a note, comment, or reminder
        about a person or company.
        
        Args:
            entity_name: Name of the person or company to add the note to
            entity_type: Type of entity - must be "PEOPLE" for a person or "COMPANY" for a company
            content: The note content/text to save
            is_private: Whether the note should be private (only visible to creator). Default: False
            tags: Optional comma-separated list of tags (e.g., "meeting,follow-up")
            
        Returns:
            Confirmation message with the created note details
        """
        # Validate and normalize entity type
        entity_type_upper = entity_type.upper()
        if entity_type_upper == "PERSON":
            entity_type_upper = "PEOPLE"
            
        if entity_type_upper not in NOTE_ENTITY_TYPES:
            return f"Invalid entity type '{entity_type}'. Must be 'PEOPLE' (or 'PERSON') for a person or 'COMPANY' for a company."
        
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # First, search for the entity to get its ID
            if entity_type_upper == "PEOPLE":
                search_query = """
                query GetWorkspacePeople($workspaceId: ID!, $search: String, $limit: Int) {
                    getWorkspacePeople(workspaceId: $workspaceId, search: $search, limit: $limit) {
                        data {
                            id
                            firstName
                            lastName
                        }
                    }
                }
                """
                result = await client.query(search_query, {
                    "workspaceId": context.workspace_id,
                    "search": entity_name,
                    "limit": 5,
                })
                entities = result.get("getWorkspacePeople", {}).get("data", [])
                
                if not entities:
                    return f"No person found matching '{entity_name}'. Please check the name and try again."
                
                # Use the first match
                entity = entities[0]
                entity_id = entity["id"]
                entity_display = f"{entity.get('firstName', '')} {entity.get('lastName', '')}".strip()
                
            else:  # COMPANY
                search_query = """
                query GetWorkspaceCompany($workspaceId: ID!, $search: String, $limit: Int) {
                    getWorkspaceCompany(workspaceId: $workspaceId, search: $search, limit: $limit) {
                        data {
                            id
                            name
                        }
                    }
                }
                """
                result = await client.query(search_query, {
                    "workspaceId": context.workspace_id,
                    "search": entity_name,
                    "limit": 5,
                })
                entities = result.get("getWorkspaceCompany", {}).get("data", [])
                
                if not entities:
                    return f"No company found matching '{entity_name}'. Please check the name and try again."
                
                entity = entities[0]
                entity_id = entity["id"]
                entity_display = entity.get("name", entity_name)
        except Exception as e:
            logger.error(f"Error searching for entity: {e}")
            return f"Error searching for entity: {str(e)}"
        finally:
            await client.close()
        
        # Build draft data for confirmation
        draft_data = {
            "entity": entity_display,
            "entity_type": entity_type_upper,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "is_private": is_private,
        }
        if tags:
            draft_data["tags"] = tags
        
        # Request confirmation - This can raise an Interrupt
        confirmation = request_create_confirmation(
            entity_type="note",
            draft_data=draft_data,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Note creation cancelled by user.{feedback}"
        
        context = get_tool_context()
        client = context.get_client()
        try:
            # Create the note
            mutation = """
            mutation CreateNote($input: CreateNoteInput!, $workspaceId: String!) {
                createNote(input: $input, workspaceId: $workspaceId) {
                    id
                    content
                    entityType
                    entityId
                    isPrivate
                    tags
                    createdAt
                    creator {
                        firstName
                        lastName
                    }
                }
            }
            """
            
            input_data = {
                "entityType": entity_type_upper,
                "entityId": entity_id,
                "content": content,
                "isPrivate": is_private,
            }
            
            if tags:
                input_data["tags"] = [t.strip() for t in tags.split(",")]
            
            result = await client.mutate(mutation, {
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            
            note = result.get("createNote")
            
            if note:
                return f"✅ Successfully created note for {entity_display}:\n\n{format_note(note)}"
            else:
                return "Failed to create note - no data returned."
                
        except Exception as e:
            logger.error(f"Error creating note: {e}")
            return f"Error creating note: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_notes(
        entity_name: str,
        entity_type: str,
        limit: int = 10,
    ) -> str:
        """List notes for a person or company.
        
        Use this tool to see all notes associated with a specific person or company.
        
        Args:
            entity_name: Name of the person or company
            entity_type: Type of entity - "PEOPLE" for a person or "COMPANY" for a company
            limit: Maximum number of notes to return (default: 10)
            
        Returns:
            Formatted list of notes
        """
        # Validate and normalize entity type
        entity_type_upper = entity_type.upper()
        if entity_type_upper == "PERSON":
            entity_type_upper = "PEOPLE"

        if entity_type_upper not in NOTE_ENTITY_TYPES:
            return f"Invalid entity type '{entity_type}'. Must be 'PEOPLE' (or 'PERSON') or 'COMPANY'."
        
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # First, find the entity
            if entity_type_upper == "PEOPLE":
                search_query = """
                query GetWorkspacePeople($workspaceId: ID!, $search: String, $limit: Int) {
                    getWorkspacePeople(workspaceId: $workspaceId, search: $search, limit: $limit) {
                        data {
                            id
                            firstName
                            lastName
                        }
                    }
                }
                """
                result = await client.query(search_query, {
                    "workspaceId": context.workspace_id,
                    "search": entity_name,
                    "limit": 5,
                })
                entities = result.get("getWorkspacePeople", {}).get("data", [])
                
                if not entities:
                    return f"No person found matching '{entity_name}'."
                
                entity = entities[0]
                entity_id = entity["id"]
                entity_display = f"{entity.get('firstName', '')} {entity.get('lastName', '')}".strip()
            else:
                search_query = """
                query GetWorkspaceCompany($workspaceId: ID!, $search: String, $limit: Int) {
                    getWorkspaceCompany(workspaceId: $workspaceId, search: $search, limit: $limit) {
                        data {
                            id
                            name
                        }
                    }
                }
                """
                result = await client.query(search_query, {
                    "workspaceId": context.workspace_id,
                    "search": entity_name,
                    "limit": 5,
                })
                entities = result.get("getWorkspaceCompany", {}).get("data", [])
                
                if not entities:
                    return f"No company found matching '{entity_name}'."
                
                entity = entities[0]
                entity_id = entity["id"]
                entity_display = entity.get("name", entity_name)
            
            # Now fetch the notes
            notes_query = """
            query GetNotes(
                $workspaceId: String!
                $entityType: NoteEntityType!
                $entityId: String!
                $limit: Int
            ) {
                notes(
                    workspaceId: $workspaceId
                    entityType: $entityType
                    entityId: $entityId
                    limit: $limit
                ) {
                    items {
                        id
                        content
                        entityType
                        isPrivate
                        tags
                        createdAt
                        creator {
                            firstName
                            lastName
                        }
                    }
                    totalCount
                }
            }
            """
            
            result = await client.query(notes_query, {
                "workspaceId": context.workspace_id,
                "entityType": entity_type_upper,
                "entityId": entity_id,
                "limit": limit,
            })
            
            notes_data = result.get("notes", {})
            notes = notes_data.get("items", [])
            total = notes_data.get("totalCount", len(notes))
            
            if not notes:
                return f"No notes found for {entity_display}."
            
            lines = [f"📋 Found {total} note(s) for **{entity_display}**:\n"]
            for note in notes:
                lines.append(format_note(note))
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error listing notes: {e}")
            return f"Error listing notes: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_note(note_id: str) -> str:
        """Get a specific note by its ID.
        
        Args:
            note_id: The ID of the note to retrieve
            
        Returns:
            The note details
        """
        context = get_tool_context()
        client = context.get_client()
        
        try:
            query = """
            query GetNote($id: String!, $workspaceId: String!) {
                note(id: $id, workspaceId: $workspaceId) {
                    id
                    content
                    entityType
                    entityId
                    isPrivate
                    tags
                    createdAt
                    updatedAt
                    creator {
                        firstName
                        lastName
                    }
                }
            }
            """
            
            result = await client.query(query, {
                "id": note_id,
                "workspaceId": context.workspace_id,
            })
            
            note = result.get("note")
            
            if not note:
                return f"Note with ID '{note_id}' not found."
            
            return format_note(note)
            
        except Exception as e:
            logger.error(f"Error getting note: {e}")
            return f"Error getting note: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_note(
        note_id: str,
        content: Optional[str] = None,
        is_private: Optional[bool] = None,
        tags: Optional[str] = None,
    ) -> str:
        """Update an existing note.
        
        Only the creator of the note can update it.
        
        Args:
            note_id: The ID of the note to update
            content: New content for the note (optional)
            is_private: Whether the note should be private (optional)
            tags: New comma-separated list of tags (optional)
            
        Returns:
            Confirmation message with the updated note
        """
        if not content and is_private is None and not tags:
            return "Please provide at least one field to update (content, is_private, or tags)."
        
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # First, get the existing note
            get_query = """
            query GetNote($id: String!, $workspaceId: String!) {
                note(id: $id, workspaceId: $workspaceId) {
                    id
                    content
                    entityType
                    entityId
                    isPrivate
                    tags
                }
            }
            """
            
            result = await client.query(get_query, {
                "id": note_id,
                "workspaceId": context.workspace_id,
            })
            
            existing_note = result.get("note")
            if not existing_note:
                return f"Note with ID '{note_id}' not found."
        except Exception as e:
            logger.error(f"Error fetching note: {e}")
            return f"Error fetching note: {str(e)}"
        finally:
            await client.close()
            
        # Build the update preview
        changes = {}
        if content:
            changes["content"] = content[:100] + "..." if len(content) > 100 else content
        if is_private is not None:
            changes["is_private"] = is_private
        if tags:
            changes["tags"] = tags
        
        # Request confirmation - This can raise an Interrupt
        confirmation = request_update_confirmation(
            entity_type="note",
            entity_name=note_id,
            changes=changes,
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Note update cancelled.{feedback}"
        
        context = get_tool_context()
        client = context.get_client()
        try:
            # Perform the update
            mutation = """
            mutation UpdateNote($id: String!, $input: UpdateNoteInput!, $workspaceId: String!) {
                updateNote(id: $id, input: $input, workspaceId: $workspaceId) {
                    id
                    content
                    entityType
                    isPrivate
                    tags
                    createdAt
                    updatedAt
                    creator {
                        firstName
                        lastName
                    }
                }
            }
            """
            
            input_data = {}
            if content:
                input_data["content"] = content
            if is_private is not None:
                input_data["isPrivate"] = is_private
            if tags:
                input_data["tags"] = [t.strip() for t in tags.split(",")]
            
            result = await client.mutate(mutation, {
                "id": note_id,
                "input": input_data,
                "workspaceId": context.workspace_id,
            })
            
            updated_note = result.get("updateNote")
            
            if updated_note:
                return f"✅ Successfully updated note:\n\n{format_note(updated_note)}"
            else:
                return "Failed to update note - no data returned."
                
        except Exception as e:
            logger.error(f"Error updating note: {e}")
            return f"Error updating note: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_note(note_id: str) -> str:
        """Delete a note.
        
        Only the creator of the note can delete it.
        
        Args:
            note_id: The ID of the note to delete
            
        Returns:
            Confirmation message
        """
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # First, get the note to show what will be deleted
            get_query = """
            query GetNote($id: String!, $workspaceId: String!) {
                note(id: $id, workspaceId: $workspaceId) {
                    id
                    content
                    entityType
                    entityId
                }
            }
            """
            
            result = await client.query(get_query, {
                "id": note_id,
                "workspaceId": context.workspace_id,
            })
            
            existing_note = result.get("note")
            if not existing_note:
                return f"Note with ID '{note_id}' not found."
        except Exception as e:
            logger.error(f"Error fetching note: {e}")
            return f"Error fetching note: {str(e)}"
        finally:
            await client.close()
            
        # Request confirmation - This can raise an Interrupt
        confirmation = request_delete_confirmation(
            entity_type="note",
            entity_name=existing_note.get("content", "")[:50] + "...",
        )
        
        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Note deletion cancelled.{feedback}"
            
        context = get_tool_context()
        client = context.get_client()
        try:
            # Delete the note
            mutation = """
            mutation DeleteNote($id: String!, $workspaceId: String!) {
                deleteNote(id: $id, workspaceId: $workspaceId)
            }
            """
            
            result = await client.mutate(mutation, {
                "id": note_id,
                "workspaceId": context.workspace_id,
            })
            
            success = result.get("deleteNote", False)
            
            if success:
                return "✅ Note deleted successfully."
            else:
                return "Failed to delete note."
                
        except Exception as e:
            logger.error(f"Error deleting note: {e}")
            return f"Error deleting note: {str(e)}"
        finally:
            await client.close()

    return [
        create_note,
        list_notes,
        get_note,
        update_note,
        delete_note,
    ]
