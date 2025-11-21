# Conversation Context Test Scenarios

## Test Case 1: "Which of them work at OpenAI?"

### Setup
- User has a conversation with the analyst
- First query returns a list of people

### Conversation Flow

#### Turn 1
**User Query**: "give me a list of all people"

**System Response**:
- Extracts 9 people from database
- Returns list with names and IDs
- Stores metadata in message:
```json
{
  "role": "ASSISTANT",
  "content": "I found 9 people matching your query:",
  "metadata": {
    "query_context": {
      "result_summary": {
        "people.list": {
          "people_names": ["Alice Smith", "Bob Jones", "Charlie Brown", ...],
          "people_ids": ["p1", "p2", "p3", ...]
        }
      }
    }
  }
}
```

#### Turn 2 (The Fix)
**User Query**: "which of them work with OpenAI?"

**Before Fix** ❌:
```
Context sent to LLM:
---
USER: give me a list of all people
ASSISTANT: I found 9 people matching your query:
---

Result: LLM treats this as fresh query, searches for "OpenAI" company,
        tries to list ALL people at OpenAI (ignoring the previous 9)
```

**After Fix** ✅:
```
Context sent to LLM:
---
Previous conversation context:
USER: give me a list of all people
ASSISTANT: I found 9 people matching your query:
  Entities returned:
  - People: Alice Smith (ID: p1), Bob Jones (ID: p2), Charlie Brown (ID: p3), ...

CRITICAL INSTRUCTIONS FOR FOLLOW-UP QUERIES:
When the query contains references to previous results (e.g., "them", "those"):
1. Identify the reference: "them" in this query
2. Find the entities in context: 9 people with IDs
3. Use the entity IDs: p1, p2, p3, ...
4. Filter those specific people

User Query: "which of them work with OpenAI?"
---

LLM Response:
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {"name": "OpenAI", "limit": 1},
      "reason": "Find OpenAI company to get company_id"
    },
    {
      "tool": "people",
      "query_type": "get_by_id",
      "params": {"person_id": "p1"},
      "reason": "Check if Alice Smith works at OpenAI"
    },
    {
      "tool": "people",
      "query_type": "get_by_id",
      "params": {"person_id": "p2"},
      "reason": "Check if Bob Jones works at OpenAI"
    },
    // ... repeat for p3-p9
  ]
}
```

**Result**: Only returns people from the original 9 who work at OpenAI ✅

---

## Test Case 2: "Show me the first one"

### Conversation Flow

#### Turn 1
**User Query**: "list all companies in the AI domain"

**System Response**:
```json
{
  "metadata": {
    "query_context": {
      "result_summary": {
        "company.list": {
          "company_names": ["OpenAI", "Anthropic", "Cohere"],
          "company_ids": ["c1", "c2", "c3"]
        }
      }
    }
  }
}
```

#### Turn 2
**User Query**: "show me the first one"

**Context sent to LLM**:
```
Previous conversation context:
USER: list all companies in the AI domain
ASSISTANT: I found 3 companies:
  Entities returned:
  - Companies: OpenAI (ID: c1), Anthropic (ID: c2), Cohere (ID: c3)

CRITICAL INSTRUCTIONS:
"the first one" → Extract first company from context: OpenAI (ID: c1)
```

**LLM Response**:
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "get_by_id",
      "params": {"company_id": "c1"},
      "reason": "Get details for the first company (OpenAI)"
    }
  ]
}
```

**Result**: Returns details for OpenAI ✅

---

## Test Case 3: "Show me emails from them"

### Conversation Flow

#### Turn 1
**User Query**: "find people at Google"

**System Response**:
```json
{
  "metadata": {
    "query_context": {
      "result_summary": {
        "people.list": {
          "people_names": ["John Doe", "Jane Smith"],
          "people_ids": ["p1", "p2"]
        }
      }
    }
  }
}
```

#### Turn 2
**User Query**: "show me emails from them"

**Context sent to LLM**:
```
Previous conversation context:
USER: find people at Google
ASSISTANT: I found 2 people:
  Entities returned:
  - People: John Doe (ID: p1), Jane Smith (ID: p2)

User Query: "show me emails from them"
```

**LLM Response**:
```json
{
  "tool_calls": [
    {
      "tool": "email",
      "query_type": "list",
      "params": {"person_id": "p1", "limit": 50},
      "reason": "Get emails from John Doe"
    },
    {
      "tool": "email",
      "query_type": "list",
      "params": {"person_id": "p2", "limit": 50},
      "reason": "Get emails from Jane Smith"
    }
  ]
}
```

**Result**: Returns emails from both people ✅

---

## Test Case 4: Mixed Entity Types

### Conversation Flow

#### Turn 1
**User Query**: "show me companies and people in the AI space"

**System Response**:
```json
{
  "metadata": {
    "query_context": {
      "result_summary": {
        "company.list": {
          "company_names": ["OpenAI", "Anthropic"],
          "company_ids": ["c1", "c2"]
        },
        "people.list": {
          "people_names": ["Sam Altman", "Dario Amodei"],
          "people_ids": ["p1", "p2"]
        }
      }
    }
  }
}
```

#### Turn 2
**User Query**: "show me the companies"

**Context sent to LLM**:
```
Previous conversation context:
USER: show me companies and people in the AI space
ASSISTANT: I found 2 companies and 2 people:
  Entities returned:
  - Companies: OpenAI (ID: c1), Anthropic (ID: c2)
  - People: Sam Altman (ID: p1), Dario Amodei (ID: p2)

User Query: "show me the companies"
```

**LLM Response**:
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "get_by_id",
      "params": {"company_id": "c1"},
      "reason": "Get OpenAI details"
    },
    {
      "tool": "company",
      "query_type": "get_by_id",
      "params": {"company_id": "c2"},
      "reason": "Get Anthropic details"
    }
  ]
}
```

**Result**: Returns only the companies (not people) ✅

---

## Expected Behavior Summary

| User Query Pattern | Context Awareness | Expected Behavior |
|-------------------|-------------------|-------------------|
| "which of them..." | ✅ Uses previous entity IDs | Filters previous results |
| "the first one" | ✅ Uses ordinal reference | Returns specific entity |
| "them" / "those" | ✅ Uses previous entity IDs | Operates on previous results |
| "that company" | ✅ Uses entity name/ID | References specific entity |
| Fresh query | ❌ No context needed | Normal search |

## Testing Steps

1. **Start a conversation**
```bash
POST /api/v1/query
{
  "query": "list all people",
  "conversation_id": null
}
```

2. **Follow up with reference**
```bash
POST /api/v1/query
{
  "query": "which of them work at OpenAI?",
  "conversation_id": "<from-step-1>"
}
```

3. **Verify logs**
- Look for: "Using X context messages for reference resolution"
- Look for: "Entities returned:" in context
- Verify: Tool calls use person IDs from previous query

4. **Verify response**
- Should return filtered subset of people
- Should NOT return ALL people at OpenAI

