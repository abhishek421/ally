# CRM AI Copilot

An AI-powered conversational assistant for CRM operations built with LangGraph, FastAPI, and multi-provider LLM support. This intelligent agent helps users interact with their CRM data through natural language, performing complex operations like searching, creating, updating, and managing companies, people, groups, and interactions.

## 🚀 Features

- **Natural Language Interface**: Interact with your CRM using plain English
- **Multi-Provider LLM Support**: Mix and match models from OpenAI, Anthropic, and Google
- **Real-time Streaming**: Server-Sent Events (SSE) for progressive feedback
- **Stateful Conversations**: Maintains context across multiple turns
- **Comprehensive CRM Operations**:
  - **Companies**: Search, create, update, delete, manage relationships
  - **People**: Full CRUD operations, relationship management
  - **Groups**: Create and manage groups, membership operations
  - **Interactions**: Notes and emails management
  - **Workspaces**: Access control and member management
- **Intelligent Planning**: Multi-stage pipeline with planning, validation, execution, and aggregation
- **Safety Features**: Confirmation required for destructive operations
- **GraphQL Integration**: Seamless connection to your CRM backend

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## 🏗️ Architecture

The application uses a LangGraph-based agent pipeline that processes user queries through multiple stages:

```
User Input
    ↓
Planner Node (analyzes query, creates execution plan)
    ↓
Validator Node (validates plan, requires confirmation for writes)
    ↓
[Conditional Routing]
    ├─→ Executor Node (executes tools)
    │       ↓
    │   Aggregator Node (normalizes results)
    │       ↓
    └─→ Final Response Node (formats output)
            ↓
        Response to Frontend
```

### Key Components

- **Graph Pipeline**: LangGraph state machine orchestrating the agent workflow
- **Tool Registry**: Collection of async tools for CRM operations
- **Memory Layer**: Redis-backed session storage for conversation continuity
- **LLM Router**: Multi-provider support for OpenAI, Anthropic, and Google models
- **FastAPI Server**: HTTP/SSE endpoints for frontend integration

## 📦 Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Redis** (for session storage)
- **Access to GraphQL CRM Backend API**
- **LLM API Keys** (at least one of: OpenAI, Anthropic, or Google)

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/analyst-ai.git
cd analyst-ai
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

**Using pip:**
```bash
pip install -r requirements.txt
```

**Or using pyproject.toml (recommended):**
```bash
pip install -e .
```

**For development (includes testing tools):**
```bash
pip install -r requirements-dev.txt
# Or: pip install -e ".[dev]"
```

### 4. Configure Environment Variables

Copy the example environment file:
```bash
cp env.example .env
```

Edit `.env` and configure your settings (see [Configuration](#configuration) section below).

### 5. Start Redis

**Using Docker (recommended):**
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

**Or install locally:**

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

### Required Configuration

```bash
# GraphQL Backend
GRAPHQL_ENDPOINT=http://localhost:4000/graphql

# Redis (Session Storage)
REDIS_URL=redis://localhost:6379/0

# LLM Provider (at least one required)
OPENAI_API_KEY=your_openai_api_key_here
# OR
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# OR
GOOGLE_API_KEY=your_google_api_key_here
```

### Optional Configuration

```bash
# Server Configuration
PORT=8000
HOST=0.0.0.0
ENV=development

# Model Configuration
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=2048

# Model Routing (Multi-Provider)
PLANNER_MODEL=gpt-4-turbo-preview
SUMMARY_MODEL=gpt-3.5-turbo
REASONING_MODEL=claude-3-opus-20240229
FALLBACK_MODEL=gemini-pro

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Session
SESSION_TTL_SECONDS=604800  # 7 days
```

See [Multi-Provider Setup Guide](docs/MULTI_PROVIDER_SETUP.md) for detailed LLM configuration.

## 🚀 Running the Application

### Development Mode

**Option 1: Using Python module (recommended for development)**
```bash
python -m src.main
```

**Option 2: Using uvicorn directly**
```bash
uvicorn src.main:app --reload --port 8000
```

The `--reload` flag enables auto-reload on code changes.

### Production Mode

**Single worker:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Multiple workers (recommended for production):**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**With Gunicorn (for better production performance):**
```bash
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Quick Start Checklist

1. ✅ Virtual environment activated
2. ✅ Dependencies installed (`pip install -e .`)
3. ✅ `.env` file configured with required variables
4. ✅ Redis running (`redis-cli ping` returns PONG)
5. ✅ GraphQL endpoint accessible
6. ✅ At least one LLM API key configured
7. ✅ Run: `python -m src.main`

## 📡 API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "service": "CRM AI Copilot"
}
```

### Send Message (Non-Streaming)

```bash
curl -X POST http://localhost:8000/api/message \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "test-1",
    "user_id": "user-1",
    "workspace_id": "ws-1",
    "message": "Find all companies in San Francisco",
  }'
```

### Stream Message (SSE)

```bash
curl -N "http://localhost:8000/api/stream?conversation_id=test-1&user_id=user-1&workspace_id=ws-1&message=Find%20companies"
```

**JavaScript Example:**
```javascript
const eventSource = new EventSource(
  '/api/stream?conversation_id=conv-123&user_id=user-456' +
  '&workspace_id=ws-789&message=Find companies'
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};
```

### Debug Endpoint (Direct Invocation)

```bash
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "test-1",
    "user_id": "user-1",
    "workspace_id": "ws-1",
    "message": "Find all companies"
  }'
```

### API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Project Structure

```
analyst-ai/
│
├── pyproject.toml          # Project configuration and dependencies
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── env.example             # Environment variables template
├── README.md               # This file
│
├── src/
│   ├── main.py             # FastAPI application entrypoint
│   ├── graph.py            # LangGraph pipeline definition
│   │
│   ├── config/
│   │   ├── settings.py     # Application configuration (Pydantic)
│   │   └── logger.py       # Logging configuration
│   │
│   ├── llm/
│   │   ├── model.py        # Multi-provider LLM router
│   │   ├── prompts.py      # LLM prompt templates
│   │   └── reasoning.py    # Reasoning utilities
│   │
│   ├── tools/
│   │   ├── graphql_client.py      # GraphQL client wrapper
│   │   ├── workspace_tools.py      # Workspace operations
│   │   ├── company_tools.py        # Company CRUD operations
│   │   ├── people_tools.py         # People CRUD operations
│   │   ├── group_tools.py          # Group management
│   │   └── interactions_tools.py   # Notes and emails
│   │
│   ├── nodes/
│   │   ├── planner.py      # Query planning node
│   │   ├── validator.py    # Plan validation node
│   │   ├── executor.py     # Tool execution node
│   │   ├── aggregator.py   # Result aggregation node
│   │   └── final_response.py # Response formatting node
│   │
│   ├── memory/
│   │   ├── state.py        # Agent state definition
│   │   ├── session_store.py # Redis session management
│   │   └── vector_memory.py # Vector memory (future)
│   │
│   ├── server/
│   │   ├── http_server.py  # HTTP/SSE endpoints
│   │   └── websocket.py    # WebSocket support (optional)
│   │
│   ├── utils/
│   │   ├── types.py        # Type definitions
│   │   ├── helpers.py      # Utility functions
│   │   └── formatting.py   # Output formatting
│   │
│   └── interfaces/
│       └── schemas.py      # Pydantic schemas
│
├── tests/
│   ├── test_tools.py       # Tool tests
│   ├── test_graph.py       # Graph pipeline tests
│   └── test_end_to_end.py  # End-to-end tests
│
└── docs/
    └── MULTI_PROVIDER_SETUP.md  # Multi-provider LLM guide
```

## 🛠️ Development

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_tools.py

# With verbose output
pytest -v
```

### Code Formatting

```bash
# Format code with Black
black src/

# Sort imports with isort
isort src/

# Run both
black src/ && isort src/
```

### Type Checking

```bash
mypy src/
```

### Linting

```bash
flake8 src/
```

### Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## 🧪 Testing

### Unit Tests

```bash
pytest tests/test_tools.py -v
```

### Integration Tests

```bash
pytest tests/test_graph.py -v
```

### End-to-End Tests

```bash
pytest tests/test_end_to_end.py -v
```

**Note:** E2E tests require:
- Running Redis instance
- Valid GraphQL endpoint
- Valid LLM API keys


### Production Checklist

- [ ] Set `ENV=production` in environment
- [ ] Configure proper CORS origins (`ALLOWED_ORIGINS`)
- [ ] Use production-grade LLM models
- [ ] Set up Redis persistence
- [ ] Configure logging aggregation
- [ ] Set up monitoring (Sentry, Prometheus)
- [ ] Use reverse proxy (nginx) for SSL termination
- [ ] Configure rate limiting
- [ ] Set up authentication middleware
- [ ] Use multiple workers for high availability

## 🔍 Troubleshooting

### Redis Connection Issues

**Problem:** `ConnectionError: Error connecting to Redis`

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# Check Redis URL in .env
echo $REDIS_URL

# Test connection
redis-cli -u redis://localhost:6379/0 ping
```

### GraphQL API Issues

**Problem:** `GraphQL request failed`

**Solution:**
```bash
# Test GraphQL endpoint
curl -X POST http://your-backend/graphql \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { types { name } } }"}'

# Verify GRAPHQL_ENDPOINT in .env
```

### Module Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Ensure you're in project root
pwd

# Ensure virtual environment is activated
which python  # Should show venv python

# Reinstall in development mode
pip install -e .
```

### LLM Provider Errors

**Problem:** `ValueError: OpenAI client not initialized`

**Solution:**
```bash
# Check API key is set
echo $OPENAI_API_KEY

# Verify SDK is installed
pip list | grep openai

# Install if missing
pip install openai
```

### Port Already in Use

**Problem:** `Address already in use`

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill process or change PORT in .env
PORT=8001
```

### Memory/State Issues

**Problem:** Conversation state not persisting

**Solution:**
```bash
# Check Redis is running
redis-cli ping

# Check Redis URL matches
redis-cli -u redis://localhost:6379/0 ping

# Clear Redis if needed (development only)
redis-cli FLUSHDB
```

## 📚 Additional Resources

- [Multi-Provider LLM Setup Guide](docs/MULTI_PROVIDER_SETUP.md)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest && black src/ && isort src/`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
- LLM support from OpenAI, Anthropic, and Google

---

**Need Help?** Open an issue on GitHub or check the [troubleshooting section](#troubleshooting).
