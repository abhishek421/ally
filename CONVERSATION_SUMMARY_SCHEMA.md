# conversationSummary Table Schema Documentation

## Overview

The `conversationSummary` table stores concise summaries of conversation message ranges. Each summary represents a condensed version of a sequence of messages within a conversation, useful for managing context windows in AI-powered chat systems.

## Table Name

```
conversationSummary
```

## Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| `id` | UUID | NO | `gen_random_uuid()` | Primary key. Unique identifier for the summary record. |
| `conversationId` | UUID | NO | - | Foreign key to `conversation.id`. Identifies which conversation this summary belongs to. |
| `workspaceId` | UUID | NO | - | Foreign key to `workspace.id`. Identifies which workspace owns this summary. |
| `summaryText` | TEXT | NO | - | The concise summary text (typically 200-500 tokens). Contains the condensed content of the message range. |
| `startMessageId` | UUID | NO | - | Foreign key to `conversationMessage.id`. ID of the first message included in this summary. |
| `endMessageId` | UUID | NO | - | Foreign key to `conversationMessage.id`. ID of the last message included in this summary. |
| `endMessageAt` | TIMESTAMP(6) | NO | - | Timestamp of the message referenced by `endMessageId`. Should be automatically looked up from the `conversationMessage` table. |
| `messageCount` | INTEGER | NO | - | Total number of messages included in the summarized range (from startMessageId to endMessageId, inclusive). |
| `summaryTokens` | INTEGER | NO | - | Token count of the summary text. Used for context window management in AI systems. |
| `createdAt` | TIMESTAMP(6) | NO | `CURRENT_TIMESTAMP` | Timestamp when the summary record was created. |
| `updatedAt` | TIMESTAMP(6) | NO | - | Timestamp when the summary record was last updated. Automatically managed by the application. |

## Relationships

### Foreign Keys

1. **conversation** (via `conversationId`)
   - References: `conversation.id`
   - On Delete: CASCADE
   - On Update: CASCADE

2. **workspace** (via `workspaceId`)
   - References: `workspace.id`
   - On Delete: CASCADE
   - On Update: CASCADE

3. **conversationMessage** (via `startMessageId`)
   - References: `conversationMessage.id`
   - Relation Name: `SummaryStartMessage`
   - On Delete: CASCADE
   - On Update: CASCADE

4. **conversationMessage** (via `endMessageId`)
   - References: `conversationMessage.id`
   - Relation Name: `SummaryEndMessage`
   - On Delete: CASCADE
   - On Update: CASCADE

## Indexes

1. **Composite Index on (conversationId, createdAt)**
   - Name: `conversationSummary_conversationId_createdAt_idx`
   - Purpose: Efficiently query summaries for a conversation ordered by creation time.

2. **Index on workspaceId**
   - Name: `conversationSummary_workspaceId_idx`
   - Purpose: Quickly find all summaries within a workspace.

## Constraints

### Primary Key
- **Constraint Name**: `conversationSummary_pkey`
- **Column**: `id`

### Foreign Key Constraints

1. `conversationSummary_conversationId_fkey` - Links to `conversation` table
2. `conversationSummary_workspaceId_fkey` - Links to `workspace` table
3. `conversationSummary_startMessageId_fkey` - Links to `conversationMessage` table
4. `conversationSummary_endMessageId_fkey` - Links to `conversationMessage` table

### Business Logic Constraints

⚠️ **Important**: The following constraints should be enforced at the application level (not at database level):

1. **Same Conversation Validation**: Both `startMessageId` and `endMessageId` must belong to the same `conversationId`.
2. **Message Order**: `startMessageId` should reference a message that comes before (or at the same time as) `endMessageId` in the conversation.
3. **Message Range**: The messages referenced by `startMessageId` and `endMessageId` must exist in the `conversationMessage` table and belong to the specified `conversationId`.
4. **Token Count**: `summaryTokens` should accurately reflect the token count of `summaryText`.

## Insert Example

### Basic Insert

```sql
INSERT INTO "conversationSummary" (
    "id",
    "conversationId",
    "workspaceId",
    "summaryText",
    "startMessageId",
    "endMessageId",
    "endMessageAt",
    "messageCount",
    "summaryTokens"
) VALUES (
    gen_random_uuid(),                                    -- id (or provide your own UUID)
    '550e8400-e29b-41d4-a716-446655440000',             -- conversationId (must exist in conversation table)
    '550e8400-e29b-41d4-a716-446655440000',             -- workspaceId (must exist in workspace table)
    'Summary of messages discussing the Q4 pipeline and revenue targets...',  -- summaryText
    '01111111-1111-1111-1111-111111111111',             -- startMessageId (must exist in conversationMessage table)
    '02222222-2222-2222-2222-222222222222',             -- endMessageId (must exist in conversationMessage table)
    '2025-11-26 10:30:00.000000',                       -- endMessageAt (timestamp from conversationMessage.timestamp)
    25,                                                  -- messageCount (number of messages in range)
    350                                                  -- summaryTokens (token count of summaryText)
);
```

### Insert with Auto-generated ID

```sql
INSERT INTO "conversationSummary" (
    "conversationId",
    "workspaceId",
    "summaryText",
    "startMessageId",
    "endMessageId",
    "endMessageAt",
    "messageCount",
    "summaryTokens"
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440000',
    'Summary of messages discussing the Q4 pipeline and revenue targets...',
    '01111111-1111-1111-1111-111111111111',
    '02222222-2222-2222-2222-222222222222',
    '2025-11-26 10:30:00.000000',
    25,
    350
)
RETURNING *;
```

### Insert with End Message Timestamp Lookup

If you need to automatically fetch `endMessageAt` from the `conversationMessage` table:

```sql
INSERT INTO "conversationSummary" (
    "conversationId",
    "workspaceId",
    "summaryText",
    "startMessageId",
    "endMessageId",
    "endMessageAt",
    "messageCount",
    "summaryTokens"
)
SELECT 
    '550e8400-e29b-41d4-a716-446655440000'::uuid,  -- conversationId
    '550e8400-e29b-41d4-a716-446655440000'::uuid,  -- workspaceId
    'Summary of messages discussing the Q4 pipeline...',  -- summaryText
    '01111111-1111-1111-1111-111111111111'::uuid,  -- startMessageId
    '02222222-2222-2222-2222-222222222222'::uuid,  -- endMessageId
    cm.timestamp,                                    -- endMessageAt (looked up automatically)
    25,                                              -- messageCount
    350                                              -- summaryTokens
FROM "conversationMessage" cm
WHERE cm.id = '02222222-2222-2222-2222-222222222222'::uuid
RETURNING *;
```

## Query Examples

### Get all summaries for a conversation

```sql
SELECT *
FROM "conversationSummary"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "createdAt" ASC;
```

### Get summaries by workspace

```sql
SELECT *
FROM "conversationSummary"
WHERE "workspaceId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "createdAt" DESC;
```

### Get latest summary for a conversation

```sql
SELECT *
FROM "conversationSummary"
WHERE "conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY "createdAt" DESC
LIMIT 1;
```

### Get summaries with message details

```sql
SELECT 
    cs.*,
    sm.content as start_message_content,
    em.content as end_message_content,
    em.timestamp as end_message_timestamp
FROM "conversationSummary" cs
LEFT JOIN "conversationMessage" sm ON cs."startMessageId" = sm.id
LEFT JOIN "conversationMessage" em ON cs."endMessageId" = em.id
WHERE cs."conversationId" = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY cs."createdAt" DESC;
```

## Data Validation Checklist

Before inserting a record, ensure:

- ✅ `conversationId` exists in the `conversation` table
- ✅ `workspaceId` exists in the `workspace` table and matches the conversation's workspace
- ✅ `startMessageId` exists in the `conversationMessage` table
- ✅ `endMessageId` exists in the `conversationMessage` table
- ✅ Both `startMessageId` and `endMessageId` belong to the same `conversationId`
- ✅ `endMessageAt` matches the timestamp of the message referenced by `endMessageId`
- ✅ `messageCount` accurately reflects the number of messages from startMessageId to endMessageId (inclusive)
- ✅ `summaryTokens` accurately counts tokens in `summaryText`
- ✅ `summaryText` is between 200-500 tokens (recommended range)

## Notes

1. **Cascade Deletes**: If a `conversation`, `workspace`, or `conversationMessage` is deleted, all related `conversationSummary` records will be automatically deleted.

2. **Timestamp Precision**: All timestamps use `TIMESTAMP(6)` precision (microseconds).

3. **UUID Format**: All ID fields use UUID v4 format.

4. **Summary Text Length**: While there's no database constraint on `summaryText` length, the recommended range is 200-500 tokens for optimal context window management.

5. **Token Counting**: The `summaryTokens` field should be calculated using the same tokenizer that the AI system uses (e.g., if using OpenAI, use tiktoken; if using Gemini, use their tokenizer).

## Related Tables

- **conversation**: Contains the parent conversation
- **conversationMessage**: Contains the messages being summarized
- **workspace**: Contains the workspace that owns the conversation

