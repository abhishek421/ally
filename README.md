# AI Analyst Service - Intelligent CRM Query System

## 📋 Overview

The **AI Analyst Service** is a production-ready, intelligent CRM query system that transforms natural language questions into structured data responses. Built with FastAPI and LangGraph, it orchestrates multiple AI agents to understand queries, extract data from various sources (PostgreSQL, DynamoDB, Redis), and format results—all through a simple REST API.

**What it does:**
- Accepts natural language queries like "Show me companies with closed deals from last year"
- Automatically resolves relative dates and extracts intent
- Queries multiple databases and data sources in parallel
- Returns formatted JSON responses with execution metadata

**Key Capabilities:**
- 🤖 Multi-agent AI pipeline using LangGraph
- 🔌 Multi-provider LLM support (OpenAI, Anthropic, Gemini)
- 🚀 Production-ready FastAPI REST API with JWT auth
- 🗄️ Multi-database integration (PostgreSQL, DynamoDB, Redis)
- 🏢 Multi-tenant workspace isolation
- ⚡ Redis-powered caching for performance
- 📊 Comprehensive health checks and monitoring

## 🏗️ Architecture Overview

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                           │
│                  (Natural Language)                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph Pipeline                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         QueryOptimizerAgent                       │    │
│  │  • Converts natural language to structured query  │    │
│  │  • Resolves relative dates (this month, last year)│    │
│  │  • Extracts entities and intent                    │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         DataExtractorAgent                         │    │
│  │  • Orchestrates multiple tools                     │    │
│  │  • Handles workspace isolation                    │    │
│  │  • Aggregates data from multiple sources          │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         ResponseFormatterAgent                      │    │
│  │  • Formats raw data into markdown response        │    │
│  │  • Generates professional, structured output      │    │
│  │  • Includes both formatted text and raw data      │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│   Final Response (Markdown + Raw Data + Metadata)           │
└──────────────────────────��───────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Tools      │    │ LLM Providers │    │  Databases   │
│              │    │              │    │              │
│ • Company    │    │ • OpenAI     │    │ • PostgreSQL │
│ • People     │    │ • Anthropic  │    │ • DynamoDB   │
│ • Email      │    │ • Gemini     │    │ • Redis      │
│ • Workspace  │    │              │    │              │
│ • Interaction│    │              │    │              │
│ • Group      │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Core Components

#### 1. **LangGraph Pipeline** (`graph/pipeline.py`)
- **State Management**: Uses TypedDict for type-safe state flow
- **Agent Orchestration**: Sequential flow through three agents
- **Checkpointing**: Memory-based checkpointing for state persistence
- **Nodes**: QueryOptimizer → DataExtractor → ResponseFormatter

#### 2. **Agents** (`agents/`)

##### QueryOptimizerAgent (`agents/query_optimizer.py`)
- **Status**: ✅ Fully Implemented
- **Model Support**: Configurable per agent (OpenAI, Anthropic, Gemini)
- **Responsibility**: 
  - Parses natural language into structured intent
  - Replaces relative time references with exact dates
  - Extracts key entities (persons, companies, dates)
  - Generates optimized query parameters
- **Output**: Structured query object ready for data extraction

##### DataExtractorAgent (`agents/data_extractor.py`)
- **Status**: ✅ Implemented
- **Model Support**: Configurable per agent (OpenAI, Anthropic, Gemini)
- **Responsibility**:
  - Parses optimized queries into structured tool calls using LLM
  - Executes database queries via tools asynchronously
  - Handles workspace/tenant isolation
  - Applies role-based access control
  - Aggregates data from multiple sources
  - Returns tool-grouped results with metadata

##### ResponseFormatterAgent (`agents/response_formatter.py`)
- **Status**: ✅ Fully Implemented
- **Model Support**: Configurable per agent (OpenAI, Anthropic, Gemini)
- **Responsibility**:
  - Formats raw data into professional markdown responses
  - Generates user-friendly, structured output with headers, tables, and lists
  - Provides both formatted markdown and raw data in response
  - Includes metadata (processing time, data sources count, response length)
  - Handles errors gracefully with fallback responses
  - Uses LLM to craft contextual, insightful responses based on extracted data

#### 3. **Tools Layer** (`tools/`)

All tools inherit from `BaseTool` and implement:
- Workspace isolation
- Permission checking
- Error handling with structured responses
- Query caching via Redis
- Audit logging

##### Available Tools

| Tool | File | Status | Operations |
|------|------|--------|------------|
| **CompanyTool** | `tools/company_tool.py` | ✅ Implemented | Search, GetById, List, Create, Update, Analytics |
| **EmailTool** | `tools/emails_tool.py` | ✅ Implemented | Search, GetById, List, Analytics |
| **PeopleTool** | `tools/people_tool.py` | ✅ Implemented | Search, GetById, List, Analytics |
| **WorkspaceTool** | `tools/workspace_tool.py` | ✅ Implemented | GetById, List |
| **InteractionTool** | `tools/interaction_tool.py` | 🚧 Placeholder | - |
| **GroupTool** | `tools/group_tool.py` | 🚧 Placeholder | - |

##### BaseTool (`tools/base_tool.py`)
- Abstract base class for all tools
- Provides caching, error handling, logging
- Standardized `ToolResult` format
- Query type enumeration (SEARCH, GET_BY_ID, LIST, CREATE, UPDATE, DELETE, ANALYTICS)

##### ToolFactory (`tools/tool_factory.py`)
- Factory pattern for creating tool instances
- Tool registry for dynamic tool discovery
- Tool metadata and capabilities introspection

#### 3. **LLM Provider Adapters** (`adapters/`)

Pluggable architecture supporting multiple LLM providers:

| Provider | File | Status | Models Supported |
|----------|------|--------|------------------|
| **OpenAI** | `adapters/llm_providers/openai_provider.py` | ✅ Implemented | GPT-3.5, GPT-4, GPT-4 Turbo |
| **Anthropic** | `adapters/llm_providers/anthropic_provider.py` | ✅ Implemented | Claude Opus, Sonnet, Haiku |
| **Gemini** | `adapters/llm_providers/gemini_provider.py` | ✅ Implemented | Gemini Pro, Gemini Ultra |

**Features**:
- Unified interface via `LLMProvider` abstract class
- Per-agent provider configuration
- Factory pattern for provider creation
- Consistent error handling and logging

#### 4. **Database Clients** (`database/`)

| Client | File | Purpose | Status |
|--------|------|----------|--------|
| **PrismaClient** | `database/prisma_client.py` | PostgreSQL connection management | ✅ Implemented |
| **DynamoDBClient** | `database/dynamodb_client.py` | DynamoDB for email sync data | ✅ Implemented |
| **RedisClient** | `database/redis_client.py` | Caching and configuration storage | ✅ Implemented |

#### 5. **Configuration** (`config/`)

- **Settings** (`config/settings.py`): 
  - Per-agent LLM configuration
  - Environment variable management
  - Query optimization templates
  - Date context generation

- **Prompts** (`prompts/`):
  - Query optimizer prompt templates
  - Modular prompt system

#### 6. **FastAPI REST API** (`api/`)

Production-ready REST API with comprehensive error handling and validation.

**Endpoints:**

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/query` | POST | Process natural language query | Yes (JWT) |
| `/health` | GET | Basic health check | No |
| `/ready` | GET | Readiness check with service status | No |

**Request/Response Schemas** (`api/v1/schemas.py`):
- `QueryRequest`: Validates query (1-2000 chars), workspace_id, user_id
- `QueryResponse`: Success flag, query, result data, execution_time_ms
- `HealthResponse`: Status and timestamp
- `ReadyResponse`: Overall status and service health checks

**Features:**
- **Header-based Authentication**: Simplified auth using `X-Workspace-ID` and `X-User-ID` headers (JWT auth commented out for development)
- **Request Validation**: Pydantic schemas with detailed error messages
- **Error Handling**: Structured error responses with codes and details
- **CORS Support**: Configurable cross-origin requests
- **Logging**: Comprehensive request/response logging with request IDs
- **Lifespan Management**: Startup/shutdown hooks for resource management

**Example Query Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: ws-123" \
  -H "X-User-ID: user-456" \
  -d '{
    "query": "Show me companies with closed deals from last year"
  }'
```

**Note**: See [API_USAGE.md](API_USAGE.md) for comprehensive API documentation and examples.

**Example Response:**
```json
{
  "success": true,
  "query": "Show me companies with closed deals from last year",
  "result": {
    "companies": [...],
    "count": 42,
    "metadata": {...}
  },
  "execution_time_ms": 1250,
  "workspace_id": "ws-123",
  "user_id": "user-456"
}
```

## 📁 Project Structure

```
analyst-ai/
├── adapters/                    # LLM Provider Adapters
│   ├── __init__.py
│   ├── llm_provider.py         # Abstract base class
│   ├── provider_factory.py     # Factory for creating providers
│   └── llm_providers/
│       ├── __init__.py
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       └── gemini_provider.py
│
├── agents/                      # Agent Implementations
│   ├── __init__.py
│   ├── query_optimizer.py      # ✅ Fully implemented
│   ├── data_extractor.py       # ✅ Implemented
│   └── response_formatter.py   # ✅ Basic implementation
│
├── tools/                       # Data Extraction Tools
│   ├── __init__.py
│   ├── base_tool.py            # ✅ Base class with caching
│   ├── tool_factory.py         # ✅ Tool factory
│   ├── company_tool.py         # ✅ Implemented
│   ├── emails_tool.py          # ✅ Implemented
│   ├── people_tool.py          # ✅ Implemented
│   ├── workspace_tool.py        # ✅ Implemented
│   ├── interaction_tool.py      # 🚧 Placeholder
│   ├── group_tool.py           # 🚧 Placeholder
│   └── companies_tool.py       # Legacy (use company_tool.py)
│
├── api/                         # FastAPI REST API
│   ├── __init__.py
│   ├── dependencies.py          # ✅ Dependency injection
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── query.py            # ✅ Query endpoint
│   │   ├── health.py           # ✅ Health endpoints
│   │   └── schemas.py          # ✅ Pydantic schemas
│   └── auth/
│       ├── __init__.py
│       └── cognito.py          # ✅ JWT validation
│
├── graph/                       # LangGraph Pipeline
│   ├── __init__.py
│   └── pipeline.py             # ✅ Main pipeline orchestration
│
├── database/                     # Database Clients
│   ├── __init__.py
│   ├── prisma_client.py        # ✅ PostgreSQL client
│   ├── dynamodb_client.py      # ✅ DynamoDB client
│   └── redis_client.py        # ✅ Redis client
│
├── config/                       # Configuration
│   ├── __init__.py
│   └── settings.py             # ✅ App settings & LLM config
│
├── prompts/                      # Prompt Templates
│   ├── __init__.py
│   └── query_optimizer_prompt.py  # ✅ Query optimization prompts
│
├── scripts/                      # Utility Scripts
│   └── health_check.py          # ✅ System health check
│
├── models/                       # Data Models
│   └── __init__.py
│
├── utils/                        # Utility Functions
│   └── __init__.py
│
├── tests/                        # Test Suite
│   ├── __init__.py
���   ├── test_query_optimizer.py
│   └── test_pipeline_integration.py
│
├── docs/                         # Documentation
│   ├── AI_ANALYST_SERVICE_ROADMAP.md
│   ├── TOOLS_ARCHITECTURE_PLAN.md
│   ├── TOOLS_IMPLEMENTATION.md
│   ├── adapter-architecture.md
│   └── schema documentation files
│
├── examples/                     # Example Usage
│   └── tool_usage_example.py
│
├── main.py                       # Entry point
├── requirements.txt              # Dependencies
└── README.md                     # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (with Prisma schema)
- DynamoDB table (`EmailSync`) - Optional
- Redis instance - Optional but recommended
- API keys for at least one LLM provider:
  - OpenAI API key (for GPT models)
  - Anthropic API key (for Claude models)
  - Google API key (for Gemini models)

### 🐳 Quick Start with Docker (Recommended)

The easiest way to run the application with all dependencies:

```bash
# 1. Clone the repository
git clone <repository-url>
cd analyst-ai

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys (DATABASE_URL will be set by docker-compose)

# 3. Start all services (PostgreSQL, Redis, and the app)
docker-compose up -d

# 4. Check service health
docker-compose logs -f app

# 5. Test the API
curl http://localhost:8000/health
# Visit http://localhost:8000/docs for interactive API documentation

# 6. Stop all services
docker-compose down
```

**What Docker Compose provides:**
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- FastAPI application (port 8000)
- Automatic service orchestration and health checks
- Persistent data volumes

### 🚀 Quick Start (Local Python Installation)

```bash
# 1. Clone and install
git clone <repository-url>
cd analyst-ai
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys and database URLs

# 3. Verify setup
python scripts/health_check.py

# 4. Start the server
python main.py

# 5. Test the API
curl http://localhost:8000/health
# Visit http://localhost:8000/docs for interactive API documentation
```

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd analyst-ai

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Configuration

#### Environment Variables

Create a `.env` file in the project root:

**Basic Configuration (all agents use same provider):**
```bash
# Global provider and model
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4

# Provider API key (choose the one matching your provider)
OPENAI_API_KEY=REDACTED
# ANTHROPIC_API_KEY=sk-ant-your-api-key
# GOOGLE_API_KEY=your-google-api-key
```

**Advanced Configuration (per-agent configuration):**
```bash
# QueryOptimizerAgent - Use OpenAI GPT-4
QUERY_OPTIMIZER_PROVIDER=openai
QUERY_OPTIMIZER_MODEL=gpt-4
QUERY_OPTIMIZER_API_KEY=sk-your-openai-key

# DataExtractorAgent - Use Anthropic Claude
DATA_EXTRACTOR_PROVIDER=anthropic
DATA_EXTRACTOR_MODEL=claude-3-opus-20240229
ANTHROPIC_API_KEY=sk-ant-your-key

# Or use Google Gemini
# DATA_EXTRACTOR_PROVIDER=gemini
# DATA_EXTRACTOR_MODEL=gemini-pro
# GOOGLE_API_KEY=your-google-api-key

# ResponseFormatterAgent - Use cheaper model
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo
```

**Database Configuration:**
```bash
# PostgreSQL (Prisma automatically reads DATABASE_URL)
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# DynamoDB (uses AWS credentials from ~/.aws/credentials or environment)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=REDACTED
AWS_SECRET_ACCESS_KEY=REDACTED

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## 🐳 Docker Deployment

### Docker Compose (Recommended)

The easiest way to deploy the application with all its dependencies:

```bash
# Start all services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f redis

# Check service status
docker-compose ps

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

### Docker Compose Configuration

The [docker-compose.yml](docker-compose.yml) includes:

1. **PostgreSQL Service**
   - Image: postgres:15-alpine
   - Port: 5432
   - Volume: postgres_data (persistent)
   - Health checks enabled

2. **Redis Service**
   - Image: redis:7-alpine
   - Port: 6379
   - Volume: redis_data (persistent)
   - AOF persistence enabled

3. **FastAPI Application**
   - Built from local Dockerfile
   - Port: 8000
   - Auto-connects to PostgreSQL and Redis
   - Health checks enabled
   - Hot-reload enabled for development

### Environment Variables for Docker

Create a `.env` file in the project root with these variables:

```bash
# Database credentials (used by docker-compose)
POSTGRES_USER=analyst_user
POSTGRES_PASSWORD=analyst_password
POSTGRES_DB=analyst_ai
POSTGRES_PORT=5432

# Redis configuration
REDIS_PORT=6379
REDIS_DB=0

# Application port
APP_PORT=8000

# LLM Provider API Keys (REQUIRED)
OPENAI_API_KEY=REDACTED
OPENAI_API_KEY=REDACTED
GOOGLE_API_KEY=your-google-api-key

# Global LLM Configuration
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4

# AWS Configuration (Optional)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=REDACTED
AWS_SECRET_ACCESS_KEY=REDACTED
AWS_COGNITO_USER_POOL_ID=your-pool-id

# Application Configuration
LOG_LEVEL=INFO
```

### Building and Running with Docker Standalone

If you prefer to run just the application container:

```bash
# Build the Docker image
docker build -t analyst-ai:latest .

# Run the container
docker run -d \
  --name analyst-ai-app \
  -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  analyst-ai:latest

# View logs
docker logs -f analyst-ai-app

# Stop the container
docker stop analyst-ai-app

# Remove the container
docker rm analyst-ai-app
```

### Production Docker Configuration

For production deployments, consider these modifications:

1. **Remove hot-reload volume mount** in docker-compose.yml:
```yaml
# Comment out this line in the app service:
# - .:/app
```

2. **Use production-grade PostgreSQL**:
   - Set strong passwords
   - Configure connection pooling
   - Set up backups

3. **Add resource limits**:
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

4. **Use secrets management**:
   - Use Docker secrets or environment secret managers
   - Never commit `.env` file to version control

5. **Set up reverse proxy**:
   - Use Nginx or Traefik for SSL/TLS termination
   - Configure rate limiting and load balancing

### Kubernetes Deployment

For Kubernetes deployments, you'll need:

1. **ConfigMap** for non-sensitive configuration
2. **Secret** for API keys and passwords
3. **Deployment** for the application
4. **Service** to expose the application
5. **PersistentVolumeClaim** for PostgreSQL and Redis
6. **Ingress** for external access

Example Kubernetes deployment structure:
```
k8s/
├── configmap.yaml
├── secrets.yaml
├── deployment.yaml
├── service.yaml
├── postgres-statefulset.yaml
├── redis-statefulset.yaml
└── ingress.yaml
```

### Running the Application

#### Option 1: FastAPI Server Mode (Recommended for Production)

```bash
# Start the FastAPI server
python main.py

# Server will start on http://localhost:8000
# API documentation available at http://localhost:8000/docs
# Alternative docs at http://localhost:8000/redoc
```

The FastAPI server provides:
- RESTful API endpoints with JWT authentication
- Interactive API documentation (Swagger UI)
- Health check endpoints
- Structured error handling
- Request/response validation

**Testing the API:**
```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Readiness check (no auth required)
curl http://localhost:8000/ready

# Process a query (header-based auth)
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: ws-123" \
  -H "X-User-ID: user-456" \
  -d '{
    "query": "Show me companies with closed deals"
  }'
```

**For detailed API usage, examples in multiple languages, and more, see [API_USAGE.md](API_USAGE.md)**

#### Option 2: CLI Mode (For Testing and Development)

```bash
# Run with example queries
python main.py cli

# Interactive mode (uncomment in main.py)
# python main.py cli  # then uncomment interactive_mode() call
```

CLI mode allows you to:
- Test queries directly from command line
- Debug the pipeline without API overhead
- Run batch query examples
- Interactive query mode for experimentation

### Example Query Flow

**Input:** "With how many companies we have closed deal previous year?"

**Pipeline Flow:**
1. **QueryOptimizerAgent**: Converts to "The user is asking you to fetch and analyze all closed deals from 2023 and return structured information"
2. **DataExtractorAgent**: Uses CompanyTool to query database for companies with closed deals in 2023
3. **ResponseFormatterAgent**: Formats results into JSON response

**Output:** JSON formatted response with extracted data from CRM databases.

## 🛠️ Development

### Current Implementation Status

#### ✅ Completed Components
- [x] LangGraph pipeline framework with state management
- [x] QueryOptimizerAgent (fully implemented with LLM integration)
- [x] DataExtractorAgent (LLM-powered tool orchestration)
- [x] ResponseFormatterAgent (basic implementation)
- [x] BaseTool with caching and error handling
- [x] CompanyTool, EmailTool, PeopleTool, WorkspaceTool
- [x] LLM provider adapters (OpenAI, Anthropic, Gemini)
- [x] Provider factory for dynamic LLM selection
- [x] Database clients (Prisma, DynamoDB, Redis)
- [x] Configuration system with per-agent LLM config
- [x] Tool factory pattern with registry
- [x] FastAPI REST API with JWT authentication
- [x] Query endpoint with request validation
- [x] Health check endpoints
- [x] Pydantic schemas for request/response validation
- [x] Error handling and logging
- [x] CORS middleware configuration
- [x] Testing framework setup
- [x] Health check script

#### 🚧 In Progress / Needs Implementation
- [ ] InteractionTool implementation
- [ ] GroupTool implementation
- [ ] Enhanced ResponseFormatter with business logic
- [ ] Workspace isolation validation (RBAC)
- [ ] Comprehensive integration tests
- [ ] Performance optimization and caching strategies
- [ ] API rate limiting and throttling
- [ ] Detailed API documentation
- [ ] Deployment configuration (Docker, K8s)

### Adding a New Tool

1. Create a new tool class inheriting from `BaseTool`:

```python
# tools/your_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import List

class YourTool(BaseTool):
    def get_supported_operations(self) -> List[QueryType]:
        return [QueryType.SEARCH, QueryType.GET_BY_ID]
    
    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        # Implement your tool logic
        pass
```

2. Register it in `ToolFactory`:

```python
# tools/tool_factory.py
from tools.your_tool import YourTool

_tool_registry = {
    # ... existing tools ...
    'your_tool': YourTool,
}
```

### Adding a New LLM Provider

1. Create provider class inheriting from `LLMProvider`:

```python
# adapters/llm_providers/your_provider.py
from adapters.llm_provider import LLMProvider

class YourProvider(LLMProvider):
    def _initialize_client(self):
        # Initialize your client
        pass
    
    def chat(self, messages, **kwargs) -> str:
        # Implement chat method
        pass
```

2. Register in `LLMProviderFactory`:

```python
# adapters/provider_factory.py
from adapters.llm_providers.your_provider import YourProvider

_providers = {
    # ... existing providers ...
    'your_provider': YourProvider,
}
```

## 🧪 Testing

### Quick Start Testing

For beginners, start with the comprehensive testing guide:

```bash
# Run health check first
python scripts/health_check.py

# Then follow the step-by-step guide
# See: docs/TESTING_GUIDE.md
```

### Run Unit Tests

```bash
# Test QueryOptimizerAgent
python tests/test_query_optimizer.py

# Test Pipeline Integration
python tests/test_pipeline_integration.py
```

### Run All Tests

```bash
# Run unit tests
python tests/test_query_optimizer.py

# Run integration tests
python tests/test_pipeline_integration.py
```

### Testing Documentation

- **[Complete Testing Guide](docs/TESTING_GUIDE.md)** - Detailed step-by-step testing instructions for beginners
- **[Quick Start Guide](docs/QUICK_START.md)** - 5-minute quick start guide
- **[Health Check Script](scripts/health_check.py)** - Automated system health verification

## 📊 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Runtime** | Python 3.11+ | Backend language |
| **Web Framework** | FastAPI | REST API with async support |
| **Server** | Uvicorn | ASGI server for FastAPI |
| **AI Orchestration** | LangGraph | Agent workflows & state management |
| **LLM Providers** | OpenAI, Anthropic, Gemini | Multi-provider AI model access |
| **Database (SQL)** | PostgreSQL + Prisma ORM | Primary CRM data store |
| **Database (NoSQL)** | DynamoDB (AWS) | Email sync data |
| **Cache** | Redis | Query caching & configuration |
| **Data Validation** | Pydantic v2 | Request/response validation |
| **Authentication** | JWT + AWS Cognito | Token-based auth |
| **API Documentation** | OpenAPI (Swagger) | Auto-generated API docs |

## 📚 Documentation

### Getting Started
- **[Testing Guide](docs/TESTING_GUIDE.md)** - Complete step-by-step testing instructions for beginners
- **[Quick Start](docs/QUICK_START.md)** - 5-minute quick start guide

### Architecture & Implementation
- **[Technical Roadmap](docs/AI_ANALYST_SERVICE_ROADMAP.md)** - Complete implementation guide
- **[Tools Architecture](docs/TOOLS_ARCHITECTURE_PLAN.md)** - Tool design patterns
- **[Tools Implementation](docs/TOOLS_IMPLEMENTATION.md)** - Tool implementation guide
- **[Adapter Architecture](docs/adapter-architecture.md)** - LLM provider adapter design
- **[Schema Documentation](docs/)** - Database schema documentation (company, people, email, etc.)

## 🔧 Key Features

### 1. Multi-Provider LLM Support
- **Unified Interface**: Single API for OpenAI, Anthropic, and Google Gemini
- **Per-Agent Configuration**: Different models for different pipeline stages
- **Cost Optimization**: Use cheaper models where appropriate
- **Easy Extension**: Add new providers via factory pattern
- **Fallback Support**: Graceful degradation if primary provider fails

### 2. Production-Ready REST API
- **FastAPI Framework**: High-performance async API
- **JWT Authentication**: Secure AWS Cognito integration
- **Request Validation**: Comprehensive Pydantic schemas
- **Error Handling**: Structured error responses with codes
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Health Checks**: Liveness and readiness endpoints
- **CORS Support**: Configurable cross-origin requests
- **Request Tracing**: UUID-based request tracking

### 3. Flexible Tool System
- **Factory Pattern**: Dynamic tool creation and registration
- **Standardized Interface**: Consistent API across all tools
- **Built-in Caching**: Redis-powered query result caching
- **Workspace Isolation**: Multi-tenant data separation
- **Async Execution**: Non-blocking tool operations
- **Error Recovery**: Graceful handling of tool failures

### 4. Intelligent Agent Pipeline
- **LangGraph Orchestration**: State-based workflow management
- **Type-Safe State**: TypedDict for compile-time safety
- **Checkpointing**: State persistence for recovery
- **Sequential Flow**: Ordered agent execution
- **Context Preservation**: State flows through all agents
- **Error Recovery**: Graceful degradation on failures

### 5. Multi-Database Architecture
- **PostgreSQL**: Primary CRM data via Prisma ORM
- **DynamoDB**: Email sync data with AWS integration
- **Redis**: Query caching and configuration storage
- **Connection Pooling**: Efficient resource management
- **Health Monitoring**: Database connectivity checks
- **Transaction Support**: ACID compliance where needed

## 🤝 Contributing

This project follows the implementation phases outlined in the [technical roadmap](docs/AI_ANALYST_SERVICE_ROADMAP.md).

**Current Development Focus:**
- Enhancing ResponseFormatterAgent with advanced formatting logic
- Implementing InteractionTool for CRM interaction tracking
- Implementing GroupTool for contact group management
- Adding comprehensive integration tests
- Performance optimization and load testing
- Deployment configuration (Docker, Kubernetes)

**How to Contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow the existing code patterns and architecture
4. Add tests for new functionality
5. Ensure all tests pass (`python -m pytest`)
6. Update documentation as needed
7. Submit a pull request

**Development Guidelines:**
- Follow PEP 8 style guide for Python code
- Use type hints for all function signatures
- Write docstrings for public methods and classes
- Add unit tests for new features
- Update the README and relevant docs
- Use async/await for I/O operations
- Leverage the factory patterns for tools and providers

## 📄 License

[Add your license information here]

---

**Built with**: Python, FastAPI, LangGraph, OpenAI, Anthropic, Google Gemini, PostgreSQL, DynamoDB, Redis

**Maintained by**: [Your Team/Organization Name]

For questions, issues, or feature requests, please open an issue on GitHub.
