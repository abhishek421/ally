# AnalystAI API Documentation

## Overview

The AnalystAI API provides REST endpoints for interacting with the LangGraph-based CRM analysis pipeline. The API supports both synchronous and streaming responses.

**Base URL:** `http://localhost:8000/api/v1`

**API Version:** 1.0.0

## Authentication

All endpoints require authentication via request body fields:
- `workspace_id` - Workspace identifier
- `user_id` - User identifier  
- `conversation_id` - Conversation identifier

These fields are passed in the request body (not headers) and are used to maintain conversation context and workspace isolation.

---

## Endpoints

### 1. Health Check

Check the health status of the API server.

**Endpoint:** `GET /api/v1/health`

**Request:** No request body required

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

**Example - cURL:**
```bash
curl http://localhost:8000/api/v1/health
```

**Example - Python:**
```python
import requests

response = requests.get("http://localhost:8000/api/v1/health")
print(response.json())
# Output: {"status": "healthy", "version": "1.0.0"}
```

**Example - JavaScript:**
```javascript
fetch('http://localhost:8000/api/v1/health')
  .then(response => response.json())
  .then(data => console.log(data));
```

---

### 2. Chat (Non-Streaming)

Process a query and return the complete response.

**Endpoint:** `POST /api/v1/chat`

**Request Body:**
```json
{
  "query": "How many people are in my workspace?",
  "workspace_id": "workspace-123",
  "user_id": "user-456",
  "conversation_id": "conv-789"
}
```

**Response:**
```json
{
  "answer": "Based on the workspace data, there are 42 people in your workspace.",
  "conversation_id": "conv-789",
  "metadata": {
    "iterations": 3,
    "tools_used": ["search_people", "get_workspace_summary"],
    "timestamp": null
  },
  "tool_calls": [
    {
      "tool": "search_people",
      "params": {"workspace_id": "workspace-123", "limit": 20},
      "result": "...",
      "iteration": 1
    }
  ],
  "reasoning_steps": [
    "I need to search for people in the workspace...",
    "Let me use the search_people tool...",
    "Based on the results, I can now provide an answer."
  ]
}
```

**Example - cURL:**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many people are in my workspace?",
    "workspace_id": "workspace-123",
    "user_id": "user-456",
    "conversation_id": "conv-789"
  }'
```

**Example - Python:**
```python
import requests
import json

url = "http://localhost:8000/api/v1/chat"
payload = {
    "query": "How many people are in my workspace?",
    "workspace_id": "workspace-123",
    "user_id": "user-456",
    "conversation_id": "conv-789"
}

response = requests.post(url, json=payload)
result = response.json()

print(f"Answer: {result['answer']}")
print(f"Tool calls: {len(result['tool_calls'])}")
print(f"Reasoning steps: {len(result['reasoning_steps'])}")
```

**Example - JavaScript:**
```javascript
fetch('http://localhost:8000/api/v1/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: "How many people are in my workspace?",
    workspace_id: "workspace-123",
    user_id: "user-456",
    conversation_id: "conv-789"
  })
})
.then(response => response.json())
.then(data => {
  console.log('Answer:', data.answer);
  console.log('Tool calls:', data.tool_calls);
  console.log('Reasoning steps:', data.reasoning_steps);
});
```

---

### 3. Chat Stream (Streaming)

Process a query and stream the response in real-time using Server-Sent Events (SSE).

**Endpoint:** `POST /api/v1/chat/stream`

**Request Body:**
```json
{
  "query": "How many people are in my workspace?",
  "workspace_id": "workspace-123",
  "user_id": "user-456",
  "conversation_id": "conv-789"
}
```

**Response Format:** Server-Sent Events (SSE)

Each event follows this format:
```
event: <chunk_type>
data: {"type": "<chunk_type>", "content": "...", "data": {...}}
```

**Stream Chunk Types:**
- `token` - Answer text tokens (streamed character by character)
- `reasoning` - Reasoning steps from the ReAct loop
- `tool_call` - Tool execution notifications with tool data
- `metadata` - General metadata updates
- `error` - Error messages
- `done` - Stream completion signal

**Example Stream:**
```
event: reasoning
data: {"type": "reasoning", "content": "I need to search for people in the workspace..."}

event: tool_call
data: {"type": "tool_call", "content": "Tool search_people called", "data": {"tool": "search_people", "params": {...}}}

event: token
data: {"type": "token", "content": "B"}

event: token
data: {"type": "token", "content": "a"}

event: token
data: {"type": "token", "content": "s"}

...

event: done
data: {"type": "done", "content": "", "data": {"metadata": {...}}}
```

**Example - cURL:**
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many people are in my workspace?",
    "workspace_id": "workspace-123",
    "user_id": "user-456",
    "conversation_id": "conv-789"
  }' \
  --no-buffer \
  -N
```

**Example - Python (Complete Test Script):**
```python
import requests
import json
import sys

def test_stream_api():
    url = "http://localhost:8000/api/v1/chat/stream"
    
    payload = {
        "query": "How many people are in my workspace?",
        "workspace_id": "test-workspace-123",
        "user_id": "test-user-456",
        "conversation_id": "test-conv-789"
    }
    
    print("Sending request to streaming endpoint...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    print("Streaming response:\n" + "="*50)
    
    try:
        response = requests.post(url, json=payload, stream=True, timeout=60)
        response.raise_for_status()
        
        answer_buffer = ""
        reasoning_count = 0
        tool_call_count = 0
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # Parse SSE format
                if line_str.startswith('event: '):
                    event_type = line_str[7:].strip()
                    continue
                
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        chunk_type = data.get('type')
                        content = data.get('content', '')
                        
                        if chunk_type == 'token':
                            answer_buffer += content
                            print(content, end='', flush=True)
                        
                        elif chunk_type == 'reasoning':
                            reasoning_count += 1
                            print(f"\n\n[Reasoning Step {reasoning_count}]")
                            print(f"{content}\n")
                        
                        elif chunk_type == 'tool_call':
                            tool_call_count += 1
                            tool_data = data.get('data', {})
                            print(f"\n[Tool Call {tool_call_count}] {tool_data.get('tool', 'unknown')}")
                            print(f"Params: {json.dumps(tool_data.get('params', {}), indent=2)}")
                        
                        elif chunk_type == 'metadata':
                            print(f"\n[Metadata] {json.dumps(data.get('data', {}), indent=2)}")
                        
                        elif chunk_type == 'error':
                            print(f"\n[ERROR] {content}")
                            sys.exit(1)
                        
                        elif chunk_type == 'done':
                            print(f"\n\n{'='*50}")
                            print(f"Stream Complete!")
                            print(f"Total reasoning steps: {reasoning_count}")
                            print(f"Total tool calls: {tool_call_count}")
                            print(f"Answer length: {len(answer_buffer)} characters")
                            break
                    
                    except json.JSONDecodeError as e:
                        print(f"\n[Parse Error] Failed to parse: {line_str[:50]}...")
                        print(f"Error: {e}")
        
        print(f"\n\nFinal Answer:\n{answer_buffer}")
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_stream_api()
```

**Example - Python (Simple):**
```python
import requests
import json

url = "http://localhost:8000/api/v1/chat/stream"
payload = {
    "query": "How many people are in my workspace?",
    "workspace_id": "workspace-123",
    "user_id": "user-456",
    "conversation_id": "conv-789"
}

response = requests.post(url, json=payload, stream=True)

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            data = json.loads(line_str[6:])
            chunk_type = data.get('type')
            content = data.get('content')
            
            if chunk_type == 'token':
                print(content, end='', flush=True)
            elif chunk_type == 'reasoning':
                print(f"\n[Reasoning] {content}")
            elif chunk_type == 'tool_call':
                print(f"\n[Tool Call] {content}")
            elif chunk_type == 'done':
                print("\n[Stream Complete]")
                break
```

**Example - JavaScript:**
```javascript
async function streamChat(query, workspaceId, userId, conversationId) {
  const response = await fetch('http://localhost:8000/api/v1/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: query,
      workspace_id: workspaceId,
      user_id: userId,
      conversation_id: conversationId,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        const chunkType = data.type;
        const content = data.content;

        if (chunkType === 'token') {
          // Append token to answer element
          document.getElementById('answer').textContent += content;
        } else if (chunkType === 'reasoning') {
          console.log('[Reasoning]', content);
        } else if (chunkType === 'tool_call') {
          console.log('[Tool Call]', content, data.data);
        } else if (chunkType === 'done') {
          console.log('[Stream Complete]');
          return;
        }
      }
    }
  }
}

// Usage
streamChat(
  "How many people are in my workspace?",
  "workspace-123",
  "user-456",
  "conv-789"
);
```

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK` - Successful request
- `400 Bad Request` - Invalid request (missing required fields, invalid JSON)
- `500 Internal Server Error` - Server error (graph execution failed, etc.)

**Error Response Format:**
```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

**Example Error Response:**
```json
{
  "error": "Graph execution failed",
  "detail": "Graph execution failed: No query to process"
}
```

---

## Testing

### Quick Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Interactive API Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

You can test all endpoints directly from the Swagger UI interface.

### Running the Server
```bash
python api_server.py
```

Or with uvicorn directly:
```bash
uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000
```

---

## Notes

1. **Conversation Context:** The `conversation_id` is used to maintain conversation history. Use the same `conversation_id` across multiple requests to maintain context.

2. **Workspace Isolation:** The `workspace_id` ensures that all queries and tool calls are scoped to the correct workspace.

3. **Streaming Performance:** The streaming endpoint provides real-time updates but may have slightly higher latency than the non-streaming endpoint due to the streaming overhead.

4. **Timeout:** Streaming requests may take longer to complete. Ensure your client has appropriate timeout settings (recommended: 60+ seconds).

5. **SSE Format:** The streaming endpoint uses Server-Sent Events (SSE) format. Each event contains a type and data payload in JSON format.

