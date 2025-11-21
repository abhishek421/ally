# API Contracts

This document defines the API contracts for the Analyst AI application.

## Overview

The API follows RESTful principles and uses JSON for data exchange. 
For streaming responses (Query API), Server-Sent Events (SSE) are used.

### Authentication

Most endpoints require the following headers:

| Header | Description | Required |
|--------|-------------|----------|
| `Authorization` | Bearer token from AWS Cognito | Yes (except health checks) |
| `X-Workspace-ID` | Workspace identifier | Yes (except health checks) |

---

## Endpoints

### 1. Conversations

#### List Conversations

Retrieve a paginated list of conversations for the current user and workspace.

*   **Endpoint**: `GET /conversations`
*   **Headers**: `X-Workspace-ID`, `Authorization`
*   **Query Parameters**:
    *   `limit` (int, default=50): Number of conversations to return (1-100).
    *   `offset` (int, default=0): Number of conversations to skip.

**Response (200 OK)**

```json
{
  "success": true,
  "conversations": [
    {
      "id": "uuid",
      "workspaceId": "uuid",
      "userId": "uuid",
      "title": "string",
      "createdAt": "timestamp",
      "updatedAt": "timestamp"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### Get Conversation

Get details of a specific conversation.

*   **Endpoint**: `GET /conversations/{conversation_id}`
*   **Headers**: `X-Workspace-ID`, `Authorization`
*   **Path Parameters**:
    *   `conversation_id` (str): UUID of the conversation.

**Response (200 OK)**

```json
{
  "success": true,
  "conversation": {
    "id": "uuid",
    "workspace_id": "uuid",
    "user_id": "uuid",
    "title": "string",
    "created_at": "timestamp",
    "updated_at": "timestamp"
  },
  "message_count": 10
}
```

#### Get Conversation Messages

Get messages for a conversation, including their content blocks.

*   **Endpoint**: `GET /conversations/{conversation_id}/messages`
*   **Headers**: `X-Workspace-ID`, `Authorization`
*   **Path Parameters**:
    *   `conversation_id` (str): UUID of the conversation.
*   **Query Parameters**:
    *   `limit` (int, default=100): Number of messages to return (1-500).
    *   `offset` (int, default=0): Number of messages to skip.

**Response (200 OK)**

```json
{
  "success": true,
  "conversation_id": "uuid",
  "messages": [
    {
      "id": "uuid",
      "role": "USER|ASSISTANT",
      "timestamp": "timestamp",
      "blocks": [
        {
          "block_id": "uuid",
          "block_type": "TEXT|TABLE|THINKING|ENTITY_LIST|ENTITY_CARD|INSIGHT_WIDGET",
          "content": "string",
          "order": 0,
          "metadata": {},
          "entity_mentions": [],
          "created_at": "timestamp"
        }
      ]
    }
  ],
  "total": 50,
  "limit": 100,
  "offset": 0
}
```

#### Delete Conversation

Delete a conversation and all its associated messages.

*   **Endpoint**: `DELETE /conversations/{conversation_id}`
*   **Headers**: `X-Workspace-ID`, `Authorization`
*   **Path Parameters**:
    *   `conversation_id` (str): UUID of the conversation.

**Response (200 OK)**

```json
{
  "success": true,
  "message": "Conversation deleted"
}
```

---

### 2. Query

#### Process Query

Process a natural language query. This endpoint streams the response using Server-Sent Events (SSE).

*   **Endpoint**: `POST /query`
*   **Headers**: `X-Workspace-ID`, `Authorization`
*   **Request Body**: `QueryRequest`

**Request Body Schema**

```json
{
  "query": "Show me revenue for Q1 for @Microsoft",
  "conversation_id": "optional-uuid",
  "entity_mentions": [
    {
      "entityId": "uuid",
      "entityType": "company|person|email|group|interaction",
      "name": "@Microsoft",
      "span": {
        "start": 27,
        "end": 37
      }
    }
  ]
}
```

**Response (Streaming SSE)**

The response is a stream of JSON objects, each prefixed with `data: `.

**Event Types:**

1.  **message_start**
    ```json
    {
      "type": "message_start",
      "message_id": "uuid",
      "conversation_id": "uuid"
    }
    ```

2.  **block_start**
    ```json
    {
      "type": "block_start",
      "block_id": "uuid",
      "block_type": "TEXT|TABLE|THINKING...",
      "order": 0,
      "metadata": {}, 
      "entity_mentions": []
    }
    ```

3.  **block_delta** (Streaming content updates)
    ```json
    {
      "type": "block_delta",
      "block_id": "uuid",
      "content": "partial content..."
    }
    ```

4.  **block_complete**
    ```json
    {
      "type": "block_complete",
      "block_id": "uuid",
      "block_type": "TEXT|TABLE|THINKING...",
      "content": "full content",
      "order": 0,
      "metadata": {},
      "entity_mentions": []
    }
    ```

5.  **message_complete**
    ```json
    {
      "type": "message_complete",
      "message_id": "uuid",
      "blocks_count": 5
    }
    ```

6.  **error**
    ```json
    {
      "type": "error",
      "error": "Error message",
      "error_code": "CODE"
    }
    ```

---

### 3. Health & System

#### Health Check

Basic liveness probe.

*   **Endpoint**: `GET /health`
*   **Authentication**: None

**Response (200 OK)**

```json
{
  "status": "healthy",
  "timestamp": "iso-timestamp"
}
```

#### Readiness Check

Verifies database and configuration dependencies.

*   **Endpoint**: `GET /ready`
*   **Authentication**: None

**Response (200 OK)**

```json
{
  "status": "ready|not_ready",
  "services": {
    "database": "ready|not_ready",
    "config_manager": "ready|not_ready"
  },
  "timestamp": "iso-timestamp"
}
```

---

## Schemas

### QueryRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Natural language query (1-2000 chars) |
| `conversation_id` | string | No | UUID of existing conversation |
| `entity_mentions` | `EntityMention[]` | No | List of entities mentioned in the query |

### EntityMention

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entityId` | string | Yes | Entity UUID |
| `entityType` | string | Yes | company, person, email, group, interaction |
| `name` | string | Yes | Display name |
| `span` | `EntityMentionSpan` | Yes | Character span in text |

### EntityMentionSpan

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start` | int | Yes | Start index |
| `end` | int | Yes | End index |

### BlockType (Enum)

*   `TEXT`: Standard text response
*   `TABLE`: Structured table data
*   `THINKING`: Internal thought process (CoT)
*   `ENTITY_LIST`: List of entities
*   `ENTITY_CARD`: Detailed entity view
*   `INSIGHT_WIDGET`: Chart or visualization

### Conversation

| Field | Type | Description |
|---|---|---|
| `id` | string | Conversation UUID |
| `workspace_id` | string | Workspace UUID |
| `user_id` | string | User UUID |
| `title` | string | Conversation title (optional) |
| `created_at` | string | ISO timestamp |
| `updated_at` | string | ISO timestamp |

### Message

| Field | Type | Description |
|---|---|---|
| `id` | string | Message UUID |
| `role` | string | USER or ASSISTANT |
| `timestamp` | string | ISO timestamp |
| `blocks` | `MessageBlock[]` | List of content blocks |

### MessageBlock

| Field | Type | Description |
|---|---|---|
| `block_id` | string | Block UUID |
| `block_type` | `BlockType` | Type of content block |
| `content` | string | Text content or stringified JSON |
| `order` | int | Display order within message |
| `metadata` | object | Optional metadata dictionary |
| `entity_mentions` | `EntityMention[]` | List of entities mentioned in this block |
| `created_at` | string | ISO timestamp |
