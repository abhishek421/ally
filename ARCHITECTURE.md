# AI Analyst System - Architecture Overview

## System Purpose

An intelligent CRM query system that transforms natural language questions into structured data responses. Users can query CRM data across multiple databases using plain English, without needing SQL knowledge.

## Core Architecture

### Multi-Agent AI Pipeline (LangGraph Orchestrated)

The system uses **LangGraph** to orchestrate three specialized agents:

1. **QueryOptimizerAgent** - Converts natural language to optimized queries
   - Resolves time references ("last year" → exact dates)
   - Extracts entities and handles conversation context
   - Location: [agents/query_optimizer.py](agents/query_optimizer.py)

2. **DataExtractorAgent** - Orchestrates multi-database data extraction
   - Plans and executes tool calls using LLM
   - Handles workspace isolation and access control
   - Supports parallel execution and pagination
   - Variants: Static ([agents/data_extractor.py](agents/data_extractor.py)) and Reactive ([agents/reactive_data_extractor.py](agents/reactive_data_extractor.py))

3. **ResponseFormatterAgent** - Formats data into human-readable responses
   - Generates markdown-formatted output
   - Adds business analyst insights
   - Location: [agents/response_formatter.py](agents/response_formatter.py)

**Advanced Components:**
- **OrchestratorAgent** - Analyzes query complexity and selects optimal execution strategy
- **ResultValidator** - Validates extraction results and determines refinement needs
- **QueryRouter** - Fast-path routing for meta queries (help, greetings)

### Data Access Layer (Tools)

Factory-managed tools provide database access with built-in caching and multi-tenancy:

| Tool | Database | Purpose |
|------|----------|---------|
| CompanyTool | PostgreSQL | Company search and analytics |
| PeopleTool | PostgreSQL | Contact management |
| EmailTool | DynamoDB | Email data retrieval |
| InteractionTool | PostgreSQL | CRM interaction tracking |
| WorkspaceTool | PostgreSQL | Workspace information |
| GroupTool | PostgreSQL | Contact group management |

**Features:** Workspace isolation, Redis caching (5min TTL), permission checking, audit logging

Location: [tools/](tools/)

### LLM Provider System

Multi-provider support with factory pattern:

- **OpenAI** (GPT-3.5, GPT-4, GPT-4 Turbo)
- **Anthropic** (Claude Opus, Sonnet, Haiku)
- **Google Gemini** (Gemini Pro, Ultra)

Per-agent LLM configuration supported. Location: [adapters/](adapters/)

### Database Clients

- **PrismaClient** (PostgreSQL) - Primary CRM data store with connection pooling
- **DynamoDBClient** - Email sync data storage
- **RedisClient** - Query result caching and configuration

Location: [database/](database/)

### REST API (FastAPI)

Key endpoints:
- `POST /api/v1/query` - Process natural language query
- `GET/POST /api/v1/conversations` - Manage conversation threads
- `GET /health` & `/ready` - Health checks
- `GET /docs` - Interactive API documentation

Authentication: Header-based (`X-Workspace-ID`, `X-User-ID`) + JWT/Cognito

Location: [api/](api/) & [main.py](main.py)

## Data Flow

```
1. User Query (REST API)
   ↓
2. QueryRouter (meta query check)
   ↓
3. Retrieve conversation context (last 10 messages)
   ↓
4. LangGraph Pipeline:
   QueryOptimizer → DataExtractor → ResultValidator → ResponseFormatter
   ↓
5. Store conversation & return response
```

**Advanced Flow:** OrchestratorAgent analyzes complexity and selects optimal strategy (static vs reactive extraction, skip optimization if unnecessary)

## Technology Stack

- **Runtime:** Python 3.11+
- **Framework:** FastAPI + Uvicorn
- **AI:** LangGraph for orchestration
- **LLMs:** OpenAI, Anthropic, Google Gemini
- **Databases:** PostgreSQL (Prisma ORM), DynamoDB, Redis
- **Validation:** Pydantic v2
- **Auth:** AWS Cognito + JWT
- **Deployment:** Docker + Docker Compose

## Directory Structure

```
analyst-ai/
├── agents/           # AI agent implementations
├── tools/            # Data access tools
├── adapters/         # LLM provider abstractions
├── api/              # REST API layer
├── graph/            # LangGraph pipeline
├── database/         # Database clients
├── config/           # Configuration management
├── prompts/          # Agent prompt templates
├── services/         # Business services
├── utils/            # Utility functions
├── prisma/           # Database schema
└── main.py           # Application entry point
```

## Key Architectural Patterns

1. **Factory Pattern** - LLM providers and tools
2. **Multi-Agent Pipeline** - LangGraph orchestration with state flow
3. **Multi-Tenancy** - Workspace-based data isolation
4. **Caching Strategy** - Redis-powered result caching
5. **Error Handling** - Structured responses with graceful degradation

## Configuration

**Priority:** Per-agent env vars → Global env vars → Database config → Defaults

Example: `QUERY_OPTIMIZER_PROVIDER=openai`, `GLOBAL_LLM_MODEL=gpt-4`

## Security

- JWT authentication (AWS Cognito)
- Workspace membership validation
- Environment-based API key management
- CORS configuration
- Data isolation per workspace

## Current Status

**Implemented:**
- Complete multi-agent pipeline
- 6 specialized CRM tools
- 3 LLM provider integrations
- Multi-database support
- Conversation context management
- Docker deployment ready

**Advanced Features:**
- Intelligent query routing
- Reactive data extraction with Think-Act-Observe-Reflect
- Result validation and refinement loops
- Performance metadata tracking

**Architecture Strengths:** Highly modular, production-ready error handling, scalable multi-tenant design, flexible LLM configuration
