# Email Tool Usage Analysis - DataExtractor Agent

## Executive Summary

After reviewing the implementation, I found **several issues** with how the EmailTool is being used in the DataExtractor agent. The current implementation has **incomplete parameter handling** and **missing critical features** documented in EMAIL_TOOl_DOCS.md.

## Current Implementation Status

### ✅ What's Working

1. **Basic Tool Integration** - EmailTool is properly registered in the ToolFactory
2. **Query Type Support** - SEARCH, GET_BY_ID, LIST, ANALYTICS operations work
3. **Result Aggregation** - Email results are properly aggregated in `_aggregate_results()`
4. **Error Handling** - Failed email tool calls don't crash the pipeline

### ❌ Critical Issues Found

---

## Issue #1: Incomplete Parameter Handling in Prompt

**Location:** [prompts/data_extractor_prompt.py:29-34](../prompts/data_extractor_prompt.py#L29-L34)

**Current Prompt:**
```python
3. **email** - Email synchronization data (external integration)
   Operations: SEARCH | GET_BY_ID | LIST | ANALYTICS
   - SEARCH: person_id, integration_id, from_email, to_email, subject, date_from (ISO 8601), date_to (ISO 8601), direction ('sent'|'received'), limit
   - GET_BY_ID: message_id (required)
   - LIST: person_id, limit
   - ANALYTICS: Returns email metrics (count, threads, response rates)
```

**Problem:**
The prompt is **missing critical parameters** that the updated EmailTool now supports:

1. ❌ **Missing `company_id`** - EmailTool now supports querying by company ([emails_tool.py:59](../tools/emails_tool.py#L59))
2. ❌ **Missing `next_token`** - Pagination support was added but not documented ([emails_tool.py:60](../tools/emails_tool.py#L60))
3. ❌ **LIST operation incomplete** - Should support both `person_id` and `company_id`

**Impact:**
- LLM won't use `company_id` parameter when searching for company emails
- LLM won't implement pagination for large email datasets
- Queries like "show all emails from Acme Corp" will fail

**Fix Required:**
Update the prompt to include:
```python
3. **email** - Email synchronization data (DynamoDB storage)
   Operations: SEARCH | GET_BY_ID | LIST | ANALYTICS
   - SEARCH: person_id, company_id, integration_id, from_email, to_email, subject, date_from (ISO 8601), date_to (ISO 8601), direction ('sent'|'received'), limit, next_token
   - GET_BY_ID: message_id (required)
   - LIST: person_id OR company_id (at least one required), limit, next_token
   - ANALYTICS: Returns email metrics (count by direction, total emails)
```

---

## Issue #2: Missing Company Email Example

**Location:** [prompts/data_extractor_prompt.py:122-152](../prompts/data_extractor_prompt.py#L122-L152)

**Current State:**
Example 3 shows person-based email search, but **no example for company-based** email queries.

**Problem:**
Without an example, the LLM may not correctly generate tool calls for queries like:
- "Show emails from Acme Corp"
- "List all emails sent to TechCo"
- "Get email threads with CompanyXYZ"

**Fix Required:**
Add Example 3.5:
```json
Example 3.5 - Company Email Search:
Optimized Query: {"intent": "search", "primary_entity": "email", "entities": {"companies": ["Acme Corp"], "time_range": {"from": "2024-01-01", "to": "2024-12-31"}}, "filters": {"direction": "received"}}
Output:
{
    "tool_calls": [
        {
            "tool": "company",
            "query_type": "search",
            "params": {
                "name": "Acme Corp",
                "limit": 1
            },
            "reason": "Find company_id for Acme Corp"
        },
        {
            "tool": "email",
            "query_type": "list",
            "params": {
                "company_id": "<company_id_from_previous_call>",
                "limit": 50
            },
            "reason": "List all emails associated with Acme Corp"
        }
    ],
    "execution_plan": "First find Acme Corp's company_id, then list emails associated with that company"
}
```

---

## Issue #3: Pagination Not Implemented in Agent

**Location:** [agents/data_extractor.py:174-262](../agents/data_extractor.py#L174-L262)

**Current State:**
The `_execute_tools_async()` method doesn't handle pagination at all.

**Problem:**
1. EmailTool now returns `next_token` in responses
2. Agent doesn't check for `has_more` flag
3. Agent doesn't make follow-up calls with `next_token`
4. Large email datasets will be truncated to first 50-100 results

**Example Scenario:**
```
User Query: "Show all emails from John Smith"
John has 500 emails
Current behavior: Returns only first 50 emails
Expected behavior: Fetch all 500 emails using pagination
```

**Fix Required:**
Implement pagination loop in `_execute_single_tool()`:
```python
async def _execute_single_tool(
    self,
    tool_name: str,
    query_type: QueryType,
    params: Dict[str, Any],
    workspace_id: str,
    user_id: str
) -> ToolResult:
    """Execute a single tool operation with automatic pagination"""

    all_results = []
    next_token = None
    has_more = True
    max_pages = 10  # Prevent infinite loops
    page_count = 0

    while has_more and page_count < max_pages:
        # Add pagination token if available
        if next_token:
            params['next_token'] = next_token

        # Execute tool
        tool = ToolFactory.create_tool(tool_name, workspace_id, user_id)
        result = await tool.execute(query_type, **params)

        if not result.success:
            # Return first result even if paginated call fails
            if all_results:
                return self._merge_paginated_results(all_results)
            return result

        # Collect results
        all_results.append(result)

        # Check for more pages
        if result.data and isinstance(result.data, dict):
            has_more = result.data.get('has_more', False)
            next_token = result.data.get('next_token')
        else:
            has_more = False

        page_count += 1

    # Merge all paginated results
    return self._merge_paginated_results(all_results)
```

---

## Issue #4: Result Aggregation Doesn't Handle Pagination Metadata

**Location:** [agents/data_extractor.py:381-387](../agents/data_extractor.py#L381-L387)

**Current Code:**
```python
elif tool_name == "email":
    if isinstance(tool_data, dict) and "emails" in tool_data:
        aggregated["emails"].extend(tool_data["emails"])
    elif isinstance(tool_data, list):
        aggregated["emails"].extend(tool_data)
    elif isinstance(tool_data, dict):
        aggregated["emails"].append(tool_data)
```

**Problem:**
- Doesn't preserve `total_count`, `has_more`, `next_token` metadata
- Client can't know if there are more results
- Can't implement "Load More" functionality in UI

**Fix Required:**
```python
elif tool_name == "email":
    if isinstance(tool_data, dict) and "emails" in tool_data:
        # Preserve pagination metadata
        aggregated["emails"].extend(tool_data["emails"])
        if "emails_metadata" not in aggregated:
            aggregated["emails_metadata"] = {}
        aggregated["emails_metadata"] = {
            "total_count": tool_data.get("total_count", 0),
            "has_more": tool_data.get("has_more", False),
            "next_token": tool_data.get("next_token"),
            "limit": tool_data.get("limit", 50)
        }
    # ... rest of handling
```

---

## Issue #5: No Privacy Filtering Implementation

**Location:** Entire codebase

**Status:** ⚠️ **NOT IMPLEMENTED**

**Documentation Reference:** [EMAIL_TOOl_DOCS.md:324-385](../docs/EMAIL_TOOl_DOCS.md#L324-L385)

**Problem:**
The documentation specifies privacy filtering with levels:
- `PRIVATE` - Only visible to creator
- `SUBJECT_ONLY` - Show subject/metadata, hide body
- `FULL_ACCESS` - Show everything

**Current State:**
- EmailTool returns all emails without privacy checks
- DataExtractor doesn't apply privacy filtering
- No integration with PostgreSQL to fetch user privacy levels

**Security Risk:**
Users can see emails from other users that should be private.

**Fix Required:**
1. Add privacy filtering to EmailTool:
```python
async def _apply_privacy_filtering(
    self,
    emails: List[Dict[str, Any]],
    current_user_id: str
) -> List[Dict[str, Any]]:
    """Filter emails based on user privacy settings"""
    # Query PostgreSQL for user privacy levels
    # Apply filtering rules as per documentation
    pass
```

2. Update DataExtractor to pass current user context
3. Integrate with PostgreSQL user settings table

---

## Issue #6: Missing DynamoDB Table Configuration Awareness

**Location:** [agents/data_extractor.py](../agents/data_extractor.py)

**Problem:**
DataExtractor doesn't validate that `DYNAMODB_TABLE` env variable is set before attempting email queries.

**Fix Required:**
Add startup validation:
```python
def __init__(self, llm_provider: Optional[LLMProvider] = None):
    # ... existing code ...

    # Validate email tool dependencies
    self._validate_email_tool_config()

def _validate_email_tool_config(self):
    """Validate email tool configuration"""
    import os
    dynamodb_table = os.getenv("DYNAMODB_TABLE")
    if not dynamodb_table:
        self._logger.warning(
            "DYNAMODB_TABLE not set - email tool queries may fail. "
            "Set DYNAMODB_TABLE environment variable."
        )
```

---

## Issue #7: Incorrect GSI1 Usage in Documentation Example

**Location:** [prompts/data_extractor_prompt.py:31](../prompts/data_extractor_prompt.py#L31)

**Current Prompt:**
```python
- SEARCH: person_id, integration_id, from_email, to_email, ...
```

**Problem:**
The prompt mentions `integration_id` but:
1. Updated EmailTool removed integration_id support
2. Original implementation used GSI1 incorrectly
3. Documentation doesn't specify integration_id queries

**Fix Required:**
Remove `integration_id` from the prompt or implement it properly if needed.

---

## Recommended Action Plan

### **High Priority (Fix Immediately)**

1. ✅ **Update [emails_tool.py](../tools/emails_tool.py)** - COMPLETED
   - ✅ Fixed DynamoDB schema
   - ✅ Added pagination support
   - ✅ Added company email support

2. ⚠️ **Update [data_extractor_prompt.py](../prompts/data_extractor_prompt.py)**
   - Add `company_id` parameter documentation
   - Add `next_token` parameter
   - Fix LIST operation documentation
   - Add company email example

3. ⚠️ **Implement Pagination in DataExtractor**
   - Add pagination loop to `_execute_single_tool()`
   - Preserve pagination metadata in results
   - Add configurable max pages limit

### **Medium Priority (Next Sprint)**

4. ⚠️ **Implement Privacy Filtering**
   - Add privacy filtering to EmailTool
   - Integrate with PostgreSQL user settings
   - Document privacy levels in API

5. ⚠️ **Add Configuration Validation**
   - Validate `DYNAMODB_TABLE` on startup
   - Add health check for DynamoDB connection
   - Better error messages for missing config

### **Low Priority (Future Enhancement)**

6. ⚠️ **Add Email Tool Tests**
   - Unit tests for EmailTool
   - Integration tests with DynamoDB
   - Mock data for test scenarios

7. ⚠️ **Add Caching**
   - Cache frequently accessed emails
   - Cache user privacy settings
   - Redis integration for analytics queries

---

## Testing Recommendations

### Test Case 1: Person Email Query
```python
Query: "Show emails from John Smith"
Expected Tool Calls:
1. people.search(first_name="John", last_name="Smith")
2. email.list(person_id="<person_id>", limit=50)

Verify:
- person_id correctly passed to email tool
- Pagination metadata returned
- Results properly aggregated
```

### Test Case 2: Company Email Query
```python
Query: "List all emails from Acme Corp"
Expected Tool Calls:
1. company.search(name="Acme Corp")
2. email.list(company_id="<company_id>", limit=50)

Verify:
- company_id correctly passed to email tool
- Company emails returned (not person emails)
```

### Test Case 3: Pagination
```python
Query: "Show all emails from very active person"
Mock Data: 250 emails

Verify:
- Multiple paginated calls made
- All 250 emails returned
- next_token handled correctly
- Stops at max_pages limit
```

### Test Case 4: Date Filtering
```python
Query: "Emails from John Smith in October 2024"
Expected Params:
{
    "person_id": "...",
    "date_from": "2024-10-01T00:00:00Z",
    "date_to": "2024-10-31T23:59:59Z"
}

Verify:
- ISO 8601 date format
- Timezone handling
- Filter applied correctly
```

---

## Summary

### Issues Found: **7**
- ❌ Critical: **3** (Incomplete parameters, missing pagination, no privacy filtering)
- ⚠️ High: **2** (Missing examples, result aggregation)
- ℹ️ Medium: **2** (Config validation, integration_id)

### Files Requiring Updates:
1. ✅ `tools/emails_tool.py` - **COMPLETED**
2. ✅ `.env.example` - **COMPLETED**
3. ⚠️ `prompts/data_extractor_prompt.py` - **NEEDS UPDATE**
4. ⚠️ `agents/data_extractor.py` - **NEEDS UPDATE**

### Next Steps:
1. Update DataExtractor prompt with complete email parameters
2. Implement pagination in DataExtractor agent
3. Add privacy filtering support
4. Write integration tests for email queries

---

**Last Updated:** 2025-01-05
**Author:** AI Code Review
**Status:** In Progress (EmailTool fixed, DataExtractor needs updates)
