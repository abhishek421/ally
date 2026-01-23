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
- [Key Files Reference](#key-files-reference)

---

## Architecture Overview

The Ally Chat feature is a **3-tier AI-powered CRM assistant** with:

- **Streaming responses** via Server-Sent Events (SSE)
- **Human-in-the-loop confirmations** for sensitive operations
- **Intelligent tool execution** for CRM operations
- **Multi-LLM support** (OpenAI, Anthropic, Gemini)
- **Conversation persistence** with PostgreSQL

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │     │   Ally Agent    │     │    Backend      │
│   (Next.js)     │────▶│   (Python)      │────▶│   (NestJS)      │
│                 │◀────│   LangGraph     │◀────│   GraphQL       │
└─────────────────┘ SSE └─────────────────┘     └─────────────────┘
```

---

## Repository Structure

| Repo | Tech Stack | Purpose |
|------|------------|---------|
| `ally` | Python, FastAPI, LangGraph | AI Agent service with tool execution |
| `frontend` | Next.js, React, TypeScript | Chat UI components and state management |
| `backend` | NestJS, GraphQL, Prisma | Conversation persistence and CRM data |

---

## 1. Ally Repo - LangGraph AI Agent (Python)

The core AI service that processes user messages and executes CRM operations.

### Technology Stack

- **Framework**: FastAPI with async/streaming support
- **AI/Orchestration**: LangGraph (ReAct pattern agent) + LangChain
- **LLM Support**: OpenAI (GPT-4), Anthropic (Claude), Google Gemini
- **Backend Communication**: GraphQL API client
- **Database**: PostgreSQL (for LangGraph conversation persistence)
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

#### Agent Graph (`src/agent/graph.py`)

- **`stream_agent()`** - Processes user messages through LangGraph ReAct agent
- **`resume_agent()`** - Continues execution after user confirmation
- Handles tool calls, results, and responses
- Can pause for user confirmation via `interrupt()`
- Automatically generates conversation titles on first message

#### Agent State (`src/agent/state.py`)

```python
class AgentState:
    messages: Annotated[list, add_messages]  # Accumulated messages
    workspace_id: str                         # CRM workspace context
    user_id: str                              # Authenticated user
    auth_token: str                           # For GraphQL calls
```

#### System Prompts (`src/agent/prompts.py`)

The agent uses a comprehensive system prompt that includes:
- **Base Instructions**: CRM operations, data management, reasoning patterns
- **Workspace Context**: Custom instructions set by workspace admins
- **User Personalization**: User's first name, greeting behavior
- **Tool Guidance**: Smart name resolution, human-in-the-loop workflows
- **Privacy & Ethics**: Data protection, user permissions

### Environment Variables

```bash
LLM_PROVIDER=openai|anthropic|gemini
LLM_MODEL=gpt-4o|claude-3-opus|gemini-pro
BACKEND_GRAPHQL_URL=http://localhost:3000/graphql
DATABASE_URL_ALLY=postgresql://...
PERPLEXITY_API_KEY=REDACTED
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
│   ├── AllyChat.tsx              # Main chat container
│   ├── AllyChatInput.tsx         # Message input field
│   ├── AllyChatMessages.tsx      # Message rendering with tool calls
│   ├── AllyChatButton.tsx        # Floating action button
│   ├── AllyConfirmation.tsx      # Confirmation dialog
│   └── index.ts                  # Component exports
├── contexts/
│   └── ally-context.tsx          # Chat state management
├── hooks/ally/
│   ├── use-ally-chat.ts          # Core chat logic hook
│   ├── use-conversations.ts      # Conversation list fetching
│   ├── use-conversation.ts       # Single conversation fetching
│   └── use-ally-data-invalidator.ts  # Cache invalidation
├── lib/
│   ├── actions/ally.actions.ts   # Server actions (mutations)
│   └── data/ally/
│       ├── get-conversations.ts  # List conversations
│       └── get-conversation.ts   # Get single conversation
├── app/api/v1/
│   └── chat/
│       ├── route.ts              # Chat proxy endpoint
│       └── confirm/route.ts      # Confirmation proxy endpoint
└── types/
    └── ally-confirmation.ts      # TypeScript types
```

### Key Components

#### AllyChat.tsx - Main Chat Container
- Orchestrates the entire chat interface
- Displays conversation history and current messages
- Manages conversation switching via history sidebar
- Shows empty state with quick action suggestions

#### AllyChatInput.tsx - Message Input
- Auto-resizing textarea (max 100px height)
- Send on Enter (Shift+Enter for newline)
- Cancel button during streaming

#### AllyChatMessages.tsx - Message Rendering
- User messages (right-aligned, primary color)
- Assistant messages (left-aligned, with Ally avatar)
- Markdown rendering with GitHub-flavored markdown
- Tool call visualization with collapsible groups
- Status indicators (completed, in-progress, failed)
- Emoji status icons (➕ add, ✏️ update, 🔍 search, ➖ remove)

#### AllyConfirmation.tsx - Confirmation Dialog
- `select_one` - Radio buttons for disambiguation
- `confirm_action` - Simple yes/no confirmation
- `confirm_with_edit` - Review and edit data before confirming
- Entity type icons and styling
- Confidence badges (High/Medium/Low)

### State Management

### Architecture: Context-Based State Persistence

**Important**: All chat state is managed in `AllyContext` (at the root layout level), not in the `useAllyChat` hook. This ensures:

- **Chat survives popup close/open**: State persists when user closes and reopens the chat popup
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

  // Actions
  sendMessage(content: string): Promise<void>
  sendConfirmation(response: ConfirmationResponsePayload): Promise<void>
  cancel(): void
  clearMessages(): void
  loadMessages(messages: ChatMessage[]): void
}
```

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

### TypeScript Types (`types/ally-confirmation.ts`)

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
  allow_cancel_feedback: boolean
  entity_type?: "person" | "company" | "group" | "view"
}

interface ConfirmationResponsePayload {
  confirmed: boolean
  selected_id?: string
  selected_ids?: string[]
  feedback?: string
}
```

---

## 3. Backend Repo - NestJS GraphQL API

Conversation persistence layer using GraphQL and Prisma.

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
└── libs/prisma-schema/prisma/
    └── schema.prisma             # Database models
```

### GraphQL Endpoints (`ally.resolver.ts`)

#### Queries
- `getAllyConversations` - Paginated list of user's conversations
- `getAllyConversation` - Single conversation with all messages
- `getAllyMessages` - Messages for a conversation with pagination

#### Mutations
- `createAllyConversation` - Create new conversation
- `updateAllyConversation` - Update title or archive status
- `deleteAllyConversation` - Delete conversation and messages
- `saveAllyMessage` - Save message to conversation

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

### Workspace Custom Instructions

```prisma
model workspaceCustomInstructions {
  id           String   @id @default(uuid()) @db.Uuid
  workspaceId  String   @unique @db.Uuid
  instructions String   @db.Text
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  updatedBy    String   @db.Uuid
}
```

---

## Data Flow

### Chat Message Flow

```
1. User types message in AllyChatInput
2. useAllyChat hook calls sendMessage()
3. Message saved to backend via saveAllyMessage() server action
4. POST request to /api/v1/chat (proxied to Ally Python service)
5. Ally returns SSE stream with events:
   - response: Text content streamed in real-time
   - tool_call: Tool execution announced
   - tool_result: Tool result returned
   - data_changed: Cache invalidation triggered
   - confirmation_required: Pauses stream, waits for user
   - done: Stream complete, message saved
6. AllyChatMessages renders final message with formatting
```

### Confirmation Flow

```
1. Ally SSE emits confirmation_required event
2. useAllyChat extracts ConfirmationRequest
3. AllyConfirmation component renders based on type
4. User selects option or edits data
5. useAllyChat.sendConfirmation() sends to /api/v1/chat/confirm
6. Ally resumes execution with SSE stream
7. Process repeats until completion
```

### Data Invalidation Flow

```
1. Ally creates/updates/deletes entity, emits data_changed event
2. useAllyChat collects changes in dataChangesRef
3. On done event, invalidateByChanges() is called
4. Hook deduplicates changes and invalidates React Query caches
5. Affected UI components refetch and re-render
```

---

## SSE Event Types

| Event | Description | Data |
|-------|-------------|------|
| `thinking` | Agent reasoning | `{ content: string }` |
| `tool_call` | Tool execution initiated | `{ name: string, args: object }` |
| `tool_result` | Tool result received | `{ name: string, result: string }` |
| `response` | Streaming text content | `{ content: string }` |
| `confirmation_required` | Pauses for user | `ConfirmationRequest` |
| `data_changed` | Cache invalidation | `{ entityType, action, entityId }` |
| `error` | Error occurred | `{ message: string }` |
| `done` | Stream complete | `{}` |

---

## Confirmation System

### Confirmation Types

| Type | Use Case | UI |
|------|----------|-----|
| `confirm_action` | Simple yes/no | Confirm/Cancel buttons |
| `select_one` | Disambiguation | Radio buttons |
| `select_many` | Multiple selection | Checkboxes |
| `confirm_with_edit` | Review before create | Editable form fields |

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
    # Handle cancellation
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

### Fuzzy Matching (`base.py`)

The tools use advanced fuzzy matching for name resolution:
- Handles typos, partial names, word reordering
- Multiple algorithms: token sort, token set, partial, standard
- Returns confidence scores (high/medium/low)
- Used in `resolve_company_name`, `resolve_person_name`, `resolve_group_name`

---

## Key Files Reference

### Ally Repo (Python)

| File | Lines | Purpose |
|------|-------|---------|
| `src/agent/graph.py` | ~300 | LangGraph agent with streaming |
| `src/agent/prompts.py` | ~200 | System prompts |
| `src/api/routes.py` | ~150 | FastAPI endpoints |
| `src/tools/read_tools.py` | ~1,793 | Read/search/resolve tools |
| `src/tools/update_tools.py` | ~1,474 | Update/modify tools |
| `src/tools/create_tools.py` | ~487 | Create entity tools |
| `src/tools/base.py` | ~428 | Fuzzy matching, base classes |
| `src/tools/confirmation.py` | ~200 | Confirmation framework |

### Frontend Repo (TypeScript)

| File | Purpose |
|------|---------|
| `components/ally/AllyChat.tsx` | Main chat container |
| `components/ally/AllyChatMessages.tsx` | Message rendering |
| `components/ally/AllyConfirmation.tsx` | Confirmation dialog |
| `hooks/ally/use-ally-chat.ts` | Core chat logic |
| `hooks/ally/use-ally-data-invalidator.ts` | Cache invalidation |
| `app/api/v1/chat/route.ts` | SSE proxy endpoint |
| `types/ally-confirmation.ts` | TypeScript types |

### Backend Repo (TypeScript)

| File | Purpose |
|------|---------|
| `apps/api/src/ally/ally.resolver.ts` | GraphQL endpoints |
| `apps/api/src/ally/ally.service.ts` | Business logic |
| `apps/api/src/ally/models/conversation.model.ts` | GraphQL models |
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
2. Click the Ally chat button (bottom-right)
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

### Debugging SSE Stream

Check browser Network tab for `/api/v1/chat` request, view EventStream tab

---

*Last updated: January 2025*
