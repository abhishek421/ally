# DataExtractorAgent Implementation Status

## 📋 Current Status

**Status**: 🚧 **Placeholder Only** - Needs Full Implementation

The `DataExtractorAgent` currently exists as a placeholder file with only a comment:
```python
# DataExtractorAgent
# Has multiple tools to search on different DB, tables, or other data storages
```

## 🎯 Required Responsibilities

According to the README and architecture documents, the DataExtractorAgent must:

1. ✅ **Execute database queries via tools**
   - Use ToolFactory to create appropriate tool instances
   - Call tools with proper query types and parameters
   - Handle tool results and errors

2. ✅ **Handle workspace/tenant isolation**
   - All tool operations should be scoped to workspace_id
   - Tools already implement workspace isolation, but agent needs to pass workspace_id

3. ⚠️ **Apply role-based access control**
   - Validate user permissions for accessing data
   - Tools have placeholder `_validate_workspace_access()` method
   - Agent needs to ensure user_id is passed to tools

4. ✅ **Aggregate data from multiple sources**
   - Parse optimized query to determine which tools to use
   - Execute queries across multiple tools if needed
   - Combine results from different data sources

5. ⚠️ **Handle pagination and large datasets**
   - Tools support pagination via limit/offset
   - Agent needs to handle paginated results and aggregate them
   - Handle large result sets efficiently

## 🔧 Implementation Requirements

### Core Components Needed

#### 1. **Query Parsing/Understanding**
The agent receives an `optimized_query` (string) from QueryOptimizerAgent. It needs to:
- Parse the optimized query to understand:
  - Which entities are mentioned (companies, people, emails, etc.)
  - What operations are needed (search, get, list, analytics)
  - What filters/parameters are required
  - Whether multiple tools need to be called

**Options:**
- **Option A**: LLM-based parsing (using DATA_EXTRACTOR_CONFIG LLM provider)
  - Use LLM to convert optimized_query into structured tool calls
  - More flexible but adds latency and cost
- **Option B**: Rule-based/pattern matching
  - Use keyword matching, entity extraction
  - Faster but less flexible
- **Option C**: Hybrid approach
  - Use rules for simple queries, LLM for complex ones

#### 2. **Tool Selection Logic**
Determine which tools to use based on query:
- **Company queries** → `CompanyTool`
- **People/Contact queries** → `PeopleTool`
- **Email queries** → `EmailTool`
- **Interaction queries** → `InteractionTool`
- **Group queries** → `GroupTool`
- **Workspace queries** → `WorkspaceTool`

#### 3. **Tool Execution**
- Create tool instances using `ToolFactory.create_tool()`
- Pass workspace_id and user_id to tools
- Execute appropriate QueryType operations:
  - `QueryType.SEARCH` - for search queries with filters
  - `QueryType.GET_BY_ID` - for specific entity lookups
  - `QueryType.LIST` - for listing entities
  - `QueryType.ANALYTICS` - for aggregated data

#### 4. **Result Aggregation**
- Collect results from all executed tools
- Handle multi-tool queries (e.g., "companies AND their emails")
- Structure data for ResponseFormatterAgent
- Handle errors gracefully (partial results if some tools fail)

#### 5. **Error Handling**
- Handle tool execution failures
- Provide meaningful error messages
- Log errors for debugging
- Return partial results if possible

### Input/Output Interface

**Input** (from pipeline state):
```python
{
    "optimized_query": str,  # e.g., "The user is asking you to fetch and analyze all closed deals from 2023..."
    "user_query": str,       # Original user query
}
```

**Output** (to pipeline state):
```python
{
    "extracted_data": {
        "results": [...],      # Combined results from tools
        "sources": [...],      # Which tools were used
        "metadata": {...},     # Query metadata, pagination info, etc.
        "errors": [...]        # Any errors encountered (optional)
    }
}
```

### Configuration Available

From `config/settings.py`:
- `DATA_EXTRACTOR_CONFIG` - LLM provider configuration
  - Can use OpenAI, Anthropic, or Gemini
  - Configurable via environment variables:
    - `DATA_EXTRACTOR_PROVIDER`
    - `DATA_EXTRACTOR_MODEL`
    - `DATA_EXTRACTOR_API_KEY`

### Available Tools

All tools are implemented and ready to use:
- ✅ `CompanyTool` - Search, GetById, List, Create, Update, Analytics
- ✅ `PeopleTool` - Search, GetById, List, Analytics
- ✅ `EmailTool` - Search, GetById, List, Analytics
- ✅ `WorkspaceTool` - GetById, List
- ⚠️ `InteractionTool` - Placeholder (needs implementation)
- ⚠️ `GroupTool` - Placeholder (needs implementation)

### Integration Points

1. **Pipeline Integration** (`graph/pipeline.py`):
   - Currently has placeholder `_data_extractor_node()` method
   - Line 48-52: TODO comment indicates implementation needed
   - Receives state with `optimized_query`
   - Must return state with `extracted_data`

2. **ToolFactory** (`tools/tool_factory.py`):
   - Fully implemented
   - Provides `create_tool(tool_name, workspace_id, user_id)`
   - Tool registry includes all available tools

3. **BaseTool** (`tools/base_tool.py`):
   - All tools inherit from this
   - Provides caching, error handling, logging
   - Standardized `ToolResult` format

## 📝 Missing Implementation Details

### 1. **Query Parsing Strategy**
- Need to decide: LLM-based vs rule-based vs hybrid
- Need prompt template if using LLM
- Need entity extraction logic
- Need to map parsed query to tool calls

### 2. **Workspace and User ID Source**
- Currently pipeline doesn't pass workspace_id or user_id
- Need to determine how these are obtained:
  - From API request context?
  - From environment/config?
  - As part of user_query?

### 3. **Multi-Tool Query Handling**
- How to handle queries requiring multiple tools?
- How to join/aggregate results from different tools?
- Example: "Show me companies and their contacts"

### 4. **Pagination Logic**
- When to use pagination?
- How to handle large result sets?
- How to communicate pagination status to ResponseFormatter?

### 5. **Error Recovery**
- What to do if one tool fails in a multi-tool query?
- How to provide partial results?
- Error reporting format

## 🔨 Implementation Checklist

- [ ] Create DataExtractorAgent class structure
- [ ] Implement query parsing (LLM-based or rule-based)
- [ ] Implement tool selection logic
- [ ] Implement tool execution with proper workspace/user context
- [ ] Implement result aggregation
- [ ] Implement error handling
- [ ] Add logging and monitoring
- [ ] Update pipeline to use DataExtractorAgent
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Update documentation

## 📚 Reference Files

- **Current placeholder**: `agents/data_extractor.py`
- **Pipeline integration**: `graph/pipeline.py` (lines 48-52)
- **Tool factory**: `tools/tool_factory.py`
- **Base tool**: `tools/base_tool.py`
- **Configuration**: `config/settings.py` (DATA_EXTRACTOR_CONFIG)
- **Example agent**: `agents/query_optimizer.py` (for structure reference)

## 🎯 Next Steps

1. **Design Decision**: Choose query parsing strategy (LLM vs rules)
2. **Architecture**: Design how workspace_id/user_id flow through pipeline
3. **Implementation**: Build core DataExtractorAgent class
4. **Integration**: Connect to pipeline
5. **Testing**: Unit and integration tests
6. **Documentation**: Update README and architecture docs

