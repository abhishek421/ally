# AI Analyst Service - Intelligent CRM Query System

## 📋 Overview

A production-ready AI-powered query system that enables natural language interaction with CRM data using LangGraph and dynamic configuration management. This system transforms complex CRM queries into structured data responses through intelligent agent orchestration.

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
│  │  • Formats raw data into JSON                      │    │
│  │  • Applies business logic                         │    │
│  │  • Generates user-friendly responses              │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│           Final Response (JSON)                               │
└──────────────────────────────────────────────────────────────┘
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
- **Status**: 🚧 Placeholder (Needs Implementation)
- **Responsibility**:
  - Execute database queries via tools
  - Handle workspace/tenant isolation
  - Apply role-based access control
  - Aggregate data from multiple sources
  - Handle pagination and large datasets

##### ResponseFormatterAgent (`agents/response_formatter.py`)
- **Status**: 🚧 Placeholder (Needs Implementation)
- **Responsibility**:
  - Format raw data into user-friendly responses
  - Apply business logic for display
  - Generate insights and summaries
  - Structure data for frontend consumption

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
│   ├── data_extractor.py      # 🚧 Placeholder
│   └── response_formatter.py  # 🚧 Placeholder
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
├── models/                       # Data Models
│   └── __init__.py
│
├── utils/                        # Utility Functions
│   └── __init__.py
│
├── tests/                        # Test Suite
│   ├── __init__.py
│   ├── test_query_optimizer.py
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
- DynamoDB table (`EmailSync`)
- Redis instance
- API keys for at least one LLM provider:
  - OpenAI API key (for GPT models)
  - Anthropic API key (for Claude models)
  - Google API key (for Gemini models)

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
# OpenAI API Configuration
OPENAI_API_KEY=REDACTED
MODEL_NAME=gpt-4
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

### Basic Usage

```bash
# Run with example queries
python main.py

# Interactive mode (uncomment in main.py)
# python main.py --interactive
```

### Example Query

**Input:** "With how many companies we have closed deal previous year?"

**Pipeline Flow:**
1. **QueryOptimizerAgent**: Converts to "The user is asking you to fetch and analyze all closed deals from 2023 and return structured information"
2. **DataExtractorAgent**: Uses CompanyTool to query database for companies with closed deals in 2023
3. **ResponseFormatterAgent**: Formats results into JSON response

**Output:** JSON formatted response with extracted data from CRM databases.

## 🛠️ Development

### Current Implementation Status

#### ✅ Completed Components
- [x] LangGraph pipeline framework
- [x] QueryOptimizerAgent with LLM integration
- [x] BaseTool with caching and error handling
- [x] CompanyTool, EmailTool, PeopleTool, WorkspaceTool
- [x] LLM provider adapters (OpenAI, Anthropic, Gemini)
- [x] Database clients (Prisma, DynamoDB, Redis)
- [x] Configuration system with per-agent LLM config
- [x] Tool factory pattern
- [x] Testing framework setup

#### 🚧 In Progress / Needs Implementation
- [ ] DataExtractorAgent implementation
- [ ] ResponseFormatterAgent implementation
- [ ] InteractionTool implementation
- [ ] GroupTool implementation
- [ ] Workspace isolation and RBAC validation
- [ ] FastAPI REST API endpoints
- [ ] Comprehensive test coverage

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
| **AI Orchestration** | LangGraph | Agent workflows & state management |
| **LLM Providers** | OpenAI, Anthropic, Gemini | AI model access |
| **Database (SQL)** | PostgreSQL + Prisma | Primary CRM data store |
| **Database (NoSQL)** | DynamoDB | Email sync data |
| **Cache** | Redis | Query caching & configuration |
| **Schema Validation** | Pydantic | Data validation |

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

### Multi-Provider LLM Support
- Unified interface for multiple LLM providers
- Per-agent provider configuration
- Easy to add new providers

### Flexible Tool System
- Factory pattern for tool creation
- Standardized tool interface
- Built-in caching and error handling
- Workspace isolation support

### Robust Pipeline
- Type-safe state management
- Checkpointing for state persistence
- Sequential agent workflow
- Error recovery mechanisms

### Database Integration
- PostgreSQL via Prisma ORM
- DynamoDB for email data
- Redis for caching
- Connection pooling and health checks

## 🤝 Contributing

This project follows the implementation phases outlined in the roadmap. Current focus is on:
- Implementing DataExtractorAgent
- Implementing ResponseFormatterAgent
- Adding remaining tools (InteractionTool, GroupTool)

## 📄 License

[Add your license information here]
