# People Schema Documentation

## Overview

The `people` table is a core entity in the SoftSync system that stores comprehensive information about individuals. It serves as the central hub for managing contact information, personal details, and relationships with other entities in the system.

## Table Structure

### Primary Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `String` (UUID) | Primary Key, Not Null | Unique identifier for the person record |
| `firstName` | `String` (VARCHAR 100) | Not Null | Person's first name |
| `lastName` | `String` (VARCHAR 100) | Nullable | Person's last name |
| `jobTitle` | `String` (VARCHAR 1000) | Nullable | Person's job title or position |
| `description` | `String` | Nullable | Additional description or notes about the person |
| `dateOfBirth` | `DateTime` (DATE) | Nullable | Person's date of birth |
| `gender` | `String` | Nullable | Person's gender |
| `imageUrl` | `String` | Nullable | URL to the person's profile image |

### Privacy and Access Control

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `privacyLevel` | `PrivacyLevel` | Default: PRIVATE | Controls visibility and access to the person's data |

**PrivacyLevel Enum Values:**
- `PRIVATE`: Data is only visible to authorized users within the workspace
- `PUBLIC`: Data can be shared more broadly

### Workspace and Ownership

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `workspaceId` | `String` (UUID) | Not Null, Foreign Key | ID of the workspace this person belongs to |
| `createdBy` | `String` (UUID) | Not Null, Foreign Key | ID of the user who created this person record |

### Timestamps

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `createdAt` | `DateTime` (TIMESTAMP) | Not Null, Default: now() | When the person record was created |
| `updatedAt` | `DateTime` (TIMESTAMP) | Not Null, Auto-updated | When the person record was last modified |

### Avatar Management

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `avatarKey` | `String` | Nullable | S3 key for the person's avatar image |
| `avatarContentType` | `String` | Nullable | MIME type of the avatar image |
| `avatarSize` | `Int` | Nullable | Size of the avatar image in bytes |
| `avatarEtag` | `String` | Nullable | ETag for the avatar image (for caching) |
| `avatarUpdatedAt` | `DateTime` | Nullable | When the avatar was last updated |

## Related Entities

### One-to-Many Relationships

The `people` table has relationships with several other entities:

#### Contact Information
- **`emails`**: Collection of email addresses associated with the person
- **`phoneNumbers`**: Collection of phone numbers associated with the person
- **`addresses`**: Collection of physical addresses associated with the person
- **`urls`**: Collection of URLs/websites associated with the person

#### Business Relationships
- **`companyMetaData`**: Junction table linking people to companies with metadata
- **`dealMetaData`**: Collection of deals associated with the person
- **`groupPeople`**: Junction table for group memberships

#### Activity and Interactions
- **`interaction`**: Collection of interactions (emails, calls, meetings, etc.)
- **`reminder`**: Collection of reminders related to the person
- **`userIntraction`**: Collection of user interactions with the person

#### System Relationships
- **`columnValues`**: Custom field values for the person
- **`columnValueSelectOption`**: Select options for custom fields

### Many-to-One Relationships

- **`creator`**: Reference to the user who created this person record
- **`workspace`**: Reference to the workspace this person belongs to

## Related Entity Schemas

### Email Schema
```sql
email {
  id        String     @id @default(uuid()) @db.Uuid
  value     String     @db.VarChar(255)
  type      EmailType? -- personal, work, other
  isPrimary Boolean    @default(false)
  verified  Boolean    @default(false)
  createdAt DateTime   @default(now()) @db.Timestamp(6)
  updatedAt DateTime   @updatedAt @db.Timestamp(6)
  personId  String?    @db.Uuid
  companyId String?    @db.Uuid
}
```

### Phone Number Schema
```sql
phoneNumber {
  id        String           @id @default(uuid()) @db.Uuid
  value     String           @db.VarChar(50)
  type      PhoneNumberType? -- mobile, work, home, other
  isPrimary Boolean          @default(false)
  createdAt DateTime         @default(now()) @db.Timestamp(6)
  updatedAt DateTime         @updatedAt @db.Timestamp(6)
  personId  String?          @db.Uuid
  companyId String?          @db.Uuid
}
```

### Address Schema
```sql
address {
  id        String       @id @default(uuid()) @db.Uuid
  value     String?      @db.VarChar(500)
  type      AddressType? -- home, work, other
  createdAt DateTime     @default(now()) @db.Timestamp(6)
  updatedAt DateTime     @updatedAt @db.Timestamp(6)
  isPrimary Boolean      @default(false)
  personId  String?      @db.Uuid
  companyId String?      @db.Uuid
}
```

### URL Schema
```sql
url {
  id        String   @id @default(uuid()) @db.Uuid
  label     String?  @db.VarChar(100)
  value     String   @db.VarChar(500)
  isPrimary Boolean  @default(false)
  createdAt DateTime @default(now()) @db.Timestamp(6)
  updatedAt DateTime @updatedAt @db.Timestamp(6)
  personId  String?  @db.Uuid
  companyId String?  @db.Uuid
}
```

### Company Metadata Schema
```sql
metaData {
  id               String   @id @default(uuid()) @db.Uuid
  isPeoplePrimary  Boolean  @default(false)
  isCompanyPrimary Boolean  @default(false)
  createdAt        DateTime @default(now()) @db.Timestamp(6)
  updatedAt        DateTime @updatedAt @db.Timestamp(6)
  peopleId         String   @db.Uuid
  companyId        String   @db.Uuid
}
```

## Database Indexes

The `people` table includes several indexes for optimal query performance:

### Primary Indexes
- `@@index([workspaceId])` - For workspace-scoped queries
- `@@index([createdBy])` - For creator-based queries
- `@@index([privacyLevel, workspaceId])` - For privacy-filtered queries
- `@@index([workspaceId, privacyLevel, createdBy])` - Composite privacy and ownership queries

### Search and Sorting Indexes
- `@@index([workspaceId, createdAt(sort: Desc)])` - For chronological listing
- `@@index([firstName, lastName])` - For name-based searches
- `@@index([workspaceId, firstName, lastName])` - For workspace-scoped name searches
- `@@index([jobTitle])` - For job title searches
- `@@index([updatedAt])` - For recent updates
- `@@index([dateOfBirth])` - For birthday queries

## Usage Examples

### Creating a Person
```typescript
const newPerson = {
  workspaceId: "workspace-uuid",
  firstName: "John",
  lastName: "Doe",
  jobTitle: "Software Engineer",
  description: "Senior developer with expertise in TypeScript",
  dateOfBirth: new Date("1990-01-15"),
  gender: "Male",
  privacyLevel: PrivacyLevel.PRIVATE,
  emails: [
    {
      value: "john.doe@company.com",
      type: EmailType.work,
      isPrimary: true,
      verified: true
    }
  ],
  phoneNumbers: [
    {
      value: "+1-555-123-4567",
      type: PhoneNumberType.mobile,
      isPrimary: true
    }
  ]
};
```

### Querying People
```typescript
// Find all people in a workspace
const people = await prisma.people.findMany({
  where: { workspaceId: "workspace-uuid" },
  include: {
    emails: true,
    phoneNumbers: true,
    addresses: true,
    urls: true,
    companyMetaData: {
      include: {
        company: true
      }
    }
  }
});

// Search by name
const searchResults = await prisma.people.findMany({
  where: {
    workspaceId: "workspace-uuid",
    OR: [
      { firstName: { contains: "John" } },
      { lastName: { contains: "Doe" } }
    ]
  }
});
```

## Data Validation Rules

### Field Constraints
- `firstName`: Required, maximum 100 characters
- `lastName`: Optional, maximum 100 characters
- `jobTitle`: Optional, maximum 1000 characters
- `description`: Optional, no length limit
- `dateOfBirth`: Optional, must be a valid date
- `gender`: Optional, free text field
- `imageUrl`: Optional, must be a valid URL if provided

### Business Rules
- Each person must belong to exactly one workspace
- Each person must have a creator (user who created the record)
- Privacy level defaults to PRIVATE if not specified
- Avatar fields are optional and used for S3 storage integration
- Related entities (emails, phones, etc.) are optional but provide contact information

## Security Considerations

- **Privacy Level**: Controls data visibility within the workspace
- **Workspace Isolation**: People records are isolated by workspace
- **Creator Tracking**: All records track who created them for audit purposes
- **Soft Delete**: Consider implementing soft delete for data retention
- **Data Encryption**: Sensitive fields should be encrypted at rest

## Performance Considerations

- **Indexing**: Multiple indexes support common query patterns
- **Pagination**: Use cursor-based pagination for large result sets
- **Eager Loading**: Include related entities only when needed
- **Caching**: Consider caching frequently accessed person data
- **Search**: Use full-text search indexes for name and description fields

## Migration and Maintenance

- **Schema Changes**: Always use Prisma migrations for schema updates
- **Data Migration**: Test data migrations thoroughly in staging
- **Index Maintenance**: Monitor index usage and performance
- **Cleanup**: Implement cleanup jobs for orphaned records
- **Backup**: Regular backups of person data due to business criticality

