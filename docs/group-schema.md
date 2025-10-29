# Group Schema Documentation

## Overview

The `group` entity represents a collection mechanism in the SoftSync system that allows users to organize and categorize different types of entities (people, companies, or deals) within their workspace. Groups provide a flexible way to segment and manage data based on various criteria.

## Database Schema

### Primary Table: `group`

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `id` | `String` (UUID) | Primary Key, Not Null | `uuid()` | Unique identifier for the group |
| `name` | `String` | Not Null | - | Display name of the group |
| `workspaceId` | `String` (UUID) | Foreign Key, Not Null | - | Reference to the workspace this group belongs to |
| `description` | `String` | Nullable | `null` | Optional detailed description of the group's purpose |
| `emoji` | `String` | Nullable | `null` | Optional emoji icon to visually represent the group |
| `isPrivate` | `Boolean` | Not Null | `true` | Controls visibility - private groups are only visible to creator |
| `type` | `GroupType` | Not Null | `PEOPLE` | Defines what type of entities this group contains |
| `isFavourite` | `Boolean` | Not Null | `false` | Marks group as a favorite for quick access |
| `isDeleted` | `Boolean` | Not Null | `false` | Soft delete flag - deleted groups are hidden but not removed |
| `isCollapse` | `Boolean` | Not Null | `true` | UI state - whether the group is collapsed/expanded in the interface |
| `createdBy` | `String` (UUID) | Foreign Key, Not Null | - | Reference to the user who created this group |
| `createdAt` | `DateTime` | Not Null | `now()` | Timestamp when the group was created |
| `updatedAt` | `DateTime` | Not Null | `now()` | Timestamp when the group was last modified |
| `favouriteOrder` | `Int` | Not Null | `0` | Sort order for favorite groups |
| `privateOrder` | `Int` | Not Null | `0` | Sort order for private groups |
| `publicOrder` | `Int` | Not Null | `0` | Sort order for public groups |

### GroupType Enumeration

The `type` field uses the `GroupType` enum with the following values:

- **`PEOPLE`** - Groups that contain individual people/contacts
- **`COMPANY`** - Groups that contain company/organization entities  
- **`DEAL`** - Groups that contain business deals/opportunities

### Relationships

#### Foreign Key Relationships

- **`workspaceId`** → `workspace.id` (Cascade Delete)
  - Each group belongs to exactly one workspace
  - When a workspace is deleted, all its groups are automatically deleted

- **`createdBy`** → `user.id` (No Action)
  - Each group has a creator user
  - User deletion does not cascade to groups (preserves group ownership)

#### One-to-Many Relationships

- **`groupCompanies`** - Collection of `groupCompany` records
  - Links companies to this group
  - Junction table for many-to-many relationship between groups and companies

- **`groupPeople`** - Collection of `groupPeople` records  
  - Links people to this group
  - Junction table for many-to-many relationship between groups and people

- **`column`** - Collection of `column` records
  - Custom columns defined for this group
  - Used for organizing and displaying group data

- **`view`** - Collection of `view` records
  - Different views/perspectives of the group data
  - Supports table and pipeline views

- **`importJob`** - Collection of `importJob` records
  - Import operations associated with this group

- **`profileColumnViewSettings`** - Collection of `profileColumnViewSettings` records
  - User-specific column visibility settings for this group

## Junction Tables

### `groupPeople` Table

Links people to groups with additional metadata:

| Field | Type | Description |
|-------|------|-------------|
| `groupId` | `String` (UUID) | Reference to the group |
| `peopleId` | `String` (UUID) | Reference to the person |
| `addedAt` | `DateTime` | When the person was added to the group |
| `addedBy` | `String` (UUID) | User who added the person to the group |

**Constraints:**
- Composite Primary Key: `(groupId, peopleId)`
- Foreign Keys: `groupId` → `group.id`, `peopleId` → `people.id`, `addedBy` → `user.id`
- Cascade delete on group and people deletion

### `groupCompany` Table

Links companies to groups with additional metadata:

| Field | Type | Description |
|-------|------|-------------|
| `groupId` | `String` (UUID) | Reference to the group |
| `companyId` | `String` (UUID) | Reference to the company |
| `addedAt` | `DateTime` | When the company was added to the group |
| `addedBy` | `String` (UUID) | User who added the company to the group |

**Constraints:**
- Composite Primary Key: `(groupId, companyId)`
- Foreign Keys: `groupId` → `group.id`, `companyId` → `company.id`, `addedBy` → `user.id`
- Cascade delete on group and company deletion

## Database Indexes

The following indexes are created for optimal query performance:

### Primary Indexes
- `[workspaceId]` - Fast workspace-based queries
- `[workspaceId, createdBy]` - User's groups within workspace
- `[workspaceId, isPrivate]` - Public/private group filtering
- `[workspaceId, type, isDeleted]` - Active groups by type
- `[workspaceId, isFavourite, isDeleted]` - Favorite groups
- `[name]` - Group name searches
- `[workspaceId, name]` - Name searches within workspace
- `[createdBy, createdAt(sort: Desc)]` - User's groups by creation time
- `[workspaceId, isPrivate, type]` - Complex filtering queries

### Junction Table Indexes
- `groupPeople`: `[peopleId]`, `[peopleId, groupId]`, `[addedBy]`, `[groupId, addedAt(sort: Desc)]`, `[peopleId, addedAt(sort: Desc)]`, `[addedBy, addedAt(sort: Desc)]`
- `groupCompany`: `[companyId]`, `[companyId, groupId]`, `[addedBy]`, `[groupId, addedAt(sort: Desc)]`, `[companyId, addedAt(sort: Desc)]`, `[addedBy, addedAt(sort: Desc)]`

## Application Models

### GroupModel (GraphQL Object Type)

Used for GraphQL API responses and includes all fields from the database schema with proper validation decorators:

```typescript
@ObjectType('Group')
@InputType('GroupInput')
export class GroupModel {
  id!: string;
  name!: string;
  workspaceId!: string;
  description?: string | null;
  emoji?: string | null;
  isPrivate!: boolean;
  type!: GroupType;
  isFavourite?: boolean;
  privateOrder!: number;
  favouriteOrder!: number;
  publicOrder!: number;
  isCollapse?: boolean;
  createdBy!: string;
}
```

### GroupDto (Data Transfer Object)

Used for data transfer operations with validation:

```typescript
export class GroupDto {
  name!: string;
  workspaceId!: string;
  description?: string | null;
  emoji?: string | null;
  isPrivate!: boolean;
  type!: GroupType;
  isFavourite?: boolean;
  publicOrder!: number;
  privateOrder!: number;
  favouriteOrder!: number;
  isCollapse?: boolean;
  createdBy!: string;
}
```

## Request Models

### CreateGroupRequest

For creating new groups:

```typescript
@InputType()
export class CreateGroupRequest {
  name!: string;
  workspaceId!: string;
  description?: string;
  emoji?: string;
  isPrivate!: boolean;
  type!: GroupType;
  isCollapse?: boolean;
  createdBy?: string;
}
```

### UpdateGroupRequest

For updating existing groups:

```typescript
@InputType()
export class UpdateGroupRequest {
  name?: string;
  description?: string;
  emoji?: string;
  isPrivate?: boolean;
  isFavourite?: boolean;
  isCollapse?: boolean;
}
```

### UpdateGroupOrderRequest

For reordering groups:

```typescript
@InputType()
export class UpdateGroupOrderRequest {
  groupId!: string;
  isAfterGroupId?: string;
  workspaceId!: string;
  orderType!: 'public' | 'private' | 'favourite';
}
```

## Usage Patterns

### Group Types and Their Purpose

1. **PEOPLE Groups**
   - Organize individual contacts and people
   - Useful for segmentation by demographics, roles, or relationships
   - Example: "Sales Prospects", "VIP Clients", "Team Members"

2. **COMPANY Groups**
   - Organize business entities and organizations
   - Useful for industry segmentation or business relationships
   - Example: "Tech Companies", "Enterprise Clients", "Partners"

3. **DEAL Groups**
   - Organize business opportunities and deals
   - Useful for pipeline management and sales stages
   - Example: "Q1 Opportunities", "High Value Deals", "Closed Won"

### Privacy and Visibility

- **Private Groups** (`isPrivate: true`)
  - Only visible to the creator
  - Useful for personal organization and notes
  - Default behavior for new groups

- **Public Groups** (`isPrivate: false`)
  - Visible to all workspace members
  - Useful for team collaboration and shared organization

### Ordering System

Groups support three independent ordering systems:
- **`favouriteOrder`** - For groups marked as favorites
- **`privateOrder`** - For private groups
- **`publicOrder`** - For public groups

This allows users to have different sorting preferences for different types of groups.

### Soft Delete Pattern

Groups use soft delete (`isDeleted` flag) rather than hard deletion:
- Preserves data integrity and audit trails
- Allows for potential recovery of accidentally deleted groups
- Maintains referential integrity with related entities

## Best Practices

1. **Naming Conventions**
   - Use descriptive, clear names for groups
   - Consider using emojis for visual identification
   - Keep names concise but meaningful

2. **Group Organization**
   - Use private groups for personal organization
   - Use public groups for team collaboration
   - Leverage favorites for frequently accessed groups

3. **Type Selection**
   - Choose the appropriate GroupType based on the entities you want to organize
   - Consider creating separate groups for different entity types rather than mixing them

4. **Performance Considerations**
   - The database indexes are optimized for common query patterns
   - Consider the workspace scope when querying groups
   - Use the appropriate order fields for sorting operations

## Related Entities

- **`workspace`** - Parent container for groups
- **`user`** - Creator and workspace members
- **`people`** - Individual contacts that can be grouped
- **`company`** - Business entities that can be grouped
- **`column`** - Custom fields for group data organization
- **`view`** - Different perspectives of group data

