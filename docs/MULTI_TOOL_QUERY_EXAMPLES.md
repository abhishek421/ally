# Multi-Tool Query Examples

This document demonstrates how the enhanced Data Extractor Agent handles complex, multi-entity queries with automatic relationship resolution and parallel execution.

## Example 1: People Linked to a Company (User's Original Example)

### Query
```
"What people do we have linked to OpenAI company?"
```

### Agent's Understanding
- Primary intent: Get people data
- Relationship: People ↔ Company (via metaData table)
- Requires: 2-step query with dependency

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {
        "name": "OpenAI",
        "limit": 1
      },
      "reason": "Find OpenAI company to get its ID for linking people",
      "can_run_parallel": false
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {
        "company_id": "<id_from_previous_call>",
        "limit": 50
      },
      "reason": "Get all people linked to OpenAI using resolved company_id",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Two-step sequential: 1) Search for OpenAI company to extract company_id, 2) Query people tool with resolved company_id to find all linked contacts",
  "requires_multi_step": true
}
```

### Execution Flow
```
1. Execute: company.search(name="OpenAI") 
   → Returns: {"id": "comp-123", "name": "OpenAI", ...}

2. Resolve placeholder: <id_from_previous_call> → "comp-123"

3. Execute: people.search(company_id="comp-123")
   → Returns: [
       {"id": "p1", "full_name": "Sam Altman", "job_title": "CEO", ...},
       {"id": "p2", "full_name": "Greg Brockman", "job_title": "President", ...},
       ...
     ]
```

### Response
```json
{
  "people": [
    {
      "id": "p1",
      "full_name": "Sam Altman",
      "job_title": "CEO",
      "company_name": "OpenAI",
      ...
    },
    {
      "id": "p2",
      "full_name": "Greg Brockman",
      "job_title": "President",
      "company_name": "OpenAI",
      ...
    }
  ],
  "_reasoning_traces": [...],
  "_execution_time_ms": 380
}
```

---

## Example 2: Emails from a Company

### Query
```
"Show me all emails from Stripe in the last 30 days"
```

### Agent's Understanding
- Primary intent: Get email data
- Relationship: Company → Emails (direct via company_id in DynamoDB)
- Requires: 2-step query with dependency

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {
        "name": "Stripe",
        "limit": 1
      },
      "reason": "Find Stripe company to get company_id for email filtering",
      "can_run_parallel": false
    },
    {
      "tool": "email",
      "query_type": "list",
      "params": {
        "company_id": "<id_from_previous_call>",
        "date_from": "2024-12-21T00:00:00Z",
        "limit": 100
      },
      "reason": "Retrieve all emails associated with Stripe in the specified time period",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Sequential: 1) Locate Stripe company, 2) Query emails using resolved company_id with date filter",
  "requires_multi_step": true
}
```

---

## Example 3: Parallel Independent Queries

### Query
```
"Show me all companies in the 'Enterprise' category and all people with 'Engineer' in their job title"
```

### Agent's Understanding
- Primary intent: Get multiple entity types
- Relationship: None (independent queries)
- Optimization: Can run in parallel

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {
        "description": "Enterprise",
        "limit": 50
      },
      "reason": "Search for companies with 'Enterprise' in description",
      "can_run_parallel": true
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {
        "job_title": "Engineer",
        "limit": 50
      },
      "reason": "Search for people with 'Engineer' in job title",
      "can_run_parallel": true
    }
  ],
  "execution_plan": "Parallel execution: Both queries are independent and can run simultaneously for optimal performance",
  "requires_multi_step": false
}
```

### Execution Flow
```
Execute in parallel using asyncio.gather():
├─ company.search(description="Enterprise")  [200ms]
└─ people.search(job_title="Engineer")      [250ms]

Total time: 250ms (vs 450ms sequential)
```

---

## Example 4: Complex Multi-Step with Mixed Execution

### Query
```
"Get me all people and interactions for Acme Corporation"
```

### Agent's Understanding
- Primary intent: Get people AND interactions for a company
- Relationship: Company → People, Company → Interactions
- Optimization: Steps 2 and 3 can run in parallel after step 1

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {
        "name": "Acme Corporation",
        "limit": 1
      },
      "reason": "Find Acme Corporation to get company_id",
      "can_run_parallel": false
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {
        "company_id": "<id_from_previous_call>",
        "limit": 100
      },
      "reason": "Get all people linked to Acme Corporation",
      "can_run_parallel": true
    },
    {
      "tool": "interaction",
      "query_type": "search",
      "params": {
        "company_id": "<id_from_previous_call>",
        "limit": 100
      },
      "reason": "Get all interactions with Acme Corporation",
      "can_run_parallel": true
    }
  ],
  "execution_plan": "Three-step hybrid: 1) Find Acme Corporation [sequential], 2-3) Get people and interactions in parallel [both depend on step 1 but independent of each other]",
  "requires_multi_step": true
}
```

### Execution Batches
```
Batch 1 (Sequential):
  └─ company.search(name="Acme Corporation")  [180ms]
     → company_id = "comp-456"

Batch 2 (Parallel):
  ├─ people.search(company_id="comp-456")     [220ms]
  └─ interaction.search(company_id="comp-456") [190ms]
     → max(220ms, 190ms) = 220ms

Total: 400ms (vs 590ms if all sequential)
```

---

## Example 5: Deep Relationship Traversal

### Query
```
"Show me emails from all people who work at companies in the 'Technology' sector"
```

### Agent's Understanding
- Primary intent: Get emails
- Relationship chain: Companies (filter) → People → Emails
- Requires: 3-step query with cascading dependencies

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {
        "description": "Technology",
        "limit": 100
      },
      "reason": "Find all companies in Technology sector",
      "can_run_parallel": false
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {
        "company_id": "<id_from_previous_call>",
        "limit": 500
      },
      "reason": "Get all people from Technology companies (Note: This would need batch processing for multiple companies)",
      "can_run_parallel": false
    },
    {
      "tool": "email",
      "query_type": "search",
      "params": {
        "person_id": "<id_from_previous_call>",
        "limit": 1000
      },
      "reason": "Retrieve emails from identified people",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Three-step sequential chain: 1) Find Technology companies, 2) Get people from those companies, 3) Get emails from those people",
  "requires_multi_step": true
}
```

**Note**: This query might require additional optimization for handling multiple company IDs. The current implementation focuses on single-entity resolution.

---

## Example 6: Analytics with Context

### Query
```
"How many people work at each of our top 10 companies?"
```

### Agent's Understanding
- Primary intent: Analytics with relationship context
- Approach: Get top companies, then count people per company
- Optimization: After getting companies, people counts could be parallel

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "list",
      "params": {
        "limit": 10,
        "offset": 0
      },
      "reason": "Get top 10 companies",
      "can_run_parallel": false
    },
    {
      "tool": "people",
      "query_type": "analytics",
      "params": {},
      "reason": "Get people analytics to derive counts per company (aggregation logic would need enhancement)",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Get top companies, then analyze people distribution across them",
  "requires_multi_step": true
}
```

---

## Example 7: Group Membership Query

### Query
```
"Who are the members of the 'Enterprise Customers' group?"
```

### Agent's Understanding
- Primary intent: Get people/companies in a group
- Relationship: Group ↔ People (many-to-many via groupPeople)
- Requires: 2-step query

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "group",
      "query_type": "search",
      "params": {
        "name": "Enterprise Customers",
        "limit": 1
      },
      "reason": "Find the group by name to get group_id",
      "can_run_parallel": false
    },
    {
      "tool": "people",
      "query_type": "search",
      "params": {
        "group_id": "<id_from_previous_call>",
        "limit": 100
      },
      "reason": "Get all people who are members of this group",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Two-step: 1) Find group by name, 2) Query people belonging to that group",
  "requires_multi_step": true
}
```

---

## Example 8: Recent Activity Analysis

### Query
```
"Show me all interactions from the last week with people from Microsoft"
```

### Agent's Understanding
- Primary intent: Get interactions with filters
- Relationship: Company → People → Interactions (or Company → Interactions directly)
- Optimization: Direct company → interactions link is more efficient

### Planned Tool Calls
```json
{
  "tool_calls": [
    {
      "tool": "company",
      "query_type": "search",
      "params": {
        "name": "Microsoft",
        "limit": 1
      },
      "reason": "Find Microsoft to get company_id",
      "can_run_parallel": false
    },
    {
      "tool": "interaction",
      "query_type": "search",
      "params": {
        "company_id": "<id_from_previous_call>",
        "date_from": "2024-01-13T00:00:00Z",
        "limit": 100
      },
      "reason": "Get interactions with Microsoft in the last week (direct company link is more efficient than going through people)",
      "can_run_parallel": false
    }
  ],
  "execution_plan": "Two-step optimized: 1) Find Microsoft company, 2) Query interactions directly using company_id (more efficient than Company→People→Interactions)",
  "requires_multi_step": true
}
```

---

## Performance Comparison

### Scenario: "Companies and People" (Independent)

**Sequential Execution** (Old):
```
company.search() → 200ms
people.search()  → 250ms
─────────────────────────
Total: 450ms
```

**Parallel Execution** (New):
```
company.search() ┐
                 ├→ max(200ms, 250ms) = 250ms
people.search()  ┘
─────────────────────────
Total: 250ms (44% faster)
```

### Scenario: "Company → People & Interactions"

**Sequential Execution** (Old):
```
company.search()      → 180ms
people.search()       → 220ms
interaction.search()  → 190ms
─────────────────────────────
Total: 590ms
```

**Parallel Execution** (New):
```
Batch 1: company.search() → 180ms
         ↓
Batch 2: people.search()     ┐
         interaction.search() ├→ max(220ms, 190ms) = 220ms
                              ┘
─────────────────────────────
Total: 400ms (32% faster)
```

---

## Key Takeaways

1. **Automatic Planning**: Agent understands relationships and plans multi-step queries without explicit instructions

2. **Intelligent Execution**: Recognizes when queries can be parallelized for better performance

3. **Dependency Resolution**: Automatically resolves entity IDs and passes them to dependent queries

4. **Error Handling**: Gracefully handles cases where entities aren't found (skips dependent steps)

5. **Comprehensive Context**: Returns complete data with relationship context (e.g., people with company names)

6. **Performance Optimization**: Reduces query time by up to 44% for independent queries

7. **Transparent Reasoning**: Provides detailed traces showing decision-making process

