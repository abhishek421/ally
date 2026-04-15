# Ally — Onboarding Reference

> Written for fast re-onboarding without reading the codebase. Concept-first, dense, scannable.
> Last updated: April 2026.

---

## Table of Contents

- [30-Second Mental Model](#30-second-mental-model)
- [End-to-End Request Flow](#end-to-end-request-flow)
- [Tool System](#tool-system)
- [Confirmation System](#confirmation-system)
- [Object Memory System](#object-memory-system)
- [Custom Instructions System](#custom-instructions-system)
- [State & Persistence](#state--persistence)
- [SSE Event Reference](#sse-event-reference)
- [Quick-Find: Where Is X?](#quick-find-where-is-x)
- [Non-Obvious Things / Gotchas](#non-obvious-things--gotchas)
- [Repo File Map](#repo-file-map)

---

## 30-Second Mental Model

Three repos, one feature:

| Repo | Stack | Role | Port |
|------|-------|------|------|
| `ally` | Python, FastAPI, LangGraph | The brain — agent, tool execution, SSE streaming | 8000 |
| `frontend` | Next.js, React | The face — chat UI, SSE consumer, confirmation dialogs | 3000 |
| `backend` | NestJS, GraphQL, Prisma | The memory — conversation persistence, custom instructions, object memories | 4400 |

**Request path:**
```
User → AllyChatInput → AllyContext → /api/v1/chat (Next proxy) → Ally Python → LangGraph → Tools → GraphQL → Backend
```

The Python agent **streams events back via SSE**. The frontend consumes them and renders progressively. There is no polling.

---

## End-to-End Request Flow

### Normal Message

```
1.  User submits message (AllyChatInput.tsx)
2.  AllyContext.sendMessage()
      → saves message via saveAllyMessage() server action → backend DB
      → POST /api/v1/chat (Next.js proxy, preserves auth headers + active URL)
3.  routes.py receives request
      → parallel fetch: user profile + workspace instructions + group instructions
      → builds ToolContext, calls stream_agent()
4.  graph.py / stream_agent():
      a. is_first_message() — check if new conversation (affects greeting behavior)
      b. is_greeting(message) check:
           YES → categories = [], tier = LITE, ~200 token system prompt, 0 tools
           NO  → tier = STANDARD, categories = None (all tools loaded)
      c. set_tool_context(ctx) — inject per-request auth into contextvars
      d. get_all_tools() or get_tools_for_categories([]) for greetings
      e. LangGraph ReAct loop begins, streaming SSE events:
           thinking (heartbeat every 1.5s) → tool_call → tool_result → response → done
      f. First message only: generate_conversation_title() → conversation_title SSE event
5.  AllyContext receives SSE stream:
      → renders messages progressively
      → on data_changed event: queues cache invalidation
      → on done: useAllyDataInvalidator fires, invalidates React Query caches by entity type
      → on conversation_title: updates sidebar
```

### Confirmation Interrupt (nested inside step 4e)

```
4e-i.  Tool calls request_confirmation() → raises ConfirmationException
4e-ii. graph.py catches → interrupt() pauses LangGraph → emits confirmation_required SSE
4e-iii.AllyContext sets pendingConfirmation → AllyConfirmation.tsx renders
4e-iv. User responds → AllyContext.sendConfirmation() → POST /api/v1/chat/confirm
4e-v.  resume_agent() loads checkpoint, injects confirmation response, continues stream
       (Can repeat — agent may pause multiple times per turn)
```

### Data Invalidation Flow

```
Tool result with DATA_CHANGE_MARKER
  → parse_data_change() strips marker, extracts { entityType, action, entityId }
  → graph.py emits data_changed SSE event
  → AllyContext accumulates changes in dataChangesRef
  → on done: useAllyDataInvalidator.invalidateByChanges()
       PERSON  → people-infinite, pipeline-data, person-profile
       COMPANY → companies-infinite, pipeline-data, company-profile
       GROUP   → user-groups + server-side revalidation
       VIEW    → user-views, user-groups
```

---

## Tool System

### Categories & Loading

Tools load **per request**. Greetings get zero tools (fast-path). All other requests load the full tool set.

| Category | Always | ~Tokens | Key Tools |
|----------|:------:|--------:|-----------|
| READ (resolvers) | ✅ | 160 | `resolve_company_name`, `resolve_person_name`, `resolve_group_name`, `get_current_page` |
| MEMORY | ✅ | 110 | `save_object_memory`, `get_object_memories` |
| COMPANIES | — | 360 | `list_companies_in_workspace/group`, `get_company_by_id`, `search_company_by_name` |
| PEOPLE | — | 360 | `list_people_in_workspace/group`, `get_person_by_id`, `search_person_by_name` |
| GROUPS | — | 220 | `list_groups_in_workspace`, `get_group_by_id`, `search_group_by_name` |
| EMAIL | — | 930 | `listEmailsFromPerson/Company`, `get_email_thread`, `list/search_email_templates`, `draft_email`, `send_email` |
| COLUMNS | — | 660 | `get_group_columns`, `get_column_options`, `get_pipeline_status_options`, `get_entities_by_status`, `resolve_column_by_name` |
| CREATE | — | 260 | `create_company`, `create_person`, `create_group`, `create_view` |
| UPDATE | — | 750 | `update_company`, `update_person`, `update_column_value`, `add/remove_from_group` |
| NOTES | — | — | `create/list/get/update/delete_note` |
| REMINDERS | — | — | `create/list/get/update/delete_reminder` |
| RESEARCH | — | — | `web_search` (Perplexity API) |
| CONTEXT | — | — | `get_entity_instructions` |

**Chitchat fast-path**: `get_tools_for_categories([])` bypasses ALWAYS_INCLUDE entirely — **zero tools loaded**. This is intentional; greetings get a ~200 token system prompt vs ~7,000 with tools.

### Model Routing (`router.py`)

Two tiers, decided by a single regex check before agent invocation.

| Tier | When | Details |
|------|------|---------|
| LITE | Greetings, acks, emoji-only | "hi", "thanks", "yes", "👍" — 0 tools, ~200 token prompt |
| STANDARD | Everything else | All tools loaded, full system prompt |

`is_greeting(message)` is the only routing gate — pure regex, <1ms, no LLM call.

### ToolContext & contextvars (`context_var.py`)

Tools are created **at startup** (for efficiency) but need **per-request auth**. Solution: `contextvars`.

```python
# graph.py, before agent runs:
set_tool_context(ToolContext(workspace_id, user_id, auth_token, active_url, ...))

# Inside any tool at call time:
ctx = get_tool_context()  # returns THIS request's context — async-safe
client = ctx.get_client() # GraphQL client with auth
```

Each asyncio task gets its own copy — concurrent requests are safe. If you write a new tool and forget to call `get_tool_context()`, it will fail with the wrong (or no) credentials.

### Fuzzy Name Resolution (`base.py`)

`resolve_company_name`, `resolve_person_name`, `resolve_group_name` use multi-algorithm fuzzy matching:
- Token sort, token set, partial match, standard Levenshtein
- Returns confidence: **high** / **medium** / **low**
- Drives `select_one` confirmation when multiple candidates match

---

## Confirmation System

### Confirmation Types

| Type | UI | When to use |
|------|----|-------------|
| `confirm_action` | Yes / No buttons | Destructive ops (delete), irreversible changes |
| `select_one` | Radio buttons + confidence badges | Entity disambiguation (multiple fuzzy matches) |
| `select_many` | Checkboxes | Multi-entity selection |
| `confirm_with_edit` | Editable form + old → new diff | Review data before create/update |
| `bulk_confirm_create` | Per-row draft table | Batch entity creation — user accepts/edits/rejects each row |

### Helper Functions (`confirmation.py`)

```python
request_create_confirmation(title, message, entity_type, draft_data)
request_update_confirmation(title, message, entity_type, draft_data)
request_delete_confirmation(title, message, entity_type)
request_column_update_confirmation(title, message, entity_type, old_value, new_value)
request_entity_selection(title, message, options)
request_bulk_create_confirmation(title, message, entity_type, entities)
# entities: list of draft dicts → frontend renders as editable draft rows
```

### Confirmation Response Shape

```typescript
interface ConfirmationResponsePayload {
  confirmed: boolean
  selected_id?: string          // select_one
  selected_ids?: string[]       // select_many
  feedback?: string             // optional cancellation reason (any type)
  accepted_ids?: string[]       // bulk_confirm_create: e.g. ["draft-0", "draft-2"]
  edited_entities?: Record<string, unknown>  // bulk_confirm_create: per-draft edits
}
```

### Frontend UI Notes

- **Status change visualization**: `confirm_with_edit` shows old value → new value with color-coded diff
- **Edit mode**: user can modify `draft_data` fields inline before confirming
- **Confidence badges**: High / Medium / Low match (driven by fuzzy resolver score)
- **Entity type icons**: Person, Company, Group, View styled chips
- **Feedback collection**: optional textarea rendered when user cancels

---

## Object Memory System

**File**: `src/tools/memory_tools.py`

Long-term per-entity facts that **persist across conversations**. Always loaded (in ALWAYS_INCLUDE) so the agent checks entity memory before acting.

### Tools

```python
save_object_memory(entity_id, entity_type, memory_text, category, object_definition_id?)
# Always call get_object_memories first to avoid duplicates

get_object_memories(entity_id, entity_type)
```

### Memory Categories

| Category | Use |
|----------|-----|
| PREFERENCE | Communication preferences, meeting styles |
| CONTEXT | Background facts about the entity |
| INTERACTION | Notes from past interactions |
| BEHAVIORAL | Observed patterns or tendencies |

### Entity Types

`PERSON` | `COMPANY` | `OBJECT` (custom object types — requires `object_definition_id`)

### Schema

```
object_memories table:
  entityId, entityType, workspaceId, memoryText, category,
  sourceConversationId, isActive, createdBy, createdAt
```

---

## Custom Instructions System

A 3-level hierarchy injected into the system prompt, allowing workspace admins and users to shape the agent's behavior without code changes.

| Level | Scope | Max Length | Fetched When |
|-------|-------|-----------|--------------|
| Workspace | All conversations in workspace | 8000 chars | Every chat start (parallel with user profile) |
| Group | Conversations while viewing a group page | 8000 chars | URL matches `/apps/groups/{uuid}` — extracted from `active_url` |
| Entity | Per entity type (Person / Company / Custom Object) | 8000 chars | On-demand via `get_entity_instructions` tool |

All instructions have audit trails (`updatedBy` tracks who last modified them).

### GraphQL Endpoints Summary

```
# Workspace
getWorkspaceCustomInstructions(workspaceId)
updateWorkspaceCustomInstructions(input)
deleteWorkspaceCustomInstructions(workspaceId)
getEntityCustomInstructions(workspaceId, entityType, objectDefinitionId?)
upsertEntityCustomInstructions(workspaceId, input)
deleteEntityCustomInstructions(workspaceId, entityType, objectDefinitionId?)

# Group
getGroupCustomInstructions(groupId)
updateGroupCustomInstructions(input)
deleteGroupCustomInstructions(groupId)
```

---

## State & Persistence

| What | Where | Notes |
|------|-------|-------|
| Chat messages (display) | `AllyContext` (React context, root layout) | In-memory; survives panel close/reopen because context is above the component |
| Chat messages (DB) | `allyMessage` table | Saved via `saveAllyMessage` server action immediately on send |
| Conversation list | `allyConversation` table | React Query, 2min stale time |
| Agent conversation state | PostgreSQL checkpointer (`DATABASE_URL_ALLY`) | LangGraph checkpoint — required for `resume_agent()` (confirmations). Falls back to `MemorySaver` if env var missing (no persistence across restarts) |
| Object memories | `object_memories` table | Via GraphQL, persists across conversations |
| Custom instructions | `workspaceCustomInstructions`, `groupCustomInstructions`, `entityCustomInstructions` | Fetched at chat start / on-demand |

**Critical**: `AllyContext` is at root layout level, not inside the chat component. This is why state (including live SSE streams) survives closing the Ally panel. If you move the context down the tree, streams will die on close.

---

## SSE Event Reference

| Event | Payload | Notes |
|-------|---------|-------|
| `thinking` | `{ content: string }` | Heartbeat every 1.5s. "Thinking..." during reasoning, "Analyzing results..." after tool call |
| `tool_call` | `{ name, args }` | Tool execution started |
| `tool_result` | `{ name, result }` | Tool result received (DATA_CHANGE_MARKER already stripped) |
| `response` | `{ content: string }` | Streamed text chunk — appended to current assistant message |
| `confirmation_required` | `ConfirmationRequest` | Agent paused; stream resumes after `/chat/confirm` |
| `data_changed` | `{ entityType, action, entityId }` | Cache invalidation signal |
| `conversation_title` | `{ title, conversation_id }` | First message only — fires after main response |
| `error` | `{ message: string }` | |
| `done` | `{}` | Stream complete; triggers deferred cache invalidation |

**Frontend tool display logic:**
- `INTERNAL_TOOLS` set (~18 tools): hidden by default in UI (lookup/query tools like resolvers)
- `ACTION_TOOLS` set (~16 tools): shown prominently (create/update/delete tools)

---

## Quick-Find: Where Is X?

| I need to... | File |
|-------------|------|
| Change the agent's behavior / personality / instructions | `ally/src/agent/prompts.py` |
| Add or modify a tool | `ally/src/tools/<category>_tools.py` → add to category getter |
| Add a new tool category | `ally/src/tools/__init__.py` (ToolCategory + TOOL_REGISTRY) |
| Change greeting detection | `ally/src/agent/router.py` — edit `GREETING_PATTERNS` |
| Add a new confirmation type | `ally/src/tools/confirmation.py` + `frontend/types/ally-confirmation.ts` + `frontend/components/ally/AllyConfirmation.tsx` |
| Change how SSE events are emitted | `ally/src/agent/graph.py` |
| Change how SSE events are consumed | `frontend/contexts/ally-context.tsx` |
| Change chat UI layout / conversation sidebar | `frontend/components/ally/AllyChat.tsx` |
| Change message rendering / tool call display | `frontend/components/ally/AllyChatMessages.tsx` |
| Change confirmation dialog UI | `frontend/components/ally/AllyConfirmation.tsx` |
| Change which queries are invalidated on data change | `frontend/hooks/ally/use-ally-data-invalidator.ts` |
| Change conversation DB persistence | `backend/apps/api/src/ally/ally.service.ts` |
| Change custom instructions GraphQL | `backend/apps/api/src/workspace/workspace.resolver.ts` |
| Change DB schema | `backend/libs/prisma-schema/prisma/schema.prisma` |
| Debug a live SSE stream | Browser DevTools → Network → `/api/v1/chat` → EventStream tab |

---

## Non-Obvious Things / Gotchas

1. **Tools are created at startup, not per-request.** Auth context is injected via `context_var.py` using Python's `contextvars`. Every tool calls `get_tool_context()` at runtime to get the correct request's credentials. If you add a new tool and skip this, it will silently use the wrong workspace/user.

2. **`get_tools_for_categories([])` is the greeting fast-path.** The empty list explicitly bypasses `ALWAYS_INCLUDE`. Do not change this to fall back to loading all tools — the zero-tool path is intentional. Greetings get a ~200 token system prompt instead of ~7,000.

3. **Routing logic is in `graph.py`, not `routes.py`.** `routes.py` resolves user profile and instructions in parallel. The greeting check and tier/tool selection happen inside `stream_agent()`.

4. **`AllyContext` is at root layout level.** State (messages, streaming connection) survives closing/reopening the Ally panel. If you ever move the context closer to the chat component, the SSE stream will terminate on unmount.

5. **LangGraph checkpointer requires `DATABASE_URL_ALLY`.** Without it, falls back to `MemorySaver` (in-memory, lost on restart). The confirmation flow (`resume_agent`) requires a persistent checkpointer — if the server restarts mid-confirmation, the conversation state is gone.

6. **`parse_data_change()` strips the marker from the tool result before it reaches the LLM.** The LLM sees the clean result. The `data_changed` SSE event is emitted separately. This means if you're debugging and a tool emits strange trailing content, it's probably a malformed `DATA_CHANGE_MARKER`.

7. **Group instructions are URL-context-aware.** The active URL (current pathname in the browser) is passed from the frontend on every chat request. `routes.py` parses `/apps/groups/{uuid}` from it to know which group to fetch instructions for. If group instructions aren't loading, check that `active_url` is being forwarded in the proxy.

8. **Bulk confirmation response shape differs from all other types.** Uses `accepted_ids` / `edited_entities` instead of `selected_id`. The frontend draft row rendering is a separate code path inside `AllyConfirmation.tsx`.

9. **`generate_conversation_title()` is a second LLM call on the same thread, after the main response.** It always uses LITE tier. The frontend listens for `conversation_title` SSE event — this fires after `done`, so the conversation is complete before the title updates.

10. **Orphaned tool calls are cleaned up on each request.** `_sanitize_conversation_history()` runs before the agent starts and removes any half-finished tool calls left by a previously interrupted/failed request. This prevents LangGraph from replaying stale tool results.

---

## Repo File Map

### `ally/src/`

```
agent/
  graph.py         LangGraph ReAct agent — stream_agent(), resume_agent(),
                   generate_conversation_title(), heartbeat system
  prompts.py       System prompt builder — injects workspace/group/entity instructions,
                   user personalization, tool guidance
  router.py        is_greeting() — regex greeting detection, ModelTier enum (LITE/STANDARD)
  state.py         AgentState schema (messages, workspace_id, user_id, auth_token)

api/
  routes.py        POST /chat, POST /chat/confirm, GET /conversations/{id}/history
                   Parallel fetch: user profile + workspace + group instructions
  middleware.py    JWT auth (AWS Cognito compatible)

tools/
  __init__.py      ToolCategory enum, TOOL_REGISTRY, ALWAYS_INCLUDE,
                   get_tools_for_categories(), get_all_tools()
  base.py          ToolContext, fuzzy matching, DATA_CHANGE_MARKER, parse_data_change()
  context_var.py   set_tool_context() / get_tool_context() — per-request injection
  read_tools.py    ALL read tools: resolvers + company/people/group read +
                   email tools (7) + column tools (5)
  create_tools.py  create_company, create_person, create_group, create_view
  update_tools.py  update_company, update_person, update_column_value, add/remove_from_group
  note_tools.py    create/list/get/update/delete_note
  reminder_tools.py create/list/get/update/delete_reminder
  memory_tools.py  save_object_memory, get_object_memories (always loaded)
  context_tools.py get_entity_instructions
  research_tools.py web_search (Perplexity)
  confirmation.py  ConfirmationType, ConfirmationRequest, request_*_confirmation helpers

graphql/
  client.py        GraphQL client + get_current_user_profile(),
                   get_workspace_custom_instructions(),
                   get_group_custom_instructions(group_id)
```

### `frontend/` (ally-related)

```
components/ally/
  AllyChat.tsx              Chat container — conversation sidebar, search, rename, delete
  AllyChatMessages.tsx      Message rendering — markdown, tool call grouping, status badges
  AllyChatInput.tsx         Auto-resize textarea, send/cancel, keyboard shortcuts
  AllyConfirmation.tsx      All confirmation dialog types + bulk draft row UI

contexts/
  ally-context.tsx          Root-level state + SSE streaming engine — single source of truth

hooks/ally/
  use-ally-chat.ts              Thin wrapper around AllyContext
  use-conversations.ts          React Query conversation list (2min stale)
  use-conversation.ts           React Query single conversation (1min stale)
  use-ally-data-invalidator.ts  Cache invalidation by entity type on data_changed events

app/api/v1/chat/
  route.ts          SSE proxy → Ally Python (preserves auth + active URL headers)
  confirm/route.ts  Confirmation proxy

lib/actions/ally.actions.ts     Server actions: create/update/delete conversation, save message
types/ally-confirmation.ts      ConfirmationRequest/Response types, ENTITY_TYPE_CONFIG,
                                CONFIDENCE_CONFIG, getStatusChangeData()
lib/types/ally.ts               ChatMessage, ToolCall, Message, ConversationSummary
```

### `backend/` (ally-related)

```
apps/api/src/ally/
  ally.resolver.ts    getAllyConversations, getAllyConversation, getAllyMessages,
                      createAllyConversation, updateAllyConversation,
                      deleteAllyConversation, saveAllyMessage
  ally.service.ts     Business logic
  models/             conversation.model.ts
  dto/                conversation.input.ts

apps/api/src/workspace/
  workspace.resolver.ts   Workspace + entity custom instructions endpoints

apps/api/src/group/group/
  Group.ts                Group custom instructions endpoints

libs/prisma-schema/prisma/schema.prisma
  → allyConversation, allyMessage
  → workspaceCustomInstructions, groupCustomInstructions, entityCustomInstructions
  → objectMemory (object_memories table)
```

---

*Last updated: April 2026*
