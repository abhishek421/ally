# Ally AI Copilot

A LangGraph-based intelligent assistant for the Allyos CRM application.

## Features

- **ReAct Pattern**: Reasoning before action for thoughtful responses
- **Streaming Responses**: Real-time streaming of thinking steps, tool calls, and final responses
- **Conversation Memory**: PostgreSQL-backed persistence for conversation history
- **CRM Tools**: Read, create, and update companies, people, and groups
- **Multi-LLM Support**: Works with both OpenAI and Anthropic models

## Prerequisites

- Python 3.11+
- PostgreSQL database
- OpenAI API key or Anthropic API key

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e ".[dev]"
```

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# LLM Configuration
# Options: "openai" or "anthropic"
LLM_PROVIDER=openai

# OpenAI API Key (required if LLM_PROVIDER=openai)
OPENAI_API_KEY=REDACTED

# Anthropic API Key (required if LLM_PROVIDER=anthropic)
OPENAI_API_KEY=REDACTED

# Model Configuration
# OpenAI: gpt-4o, gpt-4-turbo, gpt-4o-mini
# Anthropic: claude-3-5-sonnet-latest, claude-3-opus-latest
LLM_MODEL=gpt-4o

# Backend GraphQL Endpoint
BACKEND_GRAPHQL_URL=http://localhost:3000/graphql

# PostgreSQL Database URL (for LangGraph checkpointer)
DATABASE_URL_ALLY=postgresql://postgres:postgres@localhost:5432/allyos

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# AWS Cognito Configuration (for JWT validation)
AWS_COGNITO_REGION=us-east-1
AWS_COGNITO_USER_POOL_ID=your-user-pool-id
AWS_COGNITO_CLIENT_ID=your-client-id
```

## Running the Server

```bash
# Development mode with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### POST /api/v1/chat

Stream a chat message to Ally.

**Headers:**
- `Authorization: Bearer <token>` - JWT token from frontend
- `X-Workspace-ID: <workspace_id>` - Current workspace ID

**Request Body:**
```json
{
  "conversation_id": "uuid",
  "message": "What companies do we have?"
}
```

**Response:** Server-Sent Events (SSE) stream with chunks:
- `thinking` - Agent's reasoning process
- `tool_call` - Tool execution details
- `response` - Final response text
- `error` - Error messages (if any)
- `done` - Stream completion signal

### GET /health

Health check endpoint.

## Architecture

```
src/
├── main.py              # FastAPI entry point
├── config.py            # Environment configuration
├── agent/
│   ├── graph.py         # LangGraph ReAct agent
│   ├── state.py         # Agent state schema
│   └── prompts.py       # System prompts
├── tools/
│   ├── base.py          # Base tool with GraphQL client
│   ├── read_tools.py    # List/Get/Search tools
│   ├── create_tools.py  # Create tools
│   └── update_tools.py  # Update tools
├── graphql/
│   └── client.py        # GraphQL client wrapper
└── api/
    ├── routes.py        # API routes
    └── middleware.py    # Auth middleware
```

## Development

```bash
# Run tests
pytest

# Format code
black src tests

# Lint code
ruff check src tests

# Type check
mypy src
```

