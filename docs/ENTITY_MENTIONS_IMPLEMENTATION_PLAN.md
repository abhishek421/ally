# Entity Mentions Implementation Plan

## Overview

Implementation plan for adding entity mention support to the AI Analyst system. Entity mentions allow users to tag entities using `@mention` syntax in queries and enable the AI to annotate entities in responses.

**Status:** Planning Phase
**Estimated Effort:** 3-5 days
**Last Updated:** 2025-11-18

---

## Table of Contents

1. [Feature Requirements](#feature-requirements)
2. [Architecture Decisions](#architecture-decisions)
3. [Implementation Phases](#implementation-phases)
4. [Database Schema Changes](#database-schema-changes)
5. [Code Changes](#code-changes)
6. [Testing Strategy](#testing-strategy)
7. [Migration Plan](#migration-plan)

---

## Feature Requirements

### User Stories

**As a user, I want to:**
- Tag entities in my queries using `@mention` syntax (e.g., "Show me deals with @AcmeCorp")
- See entities highlighted as chips in AI responses
- Click on entity chips to navigate to entity details
- Have entity context preserved in conversation history

**As the system, I need to:**
- Store entity mentions with character spans for UI rendering
- Hydrate mentioned entities with full details for query execution
- Extract entity mentions from AI-generated responses
- Maintain frozen entity names in historical messages

### Functional Requirements

1. **User Input Mentions**
   - Frontend detects `@` trigger and shows autocomplete
   - Frontend sends structured entity mentions to backend
   - Backend stores mentions with user messages
   - Backend hydrates entities for query context

2. **AI Response Mentions**
   - Backend extracts entity names from AI response text
   - Backend calculates character spans for each mention
   - Backend stores mentions with assistant messages
   - Frontend renders chips based on span data

3. **Message Retrieval**
   - API returns messages with entity mention metadata
   - Frontend uses spans to replace text with chips
   - Clicks on chips navigate to entity pages

### Non-Functional Requirements

- **Performance:** Entity hydration must not add >100ms to query time
- **Scale:** Support max 5 entity mentions per message
- **Immutability:** Mention names are frozen snapshots (don't update if entity renamed)
- **Privacy:** Only entities visible to user can be mentioned (enforced by frontend)

---

## Architecture Decisions

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Message Threading** | Not implemented | No parent_message_id needed; simple flat message list |
| **Mention Extraction (User Input)** | Frontend responsibility | Frontend handles @ trigger, autocomplete, ID resolution, privacy filtering |
| **Mention Extraction (AI Response)** | Backend responsibility | Backend post-processes AI text to find entity spans |
| **Entity Hydration** | Backend only | Full entity details used for query execution, not returned to frontend |
| **Mention Immutability** | Frozen snapshots | Mention.name doesn't update if entity renamed in DB |
| **Span Calculation** | String search | Find entity names from extracted_data in response text |
| **Message Editing** | Not supported | Messages are immutable, spans never drift |
| **Privacy Enforcement** | Frontend | Only entities visible to user appear in autocomplete |

### Data Model Decisions

**EntityMention Structure:**
```typescript
interface EntityMention {
  entityId: string;        // UUID of company/person/etc
  entityType: "company" | "person" | "email" | "group" | "interaction";
  name: string;            // Frozen text from @mention (e.g., "AcmeCorp")
  span: {
    start: number;         // Character offset (0-indexed)
    end: number;           // Character offset (exclusive)
  }
}
```

**Storage:**
- Stored as JSON array in `conversationMessage.entityMentions`
- No separate entity mention table needed
- Max ~5 mentions per message (reasonable constraint)

---

## Implementation Phases

### Phase 1: Database Schema (Day 1 - 2-3 hours)

**Goal:** Add entity mentions field to database

**Tasks:**
1. Update Prisma schema
2. Generate migration
3. Run migration on dev database
4. Regenerate Prisma client

**Files:**
- `prisma/schema.prisma`

### Phase 2: API Schema Updates (Day 1 - 2-3 hours)

**Goal:** Add entity mention types to API request/response models

**Tasks:**
1. Create `EntityMention` Pydantic model
2. Add `entity_mentions` field to `QueryRequest`
3. Add `entity_mentions` field to `QueryResponse`
4. Add `entity_mentions` to message retrieval response

**Files:**
- `api/v1/schemas.py`

### Phase 3: Message Storage Enhancement (Day 2 - 2-3 hours)

**Goal:** Store entity mentions with messages

**Tasks:**
1. Update `create_message()` to accept entity mentions
2. Store mentions as JSON in database
3. Handle None/empty mentions gracefully

**Files:**
- `services/conversation.py`
- `api/v1/query.py` (user message storage)

### Phase 4: Pipeline Integration (Day 3 - 2-3 hours)

**Goal:** Pass entity mentions through pipeline to agents

**Tasks:**
1. Update pipeline signature to accept entity mentions
2. Update orchestrator signature
3. Pass mentions from API → Pipeline → Orchestrator → DataExtractor

**Files:**
- `graph/pipeline.py`
- `agents/orchestrator.py`

### Phase 5: Entity Hydration (Day 3 - 2-3 hours)

**Goal:** Fetch full entity details for mentioned entities

**Tasks:**
1. Implement entity hydration in DataExtractor
2. Query database for each mentioned entity
3. Add entity details to LLM prompt context
4. Cache hydrated entities during query execution

**Files:**
- `agents/data_extractor.py`

### Phase 6: AI Response Entity Extraction (Day 4 - 3-4 hours)

**Goal:** Extract entity mentions from AI-generated text

**Tasks:**
1. Create `ResponseEntityExtractor` service
2. Implement entity name search in response text
3. Calculate character spans for each mention
4. Handle multiple occurrences and case-insensitive matching

**Files:**
- `services/entity_mention_extractor.py` (new)

### Phase 7: Store AI Response with Mentions (Day 4 - 1-2 hours)

**Goal:** Store extracted mentions with assistant messages

**Tasks:**
1. Call entity extractor after response generation
2. Pass extracted mentions to background task
3. Store with assistant message

**Files:**
- `api/v1/query.py`

### Phase 8: Return Mentions in API Response (Day 4 - 1 hour)

**Goal:** Include entity mentions in query response

**Tasks:**
1. Add entity_mentions to QueryResponse
2. Return extracted mentions to frontend

**Files:**
- `api/v1/query.py`

### Phase 9: Message Retrieval API (Day 5 - 1-2 hours)

**Goal:** Return entity mentions when fetching conversation history

**Tasks:**
1. Update `get_conversation_messages` endpoint
2. Include `entityMentions` in message response
3. Handle None/missing mentions gracefully

**Files:**
- `api/v1/conversations.py`

### Phase 10: Testing & Documentation (Day 5 - 2-3 hours)

**Goal:** Verify functionality and document usage

**Tasks:**
1. Integration tests for mention storage/retrieval
2. Test entity hydration
3. Test mention extraction from AI responses
4. Update API documentation
5. Create frontend integration guide

---

## Database Schema Changes

### Prisma Schema Update

**File:** `prisma/schema.prisma`

```prisma
model conversationMessage {
  id             String           @id @db.Uuid
  conversationId String           @db.Uuid
  role           ConversationRole
  content        String           // Text with @mentions
  entityMentions Json?            // NEW: Array of EntityMention objects
  metadata       Json?
  functionCalls  Json?
  timestamp      DateTime         @default(now()) @db.Timestamp(6)

  conversation   conversation     @relation(fields: [conversationId], references: [id], onDelete: Cascade)

  @@index([conversationId, timestamp])
}
```

### Migration Commands

```bash
# Generate migration
npx prisma migrate dev --name add_entity_mentions_to_conversation_messages

# Generate Prisma client
npx prisma generate
```

### EntityMention JSON Structure

Stored in `conversationMessage.entityMentions` as JSON array:

```json
[
  {
    "entityId": "uuid-123-456",
    "entityType": "company",
    "name": "AcmeCorp",
    "span": {
      "start": 20,
      "end": 29
    }
  },
  {
    "entityId": "uuid-789-012",
    "entityType": "person",
    "name": "John Smith",
    "span": {
      "start": 45,
      "end": 55
    }
  }
]
```

---

## Code Changes

### 1. API Schema (api/v1/schemas.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class EntityMention(BaseModel):
    """Entity mention in message text"""
    entityId: str = Field(..., description="Entity UUID")
    entityType: str = Field(..., description="company|person|email|group|interaction")
    name: str = Field(..., description="Display name from @mention")
    span: Dict[str, int] = Field(..., description="{start: int, end: int}")

class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    entity_mentions: Optional[List[EntityMention]] = Field(
        default=None,
        description="Entity mentions detected by frontend"
    )

class QueryResponse(BaseModel):
    success: bool
    query: str
    result: Dict[str, Any]
    execution_time_ms: int
    workspace_id: str
    user_id: str
    conversation_id: Optional[str]
    entity_mentions: Optional[List[EntityMention]] = None  # NEW
```

### 2. Message Storage (services/conversation.py)

```python
async def create_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    entity_mentions: Optional[List[Dict[str, Any]]] = None  # NEW
) -> str:
    """
    Create a conversation message with optional entity mentions

    Args:
        conversation_id: Conversation UUID
        role: USER|ASSISTANT|SYSTEM
        content: Message text
        metadata: Optional metadata dict
        entity_mentions: List of {entityId, entityType, name, span} dicts

    Returns:
        Created message ID
    """
    message_id = str(uuid.uuid4())
    client = await prisma_client.get_client()

    create_input = {
        "id": message_id,
        "content": content,
        "role": role.upper(),
        "timestamp": datetime.utcnow(),
        "conversation": {"connect": {"id": conversation_id}}
    }

    if metadata:
        create_input["metadata"] = Json(metadata)

    # NEW: Store entity mentions
    if entity_mentions:
        create_input["entityMentions"] = Json(entity_mentions)

    await client.conversationmessage.create(data=create_input)
    return message_id
```

### 3. User Message Storage (api/v1/query.py)

```python
# Store user message immediately WITH entity mentions
user_message_id = await create_message(
    conversation_id=conversation_id,
    role="USER",
    content=request.query,
    metadata={"workspace_id": workspace_id, "user_id": user_id},
    entity_mentions=[m.dict() for m in request.entity_mentions] if request.entity_mentions else None
)
```

### 4. Pipeline Integration (graph/pipeline.py)

```python
async def run(
    self,
    user_query: str,
    workspace_id: str,
    user_id: str,
    context_messages: List[Dict[str, Any]] = None,
    entity_mentions: Optional[List[Dict[str, Any]]] = None  # NEW
) -> dict:
    """Run pipeline with optional entity mentions"""

    if self.enable_orchestrator:
        result = await self.orchestrator.orchestrate(
            user_query=user_query,
            workspace_id=workspace_id,
            user_id=user_id,
            context_messages=context_messages,
            conversation_state=conversation_state,
            entity_mentions=entity_mentions  # NEW
        )
        return self._convert_orchestration_result(result)
```

### 5. Orchestrator Integration (agents/orchestrator.py)

```python
async def orchestrate(
    self,
    user_query: str,
    workspace_id: str,
    user_id: str,
    context_messages: Optional[List[Dict]] = None,
    conversation_state: Optional['ConversationState'] = None,
    entity_mentions: Optional[List[Dict[str, Any]]] = None  # NEW
) -> OrchestrationResult:
    """Orchestrate with entity mentions"""

    # Pass to data extractor
    extraction_result = await self._run_agent(
        "data_extractor",
        lambda agent: agent.extract(
            optimized_query=user_query,
            workspace_id=workspace_id,
            user_id=user_id,
            context_messages=context_messages,
            entity_mentions=entity_mentions  # NEW
        ),
        agents_executed,
        "Data extracted"
    )
```

### 6. Entity Hydration (agents/data_extractor.py)

```python
async def extract(
    self,
    optimized_query: str,
    workspace_id: str,
    user_id: str,
    context_messages: Optional[List[Dict[str, Any]]] = None,
    entity_mentions: Optional[List[Dict[str, Any]]] = None  # NEW
) -> Dict[str, Any]:
    """Extract data with explicit entity mentions from user input"""

    # NEW: Hydrate entity mentions with full details
    hydrated_entities = {}
    if entity_mentions:
        hydrated_entities = await self._hydrate_entity_mentions(
            entity_mentions,
            workspace_id
        )

    # Build prompt with hydrated entity context
    prompt = self._build_prompt_with_entities(
        optimized_query,
        context_messages,
        hydrated_entities
    )

    # ... rest of extraction logic


async def _hydrate_entity_mentions(
    self,
    mentions: List[Dict[str, Any]],
    workspace_id: str
) -> Dict[str, Any]:
    """
    Fetch full entity details for mentioned entities

    Returns:
        {
            "companies": [<full company objects>],
            "people": [<full person objects>],
            ...
        }
    """
    from database.prisma_client import prisma_client
    client = await prisma_client.get_client()

    hydrated = {
        "companies": [],
        "people": [],
        "emails": [],
        "groups": [],
        "interactions": []
    }

    for mention in mentions:
        entity_type = mention["entityType"]
        entity_id = mention["entityId"]

        if entity_type == "company":
            company = await client.company.find_unique(
                where={"id": entity_id, "workspaceId": workspace_id}
            )
            if company:
                hydrated["companies"].append(company)

        elif entity_type == "person":
            person = await client.people.find_unique(
                where={"id": entity_id, "workspaceId": workspace_id}
            )
            if person:
                hydrated["people"].append(person)

        # TODO: Handle email, group, interaction types

    return hydrated


def _build_prompt_with_entities(
    self,
    query: str,
    context_messages: Optional[List[Dict]],
    hydrated_entities: Dict[str, Any]
) -> str:
    """Build prompt including full details of @mentioned entities"""

    prompt_parts = [self.template]

    # Add entity context if available
    if hydrated_entities and any(hydrated_entities.values()):
        entity_context = ["MENTIONED ENTITIES (from @tags):"]

        for company in hydrated_entities.get("companies", []):
            entity_context.append(
                f"- Company: {company.name} (ID: {company.id})\n"
                f"  Domain: {company.domain}\n"
                f"  Industry: {company.industry or 'N/A'}"
            )

        for person in hydrated_entities.get("people", []):
            entity_context.append(
                f"- Person: {person.firstName} {person.lastName} (ID: {person.id})\n"
                f"  Email: {person.email}\n"
                f"  Company: {person.companyName or 'N/A'}"
            )

        prompt_parts.append("\n".join(entity_context))

    # Add conversation context
    if context_messages:
        # ... existing context building logic
        pass

    prompt_parts.append(f"USER QUERY: {query}")

    return "\n\n".join(prompt_parts)
```

### 7. Entity Mention Extractor (services/entity_mention_extractor.py) - NEW FILE

```python
"""
Extract entity mentions from AI-generated response text
"""
import re
from typing import List, Dict, Any

class ResponseEntityExtractor:
    """Find entities in AI response and calculate spans"""

    def extract_mentions_from_response(
        self,
        response_text: str,
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find where entities from extracted_data appear in response text

        Args:
            response_text: AI-generated markdown response
            extracted_data: Data returned by tools (companies, people, etc.)

        Returns:
            List of EntityMention dicts
        """
        mentions = []

        # Extract company mentions
        for company in extracted_data.get("companies", []):
            company_mentions = self._find_entity_in_text(
                text=response_text,
                entity_name=company.get("name", ""),
                entity_id=company.get("id", ""),
                entity_type="company"
            )
            mentions.extend(company_mentions)

        # Extract people mentions
        for person in extracted_data.get("people", []):
            full_name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
            if full_name:
                person_mentions = self._find_entity_in_text(
                    text=response_text,
                    entity_name=full_name,
                    entity_id=person.get("id", ""),
                    entity_type="person"
                )
                mentions.extend(person_mentions)

        # TODO: Add email, group, interaction mentions as needed

        return mentions

    def _find_entity_in_text(
        self,
        text: str,
        entity_name: str,
        entity_id: str,
        entity_type: str
    ) -> List[Dict[str, Any]]:
        """
        Find all occurrences of entity_name in text

        Returns:
            List of mention dicts with spans
        """
        if not entity_name:
            return []

        mentions = []
        # Case-insensitive search
        pattern = re.escape(entity_name)

        for match in re.finditer(pattern, text, re.IGNORECASE):
            mentions.append({
                "entityId": entity_id,
                "entityType": entity_type,
                "name": match.group(),  # Actual text found (preserves case)
                "span": {
                    "start": match.start(),
                    "end": match.end()
                }
            })

        return mentions
```

### 8. AI Response Storage (api/v1/query.py)

```python
# Store assistant message with entity mentions

# Handle both successful responses and clarification requests
if isinstance(result, dict) and result.get("status") == "needs_clarification":
    assistant_text = result.get("clarification_question", "I need more information.")
else:
    assistant_text = result.get("response") if isinstance(result, dict) else str(result)

# Ensure assistant_text is not None
if not assistant_text:
    assistant_text = "I couldn't generate a response. Please try again."

# NEW: Extract entity mentions from AI response
from services.entity_mention_extractor import ResponseEntityExtractor
extractor = ResponseEntityExtractor()
ai_entity_mentions = extractor.extract_mentions_from_response(
    response_text=assistant_text,
    extracted_data=result.get("data", {}) if isinstance(result, dict) else {}
)

# Store assistant message in background with entity mentions
background_tasks.add_task(
    create_message,
    conversation_id=conversation_id,
    role="ASSISTANT",
    content=assistant_text,
    metadata={
        "workspace_id": workspace_id,
        "user_id": user_id
    },
    entity_mentions=ai_entity_mentions  # NEW
)

# Return mentions in response
execution_time_ms = int((time.time() - start_time) * 1000)

return QueryResponse(
    success=True,
    query=request.query,
    result=cleaned_result,
    execution_time_ms=execution_time_ms,
    workspace_id=workspace_id,
    user_id=user_id,
    conversation_id=conversation_id,
    entity_mentions=ai_entity_mentions  # NEW
)
```

### 9. Message Retrieval (api/v1/conversations.py)

```python
@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    user_id: str = Depends(get_current_user_id)
):
    """Get all messages in a conversation WITH entity mentions"""

    client = await prisma_client.get_client()

    messages = await client.conversationmessage.find_many(
        where={"conversationId": conversation_id},
        order={"timestamp": "asc"}
    )

    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "metadata": msg.metadata,
            "entity_mentions": msg.entityMentions or []  # NEW: Include mentions
        })

    return {
        "success": True,
        "messages": formatted_messages,
        "total": len(formatted_messages)
    }
```

---

## Testing Strategy

### Unit Tests

1. **EntityMention Model Validation**
   - Valid entity mention structure
   - Invalid span values
   - Missing required fields

2. **ResponseEntityExtractor**
   - Single entity mention extraction
   - Multiple occurrences of same entity
   - Case-insensitive matching
   - No matches found
   - Empty extracted_data

3. **Entity Hydration**
   - Hydrate single company
   - Hydrate multiple entities
   - Handle missing entity IDs
   - Workspace isolation

### Integration Tests

1. **User Message with Mentions**
   - Send query with entity mentions
   - Verify mentions stored in DB
   - Verify mentions passed to data extractor

2. **AI Response with Mentions**
   - Query returns entities
   - Verify mentions extracted from response
   - Verify mentions stored with assistant message
   - Verify mentions returned in API response

3. **Message Retrieval**
   - Fetch conversation messages
   - Verify entity mentions included
   - Verify span data correct

### End-to-End Tests

1. **Full Conversation Flow**
   - User sends query with @mention
   - AI responds with entity names
   - Fetch conversation history
   - Verify both user and AI mentions present

### Manual Testing Checklist

- [ ] Frontend sends entity mentions in QueryRequest
- [ ] User message stored with mentions
- [ ] Entity hydration adds context to LLM prompt
- [ ] AI response contains entity names
- [ ] Mentions extracted from AI response
- [ ] Assistant message stored with mentions
- [ ] QueryResponse includes entity mentions
- [ ] Message retrieval returns mentions
- [ ] Spans are accurate for UI rendering
- [ ] Privacy rules enforced (frontend)

---

## Migration Plan

### Pre-Deployment

1. **Database Migration**
   ```bash
   # On dev environment
   npx prisma migrate dev --name add_entity_mentions_to_conversation_messages
   npx prisma generate
   ```

2. **Code Deployment**
   - Deploy backend with new entity mention code
   - Backward compatible: entity_mentions optional everywhere

3. **Frontend Coordination**
   - Ensure frontend ready to send entity_mentions
   - Ensure frontend can render mentions from API

### Deployment Steps

1. **Deploy Database Migration**
   ```bash
   # On production
   npx prisma migrate deploy
   npx prisma generate
   ```

2. **Deploy Backend Code**
   - API changes are backward compatible
   - Old messages without entityMentions return empty array

3. **Deploy Frontend**
   - Frontend starts sending entity_mentions
   - Frontend starts rendering entity chips

### Rollback Plan

If issues arise:

1. **Backend Rollback**
   - Deploy previous version
   - entity_mentions field ignored (doesn't break)

2. **Database Rollback** (if needed)
   ```sql
   ALTER TABLE "conversationMessage" DROP COLUMN "entityMentions";
   ```

### Post-Deployment

1. **Monitor**
   - Check entity mention storage rate
   - Monitor query execution time (hydration cost)
   - Track mention extraction accuracy

2. **Optimize** (if needed)
   - Cache entity hydration results
   - Batch entity queries
   - Improve mention extraction regex

---

## File Summary

### Files to Create
- `services/entity_mention_extractor.py` - Extract mentions from AI responses

### Files to Modify
- `prisma/schema.prisma` - Add entityMentions field
- `api/v1/schemas.py` - Add EntityMention model, update Request/Response
- `services/conversation.py` - Update create_message()
- `api/v1/query.py` - Handle mentions in user input & AI output
- `graph/pipeline.py` - Pass mentions through pipeline
- `agents/orchestrator.py` - Forward mentions to extractor
- `agents/data_extractor.py` - Hydrate entities for context
- `api/v1/conversations.py` - Return mentions in message retrieval

### Files to Test
All modified files plus:
- Integration tests for full flow
- Unit tests for entity extractor
- Unit tests for entity hydration

---

## Effort Estimate

| Phase | Duration | Complexity |
|-------|----------|------------|
| Phase 1: Database Schema | 2-3 hours | Low |
| Phase 2: API Schema | 2-3 hours | Low |
| Phase 3: Message Storage | 2-3 hours | Medium |
| Phase 4: Pipeline Integration | 2-3 hours | Medium |
| Phase 5: Entity Hydration | 2-3 hours | Medium |
| Phase 6: Response Extraction | 3-4 hours | Medium |
| Phase 7: AI Response Storage | 1-2 hours | Low |
| Phase 8: API Response | 1 hour | Low |
| Phase 9: Message Retrieval | 1-2 hours | Low |
| Phase 10: Testing & Docs | 2-3 hours | Medium |
| **Total** | **~20-27 hours** | **3-5 days** |

---

## Frontend Integration Guide

### Sending Entity Mentions (User Input)

```typescript
// When user types @ and selects entity from autocomplete
const entityMentions = [
  {
    entityId: "uuid-123",
    entityType: "company",
    name: "AcmeCorp",  // Text user typed after @
    span: {
      start: 20,  // Character position in query
      end: 29
    }
  }
];

// Send with query
const response = await fetch('/api/v1/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Workspace-ID': workspaceId,
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    query: "Show me deals with @AcmeCorp",
    entity_mentions: entityMentions
  })
});
```

### Rendering Entity Mentions (AI Response)

```typescript
// Response includes entity mentions
const data = await response.json();

// data.entity_mentions = [
//   {
//     entityId: "uuid-456",
//     entityType: "company",
//     name: "Acme Corporation",
//     span: { start: 10, end: 26 }
//   }
// ]

// Render with chips
function renderMessageWithMentions(content: string, mentions: EntityMention[]) {
  // Sort mentions by span.start (reverse) to replace from end to start
  const sortedMentions = [...mentions].sort((a, b) => b.span.start - a.span.start);

  let result = content;

  for (const mention of sortedMentions) {
    const before = result.substring(0, mention.span.start);
    const after = result.substring(mention.span.end);

    const chip = `<EntityChip
      id="${mention.entityId}"
      type="${mention.entityType}"
      name="${mention.name}"
    />`;

    result = before + chip + after;
  }

  return result;
}
```

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Span calculation errors | High | Medium | Store span.text for validation; test thoroughly |
| Entity hydration latency | Medium | Low | Cache results; parallel queries; max 5 entities |
| Privacy leaks | High | Low | Frontend enforces visibility; backend validates workspace |
| Database migration issues | High | Low | Test on dev; backward compatible design |
| Frontend/backend mismatch | Medium | Medium | API versioning; optional fields |
| Mention extraction false positives | Low | Medium | Acceptable; improve regex over time |

---

## Success Criteria

- [ ] Users can @mention entities in queries
- [ ] Mentioned entities hydrated for query context
- [ ] AI responses annotate entities with spans
- [ ] Frontend can render entity chips
- [ ] Message retrieval includes entity mentions
- [ ] Query execution time increased by <100ms
- [ ] No privacy leaks (only visible entities mentioned)
- [ ] Backward compatible (old messages work)
- [ ] Production deployment successful
- [ ] No database performance degradation

---

## Questions & Clarifications

1. **Mention Extraction (User Input):** Confirmed frontend responsibility
2. **Parent Message ID:** Not needed, removed from scope
3. **Mention Immutability:** Confirmed frozen snapshots
4. **Entity Hydration:** Backend only, no API hydration
5. **Privacy:** Frontend enforced
6. **Message Editing:** Not supported (immutable)
7. **Scale:** Max 5 mentions per query

---

## Next Steps

1. **Get Approval:** Review plan with team
2. **Schedule Work:** Allocate 3-5 days for implementation
3. **Coordinate with Frontend:** Ensure frontend ready for @ mentions
4. **Run Migration:** Add entityMentions field to dev DB
5. **Implement Phases 1-10:** Follow implementation plan
6. **Test Thoroughly:** Unit, integration, E2E tests
7. **Deploy to Production:** Database migration → Backend → Frontend
8. **Monitor & Optimize:** Track performance and accuracy

---

**Document Version:** 1.0
**Last Updated:** 2025-11-18
**Author:** AI Analyst System Team
