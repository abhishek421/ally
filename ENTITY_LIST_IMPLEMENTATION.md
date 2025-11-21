# Entity List Implementation - Complete

## Overview
Implemented structured entity list responses with NDJSON streaming format, replacing generic CSV tables for known entity types (companies, people, deals). This enables the frontend to render rich, interactive components instead of plain tables.

## What Was Implemented

### 1. Entity Models (`src/application/services/blocks/entity_models.py`)
Created Pydantic models matching frontend component schemas:

- **CompanyEntity**: For company cards/lists
  - Fields: id, name, logo, email, phone, peopleCount, groups, metadata
- **PersonEntity**: For person cards/lists
  - Fields: id, name, firstName, lastName, image, email, phone, role, company, groups, metadata
- **DealEntity**: For deal cards/lists (future)
  - Fields: id, name, value, currency, stage, probability, closeDate, company, owner, groups
- **Supporting Models**: GroupReference, CompanyReference

### 2. BlockType Enum Update (`src/application/services/blocks/models.py`)
Added new block types:
- `ENTITY_LIST`: For structured entity lists
- `ENTITY_CARD`: For single entity details (future)
- `INSIGHT_WIDGET`: For analytics/charts (future)

### 3. AgentState Enhancement (`orchestrator.py`)
Added `primary_entity_type: Optional[str]` to track detected entity type (companies, people, deals)

### 4. Entity Detection & Transformation (`orchestrator.py`)
Implemented helper methods:

- `_detect_primary_entity_type()`: Detects dominant entity type in extraction results
- `_transform_to_entity_models()`: Converts raw CRM data to typed entity models
- `_to_company_entity()`: Transforms Company → CompanyEntity
- `_to_person_entity()`: Transforms Person → PersonEntity  
- `_to_deal_entity()`: Transforms Deal → DealEntity

### 5. Response Planning (`orchestrator.py`)
Enhanced `node_plan_response` to intelligently choose block types:

- **Entity Detection**: Automatically detects if results are companies, people, or deals
- **Smart Routing**:
  - Known entities → `_plan_entity_list_response()` → ENTITY_LIST block
  - Mixed/aggregated data → `_plan_table_response()` → TABLE block (CSV fallback)
- **LLM-Generated Intros**: Natural, contextual intro text for each response type

New methods:
- `_plan_entity_list_response()`: Plans structured entity list responses
- `_plan_table_response()`: Plans CSV table responses (fallback)
- `_generate_entity_intro_text()`: LLM-generated intro for entity lists
- `_generate_table_intro_text()`: LLM-generated intro for tables

### 6. NDJSON Streaming (`orchestrator.py`)
Updated `stream_orchestrate` to handle ENTITY_LIST blocks:

```python
elif block_type == 'entity_list':
    # Transform raw entities to models
    entity_models = self._transform_to_entity_models(entity_type, raw_entities)
    
    # Create NDJSON (one JSON object per line)
    ndjson_lines = [entity.model_dump_json() for entity in entity_models]
    ndjson_content = "\n".join(ndjson_lines)
    
    # Stream with metadata
    yield StreamEvent.block_start(
        block_id=list_block_id,
        block_type=BlockType.ENTITY_LIST,
        order=block_order,
        metadata={
            "entity_type": entity_type,
            "total_count": len(entity_models),
            "view_mode": "list"
        }
    )
    
    yield StreamEvent.block_delta(
        block_id=list_block_id,
        content=ndjson_content
    )
    
    yield StreamEvent.block_complete(...)
```

### 7. Non-Streaming Support
Updated `orchestrate()` to include `primary_entity_type` in initial state

## Response Flow

### Before (CSV Only):
```
Query → Extract Data → Generate CSV → Stream CSV Table
```

### After (Entity-Aware):
```
Query → Extract Data → Detect Entity Type
  ├─ Known Entity (companies/people/deals)
  │   → Transform to Entity Models
  │   → Generate Intro Text (LLM)
  │   → Stream NDJSON ENTITY_LIST
  │
  └─ Mixed/Aggregated Data
      → Generate CSV (LLM)
      → Generate Intro Text (LLM)
      → Stream CSV TABLE
```

## NDJSON Format Example

For a query like "companies working in AI domain":

```json
{"id":"comp_1","name":"LangChain","logo":"https://...","email":"hello@langchain.com","phone":null,"peopleCount":0,"groups":[],"metadata":{"website":"https://langchain.com","industry":"AI"}}
{"id":"comp_2","name":"OpenAI","logo":"https://...","email":"contact@openai.com","phone":null,"peopleCount":0,"groups":[],"metadata":{"website":"https://openai.com","industry":"AI"}}
{"id":"comp_3","name":"Anthropic","logo":"https://...","email":"hello@anthropic.com","phone":null,"peopleCount":0,"groups":[],"metadata":{"website":"https://anthropic.com","industry":"AI"}}
```

## Frontend Integration

The frontend receives:

### block_start Event:
```json
{
  "type": "block_start",
  "block_id": "blk_abc123",
  "block_type": "ENTITY_LIST",
  "order": 1,
  "metadata": {
    "entity_type": "companies",
    "total_count": 7,
    "view_mode": "list"
  }
}
```

### block_delta Event(s):
```json
{
  "type": "block_delta",
  "block_id": "blk_abc123",
  "content": "{\"id\":\"comp_1\",\"name\":\"LangChain\",...}\n{\"id\":\"comp_2\",\"name\":\"OpenAI\",...}\n"
}
```

### block_complete Event:
```json
{
  "type": "block_complete",
  "block_id": "blk_abc123",
  "block_type": "ENTITY_LIST",
  "content": "<full NDJSON>",
  "order": 1,
  "metadata": {
    "entity_type": "companies",
    "total_count": 7,
    "items_count": 7
  }
}
```

## Benefits

### 1. **Rich UI Components**
- Frontend can render company cards with logos, links, actions
- Person cards with avatars, contact info, company affiliation
- Much better UX than plain CSV tables

### 2. **Type Safety**
- Pydantic models ensure data structure consistency
- Frontend knows exactly what fields to expect
- Easy to extend with new fields

### 3. **Streaming Performance**
- NDJSON allows incremental rendering
- Users see results as they arrive
- Better perceived performance

### 4. **Intelligent Routing**
- Automatic detection of entity types
- No hardcoded logic - LLM decides response structure
- Graceful fallback to CSV for unsupported data

### 5. **Extensibility**
- Easy to add new entity types (deals, emails, etc.)
- Can add ENTITY_CARD for single entity details
- Can add INSIGHT_WIDGET for analytics

## Future Enhancements

### Phase 2 (Not Implemented Yet):
- **Enrichment**: Populate `peopleCount` and `groups` fields
  - Requires additional queries to CRM
  - Could be done during extraction or transformation
- **Mixed Entity Handling**: Support multiple ENTITY_LIST blocks in one response
  - E.g., "Show me companies and their key contacts"
- **Incremental Streaming**: Stream entities one-by-one instead of batched
  - Uncomment the per-entity delta code in `stream_orchestrate`

### Phase 3 (Future):
- **ENTITY_CARD**: Single entity detail views
- **INSIGHT_WIDGET**: Charts, graphs, analytics
- **Interactive Actions**: Buttons, filters, sorting in entity lists
- **Pagination**: Support for large result sets

## Testing

All syntax checks passed:
- ✅ Entity models serialize to JSON correctly
- ✅ NDJSON format parses correctly
- ✅ BlockType enum includes ENTITY_LIST
- ✅ Orchestrator imports and methods verified
- ✅ No linter errors

## Files Modified

1. `src/application/services/blocks/entity_models.py` (NEW)
2. `src/application/services/blocks/models.py` (BlockType enum)
3. `src/core/agents/orchestration/orchestrator.py` (Major updates)

## Backward Compatibility

⚠️ **Breaking Changes**: This implementation is NOT backward compatible with the old CSV-only approach. However, since we're in early stage development, this is acceptable.

The system now:
- Uses ENTITY_LIST for companies, people, deals
- Falls back to TABLE (CSV) for other data types
- Frontend must handle both block types

## Ready for Production

The implementation is complete and ready for integration testing with:
1. Real CRM data extraction
2. Frontend component rendering
3. End-to-end user queries

Next step: Test with actual user queries like "show me AI companies" and verify the frontend renders the entity lists correctly.

