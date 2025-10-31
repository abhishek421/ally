# Notes Schema Documentation

## Overview

The Notes system in SoftSync provides a comprehensive note-taking and collaboration feature that allows users to create, manage, and organize notes associated with people and companies within their workspace. The system supports hierarchical note structures (replies), file attachments, privacy controls, and tagging for better organization.

## Core Models

### NoteDto (Main Note Entity)

The primary note entity that represents a single note in the system.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` (UUID) | ✅ | Unique identifier for the note |
| `workspaceId` | `string` (UUID) | ✅ | Identifier of the workspace this note belongs to |
| `entityType` | `EntityType` | ✅ | Type of entity this note is associated with (`PEOPLE` or `COMPANY`) |
| `entityId` | `string` (UUID) | ✅ | ID of the specific person or company this note relates to |
| `content` | `string` | ✅ | The actual text content of the note |
| `isPrivate` | `boolean` | ✅ | Privacy flag - if `true`, only the creator can see this note |
| `tags` | `string[]` | ❌ | Array of tags for categorizing and organizing notes |
| `parentNoteId` | `string` (UUID) | ❌ | ID of the parent note if this is a reply/comment |
| `parentNote` | `NoteDto` | ❌ | Populated parent note object (when fetching with relationships) |
| `createdBy` | `string` (UUID) | ✅ | ID of the user who created this note |
| `createdAt` | `Date` | ✅ | Timestamp when the note was created |
| `updatedAt` | `Date` | ✅ | Timestamp when the note was last modified |

#### Field Details

**`entityType`**
- **Enum Values**: `PEOPLE`, `COMPANY`
- **Purpose**: Determines whether the note is associated with a person or a company
- **Usage**: Used for organizing notes and determining access patterns

**`isPrivate`**
- **Default**: `false`
- **Privacy Rules**:
  - Public notes (`isPrivate: false`): Visible to all workspace members
  - Private notes (`isPrivate: true`): Only visible to the creator
- **Access Control**: Enforced at the service layer during queries and individual note access

**`tags`**
- **Purpose**: Flexible categorization system for notes
- **Examples**: `["meeting", "follow-up", "important"]`, `["sales", "prospect"]`
- **Usage**: Enables filtering and searching notes by category

**`parentNoteId` & `parentNote`**
- **Purpose**: Enables hierarchical note structures (replies/comments)
- **Behavior**: 
  - `parentNoteId` stores the reference to the parent note
  - `parentNote` is populated when fetching notes with full relationship data
  - Privacy rules apply to parent notes as well

### EntityType Enum

```typescript
export enum EntityType {
  PEOPLE = 'PEOPLE',
  COMPANY = 'COMPANY',
}
```

**Purpose**: Defines the two types of entities that notes can be associated with in the system.

## Input Models

### CreateNoteInput

Used for creating new notes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entityType` | `EntityType` | ✅ | Type of entity (PEOPLE or COMPANY) |
| `entityId` | `string` (UUID) | ✅ | ID of the person or company |
| `content` | `string` | ✅ | Note content (cannot be empty) |
| `isPrivate` | `boolean` | ❌ | Privacy setting (defaults to `false`) |
| `tags` | `string[]` | ❌ | Optional tags for categorization |
| `parentNoteId` | `string` (UUID) | ❌ | ID of parent note if this is a reply |

### UpdateNoteInput

Used for updating existing notes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | `string` | ❌ | Updated note content |
| `isPrivate` | `boolean` | ❌ | Updated privacy setting |
| `tags` | `string[]` | ❌ | Updated tags array |

**Note**: Only the creator of a note can update it.

## Attachment System

### AttachmentDto

Represents file attachments associated with notes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` (UUID) | ✅ | Unique identifier for the attachment |
| `noteId` | `string` (UUID) | ✅ | ID of the note this attachment belongs to |
| `workspaceId` | `string` (UUID) | ✅ | Workspace identifier |
| `entityType` | `EntityType` | ✅ | Type of associated entity |
| `entityId` | `string` (UUID) | ✅ | ID of associated entity |
| `filename` | `string` | ✅ | Original filename of the uploaded file |
| `key` | `string` | ✅ | S3 storage key for the file |
| `contentType` | `string` | ✅ | MIME type of the file |
| `size` | `number` | ✅ | File size in bytes (max 10MB) |
| `etag` | `string` | ❌ | S3 ETag for the file |
| `uploadedBy` | `string` (UUID) | ✅ | ID of user who uploaded the file |
| `uploadedAt` | `Date` | ✅ | Upload timestamp |
| `content` | `string` | ✅ | Note content associated with the attachment |
| `isPrivate` | `boolean` | ✅ | Privacy setting for the attachment |
| `createdBy` | `string` (UUID) | ✅ | ID of the user who created the attachment |
| `createdAt` | `Date` | ✅ | Creation timestamp |
| `updatedAt` | `Date` | ✅ | Last modification timestamp |

#### Attachment Constraints

- **File Size Limit**: Maximum 10MB per file
- **Storage**: Files are stored in S3 with organized key structure
- **Privacy**: Inherits privacy settings from the associated note
- **Auto-note Creation**: If no noteId is provided, a note is automatically created

### Attachment Input Models

#### GetNoteAttachmentPresignInput
Used to get presigned URLs for file uploads.

#### ConfirmNoteAttachmentInput
Used to confirm and finalize file uploads.

#### DeleteNoteAttachmentInput
Used to delete attachment files.

#### ListNoteAttachmentsInput
Used to list attachments for a specific note with pagination.

## Pagination Model

### NotePage

Used for paginated note listings.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `items` | `NoteDto[]` | ✅ | Array of notes in the current page |
| `nextToken` | `string` | ❌ | Token for fetching the next page |
| `totalCount` | `number` | ✅ | Total number of notes available |

## Data Storage

### DynamoDB Structure

The notes system uses DynamoDB with the following key structure:

#### Primary Key (PK/SK)
- **PK**: `WORKSPACE#{workspaceId}#{entityType}#{entityId}#NOTES`
- **SK**: `{timestamp}#{noteId}` (for chronological sorting)

#### Global Secondary Index (GSI1)
- **GSI1PK**: `NOTE#{noteId}`
- **GSI1SK**: `WORKSPACE#{workspaceId}`

This structure enables:
- Efficient querying by entity (person/company)
- Chronological sorting (newest first)
- Fast lookups by note ID
- Workspace isolation

## Business Rules

### Privacy and Access Control

1. **Public Notes**: Visible to all workspace members
2. **Private Notes**: Only visible to the creator
3. **Parent Note Access**: When fetching replies, parent note privacy is respected
4. **Creator-only Operations**: Only the creator can update or delete their notes

### Validation Rules

1. **Content**: Cannot be empty when creating notes
2. **File Size**: Attachments limited to 10MB
3. **Entity Association**: Notes must be associated with either a person or company
4. **Workspace Isolation**: Notes are scoped to specific workspaces

### Hierarchical Structure

1. **Replies**: Notes can have parent notes via `parentNoteId`
2. **Privacy Inheritance**: Child notes don't inherit parent privacy settings
3. **Access Control**: Parent note access is checked when loading replies

## API Operations

### Core Note Operations

- **Create Note**: `createNote(input, workspaceId, currentUserId)`
- **Get Note**: `getNoteById(id, workspaceId, currentUserId)`
- **List Notes**: `listNotesByEntity(workspaceId, entityType, entityId, currentUserId, options)`
- **Update Note**: `updateNote(id, workspaceId, currentUserId, input)`
- **Delete Note**: `deleteNote(id, workspaceId, currentUserId)`

### Attachment Operations

- **Get Upload URL**: `getNoteAttachmentPresign(input, currentUserId)`
- **Confirm Upload**: `confirmNoteAttachment(input, currentUserId)`
- **List Attachments**: `listNoteAttachments(input, currentUserId)`
- **Delete Attachment**: `deleteNoteAttachment(...)`
- **Get Download URL**: `getNoteAttachmentDownloadUrl(key, filename, inline, contentType)`

## Use Cases

### 1. Meeting Notes
- Create notes during or after meetings
- Tag with `["meeting", "follow-up"]`
- Associate with relevant people and companies
- Attach meeting recordings or documents

### 2. Follow-up Tasks
- Create private notes for personal follow-ups
- Use tags for task categorization
- Set reminders through the system

### 3. Collaborative Documentation
- Create public notes for team visibility
- Use replies for discussions
- Organize with tags and attachments

### 4. Deal Tracking
- Associate notes with companies during sales processes
- Track interactions and decisions
- Maintain private notes for sensitive information

## Integration Points

### AI Analyst Integration
The notes system integrates with the AI Analyst feature to:
- Generate draft notes from conversations
- Suggest tags and categorization
- Provide insights based on note content

### Search Integration
Notes are indexed for:
- Full-text search across content
- Tag-based filtering
- Entity-based queries

### Notification System
Notes can trigger notifications for:
- Mentions of people or companies
- Follow-up reminders
- Collaboration updates

## Security Considerations

1. **Privacy Enforcement**: Strict privacy controls at the service layer
2. **Access Validation**: All operations validate user permissions
3. **File Security**: Secure file upload/download with presigned URLs
4. **Workspace Isolation**: Complete data separation between workspaces
5. **Audit Trail**: Creation and modification tracking for all notes

## Performance Optimizations

1. **Pagination**: Efficient pagination for large note collections
2. **Lazy Loading**: Parent notes loaded only when needed
3. **Indexing**: Optimized DynamoDB queries with proper key structures
4. **Caching**: Attachment metadata cached for quick access
5. **Batch Operations**: Efficient bulk operations for attachments

This documentation provides a comprehensive overview of the notes schema and its implementation in the SoftSync system.
