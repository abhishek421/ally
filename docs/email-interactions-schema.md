# Email & Interactions Schema Documentation

This document provides a comprehensive overview of the email and interactions schema used in the SoftSync application, including detailed field descriptions and relationships.

## ⚠️ Important Architecture Note

**The SoftSync application uses a dual-database architecture:**

- **DynamoDB**: Primary storage for email data and email interactions
- **PostgreSQL**: Storage for general interactions (calls, meetings, notes, etc.) and AI analyst queries

**Email data is NOT stored in PostgreSQL** - it's exclusively stored in DynamoDB with a specific schema optimized for email operations.

## Table of Contents
- [Email Schema (DynamoDB)](#email-schema-dynamodb)
- [Interactions Schema (PostgreSQL)](#interactions-schema-postgresql)
- [Related Models](#related-models)
- [Enums](#enums)
- [Database Relationships](#database-relationships)
- [Architecture Overview](#architecture-overview)

---

## Email Schema (DynamoDB)

**All email data is stored in DynamoDB**, not PostgreSQL. The email schema uses DynamoDB's NoSQL structure with specific partition and sort key patterns for optimal querying.

### DynamoDB Email Storage Structure

Emails are stored in DynamoDB with the following key structure:

**Primary Key Pattern:**
- `PK` (Partition Key): `WORKSPACE#{workspaceId}#PERSON#{personId}` or `WORKSPACE#{workspaceId}#INTEGRATION#{integrationId}`
- `SK` (Sort Key): `{isoDate}#{messageId}` (chronological sorting)

**GSI1 Pattern (for integration-based queries):**
- `GSI1PK`: `WORKSPACE#{workspaceId}#INTEGRATION#{integrationId}#YEAR#{year}`
- `GSI1SK`: `{isoDate}#{messageId}`

### DynamoDB Email Document Schema

| Field | Type | Description |
|-------|------|-------------|
| `PK` | `String` | Partition key (workspace + person/integration) |
| `SK` | `String` | Sort key (date + messageId) |
| `GSI1PK` | `String` | GSI1 partition key (workspace + integration + year) |
| `GSI1SK` | `String` | GSI1 sort key (date + messageId) |
| `recordType` | `String` | Always "MESSAGE" for emails |
| `personId` | `String?` | Associated person ID |
| `contactEmail` | `String?` | Primary contact email for the person |
| `messageId` | `String` | Unique message identifier |
| `subject` | `String?` | Email subject line |
| `from` | `String` | Sender email address |
| `to` | `String[]` | Array of recipient email addresses |
| `date` | `String` | ISO date string when email was sent/received |
| `direction` | `String` | "sent" or "received" |
| `body` | `String?` | HTML email body (clamped to avoid size limits) |
| `workspaceId` | `String` | Workspace identifier |
| `userId` | `String` | User identifier |
| `integrationId` | `String` | Email integration identifier |
| `processed` | `Boolean` | Whether email has been processed |
| `createdAt` | `String` | ISO date string for creation |
| `updatedAt` | `String` | ISO date string for last update |
| `participants` | `Array` | Email participants with roles |

### PostgreSQL Email Address Model (Contact Information Only)

**Note**: PostgreSQL only stores email addresses as contact information, NOT email content.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String (UUID)` | Unique identifier for the email address record |
| `value` | `String (VARCHAR 255)` | The actual email address value |
| `type` | `EmailType?` | Type of email address (personal, work, other) |
| `isPrimary` | `Boolean` | Whether this is the primary email for the person/company |
| `verified` | `Boolean` | Whether the email address has been verified |
| `createdAt` | `DateTime` | Timestamp when the record was created |
| `updatedAt` | `DateTime` | Timestamp when the record was last updated |
| `personId` | `String (UUID)?` | Reference to the person this email belongs to |
| `companyId` | `String (UUID)?` | Reference to the company this email belongs to |

**Database Constraints:**
- Unique constraint on `(personId, value)` combination
- Indexes on `isPrimary`, `value`, `personId + isPrimary`, `companyId + isPrimary`, `verified`, `type`

### Email DTO (Application Model)

The main email model used in the application:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String (UUID)` | Unique identifier for the email |
| `workspaceId` | `String (UUID)` | Workspace this email belongs to |
| `groupId` | `String (UUID)` | Group/segment this email is associated with |
| `group` | `GroupModel?` | Full group object (populated when needed) |
| `viewId` | `String?` | View ID for custom views |
| `view` | `ViewModel?` | Full view object (populated when needed) |
| `subject` | `String?` | Email subject line |
| `from` | `String?` | Sender's email address |
| `to` | `String[]` | Array of recipient email addresses |
| `recipientIds` | `RecipientInfo[]?` | Detailed recipient information with IDs |
| `cc` | `String[]?` | Carbon copy recipients |
| `bcc` | `String[]?` | Blind carbon copy recipients |
| `htmlContent` | `String?` | HTML version of email content |
| `textContent` | `String?` | Plain text version of email content |
| `files` | `EmailFileDto[]?` | Attachments associated with the email |
| `scheduledFor` | `String?` | ISO date string for scheduled sending |
| `usedPlaceholders` | `PlaceholderInfo[]?` | Placeholders used in the email |
| `status` | `EmailStatus` | Current status of the email |
| `messageId` | `String?` | External message ID from email provider |
| `createdBy` | `String (UUID)` | User who created the email |
| `createdAt` | `DateTime` | When the email was created |
| `updatedAt` | `DateTime` | When the email was last updated |

### Email Interaction Model

Model for email interactions within the system:

| Field | Type | Description |
|-------|------|-------------|
| `messageId` | `String` | Unique message identifier |
| `subject` | `String?` | Email subject |
| `from` | `String` | Sender email address |
| `to` | `String[]` | Recipient email addresses |
| `direction` | `'sent' \| 'received'` | Direction of the email |
| `body` | `String?` | Plain text body content |
| `bodyHtml` | `String?` | HTML body content |
| `date` | `DateTime` | When the email was sent/received |
| `threadId` | `String?` | Thread identifier for conversation grouping |
| `participants` | `EmailParticipantModel[]` | All participants in the email |
| `workspaceId` | `String` | Workspace identifier |
| `userId` | `String` | User identifier |
| `processed` | `Boolean` | Whether the email has been processed |
| `createdAt` | `DateTime` | Record creation timestamp |
| `updatedAt` | `DateTime` | Record update timestamp |
| `deleted` | `Boolean` | Soft delete flag |
| `labels` | `String[]?` | Email labels/tags |
| `notes` | `String?` | Additional notes |
| `ownerPrivacyLevel` | `InteractionPrivacy` | Privacy level for the interaction |
| `canEdit` | `Boolean` | Whether current user can edit |
| `canDelete` | `Boolean` | Whether current user can delete |
| `isOwn` | `Boolean` | Whether this is the user's own email |
| `source` | `String?` | Source of the interaction |
| `interactionType` | `String?` | Type of interaction |
| `eventName` | `String?` | Name of the event |
| `description` | `String?` | Event description |
| `dateTime` | `DateTime?` | Event date/time |
| `duration` | `Number?` | Event duration in minutes |
| `personId` | `String?` | Associated person ID |
| `companyId` | `String?` | Associated company ID |
| `createdById` | `String?` | Creator user ID |

---

## Interactions Schema (PostgreSQL)

**Note**: Email interactions are stored in DynamoDB, not PostgreSQL. PostgreSQL only stores non-email interactions (calls, meetings, notes, etc.).

### Core Interaction Model (PostgreSQL Database)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String (UUID)` | Unique identifier for the interaction |
| `type` | `InteractionType` | Type of interaction (EMAIL, CALENDAR, CALL, etc.) |
| `direction` | `Direction` | Direction of interaction (INBOUND, OUTBOUND) |
| `subject` | `String?` | Subject/title of the interaction |
| `content` | `String?` | Content/body of the interaction |
| `date` | `DateTime` | When the interaction occurred |
| `createdAt` | `DateTime` | When the record was created |
| `updatedAt` | `DateTime` | When the record was last updated |
| `externalId` | `String?` | External system identifier |
| `externalType` | `String?` | Type of external system |
| `metadata` | `Json?` | Additional metadata as JSON |
| `isDeleted` | `Boolean` | Soft delete flag |
| `createdById` | `String (UUID)` | User who created the record |
| `peopleId` | `String (UUID)?` | Associated person |
| `companyId` | `String (UUID)?` | Associated company |
| `workspaceId` | `String (UUID)` | Workspace identifier |

**Database Indexes:**
- `(workspaceId, date)`
- `(peopleId)`
- `(companyId)`
- `(externalId)`
- `(workspaceId, type, date)`
- `(createdById, date)`
- `(workspaceId, direction, date)`
- `(peopleId, date DESC, isDeleted)`
- `(companyId, date DESC, isDeleted)`
- `(workspaceId, type, direction, date DESC)`
- `(externalId, externalType)`
- `(subject)`
- `(content)`

---

## Related Models

### Email File DTO

Represents email attachments:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `String` | File name |
| `url` | `String` | File URL or path |
| `type` | `String?` | MIME type of the file |
| `size` | `Number?` | File size in bytes |

### Email Participant Model

Represents participants in email communications:

| Field | Type | Description |
|-------|------|-------------|
| `email` | `String` | Participant's email address |
| `personId` | `String?` | Associated person ID |
| `companyId` | `String?` | Associated company ID |
| `role` | `ParticipantRole` | Role in the email (FROM, TO, CC, BCC) |
| `relationship` | `String?` | Relationship description |

### Recipient Info

Detailed recipient information:

| Field | Type | Description |
|-------|------|-------------|
| `email` | `String` | Recipient email address |
| `personId` | `String?` | Associated person ID |
| `companyId` | `String?` | Associated company ID |
| `name` | `String?` | Recipient name |

---

## Enums

### EmailType
```typescript
enum EmailType {
  personal = 'personal',
  work = 'work',
  other = 'other'
}
```

### EmailStatus
```typescript
enum EmailStatus {
  DRAFT = 'DRAFT',           // Email is in draft state
  SENT = 'SENT',             // Email has been sent
  DELIVERED = 'DELIVERED',   // Email has been delivered
  OPENED = 'OPENED',         // Email has been opened
  CLICKED = 'CLICKED',       // Link in email has been clicked
  BOUNCED = 'BOUNCED',       // Email has bounced
  COMPLAINED = 'COMPLAINED', // Recipient has complained about the email
  REJECTED = 'REJECTED',     // Email was rejected
  FAILED = 'FAILED',         // Email sending failed
  SCHEDULED = 'SCHEDULED',   // Email is scheduled to be sent
  INREVIEW = 'INREVIEW',     // Email is under review
  REPLIED = 'REPLIED',       // Email has been replied
  PROCESSED = 'PROCESSED'    // Email has been processed
}
```

### InteractionType
```typescript
enum InteractionType {
  EMAIL = 'EMAIL',
  CALENDAR = 'CALENDAR',
  CALL = 'CALL',
  MEETING = 'MEETING',
  NOTE = 'NOTE',
  SMS = 'SMS',
  LINKEDIN_MESSAGE = 'LINKEDIN_MESSAGE',
  SOCIAL_MEDIA = 'SOCIAL_MEDIA'
}
```

### Direction
```typescript
enum Direction {
  INBOUND = 'INBOUND',   // Incoming interaction
  OUTBOUND = 'OUTBOUND'  // Outgoing interaction
}
```

### ParticipantRole
```typescript
enum ParticipantRole {
  FROM = 'FROM',  // Sender
  TO = 'TO',      // Primary recipient
  CC = 'CC',      // Carbon copy recipient
  BCC = 'BCC'     // Blind carbon copy recipient
}
```

### InteractionPrivacy
```typescript
enum InteractionPrivacy {
  PRIVATE = 'PRIVATE',         // Only visible to creator
  SUBJECT_ONLY = 'SUBJECT_ONLY', // Only subject visible to others
  FULL_ACCESS = 'FULL_ACCESS'   // Full access for workspace members
}
```

---

## Architecture Overview

### Database Usage Summary

| Data Type | Storage Location | Purpose |
|-----------|------------------|---------|
| **Email Content** | DynamoDB | Full email messages, threads, attachments |
| **Email Addresses** | PostgreSQL | Contact information only (not email content) |
| **Email Interactions** | DynamoDB | Email-specific interaction data |
| **Non-Email Interactions** | PostgreSQL | Calls, meetings, notes, calendar events |
| **AI Analyst Queries** | PostgreSQL | Uses interaction table for analytics |

### DynamoDB Email Architecture

**Key Benefits:**
- **Scalability**: Handles large volumes of email data efficiently
- **Performance**: Optimized for email-specific query patterns
- **Cost-effective**: Pay-per-use model for email storage
- **Flexibility**: NoSQL structure allows for varying email formats

**Query Patterns:**
- Person-centric: `PK = WORKSPACE#{workspaceId}#PERSON#{personId}`
- Integration-centric: `PK = WORKSPACE#{workspaceId}#INTEGRATION#{integrationId}`
- Year-based queries: Uses GSI1 for integration + year filtering

### PostgreSQL Interaction Architecture

**Key Benefits:**
- **ACID Compliance**: Reliable for critical business data
- **Complex Queries**: Supports sophisticated analytics queries
- **Relationships**: Strong relational model for connected data
- **AI Integration**: Optimized for AI analyst function calls

**Usage:**
- AI Analyst queries use PostgreSQL interaction table
- Non-email interactions (calls, meetings, notes)
- Contact information and metadata
- User and workspace management

---

## Database Relationships

### DynamoDB Email Relationships
- **Email Documents** → **Workspace**: Partitioned by workspace ID
- **Email Documents** → **Person**: Person-centric storage for contact emails
- **Email Documents** → **Integration**: Integration-centric storage for email sync

### PostgreSQL Relationships
- **email** (addresses) → **people**: Many-to-one relationship via `personId`
- **email** (addresses) → **company**: Many-to-one relationship via `companyId`
- **interaction** → **people**: Many-to-one relationship via `peopleId`
- **interaction** → **company**: Many-to-one relationship via `companyId`
- **interaction** → **workspace**: Many-to-one relationship via `workspaceId`
- **interaction** → **user**: Many-to-one relationship via `createdById`

### Key Constraints
- Email addresses must be unique per person (`personId + value` unique constraint)
- All interactions must belong to a workspace
- Soft delete pattern used (`isDeleted` flag instead of hard deletes)
- Comprehensive indexing for performance on common query patterns

---

## Usage Notes

1. **Dual Database Architecture**: Emails in DynamoDB, interactions in PostgreSQL
2. **Email Storage**: DynamoDB supports both HTML and plain text content for emails
3. **Privacy Levels**: Interactions can have different privacy levels controlling visibility
4. **External Integration**: External IDs and types allow integration with third-party systems
5. **Soft Deletes**: Records are marked as deleted rather than physically removed
6. **Audit Trail**: All records include creation and update timestamps
7. **Performance**: Extensive indexing supports efficient querying by common patterns
8. **Flexibility**: JSON metadata fields allow for extensible data storage
9. **AI Integration**: PostgreSQL interaction table powers AI analyst queries

This dual-database schema supports a comprehensive email and interaction management system with proper relationships, privacy controls, and performance optimizations tailored to each database's strengths.

