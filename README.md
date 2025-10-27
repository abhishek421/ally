# AI Analyst RAG - CRM Analysis Pipeline

## Overview
A RAG (Retrieval Augmented Generation) pipeline using LangGraph with three specialized agents for intelligent query processing and data extraction.

## Architecture

### Agents
1. **QueryOptimizerAgent**: Converts user queries to more defined and structured queries
2. **DataExtractorAgent**: Uses multiple tools to search different DB, tables, and data storages
3. **ResponseFormatterAgent**: Formats responses in proper JSON format

## Folder Structure
```
AI-Analyst-RAG/
├── agents/           # Agent implementations
├── tools/            # Data extraction tools
├── graph/            # LangGraph pipeline orchestration
├── models/           # Data models
├── config/           # Configuration files
├── database/         # Database connections
├── utils/            # Utility functions
└── tests/            # Test files
```

