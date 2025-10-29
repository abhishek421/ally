# AI Analyst Service - Technical Roadmap

## 📋 Executive Summary

This document outlines the architecture, implementation phases, and deployment strategy for the AI Analyst Service - a Python-based intelligent query system that enables natural language interaction with CRM data using LangGraph, semantic routing, and dynamic configuration management.

---

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
- **Technology**: Lightweight embeddings or pattern matching
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

---

## 🗄️ Data Architecture

### Database Setup

#### PostgreSQL Schema (Prisma)
```prisma
// Core CRM entities
model Workspace {
  id            String    @id @default(cuid())
  name          String
  settings      Json?
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
}

model Company {
  id            String    @id @default(cuid())
  workspaceId   String
  name          String
  domain        String?
  // ... other fields
}

model Person {
  id            String    @id @default(cuid())
  workspaceId   String
  email         String
  firstName     String?
  lastName      String?
  // ... other fields
}

model Deal {
  id            String    @id @default(cuid())
  workspaceId   String
  companyId     String?
  value         Decimal?
  stage         String
  // ... other fields
}

// AI Service specific tables
model AgentConfig {
  id            String    @id @default(cuid())
  agentName     String    @unique
  systemPrompt  String    @db.Text
  modelName     String
  temperature   Float     @default(0.7)
  maxTokens     Int       @default(1000)
  enabled       Boolean   @default(true)
  version       Int       @default(1)
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
  updatedBy     String?

  @@index([agentName, enabled])
}

model RouterRule {
  id            String    @id @default(cuid())
  patternType   String    // 'keyword', 'embedding', 'regex'
  pattern       String    @db.Text
  routeTo       String    // 'direct', 'standard', 'complex'
  priority      Int       @default(0)
  enabled       Boolean   @default(true)
  createdAt     DateTime  @default(now())

  @@index([enabled, priority])
}

model QueryPattern {
  id              String    @id @default(cuid())
  originalQuery   String    @db.Text
  optimizedQuery  String    @db.Text
  successRate     Float?
  avgLatencyMs    Int?
  timesUsed       Int       @default(0)
  createdAt       DateTime  @default(now())

  @@index([successRate, timesUsed])
}

model AgentMetric {
  id              String    @id @default(cuid())
  agentName       String
  configVersion   Int
  successCount    Int       @default(0)
  failureCount    Int       @default(0)
  avgLatencyMs    Int?
  totalCostUsd    Decimal?  @db.Decimal(10, 4)
  recordedAt      DateTime  @default(now())

  @@index([agentName, recordedAt])
}
```

#### DynamoDB Schema (Email Sync)
```
Table: EmailSync
- PK: workspaceId
- SK: emailId
- Attributes: from, to, subject, snippet, timestamp, threadId
- GSI: timestamp-index for time-based queries
```

#### Redis Cache Structure
```
Keys:
- agent_config:{agent_name} → JSON config (TTL: 1hr)
- query_result:{query_hash} → Cached results (TTL: 5min)
- workspace:{workspace_id}:deals → Deal list cache (TTL: 10min)
```

---

## 🎛️ Dynamic Configuration System

### Overview
A production-ready system enabling **runtime configuration changes** without code deployment, allowing developers and admins to:
- Modify agent prompts and behavior
- Switch between AI models
- Adjust temperature and token limits
- Enable/disable agents or features
- A/B test different configurations
- Rollback to previous versions instantly

### Architecture

```
┌──────────────────────────────────────────────┐
│         Admin Dashboard (Next.js)            │
│  • Edit system prompts                       │
│  • Change model settings (Claude/GPT/Gemini) │
│  • View performance metrics per config       │
│  • A/B test configurations                   │
│  • Rollback to previous versions             │
└────────────────┬─────────────────────────────┘
                 │ Admin API (FastAPI)
                 ▼
┌──────────────────────────────────────────────┐
│         PostgreSQL: Configuration DB         │
│  • agent_configs (prompts, models, params)   │
│  • router_rules (semantic routing patterns)  │
│  • query_patterns (learned optimizations)    │
│  • agent_metrics (performance tracking)      │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│           Redis: Hot Configuration           │
│  • Cached configs (fast access)              │
│  • Pub/Sub for config updates                │
│  • Hot reload without service restart        │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│         Python AI Service Instances          │
│  • Load configs on startup                   │
│  • Subscribe to config update events         │
│  • Hot reload agents when config changes     │
│  • Track metrics for each config version     │
└──────────────────────────────────────────────┘
```

### Configuration Manager Implementation

```python
class ConfigManager:
    """
    Manages dynamic agent configurations with hot reloading.
    Configs stored in PostgreSQL, cached in Redis, pub/sub for updates.
    """
    
    def __init__(self, db: Session, redis_client: Redis):
        self.db = db
        self.redis = redis_client
        self.configs: Dict[str, AgentConfig] = {}
        self._load_configs()
        self._subscribe_to_updates()
    
    def get_config(self, agent_name: str) -> AgentConfig:
        """Get config with Redis cache fallback"""
        # Check memory cache
        if agent_name in self.configs:
            return self.configs[agent_name]
        
        # Check Redis cache
        cached = self.redis.get(f"agent_config:{agent_name}")
        if cached:
            return AgentConfig.parse_raw(cached)
        
        # Load from database
        return self._reload_config(agent_name)
    
    def update_config(self, agent_name: str, updates: dict, updated_by: str):
        """
        Update config and notify all service instances.
        Changes take effect within 5 seconds across all instances.
        """
        config = self.db.query(AgentConfig).filter_by(
            agent_name=agent_name
        ).first()
        
        # Update fields
        for key, value in updates.items():
            setattr(config, key, value)
        
        config.version += 1
        config.updated_at = datetime.now()
        config.updated_by = updated_by
        self.db.commit()
        
        # Invalidate cache
        self.redis.delete(f"agent_config:{agent_name}")
        
        # Notify all instances via pub/sub
        self.redis.publish('agent_config_updates', agent_name)
        
        return config
```

### What Can Be Configured Without Code Changes

| Configuration | Description | Example Values |
|--------------|-------------|----------------|
| **System Prompt** | Agent personality and instructions | "You are a helpful CRM assistant..." |
| **Model Name** | Which LLM to use | `claude-3-5-haiku`, `gpt-4o-mini`, `gemini-2.0-flash` |
| **Temperature** | Creativity vs determinism | `0.0` (deterministic) to `1.0` (creative) |
| **Max Tokens** | Response length limit | `500`, `1000`, `2000` |
| **Enabled** | Agent on/off switch | `true`, `false` |
| **Tools** | Which tools agent can access | `["company_tool", "deals_tool"]` |
| **Timeout** | Max execution time | `5000ms`, `10000ms` |
| **Retry Logic** | Failure retry attempts | `{attempts: 3, backoff: 'exponential'}` |

### Admin API Endpoints

```python
# List all agent configurations
GET /admin/configs

# Get specific agent configuration
GET /admin/configs/{agent_name}

# Update agent configuration (hot reload)
PUT /admin/configs/{agent_name}
Body: {
  "systemPrompt": "Updated instructions...",
  "modelName": "claude-3-5-haiku",
  "temperature": 0.8
}

# Rollback to previous version
POST /admin/configs/{agent_name}/rollback
Body: { "version": 5 }

# Get performance metrics for config versions
GET /admin/metrics/{agent_name}?days=7

# A/B test configurations
POST /admin/configs/{agent_name}/ab-test
Body: {
  "configA": { "temperature": 0.7 },
  "configB": { "temperature": 0.9 },
  "splitRatio": 0.5
}
```

### Advanced Features

#### 1. Auto-Learning System
Automatically cache successful query optimizations to skip LLM calls for repeated patterns:

```python
# After 10+ successful uses of same query optimization
if query_pattern.times_used > 10 and query_pattern.success_rate > 0.8:
    # Use cached optimization (0ms, $0 cost)
    return query_pattern.optimized_query
else:
    # Use LLM for optimization
    return query_optimizer_agent.invoke(query)
```

#### 2. Workspace-Specific Configs
Different configurations for different customer tiers:

```python
# Enterprise customers get Claude Sonnet
if workspace.tier == "enterprise":
    config = get_config("query_optimizer", tier="enterprise")
else:
    config = get_config("query_optimizer", tier="standard")
```

#### 3. Gradual Rollouts
Test new configurations on subset of users before full deployment:

```python
# Route 10% of traffic to new config version
if hash(workspace_id) % 100 < 10:
    config = get_config_version("query_optimizer", version=2)
else:
    config = get_config_version("query_optimizer", version=1)
```

---

## 📁 Project Structure

```
ai-analyst-service/
├── app/
│   ├── main.py                      # FastAPI application entry
│   ├── config.py                    # Settings and environment
│   │
│   ├── agents/                      # LangGraph agents
│   │   ├── __init__.py
│   │   ├── query_optimizer.py      # QueryOptimizer agent
│   │   ├── data_extractor.py       # DataExtractor agent
│   │   ├── response_formatter.py   # ResponseFormatter agent
│   │   └── query_decomposer.py     # Complex query handler
│   │
│   ├── routers/                     # Semantic routing
│   │   ├── __init__.py
│   │   ├── semantic_router.py      # Query classification
│   │   └── route_patterns.py       # Pattern definitions
│   │
│   ├── tools/                       # Agent tools
│   │   ├── __init__.py
│   │   ├── base_tool.py            # Base tool class
│   │   ├── workspace_tool.py
│   │   ├── company_tool.py
│   │   ├── people_tool.py
│   │   ├── deals_tool.py
│   │   ├── email_tool.py
│   │   └── analytics_tool.py
│   │
│   ├── graph/                       # LangGraph workflows
│   │   ├── __init__.py
│   │   ├── agent_graph.py          # Main workflow definition
│   │   ├── state.py                # State schema
│   │   └── nodes.py                # Node implementations
│   │
│   ├── models/                      # Database models
│   │   ├── __init__.py
│   │   ├── database.py             # Prisma client setup
│   │   └── schemas.py              # Pydantic schemas
│   │
│   ├── core/                        # Core utilities
│   │   ├── __init__.py
│   │   ├── config_manager.py       # Dynamic config system
│   │   ├── cache.py                # Redis caching
│   │   ├── auth.py                 # JWT authentication
│   │   ├── rbac.py                 # Role-based access control
│   │   └── monitoring.py           # Metrics and logging
│   │
│   ├── api/                         # API routes
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── query.py            # Main query endpoint
│   │   │   └── admin.py            # Admin config endpoints
│   │   └── dependencies.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── embeddings.py           # For semantic routing
│       ├── metrics.py              # Performance tracking
│       └── validators.py
│
├── prisma/
│   ├── schema.prisma               # Database schema
│   └── migrations/                 # Migration history
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/
│   ├── seed_db.py                  # Seed development data
│   ├── migrate.py                  # Run migrations
│   └── seed_configs.py             # Initialize agent configs
│
├── .env.example                    # Environment template
├── .gitignore
├── docker-compose.yml              # Local development
├── Dockerfile                      # Production image
├── pyproject.toml                  # Poetry dependencies
├── requirements.txt                # Pip dependencies
└── README.md
```

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1-2)

#### Goals
- Setup project infrastructure
- Database connectivity
- Basic FastAPI server
- Authentication

#### Tasks
- [ ] Initialize Python project with Poetry
- [ ] Setup Prisma with PostgreSQL connection
- [ ] Create initial database schema
- [ ] Run Prisma migrations
- [ ] Setup FastAPI application structure
- [ ] Implement JWT authentication middleware
- [ ] Configure environment variables
- [ ] Setup logging and error handling
- [ ] Health check endpoints (`/health`, `/ready`)
- [ ] Docker setup for local development

#### Deliverables
- Running FastAPI server on localhost:8000
- Database migrations applied
- Basic authentication working
- API documentation at `/docs`

---

### Phase 2: Tools Layer (Week 2-3)

#### Goals
- Implement database query tools
- Workspace isolation
- Permission checking
- Basic caching

#### Tasks
- [ ] Create base tool class with common functionality
- [ ] Implement `workspace_tool`
  - Get workspace settings
  - Validate workspace access
- [ ] Implement `company_tool`
  - List companies
  - Get company by ID
  - Search companies
- [ ] Implement `people_tool`
  - List people
  - Get person by ID/email
  - Search people
- [ ] Implement `deals_tool`
  - List deals
  - Get deal by ID
  - Filter by stage/value
- [ ] Implement `email_tool` (DynamoDB)
  - Query emails by person
  - Query emails by date range
  - Full-text search
- [ ] Add Redis caching layer
- [ ] Implement RBAC (role-based access control)
- [ ] Unit tests for all tools

#### Deliverables
- 6 working tools with comprehensive coverage
- Workspace isolation enforced
- Tool response caching
- 80%+ test coverage

---

### Phase 3: Semantic Router (Week 3-4)

#### Goals
- Query classification system
- Pattern-based routing
- Performance optimization for simple queries

#### Tasks
- [ ] Design router rule schema in database
- [ ] Implement pattern matching engine
  - Keyword-based detection
  - Regex patterns
  - Embedding-based similarity (optional)
- [ ] Create route classification logic
  - Direct: Simple CRUD patterns
  - Standard: Typical queries
  - Complex: Multi-step reasoning
- [ ] Build rule management API
  - Add/update/delete rules
  - Priority ordering
- [ ] Implement direct query executor (bypass agents)
- [ ] Add router metrics tracking
- [ ] Performance benchmarks

#### Deliverables
- Working semantic router with 90%+ accuracy
- Sub-50ms classification time
- Direct path for simple queries (no LLM calls)
- Admin API for managing rules

---

### Phase 4: LangGraph Agent Implementation (Week 4-6)

#### Goals
- Build all LangGraph agents
- Implement workflow orchestration
- State management

#### Tasks

##### QueryOptimizer Agent
- [ ] Define agent configuration
- [ ] Implement system prompt
- [ ] Add tool schema awareness
- [ ] Test query parsing and optimization
- [ ] Handle ambiguous queries

##### DataExtractor Agent
- [ ] Tool binding and invocation
- [ ] Multi-tool coordination
- [ ] Error handling and retries
- [ ] Result aggregation
- [ ] Pagination support

##### ResponseFormatter Agent
- [ ] Format data for frontend consumption
- [ ] Generate natural language summaries
- [ ] Handle different response types (list, detail, analysis)
- [ ] Add insights and recommendations

##### QueryDecomposer Agent (Complex Path)
- [ ] Break down complex queries
- [ ] Sub-query orchestration
- [ ] Result synthesis
- [ ] Handle comparisons and aggregations

##### LangGraph Workflow
- [ ] Define state schema
- [ ] Build graph with conditional edges
- [ ] Implement routing logic
- [ ] Add checkpointing for debugging
- [ ] Error recovery mechanisms

#### Deliverables
- 4 fully functional agents
- End-to-end workflow execution
- State persistence and recovery
- Comprehensive logging

---

### Phase 5: Dynamic Configuration System (Week 6-7)

#### Goals
- Database-driven configuration
- Hot reload capability
- Admin UI for config management

#### Tasks
- [ ] Create `agent_configs` table schema
- [ ] Create `router_rules` table schema
- [ ] Create `query_patterns` table schema
- [ ] Create `agent_metrics` table schema
- [ ] Implement ConfigManager class
  - Load configs on startup
  - Redis caching
  - Pub/sub for updates
  - Hot reload logic
- [ ] Build Admin API endpoints
  - List/get/update configs
  - Rollback to previous versions
  - Get performance metrics
- [ ] Integrate with agents
  - Load prompts from DB
  - Respect enabled/disabled flags
  - Use configured models
- [ ] Create simple admin UI (Next.js)
  - Config editor
  - Metrics dashboard
  - Version history
- [ ] Add A/B testing capability

#### Deliverables
- Fully functional dynamic config system
- Hot reload working (changes live in <5s)
- Admin UI for non-technical users
- A/B testing framework

---

### Phase 6: Observability & Optimization (Week 7-8)

#### Goals
- Comprehensive logging
- Performance monitoring
- Cost tracking
- Query optimization

#### Tasks
- [ ] Integrate LangSmith for agent tracing
- [ ] Add structured logging (JSON format)
- [ ] Implement metrics collection
  - Query latency
  - Agent execution time
  - Tool call duration
  - Success/failure rates
  - Cost per query
- [ ] Build metrics dashboard
- [ ] Implement auto-learning system
  - Cache successful query patterns
  - Skip LLM for repeated queries
- [ ] Add performance alerts
- [ ] Optimize database queries
- [ ] Tune Redis caching strategy
- [ ] Load testing and profiling

#### Deliverables
- Full observability stack
- Metrics dashboard
- Auto-learning system reducing costs by 30%+
- Performance optimization report

---

### Phase 7: Production Readiness (Week 8-9)

#### Goals
- Security hardening
- Rate limiting
- Error handling
- Documentation

#### Tasks
- [ ] Implement rate limiting per workspace
- [ ] Add request validation and sanitization
- [ ] Security audit (SQL injection, etc.)
- [ ] Comprehensive error handling
- [ ] Add circuit breakers for external services
- [ ] API documentation (OpenAPI/Swagger)
- [ ] User guide and examples
- [ ] Deployment documentation
- [ ] Disaster recovery procedures
- [ ] Load testing (1000+ req/min)
- [ ] Penetration testing

#### Deliverables
- Production-ready service
- Security audit passed
- Complete documentation
- Load test results

---

## 🌐 Deployment Strategy

### Infrastructure Options

#### Option 1: AWS (Recommended for Scale)

**Architecture:**
```
┌─────────────────┐
│   CloudFront    │ (CDN)
└────────┬────────┘
         │
┌────────▼────────┐
│  ALB / API GW   │ (Load Balancer)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│  ECS  │ │  ECS  │ (Python Service)
│ Task1 │ │ Task2 │
└───┬───┘ └──┬────┘
    │        │
    └────┬───┘
         │
    ┌────▼────────────┐
    │                 │
┌───▼────┐  ┌────▼────┐  ┌──────▼──────┐
│   RDS  │  │DynamoDB │  │ElastiCache  │
│(Postgres)│ (Emails)│  │  (Redis)    │
└─────────┘  └─────────┘  └─────────────┘
```

**Services:**
- **Compute**: ECS Fargate (auto-scaling containers)
- **Database**: RDS PostgreSQL (Multi-AZ for HA)
- **NoSQL**: DynamoDB (email sync data)
- **Cache**: ElastiCache Redis (config + query cache)
- **Load Balancer**: Application Load Balancer
- **CDN**: CloudFront (if serving frontend)
- **Secrets**: AWS Secrets Manager
- **Monitoring**: CloudWatch + X-Ray
- **CI/CD**: GitHub Actions → ECR → ECS

**Cost Estimate** (USD/month):
- ECS Fargate (2 tasks, 1 vCPU, 2GB): ~$50
- RDS PostgreSQL (db.t4g.medium): ~$100
- DynamoDB (on-demand): ~$25
- ElastiCache (cache.t4g.small): ~$35
- ALB: ~$20
- Data transfer: ~$20
- **Total**: ~$250/month

**Deployment Steps:**
1. Build Docker image
2. Push to ECR (Elastic Container Registry)
3. Update ECS task definition
4. Deploy new revision (rolling update)
5. Monitor CloudWatch metrics

**GitHub Actions Workflow:**
```yaml
name: Deploy to AWS ECS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to ECR
        run: |
          aws ecr get-login-password --region us-east-1 | \
          docker login --username AWS --password-stdin $ECR_REGISTRY
      
      - name: Build and push image
        run: |
          docker build -t ai-analyst-service .
          docker tag ai-analyst-service:latest $ECR_REGISTRY/ai-analyst-service:latest
          docker push $ECR_REGISTRY/ai-analyst-service:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster ai-analyst-cluster \
            --service ai-analyst-service \
            --force-new-deployment
```

---

#### Option 2: Render (Recommended for Quick Start)

**Services:**
- **Web Service**: Python FastAPI (auto-deploy from Git)
- **PostgreSQL**: Managed PostgreSQL database
- **Redis**: Managed Redis instance
- **Background Workers**: Optional for async tasks

**Cost Estimate** (USD/month):
- Web Service (Standard): ~$25
- PostgreSQL (Starter): ~$20
- Redis (Basic): ~$10
- **Total**: ~$55/month

**Deployment Steps:**
1. Connect GitHub repository to Render
2. Configure environment variables
3. Set build command: `pip install -r requirements.txt && prisma generate`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Auto-deploy on Git push

**Pros:**
- ✅ Simplest deployment (Git push = deploy)
- ✅ Managed database and Redis
- ✅ Built-in SSL certificates
- ✅ Great for MVP/prototyping

**Cons:**
- ❌ Limited scaling options vs AWS
- ❌ No DynamoDB (would need MongoDB/PostgreSQL JSON)

---

#### Option 3: Railway (Good Middle Ground)

**Services:**
- **Python Service**: FastAPI application
- **PostgreSQL Plugin**: Database
- **Redis Plugin**: Caching
- **Environment Management**: Per-branch deployments

**Cost Estimate** (USD/month):
- Service usage: ~$40
- PostgreSQL: ~$15
- Redis: ~$5
- **Total**: ~$60/month

**Deployment:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Deploy
railway up
```

**Pros:**
- ✅ Developer-friendly
- ✅ Preview deployments for PRs
- ✅ Easy service linking
- ✅ Good observability

---

#### Option 4: Docker + DigitalOcean/Linode

**Setup:**
- 1x App Platform service (Python + Redis)
- 1x Managed PostgreSQL database

**Cost Estimate** (USD/month):
- App Platform (Basic): ~$12
- PostgreSQL (Basic): ~$15
- **Total**: ~$27/month

**Pros:**
- ✅ Very cost-effective
- ✅ Managed services
- ✅ Good performance

---

### Recommended Stack by Stage

| Stage | Platform | Why |
|-------|----------|-----|
| **MVP/Prototype** | Render | Fastest to deploy, managed everything |
| **Production (Small)** | Railway | Good balance of features and simplicity |
| **Production (Scale)** | AWS ECS | Enterprise features, auto-scaling, full control |
| **Budget** | DigitalOcean | Cost-effective, good enough for most use cases |

---

### Deployment Checklist

#### Pre-Deployment
- [ ] All tests passing (unit + integration + e2e)
- [ ] Environment variables documented
- [ ] Database migrations ready
- [ ] Seed data for agent configs prepared
- [ ] Performance benchmarks completed
- [ ] Security audit passed
- [ ] API documentation up-to-date

#### Initial Deployment
- [ ] Setup database (PostgreSQL + DynamoDB if AWS)
- [ ] Run migrations: `prisma migrate deploy`
- [ ] Seed agent configs: `python scripts/seed_configs.py`
- [ ] Configure Redis connection
- [ ] Set environment variables (API keys, DB URLs)
- [ ] Deploy application
- [ ] Verify health checks: `GET /health`
- [ ] Test authentication flow
- [ ] Test sample queries

#### Post-Deployment
- [ ] Setup monitoring and alerts
- [ ] Configure log aggregation
- [ ] Test error scenarios
- [ ] Load testing
- [ ] Setup automated backups
- [ ] Document rollback procedure

#### Ongoing
- [ ] Monitor performance metrics
- [ ] Review error logs daily
- [ ] Track API usage and costs
- [ ] Optimize slow queries
- [ ] Update agent configs based on feedback

---

## 📊 Success Metrics

### Performance Targets

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Query Latency (p95)** | <2s | CloudWatch/Datadog |
| **Router Classification** | <50ms | Custom metrics |
| **Direct Path Queries** | 70%+ | Router analytics |
| **Agent Success Rate** | >95% | LangSmith traces |
| **Cache Hit Rate** | >60% | Redis stats |
| **Cost per Query** | <$0.01 | Cost tracking table |

### Business Metrics

- **User Satisfaction**: >4.5/5 rating
- **Query Success Rate**: >95% queries answered correctly
- **Adoption Rate**: 60%+ of CRM users using AI Analyst monthly
- **Time Saved**: 5+ hours per user per month

---

## 🔐 Security Considerations

### Authentication & Authorization
- JWT tokens from frontend
- Workspace-level isolation
- Role-based access control (RBAC)
- API key rotation for LLM providers

### Data Protection
- Encrypt sensitive data at rest (RDS encryption)
- TLS for all data in transit
- No logging of PII in application logs
- Regular security audits

### Rate Limiting
- Per workspace: 100 queries/hour
- Per user: 20 queries/5min
- Admin endpoints: IP whitelisting

### Input Validation
- Sanitize all user inputs
- SQL injection prevention (Prisma protects)
- Prompt injection detection
- Max query length limits

---

## 🛠️ Technology Stack Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Runtime** | Python | 3.11+ | Backend language |
| **API Framework** | FastAPI | 0.100+ | REST API |
| **ORM** | Prisma | Latest | Database queries |
| **AI Orchestration** | LangGraph | Latest | Agent workflows |
| **LLM** | Claude 3.5 Haiku | Latest | Primary AI model |
| **Database** | PostgreSQL | 15+ | Primary data store |
| **NoSQL** | DynamoDB | - | Email sync data |
| **Cache** | Redis | 7+ | Configuration & query cache |
| **Embeddings** | sentence-transformers | Latest | Semantic routing (optional) |
| **Monitoring** | LangSmith | Latest | Agent observability |
| **Testing** | Pytest | Latest | Unit & integration tests |
| **CI/CD** | GitHub Actions | - | Automated deployment |

---

## 📚 Key Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.100.0"
uvicorn = "^0.23.0"
prisma = "^0.11.0"
langgraph = "^0.0.20"
langchain-anthropic = "^0.1.0"
langchain-google-genai = "^0.1.0"
redis = "^5.0.0"
boto3 = "^1.28.0"  # For DynamoDB
pydantic = "^2.0.0"
python-jose = "^3.3.0"  # JWT
passlib = "^1.7.4"  # Password hashing
python-multipart = "^0.0.6"
httpx = "^0.24.0"
sentence-transformers = "^2.2.0"  # Optional: for embeddings

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
black = "^23.7.0"
ruff = "^0.0.280"
mypy = "^1.4.0"
```

---

## 🎯 Next Steps

1. **Week 1**: Setup project, database, FastAPI basics
2. **Week 2-3**: Build tools layer with comprehensive coverage
3. **Week 3-4**: Implement semantic router
4. **Week 4-6**: Build LangGraph agents and workflow
5. **Week 6-7**: Dynamic configuration system
6. **Week 7-8**: Observability and optimization
7. **Week 8-9**: Production hardening and deployment

---

## 📞 Support & Resources

- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Prisma Python**: https://prisma-client-py.readthedocs.io/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Anthropic API**: https://docs.anthropic.com/

---

## 📝 Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-27 | Initial roadmap | Development Team |

---

**Ready to build! 🚀**

This roadmap provides a complete blueprint for implementing your AI Analyst service with LangGraph, semantic routing, dynamic configuration, and production-ready deployment strategies.
