# Project Structure

This document outlines the complete file/folder structure of the LangGraph orchestration application.

```
AnalystAI/
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── README.md                    # Project documentation
├── PROJECT_STRUCTURE.md         # This file
├── requirements.txt             # Python dependencies
│
├── data/                        # Data directories
│   ├── input/                   # Input data files
│   │   └── .gitkeep
│   └── output/                  # Output data files
│       └── .gitkeep
│
├── logs/                        # Application logs
│   └── .gitkeep
│
├── src/                         # Main application source code
│   ├── __init__.py
│   ├── main.py                  # Application entry point
│   │
│   ├── config/                  # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py          # Pydantic settings with env support
│   │
│   ├── graph/                   # Graph definition and construction
│   │   ├── __init__.py
│   │   ├── builder.py           # Graph construction logic
│   │   └── state.py             # GraphState TypedDict schema
│   │
│   ├── nodes/                   # Graph node implementations
│   │   ├── __init__.py
│   │   ├── base.py              # BaseNode abstract class
│   │   └── query_builder_node.py # Query Builder Node implementation
│   │
│   └── utils/                   # Utility modules
│       ├── __init__.py
│       ├── exceptions.py        # Custom exception classes
│       └── logger.py            # Structured logging setup
│
└── tests/                       # Test suite
    ├── __init__.py
    ├── test_graph.py            # Graph execution tests
    └── test_nodes.py            # Node unit tests
```

## Key Components

### Configuration (`src/config/`)
- **settings.py**: Centralized configuration using Pydantic Settings
- Supports environment variables via `.env` file
- Type-safe configuration with validation

### Graph (`src/graph/`)
- **state.py**: Defines the `GraphState` TypedDict schema
- **builder.py**: Constructs and compiles the LangGraph StateGraph
- Graph structure is currently being configured

### Nodes (`src/nodes/`)
- **base.py**: Abstract base class for all nodes
- **query_builder_node.py**: Query Builder Node - builds queries from user input

### Utilities (`src/utils/`)
- **logger.py**: Structured logging with structlog
- **exceptions.py**: Custom exception classes for error handling

### Main Entry Point (`src/main.py`)
- Initializes logging
- Builds and executes the graph
- Provides both sync and async execution methods

## Execution Flow

1. **Initialization**: Load configuration and setup logging
2. **Graph Construction**: Build StateGraph with nodes and edges
3. **State Creation**: Create initial GraphState with input data
4. **Execution**: 
   - Nodes process input and produce results
   - Execution path is tracked through the graph
5. **Completion**: Return final state with all results

## Dependencies

- **langgraph** (>=0.2.40): Core graph orchestration
- **langchain** (>=0.3.0): LangChain integration
- **pydantic-settings** (>=2.5.0): Configuration management
- **structlog** (>=24.1.0): Structured logging
- **pytest** (>=8.3.0): Testing framework

