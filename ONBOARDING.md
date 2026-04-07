# Ally Chat Feature - Onboarding Guide

This document provides a comprehensive overview of the Ally Chat feature architecture across all three repositories. Use this to quickly onboard instead of reading through all the code.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [1. Ally Repo - LangGraph AI Agent](#1-ally-repo---langgraph-ai-agent-python)
- [2. Frontend Repo - Next.js Chat UI](#2-frontend-repo---nextjs-chat-ui)
- [3. Backend Repo - NestJS GraphQL API](#3-backend-repo---nestjs-graphql-api)
- [Data Flow](#data-flow)
- [SSE Event Types](#sse-event-types)
- [Confirmation System](#confirmation-system)
- [Tool System](#tool-system)
- [Custom Instructions System](#custom-instructions-system)
- [Key Files Reference](#key-files-reference)

---

## Architecture Overview

The Ally Chat feature is a **3-tier AI-powered CRM assistant** with:

- **Streaming responses** via Server-Sent Events (SSE)
- **Human-in-the-loop confirmations** for sensitive operations
- **Intelligent tool execution** for CRM operations (CRUD, notes, reminders, research)
- **Multi-LLM support** (OpenAI, Anthropic, Gemini)
- **Conversation persistence** with PostgreSQL
- **Custom instructions** at workspace, group, and entity levels
- **Personalized interactions** using user profile data
- **Auto-generated conversation titles**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │     │   Ally Agent    │     │    Backend      │
│   (Next.js)     │────▶│   (Python)      │────▶│   (NestJS)      │
│                 │◀────│   LangGraph     │◀────│   GraphQL       │
└─────────────────┘ SSE └─────────────────┘     └─────────────────┘
```

---

## Repository Structure

| Repo | Tech Stack | Purpose | Local Dev Port |
|------|------------|---------|----------------|
| `ally` | Python, FastAPI, LangGraph | AI Agent service with tool execution | `8000` |
| `frontend` | Next.js, React, TypeScript | Chat UI components and state management | `3000` |
| `backend` | NestJS, GraphQL, Prisma | Conversation persistence, custom instructions, and CRM data | `4400` |

---

## 1. Ally Repo - LangGraph AI Agent (Python)

The core AI service that processes user messages and executes CRM operations.

### Technology Stack

- **Framework**: FastAPI with async/streaming support
- **AI/Orchestration**: LangGraph (ReAct pattern agent) + LangChain
- **LLM Support**: OpenAI (GPT-4), Anthropic (Claude), Google Gemini
- **Backend Communication**: GraphQL API client
- **Database**: PostgreSQL (for LangGraph conversation persistence via checkpointer)
- **Streaming**: Server-Sent Events (SSE)
- **Authentication**: JWT (AWS Cognito compatible)

### Directory Structure

```
ally/
├── src/
│   ├── main.py                    # FastAPI app entry point, CORS, lifespan
│   ├── config.py                  # Environment configuration (Settings class)
│   ├── agent/
│   │   ├── graph.py              # LangGraph ReAct agent (stream/resume logic)
│   │   ├── state.py              # Agent state schema
│   │   └── prompts.py            # System prompts with personalization
│   ├── api/
│   │   ├── routes.py             # /chat, /chat/confirm endpoints
│   │   └── middleware.py         # JWT authentication
│   ├── tools/
│   │   ├── base.py               # Base tool, fuzzy matching, data changes
│   │   ├── read_tools.py         # List/Get/Search/Resolve tools
│   │   ├── create_tools.py       # Create entity tools
│   │   ├── update_tools.py       # Update/Modify tools
│   │   ├── research_tools.py     # Web search tool
│   │   ├── confirmation.py       # Confirmation UI framework
│   │   ├── context_tools.py      # Entity-specific instructions retrieval
│   │   ├── note_tools.py         # Note CRUD tools
│   │   ├── reminder_tools.py     # Reminder CRUD tools
│   │   └── __init__.py           # Tool aggregation
│   └── graphql/
│       ├── client.py             # GraphQL client
│       └── __init__.py
├── tests/                         # Test suite
├── requirements.txt               # Python dependencies
├── pyproject.toml                # Project metadata
├── docker-compose.yml            # Local dev setup
└── Dockerfile                    # Container configuration
```

### Key Components

#### API Endpoints (`src/api/routes.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/chat` | POST | Main chat endpoint, returns SSE stream |
| `/api/v1/chat/confirm` | POST | Resume agent after user confirmation |
| `/api/v1/conversations/{id}/history` | GET | Retrieve conversation history |
| `/health` | GET | Health check |

The `/chat` endpoint now performs parallel resolution of user profile, workspace instructions, and group instructions before creating the agent. It also extracts the group ID from the active URL (`/apps/groups/{uuid}`) for group-specific context.

#### Agent Graph (`src/agent/graph.py`)

- **`stream_agent()`** - Processes user messages through LangGraph ReAct agent
- **`resume_agent()`** - Continues execution after user confirmation
- Handles tool calls, results, and responses
- Can pause for user confirmation via `interrupt()`
- **`generate_conversation_title()`** - Uses LLM to create 2-6 word titles for new conversations
- **`is_first_message()`** - Checks if conversation is new to trigger title generation
- **`get_checkpointer()`** - Returns PostgreSQL checkpointer if `DATABASE_URL_ALLY` is configured, otherwise falls back to MemorySaver
- **Heartbeat system** - Sends "Thinking..." or "Analyzing results..." events every 1.5 seconds during long operations
- **`_extract_text_content()`** - Normalizes different LLM response formats (handles Gemini's content block format)
- **`_get_result_summary()`** - Extracts human-readable summaries from tool results

#### Agent State (`src/agent/state.py`)

```python
class AgentState:
    messages: Annotated[list, add_messages]  # Accumulated messages
    workspace_id: str                         # CRM workspace context
    user_id: str                              # Authenticated user
    auth_token: str                           # For GraphQL calls
```

#### Tool Context (`src/tools/base.py`)

The `ToolContext` passed to all tools has been expanded:

```python
class ToolContext:
    workspace_id: str
    user_id: str
    auth_token: str
    active_url: Optional[str]                  # Current page URL
    user_first_name: Optional[str]             # For personalization
    user_email: Optional[str]                  # User context
    workspace_instructions: Optional[str]      # Workspace-level custom instructions
    group_instructions: Optional[str]          # Group-level custom instructions
```

#### System Prompts (`src/agent/prompts.py`)

The agent uses a comprehensive system prompt that includes:
- **Base Instructions**: CRM operations, data management, reasoning patterns
- **Workspace Context**: Custom instructions set by workspace admins
- **Group Context**: Group-specific instructions injected when in a group view
- **Entity Context**: Entity-type-specific instructions (via `get_entity_instructions` tool)
- **User Personalization**: User's first name, greeting behavior (different for new vs continuing conversations)
- **Tool Guidance**: Smart name resolution, human-in-the-loop workflows
- **Creating Entities**: Encourages sensible defaults (PEOPLE type, private groups)
- **Web Search**: Explicitly instructs agent to use `web_search` for external data
- **Privacy & Ethics**: Data protection, user permissions

#### GraphQL Client (`src/graphql/client.py`)

New methods added:
- **`get_current_user_profile()`** - Fetch database user ID, first name, and email
- **`get_workspace_custom_instructions()`** - Fetch workspace-level instructions
- **`get_group_custom_instructions(group_id)`** - Fetch group-specific instructions

#### Data Change Tracking (`src/tools/base.py`)

Tools use a marker system to track entity changes:
- `DATA_CHANGE_MARKER` appended to tool results with change metadata
- `parse_data_change()` extracts change data from results
- Enables frontend cache invalidation when data is modified

```python
class EntityType(str, Enum):
    PERSON = "person"
    COMPANY = "company"
    GROUP = "group"
    VIEW = "view"
    REMINDER = "reminder"

class ChangeAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
```

### Environment Variables

```bash
LLM_PROVIDER=openai|anthropic|gemini
LLM_MODEL=gpt-4o|claude-3-opus|gemini-pro
BACKEND_GRAPHQL_URL=http://localhost:3000/graphql
DATABASE_URL_ALLY=postgresql://...
PERPLEXITY_API_KEY=...
HOST=0.0.0.0
PORT=8000
```

---

## 2. Frontend Repo - Next.js Chat UI

React components and state management for the chat interface.

### Directory Structure

```
frontend/
├── components/ally/
│   ├── AllyChat.tsx              # Main chat container with history management
│   ├── AllyChatInput.tsx         # Message input field
│   ├── AllyChatMessages.tsx      # Message rendering with tool call grouping
│   ├── AllyChatButton.tsx        # Floating action button (currently disabled)
│   ├── AllyConfirmation.tsx      # Confirmation dialog with edit/feedback support
│   └── index.ts                  # Component exports
├── components/layout/
│   └── ally-aware-main.tsx       # Layout wrapper aware of Ally panel
├── contexts/
│   └── ally-context.tsx          # Chat state management + SSE streaming
├── hooks/ally/
│   ├── use-ally-chat.ts          # Core chat logic hook (thin wrapper)
│   ├── use-conversations.ts      # Conversation list fetching (React Query)
│   ├── use-conversation.ts       # Single conversation fetching (React Query)
│   └── use-ally-data-invalidator.ts  # Per-entity-type cache invalidation
├── lib/
│   ├── actions/ally.actions.ts   # Server actions with Zod validation
│   ├── types/ally.ts             # Extended type definitions
│   └── data/ally/
│       ├── get-conversations.ts  # List conversations
│       └── get-conversation.ts   # Get single conversation
├── lib/graphql/ally/             # GraphQL query/mutation files
│   ├── create-conversation.graphql
│   ├── delete-conversation.graphql
│   ├── get-conversation.graphql
│   ├── get-conversations.graphql
│   ├── get-messages.graphql
│   ├── save-message.graphql
│   └── update-conversation.graphql
├── app/api/v1/
│   └── chat/
│       ├── route.ts              # Chat proxy endpoint
│       └── confirm/route.ts      # Confirmation proxy endpoint
└── types/
    └── ally-confirmation.ts      # TypeScript types + entity/confidence configs
```

### Key Components

#### AllyChat.tsx - Main Chat Container
- Orchestrates the entire chat interface
- **Conversation history sidebar** with search functionality (via `nuqs` URL state)
- **Rename conversations** inline editing
- **Delete conversations** with confirmation dialog
- Conversation selection and switching
- **Quick action suggestions** in empty state
- Support for expanded/minimized view
- Responsive design for mobile and desktop

#### AllyChatInput.tsx - Message Input
- Auto-resizing textarea (max 100px height)
- Send on Enter (Shift+Enter for newline)
- Cancel button during streaming
- Focus management on mount
- Keyboard shortcut hints

#### AllyChatMessages.tsx - Message Rendering
- User messages (right-aligned, primary color)
- Assistant messages (left-aligned, with Ally avatar)
- **Full markdown rendering** (lists, code blocks, blockquotes, tables, links)
- **Advanced tool call grouping**:
  - `INTERNAL_TOOLS` set (~18 lookup/query tools hidden by default)
  - `ACTION_TOOLS` set (~16 user-facing tools displayed prominently)
  - Tool grouping by name with progress indicators
- Tool call chip display with status badges
- **Tool result formatting** with ID stripping
- Status indicators (completed, in-progress, failed)

#### AllyChatButton.tsx - Floating Action Button
- **Currently disabled** - Ally now opens from sidebar only
- Logic structure preserved but renders empty fragment

#### AllyConfirmation.tsx - Confirmation Dialog
- `select_one` - Radio buttons for disambiguation
- `confirm_action` - Simple yes/no confirmation
- `confirm_with_edit` - Review and edit data before confirming
- **Status change visualization** - Shows old value → new value with colors
- **Edit mode** - Users can modify draft data fields before confirming
- **Feedback collection** - Optional feedback textarea on cancellation
- **Confidence badges** - "High match", "Possible match", "Low match" indicators
- **Entity type icons** - Person, Company, Group, View with styled chips
- **Custom action labels** on confirm buttons

### State Management

### Architecture: Context-Based State Persistence

**Important**: All chat state is managed in `AllyContext` (at the root layout level), not in the `useAllyChat` hook. This ensures:

- **Chat survives popup close/open**: State persists when user closes and reopens the chat panel
- **SSE streams continue in background**: The streaming connection runs in the context, not tied to component lifecycle
- **Messages preserved across remounts**: No loss of messages when React re-renders

The `useAllyChat` hook is a thin wrapper that delegates to the context.

#### AllyContext (`contexts/ally-context.tsx`)

The single source of truth for all chat state:

```typescript
interface AllyContextType {
  // State (persists across popup close/open)
  messages: ChatMessage[]
  isLoading: boolean
  isConfirming: boolean
  error: string | null
  conversationId: string | null
  pendingConfirmation: ConfirmationRequest | null
  workspaceId: string | null
  isAllyOpen: boolean                          // Tracks if Ally panel is open
  setIsAllyOpen: (isOpen: boolean) => void     // Toggle Ally panel

  // Callback refs (for cross-component communication)
  onConversationCreated: MutableRefObject<((id: string) => void) | null>
  onConversationsInvalidate: MutableRefObject<(() => void) | null>

  // Actions
  sendMessage(content: string): Promise<void>
  sendConfirmation(response: ConfirmationResponsePayload): Promise<void>
  cancel(): void
  clearMessages(): void
  loadMessages(messages: ChatMessage[]): void
}
```

The context also:
- Syncs workspace ID from auth context (`activeWorkspaceId`)
- Passes active URL (current pathname) to the API for page-aware context
- Passes session ID for request tracing
- Handles the `conversation_title` SSE event to auto-update conversation names

#### useAllyChat Hook (`hooks/ally/use-ally-chat.ts`)

A thin wrapper around `AllyContext` that:
- Sets workspace ID in context
- Syncs initial conversation ID
- Registers callbacks for conversation creation and invalidation

```typescript
export function useAllyChat({
  workspaceId: string
  conversationId?: string | null
  onConversationCreated?: (conversationId: string) => void
}) => {
  // All state comes from AllyContext
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  conversationId: string | null
  sendMessage(content: string): Promise<void>
  cancel(): void
  clearMessages(): void
  loadMessages(messages: ChatMessage[]): void
  pendingConfirmation: ConfirmationRequest | null
  isConfirming: boolean
  sendConfirmation(response: ConfirmationResponsePayload): Promise<void>
}
```

#### useAllyDataInvalidator Hook (`hooks/ally/use-ally-data-invalidator.ts`)

Sophisticated per-entity-type cache invalidation:
- **Person changes**: Invalidates `people-infinite`, `pipeline-data`, `person-profile` queries
- **Company changes**: Invalidates `companies-infinite`, `pipeline-data`, `company-profile` queries
- **Group changes**: Invalidates `user-groups` queries, triggers server-side revalidation
- **View changes**: Invalidates `user-views`, `user-groups` queries
- Workspace-aware, batch invalidation with deduplication

#### useConversations / useConversation Hooks

Built with React Query:
- `useConversations`: 2-minute stale time, 5-minute GC, 1 retry
- `useConversation`: 1-minute stale time, 5-minute GC

### TypeScript Types

#### `types/ally-confirmation.ts`

```typescript
interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  isStreaming?: boolean
  toolCalls?: Array<{
    name: string
    args?: Record<string, unknown>
    result?: string
  }>
}

interface ConfirmationRequest {
  confirmation_type: "confirm_action" | "select_one" | "select_many" | "confirm_with_edit"
  title: string
  message: string
  options?: ConfirmationOption[]
  draft_data?: Record<string, unknown>
  action_label?: string              // Custom confirm button text
  allow_cancel_feedback: boolean
  entity_type?: "person" | "company" | "group" | "view"
}

interface ConfirmationResponsePayload {
  confirmed: boolean
  selected_id?: string
  selected_ids?: string[]
  feedback?: string
}

// Entity type display config (icons + labels)
const ENTITY_TYPE_CONFIG = { person, company, group, view }

// Confidence level display config (colors + labels)
const CONFIDENCE_CONFIG = { high, medium, low }

// Helper functions
getEntityTypeConfig(entityType): { icon, label }
getStatusChangeData(draftData): { field, oldValue, newValue }
```

#### `lib/types/ally.ts` (Extended types)

```typescript
interface CreatedEntity {
  type: string
  id: string
  name: string
  url: string
  details: Record<string, unknown>
}

interface ToolCall {
  tool: string
  params: Record<string, unknown>
  result: string
  parsedResult: unknown
  createdEntity?: CreatedEntity
  status: "pending" | "completed" | "failed"
}

interface Message {
  role: "user" | "assistant"
  content: string
  reasoning: string[]
  toolCalls: ToolCall[]
  isStreaming: boolean
  status: "pending" | "streaming" | "completed" | "failed"
}

interface ConversationSummary { ... }
interface ConversationMessage { ... }
```

### API Routes (Proxy)

Both `/api/v1/chat/route.ts` and `/api/v1/chat/confirm/route.ts` are proxy endpoints that:
- Forward requests to upstream Ally service (`ALLY_API_URL`)
- Preserve authentication headers (`Authorization`, `X-Workspace-ID`, `x-session-id`)
- Pass active URL context for page-aware agent behavior
- Stream SSE responses back to the client
- Handle errors with dev/prod differentiation

### Server Actions (`lib/actions/ally.actions.ts`)

All mutations use Next.js server actions with **Zod schema validation**:
- `createAllyConversation` - Creates new conversation
- `updateAllyConversation` - Updates title/archive status
- `deleteAllyConversation` - Deletes conversation
- `saveAllyMessage` - Persists messages with toolCalls

---

## 3. Backend Repo - NestJS GraphQL API

Conversation persistence and custom instructions layer using GraphQL and Prisma.

### Directory Structure

```
backend/
├── apps/api/src/ally/
│   ├── ally.module.ts            # Module definition
│   ├── ally.resolver.ts          # GraphQL endpoints
│   ├── ally.service.ts           # Business logic
│   ├── models/
│   │   └── conversation.model.ts # GraphQL models
│   └── dto/
│       └── conversation.input.ts # Input validation DTOs
├── apps/api/src/workspace/
│   ├── workspace.resolver.ts     # Workspace + entity custom instructions endpoints
│   └── models/
│       ├── custom-instructions.model.ts        # Workspace instructions model
│       └── entity-custom-instructions.model.ts # Entity instructions model
├── apps/api/src/group/group/
│   ├── Group.ts                  # Group custom instructions endpoints
│   └── models/
│       └── group-custom-instructions.model.ts  # Group instructions model
└── libs/prisma-schema/prisma/
    └── schema.prisma             # Database models
```

### GraphQL Endpoints

#### Ally Conversation Endpoints (`ally.resolver.ts`)

**Queries:**
- `getAllyConversations(workspaceId, page, limit, includeArchived)` - Paginated list of user's conversations
- `getAllyConversation(conversationId)` - Single conversation with all messages
- `getAllyMessages(conversationId, limit, beforeId)` - Messages with cursor-based pagination

**Mutations:**
- `createAllyConversation(input)` - Create new conversation
- `updateAllyConversation(input)` - Update title or archive status
- `deleteAllyConversation(conversationId)` - Delete conversation and messages
- `saveAllyMessage(input)` - Save message to conversation

#### Workspace Custom Instructions Endpoints (`workspace.resolver.ts`)

**Queries:**
- `getWorkspaceCustomInstructions(workspaceId)` - Get workspace-level instructions
- `getEntityCustomInstructions(workspaceId, entityType, objectDefinitionId?)` - Get entity-type instructions
- `getAllEntityCustomInstructions(workspaceId)` - Get all entity-type instructions

**Mutations:**
- `updateWorkspaceCustomInstructions(input)` - Upsert workspace instructions (max 8000 chars)
- `deleteWorkspaceCustomInstructions(workspaceId)` - Delete workspace instructions
- `upsertEntityCustomInstructions(workspaceId, input)` - Upsert entity-type instructions
- `deleteEntityCustomInstructions(workspaceId, entityType, objectDefinitionId?)` - Delete entity instructions

#### Group Custom Instructions Endpoints (`Group.ts`)

**Queries:**
- `getGroupCustomInstructions(groupId)` - Get group-specific instructions

**Mutations:**
- `updateGroupCustomInstructions(input)` - Upsert group instructions (max 8000 chars)
- `deleteGroupCustomInstructions(groupId)` - Delete group instructions

### Database Schema (Prisma)

```prisma
model allyConversation {
  id          String   @id @default(uuid()) @db.Uuid
  title       String?
  workspaceId String   @db.Uuid
  userId      String   @db.Uuid
  createdAt   DateTime @default(now()) @db.Timestamp(6)
  updatedAt   DateTime @updatedAt @db.Timestamp(6)
  isArchived  Boolean  @default(false)

  workspace workspace     @relation(...)
  user      user          @relation(...)
  messages  allyMessage[]

  @@index([workspaceId, userId])
  @@index([workspaceId, createdAt(sort: Desc)])
  @@index([userId, createdAt(sort: Desc)])
}

model allyMessage {
  id             String          @id @default(uuid()) @db.Uuid
  conversationId String          @db.Uuid
  role           AllyMessageRole  # USER | ASSISTANT | TOOL
  content        String
  toolCalls      Json?           @db.Json
  createdAt      DateTime        @default(now()) @db.Timestamp(6)

  conversation allyConversation @relation(...)

  @@index([conversationId, createdAt])
}

enum AllyMessageRole {
  USER
  ASSISTANT
  TOOL
}
```

### Custom Instructions Schema

```prisma
model workspaceCustomInstructions {
  id           String   @id @default(uuid()) @db.Uuid
  workspaceId  String   @unique @db.Uuid
  instructions String   @db.Text
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  updatedBy    String   @db.Uuid

  workspace    workspace @relation(...)
  updatedUser  user      @relation("customInstructionsUpdatedBy")
}

model groupCustomInstructions {
  id           String   @id @default(uuid()) @db.Uuid
  groupId      String   @unique @db.Uuid
  instructions String   @db.Text
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  updatedBy    String   @db.Uuid

  group        group @relation(...)
  updatedUser  user  @relation("groupCustomInstructionsUpdatedBy")
}

model entityCustomInstructions {
  id                 String     @id @default(uuid()) @db.Uuid
  workspaceId        String     @db.Uuid
  entityType         EntityType  # PERSON | COMPANY | OBJECT
  objectDefinitionId String?    @db.Uuid   # Only for OBJECT type
  instructions       String     @db.Text
  createdAt          DateTime   @default(now())
  updatedAt          DateTime   @updatedAt
  updatedBy          String     @db.Uuid

  workspace          workspace  @relation(...)
  objectDefinition   objectDefinition? @relation(...)
  updatedUser        user       @relation("entityCustomInstructionsUpdatedBy")

  @@unique([workspaceId, entityType, objectDefinitionId])
}
```

---

## Data Flow

### Chat Message Flow

```
1. User types message in AllyChatInput
2. AllyContext calls sendMessage()
3. Message saved to backend via saveAllyMessage() server action
4. POST request to /api/v1/chat (proxied to Ally Python service)
5. Ally resolves in parallel: user profile, workspace instructions, group instructions
6. Agent created with personalized system prompt
7. Ally returns SSE stream with events:
   - thinking: Heartbeat events every 1.5s ("Thinking...", "Analyzing results...")
   - response: Text content streamed in real-time
   - tool_call: Tool execution announced
   - tool_result: Tool result returned
   - data_changed: Cache invalidation triggered
   - confirmation_required: Pauses stream, waits for user
   - conversation_title: Auto-generated title (first message only)
   - done: Stream complete, message saved
8. AllyChatMessages renders final message with markdown formatting
```

### Confirmation Flow

```
1. Ally SSE emits confirmation_required event
2. AllyContext extracts ConfirmationRequest
3. AllyConfirmation component renders based on type
4. User selects option, edits data, or provides feedback
5. AllyContext.sendConfirmation() sends to /api/v1/chat/confirm
6. Ally resumes execution with SSE stream
7. Process can repeat (nested confirmations supported)
```

### Data Invalidation Flow

```
1. Ally creates/updates/deletes entity, emits data_changed event
2. AllyContext collects changes in dataChangesRef
3. On done event, invalidateByChanges() is called
4. useAllyDataInvalidator deduplicates changes per entity type:
   - Person: invalidates people-infinite, pipeline-data, person-profile
   - Company: invalidates companies-infinite, pipeline-data, company-profile
   - Group: invalidates user-groups, triggers server-side revalidation
   - View: invalidates user-views, user-groups
5. Affected UI components refetch and re-render
```

### Conversation Title Flow

```
1. User sends first message in a new conversation
2. After agent completes response, is_first_message() returns true
3. generate_conversation_title() uses LLM to create 2-6 word summary
4. SSE emits conversation_title event with { title, conversation_id }
5. Frontend updates conversation name in sidebar
```

---

## SSE Event Types

| Event | Description | Data |
|-------|-------------|------|
| `thinking` | Agent reasoning / heartbeat | `{ content: string }` |
| `tool_call` | Tool execution initiated | `{ name: string, args: object }` |
| `tool_result` | Tool result received | `{ name: string, result: string }` |
| `response` | Streaming text content | `{ content: string }` |
| `confirmation_required` | Pauses for user | `ConfirmationRequest` |
| `data_changed` | Cache invalidation | `{ entityType, action, entityId }` |
| `conversation_title` | Auto-generated title | `{ title: string, conversation_id: string }` |
| `error` | Error occurred | `{ message: string }` |
| `done` | Stream complete | `{}` |

---

## Confirmation System

### Confirmation Types

| Type | Use Case | UI |
|------|----------|-----|
| `confirm_action` | Simple yes/no | Confirm/Cancel buttons |
| `select_one` | Disambiguation | Radio buttons with confidence badges |
| `select_many` | Multiple selection | Checkboxes |
| `confirm_with_edit` | Review before create/update | Editable form fields with status change preview |

### Enhanced Features

- **Status change visualization**: Shows current → new value with color-coded styling
- **Edit mode**: Users can modify draft data fields inline before confirming
- **Feedback collection**: Optional textarea when user cancels an operation
- **Confidence badges**: High/Medium/Low match indicators for disambiguation
- **Entity type icons**: Visual chips for Person, Company, Group, View
- **Custom action labels**: Confirm button text customizable per operation

### Confirmation Helper Functions (`src/tools/confirmation.py`)

```python
# Specialized helpers for common patterns
request_create_confirmation(title, message, entity_type, draft_data)
request_update_confirmation(title, message, entity_type, draft_data)
request_delete_confirmation(title, message, entity_type)
request_column_update_confirmation(title, message, entity_type, old_value, new_value)
request_entity_selection(title, message, options)
```

### Workflow

```python
# In tool code (ally repo)
from src.tools.confirmation import request_confirmation, ConfirmationType

result = request_confirmation(
    confirmation_type=ConfirmationType.CONFIRM_ACTION,
    title="Create Company",
    message="Create company 'Acme Corp'?",
    entity_type="company",
    draft_data={"name": "Acme Corp", "website": "acme.com"}
)

if result.confirmed:
    # Proceed with creation
else:
    # Handle cancellation (result.feedback may contain user's reason)
```

---

## Tool System

### Tool Categories

| Category | File | Tools |
|----------|------|-------|
| **Read** | `read_tools.py` | `list_companies`, `list_people`, `list_groups`, `get_company_details`, `get_person_details`, `resolve_company_name`, `resolve_person_name`, `get_current_page` |
| **Create** | `create_tools.py` | `create_company`, `create_person`, `create_group`, `create_view` |
| **Update** | `update_tools.py` | `update_company`, `update_person`, `update_column_value`, `add_to_group`, `remove_from_group` |
| **Research** | `research_tools.py` | `web_search` (Perplexity API) |
| **Context** | `context_tools.py` | `get_entity_instructions` |
| **Notes** | `note_tools.py` | `create_note`, `list_notes`, `get_note`, `update_note`, `delete_note` |
| **Reminders** | `reminder_tools.py` | `create_reminder`, `list_reminders`, `get_reminder`, `update_reminder`, `delete_reminder` |

### Tool Grouping (Frontend)

The frontend categorizes tools for display:
- **INTERNAL_TOOLS** (~18 tools): Lookup/query tools hidden by default (e.g., `resolve_company_name`, `list_people`)
- **ACTION_TOOLS** (~16 tools): User-facing tools shown prominently (e.g., `create_company`, `update_person`)

### Fuzzy Matching (`base.py`)

The tools use advanced fuzzy matching for name resolution:
- Handles typos, partial names, word reordering
- Multiple algorithms: token sort, token set, partial, standard
- Returns confidence scores (high/medium/low)
- Used in `resolve_company_name`, `resolve_person_name`, `resolve_group_name`

---

## Custom Instructions System

A 3-level hierarchy for customizing the AI agent's behavior:

### Levels

| Level | Scope | Max Length | Description |
|-------|-------|-----------|-------------|
| **Workspace** | All conversations in workspace | 8000 chars | Global AI guidance set by admins |
| **Group** | Conversations within a specific group | 8000 chars | Group-specific AI behavior |
| **Entity** | Per entity type (Person, Company, Custom Object) | 8000 chars | Entity-type-specific handling |

### How It Works

1. **Workspace instructions** are fetched when any chat starts and injected into the system prompt
2. **Group instructions** are fetched when the user is viewing a group page (detected from active URL)
3. **Entity instructions** are fetched on-demand via the `get_entity_instructions` tool when the agent operates on specific entity types
4. All instructions have audit trails (`updatedBy` tracks who last modified them)

---

## Key Files Reference

### Ally Repo (Python)

| File | Purpose |
|------|---------|
| `src/agent/graph.py` | LangGraph agent with streaming, title generation, heartbeats |
| `src/agent/prompts.py` | System prompts with workspace/group/entity context |
| `src/api/routes.py` | FastAPI endpoints with parallel context resolution |
| `src/tools/read_tools.py` | Read/search/resolve tools |
| `src/tools/update_tools.py` | Update/modify tools |
| `src/tools/create_tools.py` | Create entity tools |
| `src/tools/note_tools.py` | Note CRUD tools |
| `src/tools/reminder_tools.py` | Reminder CRUD tools |
| `src/tools/context_tools.py` | Entity instructions retrieval |
| `src/tools/base.py` | Fuzzy matching, ToolContext, data change tracking |
| `src/tools/confirmation.py` | Confirmation framework with specialized helpers |
| `src/graphql/client.py` | GraphQL client with profile/instructions methods |

### Frontend Repo (TypeScript)

| File | Purpose |
|------|---------|
| `components/ally/AllyChat.tsx` | Main chat container with history/search/rename/delete |
| `components/ally/AllyChatMessages.tsx` | Message rendering with tool grouping and markdown |
| `components/ally/AllyConfirmation.tsx` | Confirmation with edit mode, feedback, status changes |
| `components/ally/AllyChatInput.tsx` | Auto-resizing message input |
| `components/layout/ally-aware-main.tsx` | Layout wrapper for Ally panel |
| `contexts/ally-context.tsx` | Chat state management + SSE streaming engine |
| `hooks/ally/use-ally-chat.ts` | Thin wrapper around AllyContext |
| `hooks/ally/use-ally-data-invalidator.ts` | Per-entity-type React Query cache invalidation |
| `lib/actions/ally.actions.ts` | Server actions with Zod validation |
| `lib/types/ally.ts` | Extended types (CreatedEntity, ToolCall, Message) |
| `types/ally-confirmation.ts` | Confirmation types + entity/confidence configs |
| `app/api/v1/chat/route.ts` | SSE proxy endpoint |
| `app/api/v1/chat/confirm/route.ts` | Confirmation proxy endpoint |

### Backend Repo (TypeScript)

| File | Purpose |
|------|---------|
| `apps/api/src/ally/ally.resolver.ts` | Conversation GraphQL endpoints |
| `apps/api/src/ally/ally.service.ts` | Conversation business logic |
| `apps/api/src/ally/models/conversation.model.ts` | Conversation GraphQL models |
| `apps/api/src/ally/dto/conversation.input.ts` | Conversation input DTOs |
| `apps/api/src/workspace/workspace.resolver.ts` | Workspace + entity instructions endpoints |
| `apps/api/src/workspace/models/custom-instructions.model.ts` | Workspace instructions model |
| `apps/api/src/workspace/models/entity-custom-instructions.model.ts` | Entity instructions model |
| `apps/api/src/group/group/Group.ts` | Group instructions endpoints |
| `apps/api/src/group/group/models/group-custom-instructions.model.ts` | Group instructions model |
| `libs/prisma-schema/prisma/schema.prisma` | Database schema |

---

## Quick Start for Development

### Running Locally

1. **Backend** (NestJS):
   ```bash
   cd backend
   pnpm install
   pnpm run start:dev
   ```

2. **Ally Agent** (Python):
   ```bash
   cd ally
   pip install -r requirements.txt
   python -m src.main
   # Or with Docker:
   docker-compose up
   ```

3. **Frontend** (Next.js):
   ```bash
   cd frontend
   pnpm install
   pnpm run dev
   ```

### Testing Chat Flow

1. Open the frontend at `http://localhost:3000`
2. Open the Ally chat from the sidebar
3. Send a message like "List all companies"
4. Watch the streaming response and tool calls

---

## Common Tasks

### Adding a New Tool

1. Create tool function in `ally/src/tools/` (appropriate category file)
2. Add to `__init__.py` exports
3. Tool will be automatically available to the agent

### Modifying System Prompt

Edit `ally/src/agent/prompts.py` - the `get_system_prompt()` function

### Adding New Confirmation Type

1. Add type to `ConfirmationType` enum in `ally/src/tools/confirmation.py`
2. Handle in `AllyConfirmation.tsx` frontend component

### Managing Custom Instructions

- **Workspace**: Use `updateWorkspaceCustomInstructions` / `deleteWorkspaceCustomInstructions` mutations
- **Group**: Use `updateGroupCustomInstructions` / `deleteGroupCustomInstructions` mutations
- **Entity**: Use `upsertEntityCustomInstructions` / `deleteEntityCustomInstructions` mutations

### Debugging SSE Stream

Check browser Network tab for `/api/v1/chat` request, view EventStream tab

---

*Last updated: February 2026*
