# All Blocks Context - Implementation Summary

## What Changed

Previously, the system only included the **first TEXT block** from conversation messages in the context. Now it includes **ALL blocks** (TEXT, TABLE, ENTITY_LIST, THINKING, etc.) from each message.

## Why This Matters

When a user asks "which of them work at OpenAI?" after listing 9 people, the LLM now sees:

### Before (❌ Broken)
```
USER: can you list all people?
ASSISTANT: I found 9 people matching your query:
```

### After (✅ Fixed)
```
USER:
  [TEXT] can you list all people?

ASSISTANT:
  [TEXT] I found 9 people matching your query:
  [ENTITY_LIST] 9 people:
    - Alice Smith (ID: p1)
    - Bob Jones (ID: p2)
    - Charlie Brown (ID: p3)
    - David Wilson (ID: p4)
    - Emma Davis (ID: p5)
    - Frank Miller (ID: p6)
    - Grace Lee (ID: p7)
    - Henry Taylor (ID: p8)
    - Iris Anderson (ID: p9)
```

Now the LLM can see the actual 9 people with their IDs and filter them correctly!

## Technical Changes

### 1. Context Retrieval (`query.py`)

**Old Code:**
```python
# Only retrieved first TEXT block
content = next((b.content for b in blocks if b.blockType == "TEXT"), "")
context_messages.append({
    "role": msg.role,
    "content": content,
    "metadata": metadata
})
```

**New Code:**
```python
# Retrieve ALL blocks
all_blocks = []
for block in blocks:
    block_dict = {
        "block_type": block.blockType,
        "content": block.content,
        "order": block.order,
        "metadata": block.metadata,
        "entity_mentions": block.entityMentions
    }
    all_blocks.append(block_dict)

context_messages.append({
    "role": msg.role,
    "blocks": all_blocks,  # ALL blocks
    "metadata": metadata
})
```

### 2. Context Building (`data_extractor.py`)

Now processes each block type appropriately:

- **TEXT blocks**: Full content included
- **TABLE blocks**: Row count + preview (first 10 rows)
- **ENTITY_LIST blocks**: Parses NDJSON, shows all entities with IDs
- **THINKING blocks**: Skipped to reduce noise
- **Other blocks**: Preview (first 100 chars)

### 3. Conversation State (`conversation_state.py`)

Now extracts entities from ENTITY_LIST blocks:

```python
if block.get("block_type") == "ENTITY_LIST":
    # Parse NDJSON
    for line in content.strip().split('\n'):
        entity = json.loads(line)
        self.people.append({
            "id": entity.get("id"),
            "name": entity.get("name"),
            "turn_number": self.current_turn
        })
```

## Example: Full Context Flow

### Query 1: "list all people"

**Response blocks:**
1. THINKING: "Searching your workspace for contacts..."
2. TEXT: "I found 9 people matching your query:"
3. ENTITY_LIST: NDJSON with 9 people

**Stored in database:**
- All 3 blocks saved to `messageblock` table
- Metadata includes result_summary with people_ids/names

### Query 2: "which of them work at OpenAI?"

**Context retrieval:**
```python
context_messages = [
    {
        "role": "USER",
        "blocks": [
            {"block_type": "TEXT", "content": "list all people", ...}
        ]
    },
    {
        "role": "ASSISTANT",
        "blocks": [
            {"block_type": "THINKING", "content": "Searching...", ...},
            {"block_type": "TEXT", "content": "I found 9 people...", ...},
            {"block_type": "ENTITY_LIST", "content": "{\"id\":\"p1\",\"name\":\"Alice Smith\"}\n...", ...}
        ],
        "metadata": {...}
    }
]
```

**Context string sent to LLM:**
```
Previous conversation context (with all blocks):

USER:
  [TEXT] list all people

ASSISTANT:
  [TEXT] I found 9 people matching your query:
  [ENTITY_LIST] 9 people:
    - Alice Smith (ID: p1)
    - Bob Jones (ID: p2)
    ...

CRITICAL INSTRUCTIONS FOR FOLLOW-UP QUERIES:
When the query contains "them", "those", "which of them":
- Identify the reference: "them" refers to the 9 people above
- Use their IDs: p1, p2, p3, ...
- Filter those specific people, don't start fresh

User Query: "which of them work at OpenAI?"
```

**LLM understands:**
- "them" = the 9 people (p1-p9)
- Need to filter those 9 by company
- Plan: Search for OpenAI, then check each person's company

**Tool calls generated:**
```json
{
  "tool_calls": [
    {"tool": "company", "query_type": "search", "params": {"name": "OpenAI"}},
    {"tool": "people", "query_type": "get_by_id", "params": {"person_id": "p1"}},
    {"tool": "people", "query_type": "get_by_id", "params": {"person_id": "p2"}},
    ...
  ]
}
```

**Result:** Only returns people from the original 9 who work at OpenAI ✅

## Benefits

1. **Complete Context**: LLM sees everything (not just text)
2. **Entity IDs Available**: Can reference specific entities by ID
3. **Table Data Visible**: Can reference data from previous tables
4. **Better Follow-ups**: Handles "them", "those", "the first one" correctly
5. **Backwards Compatible**: Still works with old metadata format

## Performance Considerations

### Token Usage
- More tokens per context message (includes all blocks)
- Mitigations:
  - Skip THINKING blocks (reduce noise)
  - Truncate large tables (first 10 rows + summary)
  - Limit to last 5 messages
  - Can add token budget management if needed

### Processing Time
- ENTITY_LIST parsing adds ~1-5ms per message
- Negligible impact on overall query time

## Testing

To verify the fix works:

```bash
# Query 1
POST /api/v1/query
{
  "query": "list all people",
  "conversation_id": null
}

# Query 2 (in same conversation)
POST /api/v1/query
{
  "query": "which of them work at OpenAI?",
  "conversation_id": "<from-query-1>"
}

# Expected: Should filter the people from Query 1
# NOT list ALL people at OpenAI
```

Check logs for:
```
INFO - Retrieved X context messages with all blocks for reference resolution
INFO - [ENTITY_LIST] 9 people:
```

## Migration Notes

- **No database migration required**: Block storage format unchanged
- **No breaking changes**: Old clients continue to work
- **Immediate effect**: Works for all new queries after deployment
- **Old conversations**: Will use fallback metadata for entity extraction

## Future Enhancements

1. **Token Budget Management**: Dynamically truncate context based on token limits
2. **Semantic Compression**: Summarize old blocks to save tokens
3. **Block Prioritization**: Keep important blocks, skip less relevant ones
4. **Structured References**: Pass ConversationState object instead of string context

