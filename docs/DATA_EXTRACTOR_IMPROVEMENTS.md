# Data Extractor Multi-Tool Coordination Improvements

## Overview

The Data Extractor Agent has been significantly enhanced to intelligently coordinate multiple tools for complex, relationship-based queries. It now automatically understands entity relationships and can plan multi-step queries without explicit instructions.

## Key Improvements

### 1. **Schema-Aware Intelligence**

Created a new `schema_relations.py` module that maps all entity relationships:

- **Company ↔ People**: Via metaData table
- **People → Emails**: Direct link via person_id
- **Company → Emails**: Direct link via company_id  
- **People → Interactions**: Via person_id
- **Company → Interactions**: Via company_id
- **Group ↔ People/Company**: Many-to-many relationships

The agent now understands these relationships and automatically plans multi-step queries when needed.

### 2. **Parallel Execution Support**

Independent tool calls can now run in parallel for better performance:

```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {"name": "Acme"},
      "can_run_parallel": true
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {"first_name": "John"},
      "can_run_parallel": true
    }
  ]
}
```

The execution engine:
- Groups tool calls into execution batches
- Runs independent calls in parallel within each batch
- Handles sequential dependencies across batches

### 3. **Enhanced Prompt with Relationship Guidance**

The data extractor prompt now includes:
- Complete entity relationship map
- Common query pattern recognition
- Multi-step execution examples
- Parallel vs sequential execution guidance

### 4. **Automatic Multi-Step Planning**

The agent now automatically recognizes queries that span multiple entities:

**Example Query**: "What people do we have linked to OpenAI company?"

**Automatic Plan**:
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {"name": "OpenAI", "limit": 1},
      "reason": "Find OpenAI company to get company_id",
      "can_run_parallel": false
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {"company_id": "<id_from_previous_call>", "limit": 50},
      "reason": "Get all people linked to OpenAI using resolved company_id",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Two-step: 1) Find OpenAI company, 2) Get people linked to that company",
  "requires_multi_step": true
}
```

## Query Examples

### Example 1: People at a Company
```
User: "Show me all people at Stripe"

Execution:
1. Search for company "Stripe" → get company_id
2. Search people with company_id filter
3. Return people data with company context
```

### Example 2: Company Emails
```
User: "What emails do we have from TechCorp?"

Execution:
1. Search for company "TechCorp" → get company_id
2. Query email tool with company_id
3. Return emails linked to TechCorp
```

### Example 3: Person Interactions
```
User: "Show all interactions with John Smith"

Execution:
1. Search for person "John Smith" → get person_id
2. Query interaction tool with person_id
3. Return interactions with person details
```

### Example 4: Complex Multi-Step
```
User: "Get me people and interactions for Acme Corp"

Execution:
1. Search for company "Acme Corp" → get company_id
2. Parallel execution:
   - Get people with company_id
   - Get interactions with company_id
3. Return combined data
```

### Example 5: Independent Parallel Queries
```
User: "Show me companies matching 'Tech' and people named 'Sarah'"

Execution:
Parallel execution (both independent):
- Search companies with name filter "Tech"
- Search people with first_name filter "Sarah"
Return both result sets
```

## Technical Details

### Execution Flow

```
1. Parse Query
   ↓
2. Identify Relationships & Dependencies
   ↓
3. Plan Tool Calls
   ↓
4. Group into Execution Batches
   - Batch 1: Independent calls (parallel)
   - Batch 2: Calls dependent on Batch 1 (sequential)
   - ...
   ↓
5. Execute Batches
   - Within batch: asyncio.gather() for parallel execution
   - Across batches: sequential with parameter resolution
   ↓
6. Aggregate Results
   ↓
7. Return Structured Data
```

### Parameter Resolution

Dependent tool calls use placeholder syntax:
- `<id_from_previous_call>` - Use 'id' field from previous result
- `<company_id_from_previous_call>` - Use 'company_id' from previous result
- `<person_id_from_previous_call>` - Use 'person_id' from previous result

The resolver automatically:
1. Searches through previous results (most recent first)
2. Extracts the requested field
3. Replaces placeholder with actual value
4. Skips tool call if critical parameter cannot be resolved

### Batch Grouping Algorithm

```python
def _group_into_execution_batches(tool_calls):
    """
    Groups tool calls based on:
    1. Placeholder dependencies (must be sequential)
    2. can_run_parallel flag (can group together)
    3. Order preservation (maintains logical flow)
    """
    batches = []
    current_batch = []
    
    for tool_call in tool_calls:
        if has_placeholders(tool_call):
            # Finalize current batch, start new one
            if current_batch:
                batches.append(current_batch)
            batches.append([tool_call])  # Own batch
            current_batch = []
        elif can_run_parallel(tool_call) and current_batch:
            # Add to current parallel batch
            current_batch.append(tool_call)
        else:
            # Start new batch
            if current_batch:
                batches.append(current_batch)
            current_batch = [tool_call]
    
    return batches
```

## Performance Impact

### Sequential (Old) vs Parallel (New)

**Scenario**: Query for "companies named 'Tech' and people named 'John'"

**Old Approach** (Sequential):
```
Time = Company_Search_Time + People_Search_Time
Example: 200ms + 250ms = 450ms total
```

**New Approach** (Parallel):
```
Time = max(Company_Search_Time, People_Search_Time)
Example: max(200ms, 250ms) = 250ms total
Improvement: ~45% faster
```

### Multi-Step with Parallel Sub-Steps

**Scenario**: "Get people and interactions for Acme Corp"

**Execution**:
```
Batch 1 (Sequential): Search company "Acme" (200ms)
Batch 2 (Parallel):   Search people + Search interactions
                      max(180ms, 220ms) = 220ms
Total: 420ms (vs 600ms if all sequential)
```

## Common Query Patterns Recognized

The agent automatically recognizes these patterns:

1. **"People at/from [Company]"**
   → Company search + People search with company_id

2. **"Emails from [Person]"**
   → Use person_name directly (email tool resolves internally)

3. **"Interactions with [Company/Person]"**
   → Get entity id + Interaction search

4. **"Companies and people in [Group]"**
   → Group lookup + Entity searches

5. **"Who do we know at [Company]"**
   → Company search + People search

## Configuration

No additional configuration needed. The improvements are automatically active.

### Optional: Adjusting Parallel Execution

In `data_extractor.py`, you can tune parallel execution behavior:

```python
# Maximum parallel tasks per batch (default: unlimited)
MAX_PARALLEL_TASKS_PER_BATCH = 10

# Enable/disable parallel execution globally
ENABLE_PARALLEL_EXECUTION = True
```

## Monitoring & Debugging

### Reasoning Traces

Every query now includes detailed reasoning traces:

```json
{
  "_reasoning_traces": [
    {
      "step": "parse_query",
      "timestamp": "2024-01-15T10:30:00Z",
      "decision": "Planned 2 tool call(s)",
      "tools_planned": ["company", "people"],
      "execution_plan": "Find company then get linked people"
    },
    {
      "step": "execute_company",
      "timestamp": "2024-01-15T10:30:00.150Z",
      "tool": "company",
      "query_type": "search",
      "params": {"name": "OpenAI"},
      "success": true,
      "result_count": 1
    },
    {
      "step": "execute_people",
      "timestamp": "2024-01-15T10:30:00.380Z",
      "tool": "people",
      "query_type": "search",
      "params": {"company_id": "comp-123"},
      "success": true,
      "result_count": 15
    }
  ]
}
```

### Logging

Enhanced logging for troubleshooting:

```
INFO: Grouped 3 tool calls into 2 execution batch(es)
INFO: Executing batch 1/2 with 1 tool(s)
INFO: Executing batch 2/2 with 2 tool(s)
INFO: Executing 2 independent tools in parallel
DEBUG: Tool 1: Resolved placeholder '<id_from_previous_call>' -> 'comp-123'
INFO: Data extraction completed in 420 ms
```

## Testing

### Unit Tests

Test the new capabilities:

```python
# Test parallel execution
async def test_parallel_execution():
    tool_calls = [
        {"tool": "company", "query_type": "search", 
         "params": {"name": "Acme"}, "can_run_parallel": True},
        {"tool": "people", "query_type": "search", 
         "params": {"first_name": "John"}, "can_run_parallel": True}
    ]
    
    results = await extractor._execute_tools_async(tool_calls, ws_id, user_id)
    
    # Should execute in parallel
    assert len(results) == 2
    assert results[0]["success"] and results[1]["success"]

# Test dependency resolution
async def test_dependency_resolution():
    tool_calls = [
        {"tool": "company", "query_type": "search", 
         "params": {"name": "OpenAI"}},
        {"tool": "people", "query_type": "search", 
         "params": {"company_id": "<id_from_previous_call>"}}
    ]
    
    results = await extractor._execute_tools_async(tool_calls, ws_id, user_id)
    
    # Second call should use resolved company_id
    assert results[1]["success"]
    assert "company_id" in results[1]["result"].data
```

### Integration Tests

Test real-world scenarios:

```python
async def test_people_at_company():
    query = "what people do we have linked to OpenAI company?"
    
    result = await extractor.extract(
        optimized_query=query,
        workspace_id=ws_id,
        user_id=user_id
    )
    
    # Should return people data
    assert "people" in result
    assert len(result["people"]) > 0
    
    # Should have company context
    assert result["people"][0].get("company_name") == "OpenAI"
```

## Migration Notes

### Breaking Changes

None. The improvements are backward compatible.

### Deprecated Features

None. All existing functionality is preserved.

### New Fields in Response

- `requires_multi_step`: Boolean indicating if query needed multiple steps
- `can_run_parallel`: Optional flag in tool call specifications
- Enhanced `_reasoning_traces` with batch execution info

## Best Practices

1. **Trust the Agent**: Let it automatically plan multi-step queries
2. **Use Descriptive Queries**: "people at OpenAI" is better than "people OpenAI"
3. **Leverage Parallel Execution**: Request independent data sets when possible
4. **Monitor Reasoning Traces**: Use them to understand query execution
5. **Handle Empty Results**: Previous step returning no results will skip dependent steps

## Future Enhancements

Potential improvements:

1. **Smart Caching**: Cache relationship lookups to avoid redundant queries
2. **Query Optimization**: Automatically optimize query order based on cardinality
3. **Predictive Prefetching**: Anticipate likely follow-up queries
4. **Cost-Based Execution**: Choose execution strategy based on data size estimates
5. **Cross-Entity Aggregations**: Support complex aggregations across relationships

## Related Documentation

- [Schema Relations API](./schemas/) - Entity relationship details
- [Tool Documentation](../src/tools/) - Individual tool capabilities
- [Query Examples](./TEST_QUERIES.md) - Example queries and expected results

