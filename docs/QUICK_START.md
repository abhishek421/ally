# Quick Start Testing Guide

**For detailed instructions, see [TESTING_GUIDE.md](docs/TESTING_GUIDE.md)**

## 🚀 Quick Start (5 Minutes)

### Step 1: Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create `.env` file in project root:

```bash
OPENAI_API_KEY=REDACTED
DATABASE_URL=postgresql://user:password@localhost:5432/analyst_ai
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Step 3: Setup Database

```bash
# Create database
createdb analyst_ai  # or use psql

# Generate Prisma client
prisma generate

# Push schema to database
prisma db push

# Seed LLM configuration
python scripts/seed_llm_config.py
```

### Step 4: Run Health Check

```bash
python scripts/health_check.py
```

Expected: All checks should pass ✅

### Step 5: Run Tests

```bash
# Test Query Optimizer
python tests/test_query_optimizer.py

# Test Pipeline Integration
python tests/test_pipeline_integration.py

# Run Full Pipeline
python main.py
```

## ✅ Verification Checklist

- [ ] Python 3.11+ installed
- [ ] Virtual environment activated
- [ ] Dependencies installed
- [ ] `.env` file configured
- [ ] PostgreSQL database created
- [ ] Prisma schema pushed
- [ ] LLM config seeded
- [ ] Health check passes
- [ ] Tests pass

## 🆘 Troubleshooting

**Issue**: Health check fails
→ Run `python scripts/health_check.py` and fix reported issues

**Issue**: Database connection fails
→ Check PostgreSQL is running: `pg_isready`
→ Verify DATABASE_URL in `.env`

**Issue**: API key errors
OPENAI_API_KEY=REDACTED
→ Check API key has credits

**More Help**: See [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for detailed troubleshooting

