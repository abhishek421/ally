# AI Analyst RAG - CRM Analysis Pipeline

## Overview
A RAG (Retrieval Augmented Generation) pipeline using LangGraph with three specialized agents for intelligent query processing and data extraction from CRM databases.

## How It Works

### The Pipeline Flow
1. **User Query** → "With how many companies we have closed deal previous year?"
2. **QueryOptimizerAgent** → Converts to structured query with clear intent
3. **DataExtractorAgent** → Searches databases/tables using multiple tools
4. **ResponseFormatterAgent** → Formats response in structured JSON
5. **Final Response** → Returns well-formatted results

## Architecture

### Agents
1. **QueryOptimizerAgent** (`agents/query_optimizer.py`)
   - Converts user queries to more defined and structured queries
   - Example: "what was the last mail from Sam?" → Structured query with filters

2. **DataExtractorAgent** (`agents/data_extractor.py`)
   - Uses multiple tools to search different DB, tables, and data storages
   - Tools: companies_tool, emails_tool, etc.

3. **ResponseFormatterAgent** (`agents/response_formatter.py`)
   - Formats responses in proper JSON format
   - Ensures consistent output structure

### Pipeline
- **Main Pipeline** (`graph/pipeline.py`): Orchestrates the three agents using LangGraph
- **Entry Point** (`main.py`): Run the pipeline with queries

## Folder Structure
```
AI-Analyst-RAG/
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

## Usage

### Run with a single query (default)
```bash
python main.py
```

### Interactive Mode
Edit `main.py` and switch to interactive mode:
```python
# Comment out main() and uncomment interactive_mode()
if __name__ == "__main__":
    # main()
    interactive_mode()
```

Then run:
```bash
python main.py
```
You'll get a chatbot-like interface to continuously query the pipeline.

### Use in your code
```python
from graph.pipeline import AnalystRAGPipeline

# Create pipeline
pipeline = AnalystRAGPipeline()

# Run with a query
result = pipeline.run("With how many companies we have closed deal previous year?")
print(result)
```

## Example Query
**Input:** "With how many companies we have closed deal previous year?"

**Output:** JSON formatted response with extracted data from your CRM databases.

## Setup

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configuration

#### Environment Variables
Create a `.env` file in the project root with your API credentials:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=REDACTED

# Model Configuration
MODEL_NAME=gpt-4
```

**Important:** The `.env` file is already in `.gitignore` to keep your credentials secure.

The application will automatically load these values at runtime. If no `.env` file is found, it will use empty defaults (which will cause errors when making API calls).

#### Prompt Templates
All prompt templates are stored in the `prompts/` directory as Python modules:
- `prompts/query_optimizer_prompt.py` - Query optimization prompt template
- `prompts/__init__.py` - Exports all prompt templates

You can easily modify or add new prompts by editing the `.py` files in this directory.

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
