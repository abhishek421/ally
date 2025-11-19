# Analyst AI - Test Query Sheet

## Test Environment Details
- **Workspace ID**: `550e8400-e29b-41d4-a716-446655440000`
- **User ID**: `8d0c1f2f-a71c-4009-9942-3d8d9ae48816`
- **Workspace Name**: SoftSync Test Workspace
- **Data Status**: 2 Companies, 2 People, 0 Interactions, 0 Groups

---

## Test Categories

### 1. COMPANY QUERIES

#### Test 1.1: List All Companies
**Query**: "Show me all companies"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
      "name": "Acme Corporation",
      "description": null,
      "privacyLevel": "PRIVATE",
      "createdAt": "2025-10-23T16:09:24.248Z"
    },
    {
      "id": "5e469848-d0ef-40d3-a746-f69071202041",
      "name": "Tech Solutions Inc",
      "description": null,
      "privacyLevel": "PRIVATE",
      "createdAt": "2025-10-23T16:09:24.248Z"
    }
  ],
  "total_count": 2
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `list`
- Params: `{limit: 50, offset: 0}`

---

#### Test 1.2: Search Company by Name
**Query**: "Find Acme Corporation"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
      "name": "Acme Corporation",
      "description": null,
      "privacyLevel": "PRIVATE"
    }
  ],
  "total_count": 1
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `search`
- Params: `{name: "Acme Corporation"}`

---

#### Test 1.3: Get Company by ID
**Query**: "Get details for company bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e"

**Expected Output**:
```json
{
  "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
  "name": "Acme Corporation",
  "description": null,
  "privacy_level": "PRIVATE",
  "created_at": "2025-10-23T16:09:24.248Z",
  "emails": [],
  "phone_numbers": [],
  "addresses": [],
  "urls": []
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `get_by_id`
- Params: `{company_id: "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e"}`

---

#### Test 1.4: Company Analytics
**Query**: "Give me analytics about companies"

**Expected Output**:
```json
{
  "total_companies": 2,
  "by_privacy_level": {
    "PRIVATE": 2
  },
  "recent_companies_30d": 2,
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `analytics`
- Params: `{}`

---

#### Test 1.5: Search Company (Partial Match)
**Query**: "Find companies with 'Tech' in the name"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "5e469848-d0ef-40d3-a746-f69071202041",
      "name": "Tech Solutions Inc",
      "description": null,
      "privacyLevel": "PRIVATE"
    }
  ],
  "total_count": 1
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `search`
- Params: `{name: "Tech"}`

---

### 2. PEOPLE QUERIES

#### Test 2.1: List All People
**Query**: "Show me all people"

**Expected Output**:
```json
{
  "people": [
    {
      "id": "4b2b7412-7279-44ac-a761-7bbae8c9faf2",
      "firstName": "John",
      "lastName": "Doe",
      "jobTitle": null,
      "privacyLevel": "PRIVATE",
      "createdAt": "2025-10-23T16:09:24.240Z"
    },
    {
      "id": "df3df196-0d06-409a-b1f5-88dfcd62a9a9",
      "firstName": "Jane",
      "lastName": "Smith",
      "jobTitle": null,
      "privacyLevel": "PRIVATE",
      "createdAt": "2025-10-23T16:09:24.240Z"
    }
  ],
  "total_count": 2
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `list`
- Params: `{limit: 50, offset: 0}`

---

#### Test 2.2: Search Person by First Name
**Query**: "Find John"

**Expected Output**:
```json
{
  "people": [
    {
      "id": "4b2b7412-7279-44ac-a761-7bbae8c9faf2",
      "firstName": "John",
      "lastName": "Doe",
      "jobTitle": null,
      "privacyLevel": "PRIVATE"
    }
  ],
  "total_count": 1
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `search`
- Params: `{first_name: "John"}`

---

#### Test 2.3: Search Person by Last Name
**Query**: "Find people with last name Smith"

**Expected Output**:
```json
{
  "people": [
    {
      "id": "df3df196-0d06-409a-b1f5-88dfcd62a9a9",
      "firstName": "Jane",
      "lastName": "Smith",
      "jobTitle": null,
      "privacyLevel": "PRIVATE"
    }
  ],
  "total_count": 1
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `search`
- Params: `{last_name: "Smith"}`

---

#### Test 2.4: Get Person by ID
**Query**: "Get details for person 4b2b7412-7279-44ac-a761-7bbae8c9faf2"

**Expected Output**:
```json
{
  "id": "4b2b7412-7279-44ac-a761-7bbae8c9faf2",
  "first_name": "John",
  "last_name": "Doe",
  "job_title": null,
  "privacy_level": "PRIVATE",
  "created_at": "2025-10-23T16:09:24.240Z",
  "emails": [],
  "phone_numbers": [],
  "addresses": [],
  "urls": [],
  "companies": []
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `get_by_id`
- Params: `{person_id: "4b2b7412-7279-44ac-a761-7bbae8c9faf2"}`

---

#### Test 2.5: People Analytics
**Query**: "Give me analytics about people"

**Expected Output**:
```json
{
  "total_people": 2,
  "by_privacy_level": {
    "PRIVATE": 2
  },
  "by_job_title": {},
  "recent_people_30d": 2,
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `analytics`
- Params: `{}`

---

### 3. INTERACTION QUERIES

#### Test 3.1: List All Interactions
**Query**: "Show me all interactions"

**Expected Output**:
```json
{
  "interactions": [],
  "total_count": 0,
  "has_more": false
}
```

**Tool Execution**:
- Tool: `interaction`
- Query Type: `list`
- Params: `{limit: 50, offset: 0}`

**Note**: Currently no interactions in the database

---

#### Test 3.2: Interaction Analytics
**Query**: "Give me analytics about interactions"

**Expected Output**:
```json
{
  "total_interactions": 0,
  "by_type": {},
  "by_direction": {},
  "recent_interactions_30d": 0,
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Tool Execution**:
- Tool: `interaction`
- Query Type: `analytics`
- Params: `{}`

---

### 4. WORKSPACE QUERIES

#### Test 4.1: Get Workspace Information
**Query**: "Tell me about this workspace"

**Expected Output**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "SoftSync Test Workspace",
  "created_at": "2025-10-23T16:09:24.227Z",
  "members": [
    {
      "id": "8d0c1f2f-a71c-4009-9942-3d8d9ae48816",
      "email": "abhishek0art@gmail.com",
      "firstName": "Abhishek",
      "lastName": "Choudhary",
      "role": "MEMBER"
    },
    {
      "email": "harshsinghrathorr@gmail.com",
      "firstName": "Harsh",
      "lastName": "Singh",
      "role": "OWNER"
    }
  ]
}
```

**Tool Execution**:
- Tool: `workspace`
- Query Type: `get_by_id`
- Params: `{workspace_id: "550e8400-e29b-41d4-a716-446655440000"}`

---

### 5. COMPLEX/MULTI-STEP QUERIES

#### Test 5.1: Count Everything
**Query**: "How many companies, people, and interactions do I have?"

**Expected Output**:
```json
{
  "summary": {
    "companies": 2,
    "people": 2,
    "interactions": 0,
    "groups": 0
  }
}
```

**Tool Execution** (Multi-step):
1. Tool: `company`, Query Type: `analytics`
2. Tool: `people`, Query Type: `analytics`
3. Tool: `interaction`, Query Type: `analytics`
4. Tool: `group`, Query Type: `analytics`

---

#### Test 5.2: Find All Private Entities
**Query**: "Show me all private companies and people"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
      "name": "Acme Corporation",
      "privacyLevel": "PRIVATE"
    },
    {
      "id": "5e469848-d0ef-40d3-a746-f69071202041",
      "name": "Tech Solutions Inc",
      "privacyLevel": "PRIVATE"
    }
  ],
  "people": [
    {
      "id": "4b2b7412-7279-44ac-a761-7bbae8c9faf2",
      "firstName": "John",
      "lastName": "Doe",
      "privacyLevel": "PRIVATE"
    },
    {
      "id": "df3df196-0d06-409a-b1f5-88dfcd62a9a9",
      "firstName": "Jane",
      "lastName": "Smith",
      "privacyLevel": "PRIVATE"
    }
  ]
}
```

**Tool Execution** (Multi-step):
1. Tool: `company`, Query Type: `search`, Params: `{privacy_level: "PRIVATE"}`
2. Tool: `people`, Query Type: `search`, Params: `{privacy_level: "PRIVATE"}`

---

#### Test 5.3: Recent Activity Summary
**Query**: "What was created in the last 30 days?"

**Expected Output**:
```json
{
  "recent_activity": {
    "companies_created_30d": 2,
    "people_created_30d": 2,
    "interactions_created_30d": 0
  },
  "total": {
    "companies": 2,
    "people": 2,
    "interactions": 0
  }
}
```

**Tool Execution** (Multi-step):
1. Tool: `company`, Query Type: `analytics`
2. Tool: `people`, Query Type: `analytics`
3. Tool: `interaction`, Query Type: `analytics`

---

### 6. EDGE CASES & ERROR HANDLING

#### Test 6.1: Invalid Company ID
**Query**: "Get company with ID 00000000-0000-0000-0000-000000000000"

**Expected Output**:
```json
{
  "error": "Company not found",
  "company_id": "00000000-0000-0000-0000-000000000000"
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `get_by_id`
- Params: `{company_id: "00000000-0000-0000-0000-000000000000"}`

---

#### Test 6.2: Search with No Results
**Query**: "Find company named 'NonExistent Corp'"

**Expected Output**:
```json
{
  "companies": [],
  "total_count": 0,
  "has_more": false
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `search`
- Params: `{name: "NonExistent Corp"}`

---

#### Test 6.3: Empty Query
**Query**: "Find people with first name ''"

**Expected Output**:
```json
{
  "people": [],
  "total_count": 0
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `search`
- Params: `{first_name: ""}`

---

### 7. PAGINATION TESTS

#### Test 7.1: List Companies with Limit
**Query**: "Show me the first 1 company"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
      "name": "Acme Corporation"
    }
  ],
  "total_count": 2,
  "has_more": true,
  "limit": 1,
  "offset": 0
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `list`
- Params: `{limit: 1, offset: 0}`

---

#### Test 7.2: List Companies with Offset
**Query**: "Show me companies starting from offset 1"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "5e469848-d0ef-40d3-a746-f69071202041",
      "name": "Tech Solutions Inc"
    }
  ],
  "total_count": 2,
  "has_more": false,
  "limit": 50,
  "offset": 1
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `list`
- Params: `{limit: 50, offset: 1}`

---

### 8. NATURAL LANGUAGE QUERY TESTS

#### Test 8.1: Conversational Query
**Query**: "Hey, can you show me what companies we have?"

**Expected Output**: Same as Test 1.1

**Tool Execution**:
- Tool: `company`
- Query Type: `list`
- Params: `{limit: 50, offset: 0}`

---

#### Test 8.2: Ambiguous Query (Should Ask for Clarification)
**Query**: "Find John"

**Expected Behavior**:
- Should search for people with first name "John"
- May ask: "Are you looking for a person or a company named John?"

**Tool Execution**:
- Tool: `people`
- Query Type: `search`
- Params: `{first_name: "John"}`

---

#### Test 8.3: Multi-Entity Query
**Query**: "Show me John Doe and Acme Corporation"

**Expected Output**:
```json
{
  "people": [
    {
      "id": "4b2b7412-7279-44ac-a761-7bbae8c9faf2",
      "firstName": "John",
      "lastName": "Doe"
    }
  ],
  "companies": [
    {
      "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
      "name": "Acme Corporation"
    }
  ]
}
```

**Tool Execution** (Multi-step):
1. Tool: `people`, Query Type: `search`, Params: `{first_name: "John", last_name: "Doe"}`
2. Tool: `company`, Query Type: `search`, Params: `{name: "Acme Corporation"}`

---

### 9. FILTER COMBINATION TESTS

#### Test 9.1: Company with Privacy Filter
**Query**: "Show me all private companies"

**Expected Output**:
```json
{
  "companies": [
    {
      "id": "bdd72231-c6d0-4bd4-8cbe-5e7dfab01e6e",
      "name": "Acme Corporation",
      "privacyLevel": "PRIVATE"
    },
    {
      "id": "5e469848-d0ef-40d3-a746-f69071202041",
      "name": "Tech Solutions Inc",
      "privacyLevel": "PRIVATE"
    }
  ],
  "total_count": 2
}
```

**Tool Execution**:
- Tool: `company`
- Query Type: `search`
- Params: `{privacy_level: "PRIVATE"}`

---

#### Test 9.2: People with Multiple Filters
**Query**: "Find people with first name John and privacy level PRIVATE"

**Expected Output**:
```json
{
  "people": [
    {
      "id": "4b2b7412-7279-44ac-a761-7bbae8c9faf2",
      "firstName": "John",
      "lastName": "Doe",
      "privacyLevel": "PRIVATE"
    }
  ],
  "total_count": 1
}
```

**Tool Execution**:
- Tool: `people`
- Query Type: `search`
- Params: `{first_name: "John", privacy_level: "PRIVATE"}`

---

## Test Execution Guidelines

### Running Tests
1. Use the API endpoint: `POST /api/v1/query`
2. Include headers:
   - `X-Workspace-ID: 550e8400-e29b-41d4-a716-446655440000`
   - `X-User-ID: 8d0c1f2f-a71c-4009-9942-3d8d9ae48816`
3. Send the query in the request body

### Success Criteria
- Response structure matches expected output
- Correct tool is selected
- Query type is accurate
- Parameters are properly extracted
- Response time < 5 seconds
- No errors in execution

### Notes
- Some tests may return empty results due to limited test data
- Expected outputs show the structure; actual timestamps may vary
- Test with the ReActive system to see multi-step reasoning
- Monitor the reasoning traces for debugging

---

## Additional Test Scenarios to Add (Once More Data is Available)

1. **Interaction Tests** (when interaction data is available)
   - Search by interaction type (EMAIL, CALENDAR, CALL)
   - Search by direction (INBOUND, OUTBOUND)
   - Search by date range
   - Get interactions for a specific person/company

2. **Email Tests** (when email data is available)
   - Search emails by person
   - Search emails by company
   - Find primary emails

3. **Group Tests** (when group data is available)
   - List all groups
   - Search groups by name
   - Get group members
   - Get groups by type (PEOPLE, COMPANY)

4. **Date Range Tests**
   - Companies created in date range
   - People created in date range
   - Interactions in date range

5. **Relationship Tests**
   - Find people working at a specific company
   - Find companies associated with a person
   - Find all interactions with a person at a company
