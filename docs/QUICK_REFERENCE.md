# AI Analyst Agent - Quick Reference Guide

## Project Overview

**Type**: Production-ready CRM query system using LLMs  
**Size**: 52 Python files (~6,400 LOC)  
**Architecture**: FastAPI + LangGraph + Multi-LLM providers  
**Status**: Active development (dev branch)  

## Key Statistics

| Metric | Value |
|--------|-------|
| Agents | 3 (Query Optimizer, Data Extractor, Response Formatter) |
| Tools | 6 (Company, People, Email, Workspace, Interaction, Group) |
| LLM Providers | 3 (OpenAI, Anthropic, Gemini) |
| Databases | 3 (PostgreSQL, DynamoDB, Redis) |
| API Endpoints | 5 main routes |
| Python Files | 52 |
| Lines of Code | 6,400+ |

## Architecture at a Glance

```
Natural Language Query
        ↓
[FastAPI REST API]
        ↓
[LangGraph 3-Stage Pipeline]
  1. QueryOptimizer (parse & structure)
  2. DataExtractor (execute tools in parallel)
  3. ResponseFormatter (format markdown output)
        ↓
[Tools + Databases + LLMs]
        ↓
Formatted Response + Raw Data + Metadata
```

## Core Components

### Agents (3 specialized AI agents)
- **QueryOptimizerAgent**: Parse queries, resolve dates, extract entities
- **DataExtractorAgent**: Plan and execute tool calls, aggregate results
- **ResponseFormatterAgent**: Format output with business analyst persona

### Tools (6 data access abstractions)
- **CompanyTool**: Company search, analytics
- **PeopleTool**: Contact management
- **EmailTool**: Email data retrieval
- **WorkspaceTool**: Workspace operations
- **InteractionTool**: CRM interactions
- **GroupTool**: Contact groups

### Databases (3 technologies)
- **PostgreSQL** (via Prisma): Primary CRM data
- **DynamoDB**: Email sync data
- **Redis**: Query result caching (5-min TTL)

### LLM Providers (3 switchable implementations)
- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Anthropic**: Claude models
- **Gemini**: Google's AI models

## File Organization

```
analyst-ai/
├── adapters/          → LLM provider abstractions
├── agents/            → 3-stage pipeline agents
├── api/               → FastAPI REST endpoints
├── database/          → DB clients (Prisma, DynamoDB, Redis)
├── tools/             → Data access tools
├── graph/             → LangGraph pipeline orchestration
├── config/            → Configuration management
├── prompts/           → System prompts & personas
├── tests/             → Integration tests
├── docs/              → Documentation
├── main.py            → Entry point (server & CLI modes)
├── requirements.txt   → Dependencies
├── Dockerfile         → Container definition
└── docker-compose.yml → Dev environment
```

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web Framework | FastAPI + Uvicorn |
| Agent Orchestration | LangGraph |
| Validation | Pydantic v2 |
| SQL ORM | Prisma |
| Type Hints | Built-in (Python 3.11) |
| Containerization | Docker |
| CI/CD | GitHub Actions → AWS ECR |

## Configuration Quick Start

### Required Environment Variables

```bash
# Database (required)
DATABASE_URL=postgresql://user:pass@host:5432/db

# LLM Config (global - required)
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4

# At least one LLM API key (required)
OPENAI_API_KEY=REDACTED
```

### Optional Environment Variables

```bash
# Per-agent LLM config (overrides global)
QUERY_OPTIMIZER_PROVIDER=openai
QUERY_OPTIMIZER_MODEL=gpt-4
DATA_EXTRACTOR_PROVIDER=anthropic
DATA_EXTRACTOR_MODEL=claude-3-opus
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo

# Redis (caching)
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Key Design Patterns

1. **Factory Pattern** (LLMProviderFactory, ToolFactory)
2. **Strategy Pattern** (Pluggable LLM providers)
3. **Abstract Factory** (BaseTool for tools)
4. **State Machine** (LangGraph pipeline)
5. **Dependency Injection** (FastAPI, agent initialization)
6. **Adapter Pattern** (LLM provider adapters)

## Main API Endpoint

```
POST /api/v1/query
Headers:
  X-Workspace-ID: workspace identifier
  X-User-ID: user identifier
Body:
  {"query": "Show me companies with closed deals from last year"}
Response:
  {
    "success": true,
    "query": "...",
    "result": {
      "formatted_response": "# Companies with Closed Deals...",
      "raw_data": {...},
      "execution_metadata": {...}
    },
    "execution_time_ms": 1250,
    "workspace_id": "...",
    "user_id": "..."
  }
```

## Running the Application

### Development (Docker)
```bash
docker-compose up -d
curl http://localhost:8000/health
# API available at http://localhost:8000/docs
```

### CLI Mode
```bash
python main.py cli
```

### Production
```bash
docker build -f Dockerfile -t analyst-ai:latest .
docker run -d -p 8000:8000 --env-file .env.prod analyst-ai:latest
```

## Critical Issues to Address

### High Priority
1. **Security**: No workspace access validation (stub TODO)
2. **Error Handling**: Missing pipeline error handling
3. **Async**: Incomplete async/await patterns
4. **Authentication**: Header-based auth not secure without HTTPS

### Medium Priority
1. **Testing**: Only integration tests exist
2. **Monitoring**: No observability/metrics
3. **Rate Limiting**: Not implemented
4. **Configuration**: 4-level fallback too complex

### Low Priority
1. **Docker**: Runs as root user
2. **CI/CD**: No semantic versioning
3. **Write Operations**: Not yet implemented

## Performance Characteristics

- **Query Processing**: ~1-2 seconds typical (LLM dependent)
- **Cache Hit**: <100ms with Redis cache
- **Tool Execution**: Parallel with asyncio
- **Response Size**: Markdown + raw data + metadata
- **Concurrent Users**: Limited by LLM rate limits

## Monitoring & Health Checks

Available endpoints:
- `GET /health` - Basic health status
- `GET /ready` - Readiness with service checks
- `GET /admin` - Admin panel

## Deployment Checklist

- [ ] All environment variables configured
- [ ] Database migrations applied
- [ ] LLM API keys validated
- [ ] Redis accessible
- [ ] AWS credentials (if using DynamoDB)
- [ ] HTTPS/TLS configured
- [ ] Rate limiting configured
- [ ] Monitoring/alerting setup
- [ ] Backup procedures documented

## Quick Debugging Tips

1. Check logs: `docker-compose logs -f app`
2. Test health: `curl http://localhost:8000/health`
3. API docs: Visit `http://localhost:8000/docs`
4. Database: Verify DATABASE_URL and Prisma schema
5. LLM: Test with `python scripts/health_check.py`
6. Redis: Check with `redis-cli -p 6380 PING`

## Document Location

Full analysis: `/docs/CODEBASE_ANALYSIS.md`  
Quick reference: This file  
README: Root of project with examples  

---

**Last Updated**: November 5, 2025  
**Repository**: /Users/abhi/Documents/SoftSync/analyst-ai  
**Branch**: dev
