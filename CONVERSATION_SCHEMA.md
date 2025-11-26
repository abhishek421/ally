# conversation Table Schema Documentation

## Overview

The `conversation` table stores conversation sessions between users and AI assistants. Each conversation represents a continuous chat session within a workspace, containing multiple messages and optional summaries. Conversations are used to maintain context and history in AI-powered chat applications.

## Table Name

```
conversation
```

## Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | UUID | NO | `gen_random_uuid()` | Primary key. Unique identifier for the conversation. |
| `workspaceId` | UUID | NO | - | Foreign key to `workspace.id`. Identifies which workspace owns this conversation. |
| `userId` | UUID | NO | - | Foreign key to `user.id`. Identifies the user who created/owns this conversation. |
| `title` | TEXT | YES | NULL | Optional title or name for the conversation. Can be user-provided or auto-generated. |
| `context` | JSONB | YES | NULL | Optional JSON object containing conversation metadata, context, settings, or additional data. Can store custom fields, preferences, or state information. |
| `createdAt` | TIMESTAMP(6) | NO | `CURRENT_TIMESTAMP` | Timestamp when the conversation was created. |
| `updatedAt` | TIMESTAMP(6) | NO | - | Timestamp when the conversation was last updated. Automatically managed by the application (updates on any change). |

## Relationships

### Foreign Keys

1. **user** (via `userId`)
   - References: `user.id`
   - On Delete: CASCADE
   - On Update: CASCADE
   - Description: The user who created and owns this conversation.

2. **workspace** (via `workspaceId`)
   - References: `workspace.id`
   - On Delete: CASCADE
   - On Update: CASCADE
   - Description: The workspace this conversation belongs to.

### One-to-Many Relations

3. **messages** (via `conversationMessage`)
   - Related Table: `conversationMessage`
   - Foreign Key: `conversationMessage.conversationId` → `conversation.id`
   - Description: All messages that belong to this conversation.

4. **summaries** (via `conversationSummary`)
   - Related Table: `conversationSummary`
   - Foreign Key: `conversationSummary.conversationId` → `conversation.id`
   - Description: All summaries created for this conversation.

## Indexes

1. **Composite Index on (workspaceId, userId)**
   - Columns: `workspaceId`, `userId`
   - Purpose: Efficiently query conversations for a specific user within a workspace.

2. **Index on workspaceId**
   - Column: `workspaceId`
   - Purpose: Quickly find all conversations within a workspace.

3. **Index on userId**
   - Column: `userId`
   - Purpose: Quickly find all conversations created by a specific user.

4. **Index on createdAt**
   - Column: `createdAt`
   - Purpose: Efficiently sort conversations by creation time (e.g., latest conversations first).

## Constraints

### Primary Key
- **Constraint Name**: `conversation_pkey`
- **Column**: `id`

### Foreign Key Constraints

1. `conversation_userId_fkey` - Links to `user` table
2. `conversation_workspaceId_fkey` - Links to `workspace` table

### Business Logic Constraints

⚠️ **Important**: The following constraints should be enforced at the application level:

1. **Workspace Membership**: The `userId` must be a member of the specified `workspaceId` (check `workspaceMember` table).
2. **Context JSON Structure**: If `context` is provided, it should be valid JSON. Common fields might include:
   - Conversation settings (e.g., `{ "model": "gemini-2.0-flash", "temperature": 0.7 }`)
   - UI state (e.g., `{ "pinned": false, "archived": false }`)
   - Custom metadata (e.g., `{ "tags": ["sales", "q4"], "priority": "high" }`)

## Insert Examples

### Basic Insert

```sql
INSERT INTO "conversation" (
    "id",
    "workspaceId",
    "userId",
    "title",
    "context"
) VALUES (
    gen_random_uuid(),                                    -- id (or provide your own UUID)
    '550e8400-e29b-41d4-a716-446655440000',             -- workspaceId (must exist in workspace table)
    '6edf9760-c26e-4a4c-b641-1a23381f9268',             -- userId (must exist in user table)
    'Q4 Sales Pipeline Discussion',                      -- title (optional)
    '{"model": "gemini-2.0-flash", "temperature": 0.7}'::jsonb  -- context (optional JSON)
);
```

### Insert with Auto-generated ID

```sql
INSERT INTO "conversation" (
    "workspaceId",
    "userId",
    "title",
    "context"
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    '6edf9760-c26e-4a4c-b641-1a23381f9268',
    'Q4 Sales Pipeline Discussion',
    '{"model": "gemini-2.0-flash", "temperature": 0.7}'::jsonb
)
RETURNING *;
```

### Insert without Optional Fields

```sql
INSERT INTO "conversation" (
    "workspaceId",
    "userId"
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    '6edf9760-c26e-4a4c-b641-1a23381f9268'
)
RETURNING id, "workspaceId", "userId", "createdAt";
```

### Insert with Complex Context JSON

```sql
INSERT INTO "conversation" (
    "workspaceId",
    "userId",
    "title",
    "context"
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    '6edf9760-c26e-4a4c-b641-1a23381f9268',
    'Account Health Analysis',
    '{
        "model": "gemini-2.0-flash",
        "temperature": 0.7,
        "maxTokens": 8192,
        "settings": {
            "enableFunctionCalls": true,
            "enableStreaming": true
        },
        "metadata": {
            "source": "web",
            "tags": ["sales", "analysis"],
            "priority": "high"
        }
    }'::jsonb
)
RETURNING *;
```

## Query Examples

### Get all conversations for a user in a workspace

```sql
SELECT *
FROM "conversation"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "userId" = '6edf9760-c26e-4a4c-b641-1a23381f9268'
ORDER BY "createdAt" DESC;
```

### Get all conversations in a workspace

```sql
SELECT *
FROM "conversation"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "createdAt" DESC;
```

### Get a specific conversation with user details

```sql
SELECT 
    c.*,
    u.email as user_email,
    u."firstName" as user_first_name,
    u."lastName" as user_last_name
FROM "conversation" c
INNER JOIN "user" u ON c."userId" = u.id
WHERE c.id = '550e8400-e29b-41d4-a716-446655440000';
```

### Get conversation with message count

```sql
SELECT 
    c.*,
    COUNT(cm.id) as message_count,
    MAX(cm.timestamp) as last_message_at
FROM "conversation" c
LEFT JOIN "conversationMessage" cm ON c.id = cm."conversationId"
WHERE c.id = '550e8400-e29b-41d4-a716-446655440000'
GROUP BY c.id;
```

### Get conversations with latest message preview

```sql
SELECT 
    c.*,
    cm.content as latest_message_content,
    cm.role as latest_message_role,
    cm.timestamp as latest_message_time
FROM "conversation" c
LEFT JOIN LATERAL (
    SELECT content, role, timestamp
    FROM "conversationMessage"
    WHERE "conversationId" = c.id
    ORDER BY timestamp DESC
    LIMIT 1
) cm ON true
WHERE c."workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY c."createdAt" DESC;
```

### Get conversations with summary count

```sql
SELECT 
    c.*,
    COUNT(cs.id) as summary_count,
    MAX(cs."createdAt") as latest_summary_at
FROM "conversation" c
LEFT JOIN "conversationSummary" cs ON c.id = cs."conversationId"
WHERE c."workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
GROUP BY c.id
ORDER BY c."createdAt" DESC;
```

### Search conversations by title

```sql
SELECT *
FROM "conversation"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "title" ILIKE '%pipeline%'
ORDER BY "createdAt" DESC;
```

### Get conversations created in the last 7 days

```sql
SELECT *
FROM "conversation"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "createdAt" >= NOW() - INTERVAL '7 days'
ORDER BY "createdAt" DESC;
```

### Query conversations by context JSON field

```sql
-- Find conversations with specific model
SELECT *
FROM "conversation"
WHERE "context"->>'model' = 'gemini-2.0-flash'
  AND "workspaceId" = '550e8400-e29b-41d4-a716-446655440000';

-- Find conversations with specific tag in metadata
SELECT *
FROM "conversation"
WHERE "context"->'metadata'->'tags' ? 'sales'
  AND "workspaceId" = '550e8400-e29b-41d4-a716-446655440000';
```

## Update Examples

### Update conversation title

```sql
UPDATE "conversation"
SET 
    "title" = 'Updated Conversation Title',
    "updatedAt" = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440000';
```

### Update conversation context

```sql
UPDATE "conversation"
SET 
    "context" = jsonb_set(
        COALESCE("context", '{}'::jsonb),
        '{metadata}',
        '{"tags": ["sales", "q4", "updated"]}'::jsonb
    ),
    "updatedAt" = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440000';
```

### Merge context JSON

```sql
UPDATE "conversation"
SET 
    "context" = COALESCE("context", '{}'::jsonb) || '{"lastUpdated": "2025-11-26"}'::jsonb,
    "updatedAt" = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440000';
```

## Delete Examples

### Delete a conversation (cascades to messages and summaries)

```sql
DELETE FROM "conversation"
WHERE id = '550e8400-e29b-41d4-a716-446655440000';
```

⚠️ **Warning**: Deleting a conversation will automatically delete:
- All related `conversationMessage` records (CASCADE)
- All related `conversationSummary` records (CASCADE)

### Delete all conversations for a user in a workspace

```sql
DELETE FROM "conversation"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "userId" = '6edf9760-c26e-4a4c-b641-1a23381f9268';
```

### Delete old conversations (older than 90 days)

```sql
DELETE FROM "conversation"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "createdAt" < NOW() - INTERVAL '90 days';
```

## Data Validation Checklist

Before inserting a record, ensure:

- ✅ `workspaceId` exists in the `workspace` table
- ✅ `userId` exists in the `user` table
- ✅ User is a member of the specified workspace (check `workspaceMember` table)
- ✅ `title` is not empty if provided (application-level validation)
- ✅ `context` is valid JSON if provided
- ✅ UUIDs are in valid UUID v4 format

## Context JSON Examples

The `context` field can store various types of metadata. Here are common use cases:

### AI Model Configuration
```json
{
  "model": "gemini-2.0-flash",
  "temperature": 0.7,
  "maxTokens": 8192,
  "topP": 0.95
}
```

### UI State
```json
{
  "uiState": {
    "pinned": false,
    "archived": false,
    "folder": "work"
  }
}
```

### Conversation Metadata
```json
{
  "metadata": {
    "tags": ["sales", "q4", "important"],
    "priority": "high",
    "source": "web",
    "sessionId": "abc123"
  }
}
```

### Combined Example
```json
{
  "model": "gemini-2.0-flash",
  "temperature": 0.7,
  "settings": {
    "enableFunctionCalls": true,
    "enableStreaming": true
  },
  "metadata": {
    "tags": ["sales"],
    "priority": "high"
  },
  "uiState": {
    "pinned": true
  }
}
```

## Notes

1. **Cascade Deletes**: 
   - If a `user` or `workspace` is deleted, all related `conversation` records will be automatically deleted.
   - When a `conversation` is deleted, all related `conversationMessage` and `conversationSummary` records are automatically deleted.

2. **Timestamp Precision**: All timestamps use `TIMESTAMP(6)` precision (microseconds).

3. **UUID Format**: All ID fields use UUID v4 format.

4. **Auto-update**: The `updatedAt` field is automatically updated by the application when any field changes. Ensure your application framework handles this.

5. **Context Field**: The `context` JSONB field is flexible and can store any valid JSON structure. Use it for conversation-specific settings, metadata, or state that doesn't need a dedicated column.

6. **Title Generation**: If `title` is not provided, applications often auto-generate titles from the first user message or based on conversation content.

## Related Tables

- **user**: Contains the user who created the conversation
- **workspace**: Contains the workspace that owns the conversation
- **conversationMessage**: Contains all messages within this conversation
- **conversationSummary**: Contains summaries of message ranges in this conversation
- **workspaceMember**: Validates that the user is a member of the workspace

## Common Use Cases

1. **Creating a new conversation**: Insert a new record with `workspaceId` and `userId`.
2. **Listing user conversations**: Query by `workspaceId` and `userId`, ordered by `createdAt`.
3. **Finding recent conversations**: Query by `workspaceId` and filter by `createdAt`.
4. **Storing conversation settings**: Use the `context` JSON field to store model settings, preferences, etc.
5. **Conversation metadata**: Use `context` JSON for tags, priorities, custom fields.

