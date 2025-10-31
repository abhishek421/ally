# Workspace Schema Documentation

## Overview

The `workspace` model is the central entity in the SoftSync application that represents a collaborative workspace where users can manage companies, people, groups, and other business-related data. Each workspace acts as a container for all related entities and provides multi-tenancy capabilities.

## Database Schema

### Primary Fields

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | `String` | Unique identifier for the workspace | Primary Key, UUID, Auto-generated |
| `name` | `String` | Human-readable name of the workspace | Required, Indexed |
| `createdAt` | `DateTime` | Timestamp when the workspace was created | Auto-generated, Indexed |
| `updatedAt` | `DateTime` | Timestamp when the workspace was last modified | Auto-updated |

### Avatar Fields

The workspace supports avatar functionality with the following fields:

| Field | Type | Description | Purpose |
|-------|------|-------------|---------|
| `avatarKey` | `String?` | S3 object key for the avatar image | References the file in cloud storage |
| `avatarContentType` | `String?` | MIME type of the avatar image | Used for proper content serving (e.g., "image/jpeg") |
| `avatarSize` | `Int?` | File size of the avatar in bytes | Used for storage management and validation |
| `avatarEtag` | `String?` | ETag for cache validation | Enables efficient caching and change detection |
| `avatarUpdatedAt` | `DateTime?` | Timestamp when avatar was last updated | Tracks avatar modification time |

## Relationships

The workspace has extensive relationships with other entities in the system:

### Core Business Entities

- **`company[]`** - Companies associated with this workspace
  - Relationship: One-to-Many (`@relation("companyWorkspace")`)
  - Purpose: Stores business entities and their information

- **`people[]`** - People/contacts associated with this workspace
  - Relationship: One-to-Many (`@relation("peopleWorkspace")`)
  - Purpose: Stores individual contacts and their details

- **`group[]`** - Groups for organizing companies and people
  - Relationship: One-to-Many
  - Purpose: Provides categorization and organization capabilities

### User Management

- **`members[]`** - Workspace members (users with access)
  - Relationship: One-to-Many via `workspaceMember` junction table
  - Purpose: Manages user access and permissions
  - Roles: `ADMIN`, `MEMBER`, `OWNER`

- **`invitations[]`** - Pending user invitations
  - Relationship: One-to-Many via `userInvitation`
  - Purpose: Handles workspace invitation workflow

- **`sessions[]`** - User sessions within this workspace
  - Relationship: One-to-Many
  - Purpose: Tracks user activity and authentication

### Communication & Integration

- **`conversations[]`** - Chat conversations within the workspace
  - Relationship: One-to-Many
  - Purpose: Internal communication system

- **`emailIntegration[]`** - Email service integrations
  - Relationship: One-to-Many
  - Purpose: Connects external email services

- **`interaction[]`** - User interactions and activities
  - Relationship: One-to-Many
  - Purpose: Tracks user engagement and actions

### Data Management

- **`importJob[]`** - Data import operations
  - Relationship: One-to-Many
  - Purpose: Manages bulk data imports

- **`reminder[]`** - Scheduled reminders
  - Relationship: One-to-Many
  - Purpose: Task and follow-up management

- **`view[]`** - Custom views and filters
  - Relationship: One-to-Many
  - Purpose: User-defined data presentation

- **`dismissedDuplicatePairs[]`** - Resolved duplicate records
  - Relationship: One-to-Many
  - Purpose: Tracks duplicate resolution decisions

## Database Indexes

The workspace model includes several indexes for performance optimization:

- **`@@index([name])`** - Enables fast workspace name lookups
- **`@@index([createdAt])`** - Optimizes chronological queries

## Usage Patterns

### Creating a Workspace

```typescript
// Example workspace creation
const workspace = {
  name: "Acme Corporation",
  // Avatar fields are optional and set separately
};
```

### Avatar Management

```typescript
// Setting workspace avatar
await workspaceService.setAvatar(workspaceId, {
  key: "workspaces/avatar-123.jpg",
  contentType: "image/jpeg",
  size: 1024000,
  etag: "abc123def456",
  updatedAt: new Date()
});

// Clearing avatar
await workspaceService.clearAvatar(workspaceId);
```

### Member Management

```typescript
// Adding workspace member
const member = {
  userId: "user-uuid",
  workspaceId: "workspace-uuid",
  role: "MEMBER" // ADMIN, MEMBER, or OWNER
};
```

## Security Considerations

- **Multi-tenancy**: Each workspace is isolated from others
- **Role-based Access**: Members have different permission levels
- **Data Isolation**: All related entities are scoped to workspace
- **Avatar Security**: Avatar files are stored securely in S3 with proper access controls

## API Integration

The workspace is exposed through GraphQL with the following model:

```typescript
@ObjectType({ description: 'Workspace model for GraphQL responses' })
export class WorkspaceModel {
  @Field(() => ID, { description: 'Unique identifier for the workspace' })
  id: string;

  @Field({ description: 'Name of the workspace' })
  name: string;

  @Field({ description: 'Creation timestamp', nullable: true })
  createdAt?: Date;

  @Field({ description: 'Last update timestamp', nullable: true })
  updatedAt?: Date;

  @Field(() => String, { nullable: true })
  avatarUrl?: string | null;
}
```

## Best Practices

1. **Naming**: Use descriptive, business-relevant workspace names
2. **Avatar Management**: Implement proper file validation and size limits
3. **Member Roles**: Assign appropriate roles based on user responsibilities
4. **Data Cleanup**: Implement proper cascade deletion for related entities
5. **Performance**: Leverage indexes for common query patterns

## Related Documentation

- [Company Schema](./company-schema.md)
- [People Schema](./people-schema.md)
- [Group Schema](./group-schema.md)
- [User Management](./user-management.md)
- [Avatar Management](./avatar-management.md)
