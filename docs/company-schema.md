# Company Schema Documentation

This document provides a comprehensive overview of the Company schema used in the SoftSync application, including all fields, relationships, and their meanings.

## Overview

The Company schema represents business entities in the system. It includes core company information, contact details, relationships with people, and various metadata fields for tracking and organization purposes.

## Core Fields

### Primary Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `String` (UUID) | Yes | Unique identifier for the company |
| `name` | `String` (max 100 chars) | Yes | Company name |
| `description` | `String` | No | Optional description of the company |
| `imageUrl` | `String` | No | URL to company logo/image |
| `privacyLevel` | `PrivacyLevel` | No | Privacy setting (defaults to PRIVATE) |

### Timestamps

| Field | Type | Description |
|-------|------|-------------|
| `createdAt` | `DateTime` | When the company record was created (auto-generated) |
| `updatedAt` | `DateTime` | When the company record was last updated (auto-updated) |

### Workspace & User Context

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workspaceId` | `String` (UUID) | Yes | ID of the workspace this company belongs to |
| `createdBy` | `String` (UUID) | Yes | ID of the user who created this company |

### Avatar Management

| Field | Type | Description |
|-------|------|-------------|
| `avatarKey` | `String` | S3 key for company avatar file |
| `avatarContentType` | `String` | MIME type of the avatar file |
| `avatarSize` | `Int` | Size of the avatar file in bytes |
| `avatarEtag` | `String` | ETag for avatar file integrity |
| `avatarUpdatedAt` | `DateTime` | When the avatar was last updated |

## Related Data Models

### Contact Information

#### Emails
Companies can have multiple email addresses through the `emails` relationship.

**Email Model Fields:**
- `id`: Unique identifier
- `value`: Email address (max 255 chars)
- `type`: Email type enum (`personal`, `work`, `other`)
- `isPrimary`: Boolean indicating if this is the primary email
- `verified`: Boolean indicating if the email is verified
- `createdAt`/`updatedAt`: Timestamps

#### Phone Numbers
Companies can have multiple phone numbers through the `phoneNumbers` relationship.

**Phone Number Model Fields:**
- `id`: Unique identifier
- `value`: Phone number (max 50 chars)
- `type`: Phone type enum (`mobile`, `work`, `home`, `other`)
- `isPrimary`: Boolean indicating if this is the primary phone number
- `createdAt`/`updatedAt`: Timestamps

#### Addresses
Companies can have multiple addresses through the `addresses` relationship.

**Address Model Fields:**
- `id`: Unique identifier
- `value`: Address text (max 500 chars)
- `type`: Address type enum (`home`, `work`, `other`)
- `isPrimary`: Boolean indicating if this is the primary address
- `createdAt`/`updatedAt`: Timestamps

#### URLs
Companies can have multiple URLs through the `urls` relationship.

**URL Model Fields:**
- `id`: Unique identifier
- `value`: URL (max 500 chars)
- `label`: Optional label for the URL (max 100 chars)
- `isPrimary`: Boolean indicating if this is the primary URL
- `createdAt`/`updatedAt`: Timestamps

### People Relationships

#### People Metadata
Companies are linked to people through the `peopleMetaData` relationship, which represents the association between companies and people.

**Metadata Model Fields:**
- `id`: Unique identifier
- `peopleId`: ID of the associated person
- `companyId`: ID of the associated company
- `isPeoplePrimary`: Boolean indicating if this is the primary company for the person
- `isCompanyPrimary`: Boolean indicating if this is the primary person for the company
- `createdAt`/`updatedAt`: Timestamps

### Business Relationships

#### Groups
Companies can be added to groups through the `groupCompanies` relationship for organizational purposes.

#### Deals
Companies can be associated with deals through the `dealMetaData` relationship for CRM functionality.

#### Interactions
Companies can have interaction records through the `interaction` relationship for tracking communications and activities.

#### Reminders
Companies can have associated reminders through the `reminder` relationship.

### Custom Fields

#### Column Values
Companies support custom fields through the `columnValues` relationship, allowing for flexible data storage beyond the core schema.

#### Column Value Select Options
For select-type custom fields, companies can have predefined options through the `columnValueSelectOption` relationship.

## Enums

### PrivacyLevel
- `PRIVATE`: Company data is private to the workspace
- `PUBLIC`: Company data is publicly accessible

### EmailType
- `personal`: Personal email address
- `work`: Work/business email address
- `other`: Other type of email address

### PhoneNumberType
- `mobile`: Mobile phone number
- `work`: Work phone number
- `home`: Home phone number
- `other`: Other type of phone number

### AddressType
- `home`: Home address
- `work`: Work/business address
- `other`: Other type of address

### CompanyOperation
Used for batch operations on company data:
- `CREATE`: Create new record
- `UPDATE`: Update existing record
- `DELETE`: Delete existing record

## Database Indexes

The company table has several indexes for optimal query performance:

- `workspaceId`: For workspace-scoped queries
- `createdBy`: For user-scoped queries
- `name, workspaceId`: For name searches within workspace
- `privacyLevel, workspaceId`: For privacy-filtered queries
- `workspaceId, privacyLevel, createdBy`: For complex filtering
- `workspaceId, createdAt(sort: Desc)`: For chronological ordering
- `name`: For global name searches
- `workspaceId, name`: For workspace-specific name searches
- `description`: For description-based searches
- `updatedAt`: For change tracking

## GraphQL Integration

The company schema is fully integrated with GraphQL through:

- **ObjectType**: `CompanyModel` class with GraphQL field decorators
- **InputType**: `CreateCompanyInput` and `UpdateCompanyInput` for mutations
- **Enum Registration**: All enums are registered with GraphQL for type safety
- **Validation**: Class-validator decorators for input validation

## Usage Examples

### Creating a Company
```typescript
const companyData = {
  name: "Acme Corporation",
  description: "Leading technology company",
  emails: [
    {
      value: "contact@acme.com",
      type: "work",
      isPrimary: true,
      verified: true
    }
  ],
  phoneNumbers: [
    {
      value: "+1-555-0123",
      type: "work",
      isPrimary: true
    }
  ],
  addresses: [
    {
      value: "123 Business St, City, State 12345",
      type: "work",
      isPrimary: true
    }
  ],
  urls: [
    {
      value: "https://acme.com",
      label: "Website",
      isPrimary: true
    }
  ],
  privacyLevel: "PRIVATE",
  workspaceId: "workspace-uuid"
};
```

### Updating Company Data
```typescript
const updateData = {
  id: "company-uuid",
  name: "Acme Corp Inc.",
  emails: [
    {
      operation: "UPDATE",
      id: "email-uuid",
      value: "info@acme.com",
      isPrimary: true
    }
  ]
};
```

## Best Practices

1. **Required Fields**: Always provide `name` and `workspaceId` when creating companies
2. **Primary Contacts**: Mark one email, phone number, address, and URL as primary
3. **Privacy**: Use appropriate privacy levels based on data sensitivity
4. **Validation**: Ensure email addresses are properly formatted and URLs are valid
5. **Relationships**: Use the metadata relationship to properly link people to companies
6. **Indexing**: Leverage the database indexes for efficient querying by workspace, creator, or privacy level

## Related Documentation

- [Workspace Schema](./workspace-schema.md)
- [People Schema](./people-schema.md)
- [API Documentation](../api/README.md)
- [Database Schema](../libs/prisma-schema/README.md)

