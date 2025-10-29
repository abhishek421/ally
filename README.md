# AI Analyst Service - Intelligent CRM Query System

## 📋 Overview
A production-ready AI-powered query system that enables natural language interaction with CRM data using LangGraph, semantic routing, and dynamic configuration management. This system transforms complex CRM queries into structured data responses through intelligent agent orchestration.

## 🏗️ Architecture Overview

### High-Level System Design
```
┌─────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                      │
│                     (TypeScript / React)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST/GraphQL API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python AI Service (FastAPI)                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Semantic Query Router                  │    │
│  │         (Classify query complexity/type)            │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│    ┏━━━━━━━━━━┻━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓       │
│    ▼                      ▼                          ▼       │
│  ┌──────────┐      ┌─────────────┐         ┌──────────────┐│
│  │  Direct  │      │  Standard   │         │   Complex    ││
│  │   Path   │      │    Path     │         │     Path     ││
│  └────┬─────┘      └──────┬──────┘         └──────┬───────┘│
│       │                   │                        │        │
│       │          ┌────────▼────────┐               │        │
│       │          │ QueryOptimizer  │               │        │
│       │          │     Agent       │    ┌──────────▼──────┐│
│       │          └────────┬────────┘    │ QueryDecomposer ││
│       │                   │             │     Agent       ││
│       │          ┌────────▼────────┐    └────────┬────────┘│
│       │          │ DataExtractor   │             │         │
│       └──────────►     Agent       │◄────────────┘         │
│                  └────────┬────────┘                        │
│                           │                                 │
│                  ┌────────▼────────┐                        │
│                  │ResponseFormatter│                        │
│                  │     Agent       │                        │
│                  └────────┬────────┘                        │
│                           │                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │              LangGraph Orchestration                │    │
│  │  • State Management  • Conditional Routing          │    │
│  │  • Checkpointing     • Error Recovery               │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │                  Tools Layer                        │    │
│  │  workspace_tool │ company_tool │ people_tool        │    │
│  │  deals_tool     │ email_tool   │ analytics_tool     │    │
│  └────────────────────────────────────────────────────┘    │
└───────────────────────┬──────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐    ┌──────────┐    ┌─────────┐
   │PostgreSQL│    │ DynamoDB │    │  Redis  │
   │  (CRM)   │    │ (Emails) │    │ (Cache) │
   └──────────┘    └──────────┘    └─────────┘
```

### Core Components

#### 1. **Semantic Query Router**
- **Purpose**: Classify incoming queries to optimize routing
- **Routes**:
  - **Direct Path**: Simple CRUD operations (no LLM needed)
  - **Standard Path**: Typical queries requiring optimization
  - **Complex Path**: Multi-step reasoning, aggregations, comparisons
- **Performance**: <50ms classification time

#### 2. **LangGraph Agent Workflow**

##### Agent: QueryOptimizer
- **Model**: Claude 3.5 Haiku / Gemini 2.0 Flash
- **Responsibility**: 
  - Parse natural language into structured intent
  - Identify required data entities and fields
  - Resolve ambiguities in user queries
  - Generate optimized query parameters
- **Output**: Structured query object with tool selection

##### Agent: DataExtractor
- **Responsibility**:
  - Execute database queries via tools
  - Handle workspace/tenant isolation
  - Apply role-based access control
  - Aggregate data from multiple sources
  - Handle pagination and large datasets
- **Tools**:
  - `workspace_tool`: Workspace metadata and settings
  - `company_tool`: Company CRUD operations
  - `people_tool`: People/contacts queries
  - `deals_tool`: Deal pipeline operations
  - `email_tool`: Email sync data (DynamoDB)
  - `analytics_tool`: Aggregations and metrics

##### Agent: ResponseFormatter
- **Model**: Claude 3.5 Haiku
- **Responsibility**:
  - Format raw data into user-friendly responses
  - Apply business logic for display
  - Generate insights and summaries
  - Structure data for frontend consumption
- **Output**: JSON response ready for frontend rendering

##### Agent: QueryDecomposer (Complex Path)
- **Responsibility**:
  - Break complex queries into sub-queries
  - Orchestrate multi-step data retrieval
  - Perform comparisons and analysis
  - Synthesize results from multiple sources

#### 3. **Tools Layer**
All tools implement:
- Workspace isolation
- Permission checking
- Error handling with structured responses
- Query caching for performance
- Audit logging

## 📁 Current Project Structure
```
AI-Analyst-RAG/
├── adapters/         # LLM Provider Adapters
│   ├── llm_provider.py
│   ├── provider_factory.py
│   ├── llm_providers/
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── gemini_provider.py
│   │   └── __init__.py
│   └── __init__.py
├── agents/           # Agent implementations
│   ├── query_optimizer.py
│   ├── data_extractor.py
│   └── response_formatter.py
├── tools/            # Data extraction tools
│   ├── base_tool.py
│   ├── companies_tool.py
│   └── emails_tool.py
├── prompts/          # Prompt templates
│   ├── query_optimizer_prompt.py
│   └── __init__.py
├── graph/            # LangGraph pipeline orchestration
│   └── pipeline.py   # Main pipeline definition
├── models/           # Data models
├── config/           # Configuration files
├── database/         # Database connections
├── utils/            # Utility functions
├── tests/            # Test files
├── main.py           # Entry point
└── README.md         # This file
```

## 🚧 Implementation Status

### ✅ Completed
- [x] Basic project structure setup
- [x] LangGraph pipeline framework
- [x] Agent skeleton files
- [x] Tool skeleton files
- [x] Documentation roadmap

### 🚧 In Progress
- [ ] Agent implementations (QueryOptimizer, DataExtractor, ResponseFormatter)
- [ ] Tool implementations (BaseTool, CompaniesTool, EmailsTool)
- [ ] Configuration system
- [ ] Database models and connections

### 📋 Planned (Phase 1-7)
- [ ] Semantic Query Router
- [ ] Dynamic Configuration System
- [ ] Database integration (PostgreSQL, DynamoDB, Redis)
- [ ] Authentication and RBAC
- [ ] Admin API endpoints
- [ ] Observability and monitoring
- [ ] Production deployment

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database
- Redis instance
- Anthropic API key (for Claude models)

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

### Basic Usage
```bash
# Run with a single query
python main.py

# Interactive mode
python main.py --interactive
```

### Example Query
**Input:** "With how many companies we have closed deal previous year?"

**Output:** JSON formatted response with extracted data from your CRM databases.

## 🛠️ Development

### Current Implementation Status
The project is currently in **Phase 1** (Foundation) with basic structure in place. Key components need implementation:

1. **Agent Implementations** - Core logic for QueryOptimizer, DataExtractor, ResponseFormatter
2. **Tool Implementations** - Database query tools with workspace isolation
3. **Configuration System** - Dynamic config management
4. **Database Integration** - PostgreSQL, DynamoDB, Redis connections

### Next Steps
1. Implement agent logic in `agents/` directory
2. Build tool classes in `tools/` directory  
3. Setup database models and connections
4. Implement semantic query router
5. Add dynamic configuration system

## 📊 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Runtime** | Python 3.11+ | Backend language |
| **AI Orchestration** | LangGraph | Agent workflows |
| **LLM** | Claude 3.5 Haiku | Primary AI model |
| **Database** | PostgreSQL | Primary data store |
| **NoSQL** | DynamoDB | Email sync data |
| **Cache** | Redis | Configuration & query cache |
| **API Framework** | FastAPI | REST API (planned) |

## 📚 Documentation

- **[Technical Roadmap](docs/AI_ANALYST_SERVICE_ROADMAP.md)** - Complete implementation guide
- **[Architecture Overview](#architecture-overview)** - System design and components
- **[Project Structure](#current-project-structure)** - File organization

## 🤝 Contributing

This project follows the implementation phases outlined in the roadmap. Current focus is on Phase 1-2: Foundation and Tools Layer.

## 📄 License

[Add your license information here]
## Setup

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configuration

#### Environment Variables
Create a `.env` file in the project root with your API credentials.

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
DATA_EXTRACTOR_MODEL=claude-3-opus
ANTHROPIC_API_KEY=sk-ant-your-key

# Or use Google Gemini
# DATA_EXTRACTOR_PROVIDER=gemini
# DATA_EXTRACTOR_MODEL=gemini-pro
# GOOGLE_API_KEY=your-google-api-key

# ResponseFormatterAgent - Use cheaper model
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo
```

**Important:** The `.env` file is already in `.gitignore` to keep your credentials secure.

The application will automatically load these values at runtime. If no `.env` file is found, it will use empty defaults (which will cause errors when making API calls).

#### Prompt Templates
All prompt templates are stored in the `prompts/` directory as Python modules:
- `prompts/query_optimizer_prompt.py` - Query optimization prompt template
- `prompts/__init__.py` - Exports all prompt templates

You can easily modify or add new prompts by editing the `.py` files in this directory.

#### LLM Provider Adapters
The system supports multiple LLM providers through a unified adapter interface:

**Available Providers:**
- **OpenAI** (`adapters/openai_provider.py`) - Supports GPT-3.5, GPT-4
- **Anthropic** (`adapters/anthropic_provider.py`) - Supports Claude models (Opus, Sonnet, Haiku)
- **Google Gemini** (`adapters/gemini_provider.py`) - Supports Gemini Pro, Gemini Ultra

**How It Works:**
```python
# Each agent can use any provider
from adapters import LLMProviderFactory

# Create a provider from config
config = {
    'provider': 'openai',
    'model': 'gpt-4',
    'api_key': 'sk-...'
}
provider = LLMProviderFactory.create(config)

# Use in agent
agent = QueryOptimizerAgent(llm_provider=provider)
```

**Adding New Providers:**
1. Create a new provider class in `adapters/` that extends `BaseLLMProvider`
2. Implement the `chat()` method
3. Register it in `provider_factory.py`

## Testing

### Run Unit Tests
```bash
python tests/test_query_optimizer.py
```

### Run Integration Tests
```bash
python tests/test_pipeline_integration.py
```

### Run All Tests
```bash
# Run unit tests
python tests/test_query_optimizer.py

# Run integration tests
python tests/test_pipeline_integration.py
```

## Development Status
✅ **QueryOptimizerAgent** - Implemented with pattern-based optimization  
🚧 **DataExtractorAgent** - Needs implementation  
🚧 **ResponseFormatterAgent** - Needs implementation
