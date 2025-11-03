# AI Analyst Agent

A production-ready, intelligent CRM query system that transforms natural language questions into structured data responses. Built with FastAPI and LangGraph, it orchestrates multiple AI agents to understand queries, extract data from various sources (PostgreSQL, DynamoDB, Redis), and format results through a simple REST API.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Components](#components)
- [Installation](#installation)
- [Docker Deployment](#docker-deployment)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Development](#development)
- [Testing](#testing)
- [License](#license)

## Overview

The AI Analyst Service provides a natural language interface to query CRM data across multiple databases. Users can ask questions like:

- "Show me companies with closed deals from last year"
- "List all emails from contacts in Q4"
- "How many people interacted with us last month?"

The system automatically:
- Parses natural language queries into structured intent
- Resolves relative dates and time references
- Queries multiple databases in parallel
- Formats responses with both human-readable markdown and raw data

## Features

### Core Capabilities

- **Multi-Agent AI Pipeline**: Orchestrated workflow using LangGraph with three specialized agents
- **Multi-Provider LLM Support**: Seamlessly switch between OpenAI, Anthropic, and Google Gemini
- **RESTful API**: Production-ready FastAPI with comprehensive validation and error handling
- **Multi-Database Integration**: Unified access to PostgreSQL, DynamoDB, and Redis
- **Multi-Tenant Architecture**: Workspace-based isolation for data security
- **Intelligent Caching**: Redis-powered query result caching for optimal performance
- **Comprehensive Monitoring**: Health checks and readiness endpoints for production deployments

### System Features

- **Per-Agent LLM Configuration**: Use different models for different pipeline stages (cost optimization)
- **Type-Safe State Management**: TypedDict-based state flow with LangGraph checkpointing
- **Factory Pattern Architecture**: Extensible tool and provider system
- **Async Operations**: Non-blocking I/O for optimal performance
- **Error Recovery**: Graceful degradation with structured error responses

## Architecture

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
│  │      QueryOptimizerAgent                           │    │
│  │  • Natural language parsing                        │    │
│  │  • Date/time resolution                           │    │
│  │  • Entity extraction                              │    │
│  │  • Intent structuring                             │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │      DataExtractorAgent                            │    │
│  │  • Tool orchestration                              │    │
│  │  • LLM-powered query planning                     │    │
│  │  • Parallel data extraction                       │    │
│  │  • Workspace isolation                            │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │      ResponseFormatterAgent                        │    │
│  │  • Markdown formatting                            │    │
│  │  • Business analyst persona                      │    │
│  │  • Structured output generation                   │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│   Final Response (Markdown + Raw Data + Metadata)           │
└──────────────────────────┬───────────────────────────────────┘
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

### Data Flow

1. **Query Input**: User submits natural language query via REST API
2. **Query Optimization**: QueryOptimizerAgent structures and enhances the query
3. **Data Extraction**: DataExtractorAgent uses LLM to plan and execute tool calls
4. **Response Formatting**: ResponseFormatterAgent formats results with business context
5. **Response Output**: Returns formatted markdown, raw data, and execution metadata

## Components

### Agents

The system uses three specialized AI agents orchestrated by LangGraph:

#### 1. QueryOptimizerAgent (`agents/query_optimizer.py`)

**Purpose**: Transforms natural language queries into structured, actionable queries.

**Responsibilities**:
- Parses user intent from natural language
- Resolves relative time references (e.g., "last year" → "2023-01-01 to 2023-12-31")
- Extracts entities (companies, people, dates, etc.)
  - Generates optimized query parameters
- Normalizes ambiguous queries

**Input**: Natural language user query  
**Output**: Structured, optimized query string

#### 2. DataExtractorAgent (`agents/data_extractor.py`)

**Purpose**: Orchestrates data extraction from multiple sources using specialized tools.

**Responsibilities**:
  - Parses optimized queries into structured tool calls using LLM
- Coordinates multiple tools for parallel data extraction
  - Handles workspace/tenant isolation
  - Applies role-based access control
  - Aggregates data from multiple sources
  - Returns tool-grouped results with metadata

**Input**: Optimized query from QueryOptimizerAgent  
**Output**: Extracted data grouped by tool with execution metadata

#### 3. ResponseFormatterAgent (`agents/response_formatter.py`)

**Purpose**: Formats raw extracted data into professional, human-readable responses.

**Responsibilities**:
  - Formats raw data into professional markdown responses
- Applies business analyst persona for contextual insights
- Generates structured output with headers, tables, and lists
- Provides both formatted markdown and raw data
- Includes metadata (processing time, data sources, response length)
  - Handles errors gracefully with fallback responses

**Input**: Optimized query + extracted data  
**Output**: Formatted markdown response with raw data and metadata

### Tools

Tools are specialized data access components that abstract database operations. All tools inherit from `BaseTool` and implement workspace isolation, permission checking, error handling, query caching, and audit logging.

#### Available Tools

| Tool | Module | Supported Operations | Description |
|------|--------|---------------------|-------------|
| **CompanyTool** | `tools/company_tool.py` | Search, GetById, List, Analytics | Company data operations including search, retrieval, and analytics |
| **PeopleTool** | `tools/people_tool.py` | Search, GetById, List, Analytics | People/contact management operations |
| **EmailTool** | `tools/emails_tool.py` | Search, GetById, List, Analytics | Email data retrieval and search operations |
| **WorkspaceTool** | `tools/workspace_tool.py` | GetById, List | Workspace information retrieval |
| **InteractionTool** | `tools/interaction_tool.py` | Search, GetById, List | CRM interaction tracking operations |
| **GroupTool** | `tools/group_tool.py` | Search, GetById, List | Contact group management operations |

#### Tool Operations

All tools support the following query types (defined in `QueryType` enum):

- **SEARCH**: Search operations with filters and parameters
- **GET_BY_ID**: Retrieve specific records by ID
- **LIST**: Paginated listing operations
- **ANALYTICS**: Aggregated analytics and reporting operations

#### BaseTool Features

- **Workspace Isolation**: Automatic workspace/tenant data separation
- **Permission Checking**: Role-based access control validation
- **Query Caching**: Redis-powered result caching (5-minute default TTL)
- **Error Handling**: Structured error responses with execution metadata
- **Audit Logging**: Comprehensive operation logging

#### ToolFactory (`tools/tool_factory.py`)

Factory pattern implementation for tool creation and management:

- Dynamic tool instance creation
- Tool registry for discovery
- Tool metadata introspection
- Runtime tool registration/unregistration

### LLM Provider Adapters

Pluggable architecture supporting multiple LLM providers with a unified interface.

#### Supported Providers

| Provider | Module | Models Supported |
|----------|--------|------------------|
| **OpenAI** | `adapters/llm_providers/openai_provider.py` | GPT-3.5, GPT-4, GPT-4 Turbo |
| **Anthropic** | `adapters/llm_providers/anthropic_provider.py` | Claude Opus, Claude Sonnet, Claude Haiku |
| **Gemini** | `adapters/llm_providers/gemini_provider.py` | Gemini Pro, Gemini Ultra |

#### Features

- **Unified Interface**: `LLMProvider` abstract base class
- **Per-Agent Configuration**: Different models for different agents
- **Factory Pattern**: `LLMProviderFactory` for dynamic provider creation
- **Consistent Error Handling**: Standardized error responses across providers

### Database Clients

Multi-database architecture with specialized clients:

#### PrismaClient (`database/prisma_client.py`)

- **Database**: PostgreSQL
- **Purpose**: Primary CRM data store
- **Features**: Type-safe ORM, connection pooling, transaction support

#### DynamoDBClient (`database/dynamodb_client.py`)

- **Database**: AWS DynamoDB
- **Purpose**: Email sync data and high-throughput operations
- **Features**: AWS SDK integration, batch operations

#### RedisClient (`database/redis_client.py`)

- **Database**: Redis
- **Purpose**: Query result caching and configuration storage
- **Features**: TTL-based caching, connection pooling

### Configuration System

#### Settings (`config/settings.py`)

- Per-agent LLM configuration
- Environment variable management
- Query optimization templates
- Date context generation

#### LLM Configuration

Supports both global and per-agent LLM configuration:

- **Global Configuration**: Single provider/model for all agents
- **Per-Agent Configuration**: Different models for optimizer, extractor, and formatter
- **Environment-Based**: Configuration via environment variables

### REST API (`api/`)

Production-ready FastAPI REST API with comprehensive features.

#### Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/query` | POST | Process natural language query | Yes (Headers) |
| `/health` | GET | Basic health check | No |
| `/ready` | GET | Readiness check with service status | No |
| `/admin` | GET | Admin panel interface | No |
| `/docs` | GET | Interactive API documentation (Swagger) | No |

#### Authentication

Currently uses header-based authentication:
- `X-Workspace-ID`: Workspace identifier
- `X-User-ID`: User identifier

JWT authentication with AWS Cognito is available but commented out for development.

#### Request/Response Schemas

- **QueryRequest**: Validates query (1-2000 chars), workspace_id, user_id
- **QueryResponse**: Success flag, query, result data, execution_time_ms
- **HealthResponse**: Status and timestamp
- **ReadyResponse**: Overall status and service health checks

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL database (with Prisma schema applied)
- Redis instance (optional but recommended)
- API keys for at least one LLM provider:
  - OpenAI API key (for GPT models)
  - Anthropic API key (for Claude models)
  - Google API key (for Gemini models)
- DynamoDB table (`EmailSync`) - Optional

### Local Installation

```bash
# Clone the repository
git clone <repository-url>
cd analyst-ai

# Install dependencies
pip install -r requirements.txt

# Generate Prisma client
python -m prisma generate

# Configure environment
cp .env.example .env
# Edit .env with your API keys and database URLs

# Verify setup
python scripts/health_check.py

# Start the server
python main.py
```

The server will start on `http://localhost:8000` with API documentation available at `http://localhost:8000/docs`.

## Docker Deployment

### Quick Start with Docker Compose

The easiest way to run the application with all dependencies:

```bash
# 1. Clone the repository
git clone <repository-url>
cd analyst-ai

# 2. Create environment file
cp .env.example .env
# Edit .env with your API keys (DATABASE_URL will be set by docker-compose)

# 3. Start all services (Redis and the app)
docker-compose up -d

# 4. Check service health
docker-compose logs -f app

# 5. Test the API
curl http://localhost:8000/health

# 6. Access API documentation
# Visit http://localhost:8000/docs for interactive API documentation

# 7. Stop all services
docker-compose down
```

### Docker Compose Services

The `docker-compose.yml` includes:

1. **Redis Service**
   - Image: `redis:7-alpine`
   - Port: `6380` (external) → `6379` (container)
   - Volume: `redis_data` (persistent)
   - Health checks enabled
   - AOF persistence enabled

2. **FastAPI Application**
   - Built from local `Dockerfile`
   - Port: `8000`
   - Auto-connects to Redis
   - Health checks enabled
   - Hot-reload enabled for development (volume mount)
   - Prisma client generated during build

### Docker Compose Environment Variables

Create a `.env` file in the project root:

```bash
# Redis Configuration
REDIS_DB=0
REDIS_EXTERNAL_PORT=6380

# Service-Specific Port (Analyst AI Service)
ANALYST_AI_PORT=8000

# LLM Provider API Keys (REQUIRED - at least one)
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=REDACTED_OPENAI_API_KEY
GOOGLE_API_KEY=your-google-api-key

# Global LLM Configuration
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4

# Per-Agent Configuration (optional - overrides global)
QUERY_OPTIMIZER_PROVIDER=openai
QUERY_OPTIMIZER_MODEL=gpt-4
DATA_EXTRACTOR_PROVIDER=anthropic
DATA_EXTRACTOR_MODEL=claude-3-opus-20240229
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo

# AWS Configuration (Optional - for DynamoDB)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_COGNITO_USER_POOL_ID=your-pool-id

# Database Configuration
# Note: DATABASE_URL is set in docker-compose.yml to connect to host PostgreSQL
# For Docker-based PostgreSQL, uncomment the postgres service in docker-compose.yml

# Application Configuration
LOG_LEVEL=INFO
```

### Production Deployment

For production, use the production override file:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The production configuration includes:
- Resource limits and reservations
- Removed hot-reload volume
- Production-grade logging levels
- Optimized PostgreSQL and Redis settings

### Standalone Docker

To build and run just the application container:

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
```

## Configuration

### Environment Variables

#### Basic Configuration (Global LLM)

All agents use the same provider and model:

```bash
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4
OPENAI_API_KEY=sk-your-openai-api-key
```

#### Advanced Configuration (Per-Agent)

Use different models for different agents:

```bash
# QueryOptimizerAgent - Use OpenAI GPT-4
QUERY_OPTIMIZER_PROVIDER=openai
QUERY_OPTIMIZER_MODEL=gpt-4
OPENAI_API_KEY=sk-your-openai-key

# DataExtractorAgent - Use Anthropic Claude
DATA_EXTRACTOR_PROVIDER=anthropic
DATA_EXTRACTOR_MODEL=claude-3-opus-20240229
ANTHROPIC_API_KEY=sk-ant-your-key

# ResponseFormatterAgent - Use cheaper model
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo
```

#### Database Configuration

```bash
# PostgreSQL (Prisma automatically reads DATABASE_URL)
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# DynamoDB (uses AWS credentials from ~/.aws/credentials or environment)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## Usage

### API Usage

#### Process a Query

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: ws-123" \
  -H "X-User-ID: user-456" \
  -d '{
    "query": "Show me companies with closed deals from last year"
  }'
```

#### Example Response

```json
{
  "success": true,
  "query": "Show me companies with closed deals from last year",
  "result": {
    "formatted_response": "# Companies with Closed Deals in 2023\n\n...",
    "raw_data": {
      "companies": [...],
      "metadata": {...}
    },
    "execution_metadata": {
      "processing_time_ms": 1250,
      "data_sources_count": 1,
      "response_length": 1234
    }
  },
  "execution_time_ms": 1250,
  "workspace_id": "ws-123",
  "user_id": "user-456"
}
```

### CLI Mode (Development)

For testing and development:

```bash
python main.py cli
```

This runs example queries without the API layer.

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

The API automatically generates OpenAPI schemas from FastAPI route definitions.

## Project Structure

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
│   ├── query_optimizer.py      # Query optimization agent
│   ├── data_extractor.py       # Data extraction agent
│   └── response_formatter.py   # Response formatting agent
│
├── tools/                       # Data Extraction Tools
│   ├── __init__.py
│   ├── base_tool.py            # Base class with caching
│   ├── tool_factory.py         # Tool factory
│   ├── company_tool.py         # Company operations
│   ├── emails_tool.py          # Email operations
│   ├── people_tool.py          # People/contact operations
│   ├── workspace_tool.py        # Workspace operations
│   ├── interaction_tool.py     # Interaction tracking
│   └── group_tool.py           # Group management
│
├── api/                         # FastAPI REST API
│   ├── __init__.py
│   ├── dependencies.py         # Dependency injection
│   ├── auth/
│   │   ├── __init__.py
│   │   └── cognito.py          # JWT validation
│   └── v1/
│       ├── __init__.py
│       ├── query.py            # Query endpoint
│       ├── health.py           # Health endpoints
│       ├── admin.py            # Admin endpoints
│       └── schemas.py          # Pydantic schemas
│
├── graph/                       # LangGraph Pipeline
│   ├── __init__.py
│   └── pipeline.py             # Main pipeline orchestration
│
├── database/                     # Database Clients
│   ├── __init__.py
│   ├── prisma_client.py        # PostgreSQL client
│   ├── dynamodb_client.py      # DynamoDB client
│   └── redis_client.py         # Redis client
│
├── config/                       # Configuration
│   ├── __init__.py
│   ├── settings.py             # App settings & LLM config
│   └── models/
│       ├── __init__.py
│       └── llm_config.py      # LLM configuration models
│
├── prompts/                      # Prompt Templates
│   ├── __init__.py
│   ├── business_analyst_persona.py
│   ├── query_optimizer_prompt.py
│   ├── data_extractor_prompt.py
│   └── response_formatter_prompt.py
│
├── scripts/                      # Utility Scripts
│   ├── health_check.py          # System health check
│   └── seed_llm_config.py      # LLM config seeding
│
├── tests/                        # Test Suite
│   ├── __init__.py
│   └── test_pipeline_integration.py
│
├── docs/                         # Documentation
│   ├── archive/
│   └── schemas/                 # Schema documentation
│
├── static/                       # Static Files
│   └── admin.html               # Admin panel
│
├── main.py                       # Entry point
├── requirements.txt              # Dependencies
├── Dockerfile                    # Docker image definition
├── docker-compose.yml            # Docker Compose configuration
└── README.md                     # This file
```

## Technology Stack

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

## Development

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

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Use type hints for all function signatures
- Write docstrings for public methods and classes
- Add unit tests for new features
- Use async/await for I/O operations
- Leverage the factory patterns for tools and providers

## Testing

### Health Check

```bash
python scripts/health_check.py
```

### Integration Tests

```bash
python tests/test_pipeline_integration.py
```

### API Testing

Use the interactive documentation at `http://localhost:8000/docs` or use curl:

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready
```

## License

[Add your license information here]

---

**Built with**: Python, FastAPI, LangGraph, OpenAI, Anthropic, Google Gemini, PostgreSQL, DynamoDB, Redis

**Maintained by**: [Your Team/Organization Name]

For questions, issues, or feature requests, please open an issue on GitHub.
