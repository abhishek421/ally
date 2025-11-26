# conversationMessage Table Documentation

This document provides complete details about the `conversationMessage` table for inserting and reading data.

## Table Overview

The `conversationMessage` table stores individual messages within AI conversations. Each message belongs to a conversation and contains role-based content (user, assistant, system, or function messages).

**Table Name**: `conversationMessage` (case-sensitive in Prisma, but PostgreSQL table names are case-insensitive)

---

## Table Structure

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|------------|-----------|----------|---------|-------------|
| `id` | UUID | NOT NULL | Generated | Primary key - Unique identifier for the message |
| `conversationId` | UUID | NOT NULL | - | Foreign key to `conversation.id` |
| `role` | TEXT (Enum) | NOT NULL | - | Message role: `USER`, `ASSISTANT`, `SYSTEM`, or `FUNCTION` |
| `content` | TEXT | NOT NULL | - | The message content/text |
| `metadata` | JSONB | NULL | NULL | Optional JSON metadata for the message |
| `functionCalls` | JSONB | NULL | NULL | Optional JSON array of function calls (for FUNCTION role) |
| `timestamp` | TIMESTAMP(6) | NOT NULL | CURRENT_TIMESTAMP | Message timestamp with microsecond precision |

### Primary Key
- **Column**: `id`
- **Type**: UUID
- **Constraint Name**: `conversationMessage_pkey`

### Foreign Keys

| Foreign Key Column | References Table | References Column | On Delete | On Update |
|-------------------|------------------|------------------|-----------|-----------|
| `conversationId` | `conversation` | `id` | CASCADE | CASCADE |

**Important**: When a conversation is deleted, all its messages are automatically deleted (CASCADE).

### Indexes

The table has the following indexes for optimized queries:

1. **`conversationMessage_conversationId_idx`**
   - Columns: `conversationId`
   - Purpose: Fast lookup of all messages in a conversation

2. **`conversationMessage_conversationId_timestamp_idx`**
   - Columns: `conversationId`, `timestamp`
   - Purpose: Fast retrieval of messages in chronological order for a conversation

3. **`conversationMessage_role_idx`**
   - Columns: `role`
   - Purpose: Fast filtering by message role

---

## Enum Values: ConversationRole

The `role` column accepts one of the following values:

- **`USER`** - Message from the user
- **`ASSISTANT`** - Message from the AI assistant
- **`SYSTEM`** - System message
- **`FUNCTION`** - Function call message

**Note**: The enum values are case-sensitive. Use uppercase exactly as shown.

---

## Data Types Details

### UUID
- Format: Standard UUID v4 format (e.g., `550e8400-e29b-41d4-a716-446655440000`)
- Can be generated using PostgreSQL's `gen_random_uuid()` function

### TIMESTAMP(6)
- Format: `YYYY-MM-DD HH:MM:SS.ffffff` (with microsecond precision)
- Timezone: Stored without timezone (use UTC for consistency)
- Example: `2024-01-15 14:30:45.123456`

### JSONB
- PostgreSQL's binary JSON format
- Supports nested objects and arrays
- Can be queried using JSON operators
- Example: `{"key": "value", "nested": {"field": 123}}`

---

## INSERT Operations

### Basic INSERT (All Required Fields)

```sql
INSERT INTO "conversationMessage" (
    "id",
    "conversationId",
    "role",
    "content",
    "timestamp"
)
VALUES (
    gen_random_uuid(),  -- Auto-generate UUID
    '550e8400-e29b-41d4-a716-446655440000',  -- Valid conversationId UUID
    'USER',  -- Role: USER, ASSISTANT, SYSTEM, or FUNCTION
    'Hello, how can I help you?',  -- Message content
    CURRENT_TIMESTAMP  -- Current timestamp
);
```

### INSERT with Optional Fields (metadata and functionCalls)

```sql
INSERT INTO "conversationMessage" (
    "id",
    "conversationId",
    "role",
    "content",
    "metadata",
    "functionCalls",
    "timestamp"
)
VALUES (
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'ASSISTANT',
    'I can help you with that.',
    '{"source": "api", "model": "gpt-4"}'::jsonb,  -- JSON metadata
    '[{"name": "get_weather", "arguments": {"city": "New York"}}]'::jsonb,  -- Function calls
    CURRENT_TIMESTAMP
);
```

### INSERT with Specific UUID

```sql
INSERT INTO "conversationMessage" (
    "id",
    "conversationId",
    "role",
    "content",
    "timestamp"
)
VALUES (
    '123e4567-e89b-12d3-a456-426614174000',  -- Specific UUID
    '550e8400-e29b-41d4-a716-446655440000',
    'SYSTEM',
    'System initialization complete',
    '2024-01-15 10:30:00.000000'::timestamp(6)
);
```

### INSERT with Function Role

```sql
INSERT INTO "conversationMessage" (
    "id",
    "conversationId",
    "role",
    "content",
    "functionCalls",
    "timestamp"
)
VALUES (
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'FUNCTION',
    'Function call executed',
    '[
        {
            "name": "search_database",
            "arguments": {
                "query": "find users",
                "limit": 10
            },
            "result": {
                "count": 5,
                "items": []
            }
        }
    ]'::jsonb,
    CURRENT_TIMESTAMP
);
```

### INSERT Multiple Messages (Bulk Insert)

```sql
INSERT INTO "conversationMessage" (
    "id",
    "conversationId",
    "role",
    "content",
    "timestamp"
)
VALUES
    (gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000', 'USER', 'First message', CURRENT_TIMESTAMP),
    (gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000', 'ASSISTANT', 'Response to first', CURRENT_TIMESTAMP),
    (gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000', 'USER', 'Second message', CURRENT_TIMESTAMP);
```

### INSERT with NULL Optional Fields

```sql
INSERT INTO "conversationMessage" (
    "id",
    "conversationId",
    "role",
    "content",
    "metadata",
    "functionCalls",
    "timestamp"
)
VALUES (
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'USER',
    'Simple message without metadata',
    NULL,  -- Explicitly set to NULL
    NULL,  -- Explicitly set to NULL
    CURRENT_TIMESTAMP
);
```

---

## SELECT Operations

### Get All Messages for a Conversation (Ordered by Timestamp)

```sql
SELECT 
    "id",
    "conversationId",
    "role",
    "content",
    "metadata",
    "functionCalls",
    "timestamp"
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "timestamp" ASC;
```

### Get Messages by Role

```sql
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "role" = 'USER'
ORDER BY "timestamp" ASC;
```

### Get Latest N Messages

```sql
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "timestamp" DESC
LIMIT 10;
```

### Get Messages with Metadata

```sql
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "metadata" IS NOT NULL
ORDER BY "timestamp" ASC;
```

### Get Messages with Function Calls

```sql
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "functionCalls" IS NOT NULL
ORDER BY "timestamp" ASC;
```

### Get Messages in Date Range

```sql
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "timestamp" >= '2024-01-01 00:00:00'::timestamp(6)
  AND "timestamp" <= '2024-01-31 23:59:59'::timestamp(6)
ORDER BY "timestamp" ASC;
```

### Get Message Count by Role

```sql
SELECT 
    "role",
    COUNT(*) as message_count
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
GROUP BY "role";
```

### Query JSONB Fields (metadata)

```sql
-- Get messages where metadata contains a specific key
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "metadata" ? 'source';  -- Check if 'source' key exists

-- Get messages where metadata has a specific value
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "metadata"->>'model' = 'gpt-4';  -- Get value and compare
```

### Query JSONB Fields (functionCalls)

```sql
-- Get messages with specific function name in functionCalls
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "functionCalls"::text LIKE '%search_database%';

-- More precise JSONB query
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND EXISTS (
    SELECT 1
    FROM jsonb_array_elements("functionCalls") AS func
    WHERE func->>'name' = 'search_database'
  );
```

### Get Single Message by ID

```sql
SELECT *
FROM "conversationMessage"
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

---

## UPDATE Operations

### Update Message Content

```sql
UPDATE "conversationMessage"
SET "content" = 'Updated message content'
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

### Update Metadata

```sql
UPDATE "conversationMessage"
SET "metadata" = '{"updated": true, "version": 2}'::jsonb
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

### Update Function Calls

```sql
UPDATE "conversationMessage"
SET "functionCalls" = '[
    {
        "name": "updated_function",
        "arguments": {"new": "value"}
    }
]'::jsonb
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

### Update Timestamp

```sql
UPDATE "conversationMessage"
SET "timestamp" = '2024-01-15 15:30:00.000000'::timestamp(6)
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

### Update Multiple Fields

```sql
UPDATE "conversationMessage"
SET 
    "content" = 'Updated content',
    "metadata" = '{"updated": true}'::jsonb,
    "timestamp" = CURRENT_TIMESTAMP
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

---

## DELETE Operations

### Delete Single Message

```sql
DELETE FROM "conversationMessage"
WHERE "id" = '123e4567-e89b-12d3-a456-426614174000';
```

### Delete All Messages in a Conversation

```sql
DELETE FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000';
```

### Delete Messages by Role

```sql
DELETE FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "role" = 'SYSTEM';
```

### Delete Messages Older Than Date

```sql
DELETE FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
  AND "timestamp" < '2024-01-01 00:00:00'::timestamp(6);
```

**Note**: When a conversation is deleted, all its messages are automatically deleted due to CASCADE foreign key constraint.

---

## Important Constraints and Rules

### Required Fields
- `id` - Must be a valid UUID
- `conversationId` - Must reference an existing `conversation.id`
- `role` - Must be one of: `USER`, `ASSISTANT`, `SYSTEM`, `FUNCTION`
- `content` - Cannot be NULL or empty
- `timestamp` - Automatically set to CURRENT_TIMESTAMP if not provided

### Foreign Key Constraints
- `conversationId` must exist in the `conversation` table
- If the referenced conversation is deleted, all messages are automatically deleted (CASCADE)

### Data Validation
- `role` must be exactly one of the enum values (case-sensitive)
- `content` should not be empty (application-level validation recommended)
- UUIDs must be in valid UUID format
- JSONB fields must contain valid JSON

### Best Practices

1. **Always provide conversationId**: Every message must belong to a conversation
2. **Use proper role values**: Stick to the enum values exactly
3. **Order messages by timestamp**: Use `ORDER BY timestamp ASC` when retrieving conversation history
4. **Handle JSONB carefully**: Validate JSON structure before inserting
5. **Use transactions**: When inserting multiple messages, wrap in a transaction
6. **Index usage**: Queries filtering by `conversationId` are optimized by indexes

---

## Example Use Cases

### Complete Conversation Flow

```sql
-- 1. Create a conversation (assume conversationId exists)
-- conversationId: '550e8400-e29b-41d4-a716-446655440000'

-- 2. Insert user message
INSERT INTO "conversationMessage" ("id", "conversationId", "role", "content", "timestamp")
VALUES (
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'USER',
    'What is the weather today?',
    CURRENT_TIMESTAMP
);

-- 3. Insert assistant response
INSERT INTO "conversationMessage" ("id", "conversationId", "role", "content", "metadata", "timestamp")
VALUES (
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'ASSISTANT',
    'I can help you check the weather. Let me call a function to get that information.',
    '{"model": "gpt-4", "tokens": 25}'::jsonb,
    CURRENT_TIMESTAMP
);

-- 4. Insert function call
INSERT INTO "conversationMessage" ("id", "conversationId", "role", "content", "functionCalls", "timestamp")
VALUES (
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'FUNCTION',
    'Function call executed',
    '[{"name": "get_weather", "arguments": {"location": "New York"}}]'::jsonb,
    CURRENT_TIMESTAMP
);

-- 5. Retrieve all messages in order
SELECT 
    "role",
    "content",
    "timestamp"
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "timestamp" ASC;
```

---

## Common Patterns

### Pattern 1: Insert and Return ID

```sql
INSERT INTO "conversationMessage" ("id", "conversationId", "role", "content", "timestamp")
VALUES (gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000', 'USER', 'Message', CURRENT_TIMESTAMP)
RETURNING "id";
```

### Pattern 2: Check if Conversation Exists Before Insert

```sql
INSERT INTO "conversationMessage" ("id", "conversationId", "role", "content", "timestamp")
SELECT 
    gen_random_uuid(),
    '550e8400-e29b-41d4-a716-446655440000',
    'USER',
    'Message',
    CURRENT_TIMESTAMP
WHERE EXISTS (
    SELECT 1 FROM "conversation" 
    WHERE "id" = '550e8400-e29b-41d4-a716-446655440000'
);
```

### Pattern 3: Get Message Count

```sql
SELECT COUNT(*) as total_messages
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000';
```

### Pattern 4: Get Last Message

```sql
SELECT *
FROM "conversationMessage"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "timestamp" DESC
LIMIT 1;
```

---

## Error Handling

### Common Errors and Solutions

1. **Foreign Key Violation**
   ```
   ERROR: insert or update on table "conversationMessage" violates foreign key constraint
   ```
   **Solution**: Ensure `conversationId` exists in the `conversation` table

2. **Invalid UUID Format**
   ```
   ERROR: invalid input syntax for type uuid
   ```
   **Solution**: Use valid UUID format or `gen_random_uuid()` function

3. **Invalid Enum Value**
   ```
   ERROR: invalid input value for enum ConversationRole
   ```
   **Solution**: Use exactly: `USER`, `ASSISTANT`, `SYSTEM`, or `FUNCTION`

4. **Invalid JSONB**
   ```
   ERROR: invalid input syntax for type jsonb
   ```
   **Solution**: Ensure JSON is valid and use `::jsonb` cast

---

## Performance Considerations

1. **Indexes**: Queries filtering by `conversationId` are fast due to indexes
2. **Ordering**: Use `ORDER BY timestamp ASC` for chronological order (indexed)
3. **Bulk Inserts**: Use transactions for multiple inserts
4. **JSONB Queries**: JSONB queries can be slower; consider extracting frequently queried fields

---

## Related Tables

- **`conversation`**: Parent table containing conversation metadata
- **`user`**: Referenced through `conversation.userId`
- **`workspace`**: Referenced through `conversation.workspaceId`

---

**Last Updated**: Based on Prisma schema analysis
**Schema Location**: `sync-core/libs/prisma-schema/prisma/schema.prisma`

