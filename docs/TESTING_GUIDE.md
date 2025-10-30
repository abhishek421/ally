# AI Analyst RAG System - Complete Testing Guide

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Initial Configuration](#initial-configuration)
5. [Testing Individual Components](#testing-individual-components)
6. [Testing the Full Pipeline](#testing-the-full-pipeline)
7. [Advanced Testing Scenarios](#advanced-testing-scenarios)
8. [Troubleshooting](#troubleshooting)
9. [Quick Reference](#quick-reference)

---

## Prerequisites

### Required Software

Before you begin testing, ensure you have the following installed:

1. **Python 3.11+**
   ```bash
   python --version  # Should show 3.11 or higher
   ```

2. **PostgreSQL Database**
   - Install PostgreSQL (version 12 or higher)
   - Ensure PostgreSQL service is running
   - Note the database name, username, password, and port (default: 5432)

3. **Redis Server**
   - Install Redis (version 6.0 or higher)
   - Ensure Redis service is running
   - Default port: 6379

4. **DynamoDB** (Optional - for email sync data)
   - AWS account with DynamoDB access, OR
   - Local DynamoDB instance for development

5. **LLM API Keys** (at least one required)
   - **OpenAI API Key**: Get from https://platform.openai.com/api-keys
   - **Anthropic API Key**: Get from https://console.anthropic.com/
   - **Google API Key**: Get from https://makersuite.google.com/app/apikey

### Verify Prerequisites

Run these commands to check your setup:

```bash
# Check Python version
python --version

# Check PostgreSQL (macOS/Linux)
psql --version

# Check Redis
redis-cli ping  # Should return "PONG"

# Check if PostgreSQL is running
pg_isready  # Should return "accepting connections"
```

---

## Environment Setup

### Step 1: Clone and Navigate to Project

```bash
cd /Users/abhi/Documents/SoftSync/analyst-ai
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Verify installation
pip list | grep -E "(langgraph|openai|anthropic|prisma|redis)"
```

### Step 4: Create Environment File

Create a `.env` file in the project root:

```bash
touch .env
```

Add the following configuration to `.env`:

```bash
# ============================================================================
# LLM Provider Configuration
# ============================================================================
# At minimum, configure ONE provider below

# OpenAI Configuration (Recommended for beginners)
OPENAI_API_KEY=REDACTED
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4

# Optional: Anthropic Configuration
OPENAI_API_KEY=REDACTED
# DATA_EXTRACTOR_PROVIDER=anthropic
# DATA_EXTRACTOR_MODEL=claude-3-opus-20240229

# Optional: Google Gemini Configuration
# GOOGLE_API_KEY=your-google-api-key-here
# QUERY_OPTIMIZER_PROVIDER=gemini
# QUERY_OPTIMIZER_MODEL=gemini-pro

# ============================================================================
# Database Configuration
# ============================================================================

# PostgreSQL Database URL
# Format: postgresql://username:password@host:port/database_name
DATABASE_URL=postgresql://postgres:password@localhost:5432/analyst_ai

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ============================================================================
# AWS Configuration (for DynamoDB - Optional)
# ============================================================================
# AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=REDACTED
AWS_SECRET_ACCESS_KEY=REDACTED
```

**Important**: Replace the placeholder values with your actual credentials:
OPENAI_API_KEY=REDACTED
- Replace `postgres:password@localhost:5432/analyst_ai` with your PostgreSQL connection string
- Update Redis host/port if using a remote instance

### Step 5: Verify Environment Variables

```bash
# Load environment variables
source .env  # On macOS/Linux
# Or use: export $(cat .env | xargs)

# Verify key variables are set
OPENAI_API_KEY=REDACTED
echo $DATABASE_URL    # Should show your database URL
```

---

## Database Setup

### Step 1: Create PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE analyst_ai;

# Verify database was created
\l

# Exit psql
\q
```

### Step 2: Setup Prisma Schema

The Prisma schema is already configured in `prisma/schema.prisma`. Now we need to:

1. **Generate Prisma Client**
   ```bash
   # Install Prisma CLI if not already installed
   pip install prisma

   # Generate Prisma client
   prisma generate

   # This creates the Prisma client based on schema.prisma
   ```

2. **Push Schema to Database** (Creates tables)
   ```bash
   # Push schema to database (creates tables)
   prisma db push

   # Verify tables were created
   psql -U postgres -d analyst_ai -c "\dt"
   # Should show: GlobalLLMConfig and AgentLLMConfig tables
   ```

### Step 3: Test Database Connection

Create a test script `test_db_connection.py`:

```python
import asyncio
from database.prisma_client import prisma_client

async def test_connection():
    try:
        await prisma_client.connect()
        print("✅ Database connection successful!")
        
        # Test query
        client = await prisma_client.get_client()
        count = await client.globalllmconfig.count()
        print(f"✅ Database query successful! GlobalLLMConfig count: {count}")
        
        await prisma_client.disconnect()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
```

Run the test:

```bash
python test_db_connection.py
```

Expected output:
```
✅ Database connection successful!
✅ Database query successful! GlobalLLMConfig count: 0
```

### Step 4: Test Redis Connection

Create a test script `test_redis_connection.py`:

```python
from database.redis_client import redis_client

def test_connection():
    try:
        # Test connection
        redis_client.set("test_key", "test_value")
        value = redis_client.get("test_key")
        
        if value == "test_value":
            print("✅ Redis connection successful!")
        else:
            print("❌ Redis test failed: value mismatch")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")

if __name__ == "__main__":
    test_connection()
```

Run the test:

```bash
python test_redis_connection.py
```

Expected output:
```
✅ Redis connection successful!
```

---

## Initial Configuration

### Step 1: Seed LLM Configuration

The system needs initial LLM configuration in the database. Run the seeding script:

```bash
python scripts/seed_llm_config.py
```

Expected output:
```
INFO:__main__:Starting LLM configuration seeding...
INFO:__main__:Connected to database
INFO:__main__:Created default global LLM config: openai/gpt-4
INFO:__main__:Created agent config for 'query_optimizer': inherit/inherit
INFO:__main__:Created agent config for 'data_extractor': inherit/inherit
INFO:__main__:Created agent config for 'response_formatter': inherit/gpt-3.5-turbo
INFO:__main__:LLM configuration seeding completed successfully
INFO:__main__:Disconnected from database
INFO:__main__:Seeding completed!
```

### Step 2: Verify Configuration

Query the database to verify configuration was created:

```bash
psql -U postgres -d analyst_ai

# Check global config
SELECT * FROM "GlobalLLMConfig";

# Check agent configs
SELECT * FROM "AgentLLMConfig";

# Exit
\q
```

You should see:
- 1 row in `GlobalLLMConfig` with provider='openai', model='gpt-4'
- 3 rows in `AgentLLMConfig` for query_optimizer, data_extractor, and response_formatter

---

## Testing Individual Components

### Test 1: Query Optimizer Agent

The QueryOptimizerAgent converts natural language queries into structured queries.

**Run the test:**

```bash
python tests/test_query_optimizer.py
```

**Expected Output:**
```
############################################################
# QueryOptimizerAgent Tests
############################################################

============================================================
Test 1: Email Query with Person Info
============================================================
Input:  what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}
Output: [Optimized query showing structured intent]
✓ Test passed

============================================================
Test 2: Deal Query
============================================================
Input:  With how many companies we have closed deal previous year?
Output: [Optimized query with date resolution]
✓ Test passed

...

============================================================
✓ All tests passed!
============================================================
```

**What This Tests:**
- ✅ Agent initialization
- ✅ Natural language to structured query conversion
- ✅ Person information extraction
- ✅ Date/time resolution (e.g., "previous year" → actual dates)
- ✅ Query intent understanding

**If Tests Fail:**
OPENAI_API_KEY=REDACTED
- Verify you have sufficient API credits
- Check internet connection
- Review error messages for specific issues

### Test 2: Individual Tool Tests

Test individual tools to ensure they can connect to databases and retrieve data.

**Test Company Tool:**

Create `test_company_tool.py`:

```python
import asyncio
from tools.company_tool import CompanyTool

async def test_company_tool():
    tool = CompanyTool()
    
    # Test workspace isolation
    workspace_id = "test-workspace-123"
    user_id = "test-user-456"
    
    # Test LIST operation
    result = await tool.execute(
        query_type="LIST",
        workspace_id=workspace_id,
        user_id=user_id,
        limit=10
    )
    
    print(f"Tool Result: {result}")
    print(f"Success: {result.success}")
    print(f"Data: {result.data}")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_company_tool())
```

**Run the test:**

```bash
python test_company_tool.py
```

**Expected Output:**
```
Tool Result: ToolResult(success=True, data={...}, error=None)
Success: True
Data: {'companies': [...], 'total': 0}
```

**What This Tests:**
- ✅ Tool initialization
- ✅ Database connection
- ✅ Workspace isolation
- ✅ Query execution
- ✅ Result formatting

**Test Email Tool:**

Similar pattern - create `test_email_tool.py`:

```python
import asyncio
from tools.emails_tool import EmailsTool

async def test_email_tool():
    tool = EmailsTool()
    
    workspace_id = "test-workspace-123"
    user_id = "test-user-456"
    
    # Test SEARCH operation
    result = await tool.execute(
        query_type="SEARCH",
        workspace_id=workspace_id,
        user_id=user_id,
        query_params={"limit": 5}
    )
    
    print(f"Tool Result: {result}")
    return result

if __name__ == "__main__":
    asyncio.run(test_email_tool())
```

**Test People Tool:**

```python
import asyncio
from tools.people_tool import PeopleTool

async def test_people_tool():
    tool = PeopleTool()
    
    workspace_id = "test-workspace-123"
    user_id = "test-user-456"
    
    result = await tool.execute(
        query_type="LIST",
        workspace_id=workspace_id,
        user_id=user_id,
        limit=10
    )
    
    print(f"Tool Result: {result}")
    return result

if __name__ == "__main__":
    asyncio.run(test_people_tool())
```

---

## Testing the Full Pipeline

### Test 1: Integration Test (No LangGraph)

This test verifies the pipeline logic without requiring LangGraph state management.

**Run the test:**

```bash
python tests/test_pipeline_integration.py
```

**Expected Output:**
```
============================================================
AI Analyst Pipeline - Integration Tests
============================================================

============================================================
Integration Test 1: Email Query Pipeline
============================================================
============================================================
Integration Test: Query Optimizer -> Mock Data Extractor -> Mock Formatter
============================================================

Step 1 - Original Query: what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}

Step 2 - Optimized Query: [Structured query from QueryOptimizerAgent]

Step 3 - Extracted Data: {'emails': [...], 'person': {...}}

Step 4 - Final Response: {'query': ..., 'data': ..., 'formatted_response': {...}}

✓ Pipeline logic executed successfully
✓ Result structure is valid
✓ Email pipeline test passed

============================================================
Integration Test 2: Deal Query Pipeline
============================================================
...

============================================================
✓ All integration tests passed!
============================================================
```

**What This Tests:**
- ✅ End-to-end pipeline flow
- ✅ Query optimization step
- ✅ Data extraction step (mocked)
- ✅ Response formatting step (mocked)
- ✅ Result structure validation

### Test 2: Full Pipeline with LangGraph

This test runs the complete LangGraph pipeline with all agents.

**Run the main application:**

```bash
python main.py
```

**Expected Output:**
```
INFO:__main__:Initializing application configuration...
INFO:__main__:Application initialized successfully
INFO:__main__:Global LLM config: openai/gpt-4
INFO:__main__:Agent 'query_optimizer' config: openai/gpt-4 (source: db_global)
INFO:__main__:Agent 'data_extractor' config: openai/gpt-4 (source: db_global)
INFO:__main__:Agent 'response_formatter' config: openai/gpt-3.5-turbo (source: db_agent)

============================================================
Original Query: what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}
============================================================

Pipeline Result:
{
  'query': '[Optimized query]',
  'data': {'extracted_data': {...}},
  'formatted_response': 'JSON formatted response'
}

============================================================
Original Query: With how many companies we have closed deal previous year?
============================================================

Pipeline Result:
{
  'query': '[Optimized query with date resolution]',
  'data': {'extracted_data': {...}},
  'formatted_response': 'JSON formatted response'
}
```

**What This Tests:**
- ✅ Complete LangGraph pipeline execution
- ✅ State management between agents
- ✅ Configuration loading from database
- ✅ Agent orchestration
- ✅ Error handling and recovery

### Test 3: Interactive Mode

For interactive testing, modify `main.py` temporarily:

```python
# In main.py, change:
if __name__ == "__main__":
    # ... initialization code ...
    
    # Comment out main()
    # main()
    
    # Uncomment interactive_mode()
    interactive_mode()
```

Then run:

```bash
python main.py
```

**Interactive Session Example:**
```
AI Analyst Pipeline
Type 'exit' to quit

Enter your query: what was the last email from john?
Processing: what was the last email from john?

Result:
{
  'query': '[Optimized query]',
  'data': {...},
  'formatted_response': {...}
}

==================================================

Enter your query: show me all companies in New York
Processing: show me all companies in New York

Result:
{...}

Enter your query: exit
Exiting...
```

---

## Advanced Testing Scenarios

### Scenario 1: Test with Different LLM Providers

Test the system with different providers to verify multi-provider support.

**1. Test with OpenAI:**

```bash
# Set in .env
OPENAI_API_KEY=REDACTED
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4

python main.py
```

**2. Test with Anthropic:**

```bash
# Set in .env
ANTHROPIC_API_KEY=sk-ant-your-key
GLOBAL_LLM_PROVIDER=anthropic
GLOBAL_LLM_MODEL=claude-3-opus-20240229

python main.py
```

**3. Test with Per-Agent Configuration:**

```bash
# Set in .env
OPENAI_API_KEY=REDACTED
ANTHROPIC_API_KEY=sk-ant-your-key

# QueryOptimizer uses OpenAI
QUERY_OPTIMIZER_PROVIDER=openai
QUERY_OPTIMIZER_MODEL=gpt-4

# DataExtractor uses Anthropic
DATA_EXTRACTOR_PROVIDER=anthropic
DATA_EXTRACTOR_MODEL=claude-3-opus-20240229

# ResponseFormatter uses cheaper OpenAI model
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo

python main.py
```

### Scenario 2: Test with Database Configuration

After seeding the database, configurations are loaded from DB instead of env vars.

**1. Update Configuration via Database:**

```bash
psql -U postgres -d analyst_ai

# Update global config
UPDATE "GlobalLLMConfig" 
SET provider='anthropic', model='claude-3-sonnet-20240229' 
WHERE enabled=true;

# Update agent config
UPDATE "AgentLLMConfig" 
SET provider='openai', model='gpt-3.5-turbo' 
WHERE "agentName"='response_formatter';

# Verify changes
SELECT * FROM "GlobalLLMConfig";
SELECT * FROM "AgentLLMConfig";

\q
```

**2. Restart Application:**

```bash
python main.py
```

The application should now use the database configuration instead of environment variables.

### Scenario 3: Test Error Handling

**1. Test with Invalid API Key:**

```bash
# Temporarily set invalid key
OPENAI_API_KEY=REDACTED

python main.py
```

Expected: Should show error messages but continue with fallback if available.

**2. Test with Database Connection Failure:**

```bash
# Stop PostgreSQL
sudo service postgresql stop  # Linux
# or
brew services stop postgresql  # macOS

python main.py
```

Expected: Should log warnings and fall back to environment variables.

**3. Test with Redis Connection Failure:**

```bash
# Stop Redis
redis-cli shutdown

python main.py
```

Expected: Should log warnings but continue execution (caching disabled).

### Scenario 4: Test Tool Execution

Test individual tools with real database queries:

**Create `test_full_tool_flow.py`:**

```python
import asyncio
from tools.company_tool import CompanyTool
from tools.emails_tool import EmailsTool
from tools.people_tool import PeopleTool

async def test_tools():
    workspace_id = "workspace-123"
    user_id = "user-456"
    
    tools = [
        CompanyTool(),
        EmailsTool(),
        PeopleTool()
    ]
    
    for tool in tools:
        print(f"\n{'='*60}")
        print(f"Testing {tool.__class__.__name__}")
        print('='*60)
        
        # Test LIST operation
        result = await tool.execute(
            query_type="LIST",
            workspace_id=workspace_id,
            user_id=user_id,
            limit=5
        )
        
        print(f"Success: {result.success}")
        if result.success:
            print(f"Data Keys: {list(result.data.keys())}")
        else:
            print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_tools())
```

Run:

```bash
python test_full_tool_flow.py
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: "ModuleNotFoundError: No module named 'langgraph'"

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### Issue 2: "Database connection failed"

**Symptoms:**
- Error: `Connection refused` or `database does not exist`

**Solution:**
```bash
# Check PostgreSQL is running
pg_isready

# Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Test connection manually
psql -U postgres -d analyst_ai -c "SELECT 1;"

# If database doesn't exist, create it
psql -U postgres -c "CREATE DATABASE analyst_ai;"
```

#### Issue 3: "API key not found"

**Symptoms:**
- Error: `API key not found` or `Invalid API key`

**Solution:**
```bash
# Check API key is set
OPENAI_API_KEY=REDACTED

# Verify .env file
cat .env | grep API_KEY

# Test API key manually (OpenAI example)
curl https://api.openai.com/v1/models \
OPENAI_API_KEY=REDACTED
```

#### Issue 4: "Prisma client not generated"

**Symptoms:**
- Error: `ModuleNotFoundError: No module named 'prisma` or `'prisma' has no attribute 'PrismaClient'`

**Solution:**
```bash
# Generate Prisma client
prisma generate

# Verify client was generated
ls -la prisma/ | grep client
```

#### Issue 5: "Redis connection failed"

**Symptoms:**
- Warning: `Redis connection failed`

**Solution:**
```bash
# Check Redis is running
redis-cli ping  # Should return "PONG"

# Check Redis configuration
redis-cli CONFIG GET port

# Verify REDIS_HOST and REDIS_PORT in .env
cat .env | grep REDIS
```

#### Issue 6: "No configuration found in database"

**Symptoms:**
- Warning: `No global LLM config found in database`

**Solution:**
```bash
# Run seeding script
python scripts/seed_llm_config.py

# Verify configuration was created
psql -U postgres -d analyst_ai -c "SELECT * FROM \"GlobalLLMConfig\";"
```

#### Issue 7: "Invalid query format"

**Symptoms:**
- Error: `Invalid query format` or unexpected query optimization results

**Solution:**
- Check your query syntax
- Ensure API key has sufficient credits
- Try a simpler query first
- Check logs for detailed error messages

#### Issue 8: "Tool execution failed"

**Symptoms:**
- Error: `Tool execution failed` or empty results

**Solution:**
```bash
# Check database has data
psql -U postgres -d analyst_ai -c "SELECT COUNT(*) FROM \"Company\";"

# Verify workspace_id and user_id are valid
# Check tool logs for specific errors

# Test tool directly (see Scenario 4 above)
```

### Debug Mode

Enable detailed logging:

```python
# Add to your test script or main.py
import logging
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
```

### Verify System Health

Run this comprehensive health check:

```bash
# Create health_check.py
cat > health_check.py << 'EOF'
import asyncio
import sys
import os

async def check_system():
    print("="*60)
    print("System Health Check")
    print("="*60)
    
    # Check Python version
    print(f"\n✅ Python: {sys.version}")
    
    # Check environment variables
    print("\n📋 Environment Variables:")
OPENAI_API_KEY=REDACTED
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ❌ {var}: NOT SET")
    
    # Check database connection
    print("\n🗄️  Database Connection:")
    try:
        from database.prisma_client import prisma_client
        await prisma_client.connect()
        client = await prisma_client.get_client()
        count = await client.globalllmconfig.count()
        print(f"  ✅ Connected! Config count: {count}")
        await prisma_client.disconnect()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    # Check Redis connection
    print("\n🔴 Redis Connection:")
    try:
        from database.redis_client import redis_client
        redis_client.set("health_check", "ok")
        value = redis_client.get("health_check")
        if value == "ok":
            print("  ✅ Connected!")
        else:
            print("  ❌ Value mismatch")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    # Check LLM provider
    print("\n🤖 LLM Provider:")
    try:
        from config.config_manager import get_config_manager
        config_manager = get_config_manager()
        await config_manager.initialize()
        config = config_manager.get_agent_config_sync("query_optimizer")
        print(f"  ✅ Provider: {config.provider}/{config.model} (source: {config.source})")
        if config.api_key:
            print(f"  ✅ API Key: Set")
        else:
            print(f"  ❌ API Key: NOT SET")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    print("\n" + "="*60)
    print("Health check complete!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(check_system())
EOF

python health_check.py
```

---

## Quick Reference

### Common Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database
prisma generate
prisma db push
python scripts/seed_llm_config.py

# Testing
python tests/test_query_optimizer.py
python tests/test_pipeline_integration.py
python main.py

# Debug
python -m pdb main.py  # Python debugger
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
```

### Test Checklist

Use this checklist to verify your system is working:

- [ ] Python 3.11+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with API keys
- [ ] PostgreSQL database created and running
- [ ] Prisma schema pushed to database (`prisma db push`)
- [ ] LLM configuration seeded (`python scripts/seed_llm_config.py`)
- [ ] Redis server running
- [ ] Database connection test passes
- [ ] Redis connection test passes
- [ ] QueryOptimizerAgent tests pass
- [ ] Integration tests pass
- [ ] Full pipeline runs successfully

### Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | Main entry point, runs pipeline |
| `graph/pipeline.py` | LangGraph pipeline orchestration |
| `agents/query_optimizer.py` | Query optimization agent |
| `agents/data_extractor.py` | Data extraction agent |
| `tools/company_tool.py` | Company data tool |
| `tools/emails_tool.py` | Email data tool |
| `config/settings.py` | Configuration management |
| `tests/test_query_optimizer.py` | Query optimizer tests |
| `tests/test_pipeline_integration.py` | Integration tests |
| `.env` | Environment variables |
| `prisma/schema.prisma` | Database schema |

### Query Examples

Test with these example queries:

1. **Email Query:**
   ```
   what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}
   ```

2. **Deal Query:**
   ```
   With how many companies we have closed deal previous year?
   ```

3. **Company Query:**
   ```
   Show me all companies in New York
   ```

4. **People Query:**
   ```
   Find all contacts from Acme Corp
   ```

5. **Date-based Query:**
   ```
   What deals were closed this month?
   ```

---

## Next Steps

After completing basic testing:

1. **Add Test Data**: Populate your database with sample companies, people, and emails
2. **Test Real Queries**: Test with actual CRM data scenarios
3. **Performance Testing**: Test with large datasets
4. **Error Scenarios**: Test error handling and recovery
5. **Integration Testing**: Test with frontend or API endpoints

---

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review error logs with debug logging enabled
3. Verify all prerequisites are met
4. Check database and Redis connections
5. Verify API keys are valid and have credits

---

## Conclusion

This guide provides a comprehensive testing workflow for the AI Analyst RAG system. Follow each section step-by-step, and verify each component before moving to the next. Once all tests pass, your system is ready for use!

Happy Testing! 🚀

