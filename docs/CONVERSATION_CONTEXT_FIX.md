# Conversation Context Memory Fix

## Issue Summary

The system was **retrieving conversation context** but **not using entity data** properly, causing follow-up queries with references like "them", "those", "which of them" to fail.

### Example Failure Case

**Query 1**: "give me a list of all people"  
**Response 1**: Returns 9 people successfully ✅

**Query 2**: "which of them work with OpenAI?"  
**Expected**: Filter the 9 people by those working at OpenAI  
**Actual**: Treats it as a fresh query, searches for "OpenAI" company, tries to list ALL people at OpenAI (ignoring the previous 9) ❌

### Root Cause

The data extractor was receiving `context_messages` but only extracting the **first TEXT block**, not **ALL blocks** (TABLE, ENTITY_LIST, etc.) which contain the actual entity data.

#### What Was Happening

```python
# Before fix - Only first TEXT block
blocks = await client.messageblock.find_many(...)
content = next((b.content for b in blocks if b.blockType == "TEXT"), "")

context_messages.append({
    "role": msg.role,
    "content": content,  # ❌ Missing other blocks!
    "metadata": metadata
})
```

So the LLM saw:
```
USER: can you list all people?
ASSISTANT: I found 9 people matching your query:
```

But **NOT** the actual ENTITY_LIST block with all people:
```
[ENTITY_LIST] 9 people:
  - Alice Smith (ID: p1)
  - Bob Jones (ID: p2)
  - Charlie Brown (ID: p3)
  ...
```

## The Fix

### 1. Retrieve ALL Blocks (`query.py`)

Changed context retrieval to include **all blocks** from each message:

```python
# After fix - Include ALL blocks
for msg in reversed(messages[1:]):
    blocks = await client.messageblock.find_many(...)
    
    # Convert all blocks to serializable format
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
        "blocks": all_blocks,  # ✨ ALL blocks (not just text)
        "metadata": metadata
    })
```

### 2. Enhanced Context Building (`data_extractor.py`)

Now processes **all blocks** (TEXT, TABLE, ENTITY_LIST) from context messages:

```python
# After fix - Process all block types
for msg in context_messages[-5:]:
    blocks = msg.get("blocks", [])
    
    for block in blocks:
        block_type = block.get("block_type")
        
        if block_type == "TEXT":
            # Include text
            context_lines.append(f"  [TEXT] {content}")
        
        elif block_type == "TABLE":
            # Include table with row preview
            context_lines.append(f"  [TABLE] {row_count} rows:")
            context_lines.append(table_preview)
        
        elif block_type == "ENTITY_LIST":
            # Parse NDJSON and show all entities with IDs
            entities = parse_ndjson(content)
            context_lines.append(f"  [ENTITY_LIST] {len(entities)} {entity_type}:")
            for entity in entities:
                context_lines.append(f"    - {entity.name} (ID: {entity.id})")
```

### 2. Critical Instructions for Follow-up Queries

Added detailed instructions for handling conversational references:

```
CRITICAL INSTRUCTIONS FOR FOLLOW-UP QUERIES:
When the query contains references to previous results (e.g., "them", "those", "which of them"):

1. Identify the reference: "them", "those", "which of them", "the first one"
2. Find the entities in context: Look at "Entities returned" section
3. Use the entity IDs: Extract IDs from context and use them in tool calls
4. Create the right tool calls: Filter previous results, don't start fresh

EXAMPLES:
- "which of them work with OpenAI?" (after listing 9 people)
  → Use the 9 person IDs from context
  → Search for OpenAI company
  → Filter the 9 people by company_id
```

### 3. Updated Base Prompt Template

Added guidance in `data_extractor_prompt.py`:

```
CONVERSATIONAL REFERENCES (FOLLOW-UP QUERIES):
- "them" / "those" / "these" → Refers to entities from previous response
- "which of them [filter]" → Filter the previous result set
- "the first one" → Ordinal reference to previous results
```

## How It Works Now

### Flow for "which of them work with OpenAI?"

1. **Context Retrieval** (ENHANCED ✨)
   - Retrieves 2 messages from conversation history
   - **Now includes ALL blocks** (not just text):
     - TEXT blocks
     - TABLE blocks  
     - ENTITY_LIST blocks
   - Conversation state rebuilt: 9 people

2. **Comprehensive Context Building** (NEW ✨)
   - Processes **all block types** from each message
   - Parses ENTITY_LIST blocks to extract actual entity data
   - Builds rich context string:
   ```
   Previous conversation context (with all blocks):
   
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

3. **Smart Parsing** (NEW ✨)
   - LLM sees the 9 people with their IDs
   - Recognizes "them" refers to the 9 people
   - Plans tool calls to filter those 9 people by company

4. **Execution**
   - Searches for "OpenAI" company → Gets company_id
   - Filters the 9 person IDs by checking company association
   - Returns only people from the original 9 who work at OpenAI

## Files Changed

1. **`src/interfaces/api/v1/routes/query.py`**
   - Changed context retrieval to include **ALL blocks** (not just first TEXT block)
   - Now serializes complete block data: block_type, content, metadata, entity_mentions
   - Provides rich multi-block context to downstream agents

2. **`src/core/agents/extraction/data_extractor.py`**
   - Enhanced `_parse_optimized_query()` to process **all block types**
   - Parses ENTITY_LIST blocks to extract entity IDs and names
   - Includes TABLE blocks with row previews
   - Added critical instructions for follow-up queries with examples

3. **`src/application/services/conversation/conversation_state.py`**
   - Updated `rebuild_from_messages()` to handle new blocks-based format
   - Parses ENTITY_LIST blocks as primary source of entity data
   - Falls back to metadata for backwards compatibility
   - Added json import for NDJSON parsing

4. **`src/shared/prompts/data_extractor_prompt.py`**
   - Added "CONVERSATIONAL REFERENCES" section
   - Documented common reference patterns ("them", "those", "the first one")
   - Provided guidance on filtering vs fresh queries

## Testing

To test this fix:

```python
# Query 1
"list all people"
→ Should return N people

# Query 2 (in same conversation)
"which of them work at OpenAI?"
→ Should filter the N people, not list ALL people at OpenAI
→ Should use person IDs from Query 1 context

# Query 3
"show me the first one"
→ Should get the first person from Query 1
```

## Impact

- ✅ Follow-up queries with "them", "those" now work
- ✅ Ordinal references ("the first one") work
- ✅ Filtering previous results works
- ✅ Conversation feels more natural and contextual
- ✅ No breaking changes to existing queries

## Future Improvements

1. **Conversation State Integration**: Pass structured `ConversationState` object directly to data extractor (not just raw messages)
2. **Reference Resolution**: Add a dedicated reference resolver that maps "them" → specific entity IDs before parsing
3. **Context Window Management**: Limit entity data in context to avoid token bloat (currently includes all entities)
4. **Semantic Understanding**: Use embeddings to match ambiguous references to entities

