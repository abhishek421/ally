# Multi-Agent Database Chatbot - Modular Architecture

This document describes the modular architecture of the multi-agent database chatbot system.

## Architecture Overview

The system is now organized into separate, maintainable modules:

```
agents/
├── __init__.py              # Package initialization and exports
├── base_agent.py            # Base class for all agents
├── query_agent.py           # Query understanding agent
├── sql_agent.py             # SQL generation agent
├── executor_agent.py        # Database execution agent
├── formatter_agent.py       # Response formatting agent
└── chatbot.py              # Main chatbot orchestrator
```

## Agent Classes

### BaseAgent (`base_agent.py`)
- **Purpose**: Base class providing common functionality for all agents
- **Key Methods**:
  - `run(state: AgentState) -> AgentState`: Abstract method to be implemented by subclasses
  - `_log_message()`: Helper to log messages to state
  - `_set_error()`: Helper to set errors in state

### QueryUnderstandingAgent (`query_agent.py`)
- **Purpose**: Analyzes user queries and determines intent
- **Responsibilities**:
  - Parse natural language queries
  - Extract key entities and parameters
  - Determine query intent
  - Provide structured intent description

### SQLGeneratorAgent (`sql_agent.py`)
- **Purpose**: Converts user intent into SQL queries
- **Responsibilities**:
  - Analyze intent from query understanding agent
  - Use schema information to understand available tables
  - Generate safe SELECT queries
  - Handle JOINs and relationships
  - Ensure query safety

### DatabaseExecutorAgent (`executor_agent.py`)
- **Purpose**: Safely executes SQL queries
- **Responsibilities**:
  - Execute SQL queries using database tools
  - Handle query validation
  - Manage database connections
  - Return query results

### ResponseFormatterAgent (`formatter_agent.py`)
- **Purpose**: Formats query results into human-readable responses
- **Responsibilities**:
  - Convert raw database results to readable format
  - Provide context and explanations
  - Suggest follow-up questions
  - Handle empty results gracefully

### MultiAgentChatbot (`chatbot.py`)
- **Purpose**: Orchestrates the multi-agent workflow
- **Responsibilities**:
  - Initialize all agents
  - Build LangGraph workflow
  - Manage agent state transitions
  - Handle errors and exceptions
  - Provide main chat interface

## State Management

The `AgentState` TypedDict defines the shared state between agents:

```python
class AgentState(TypedDict):
    messages: List[Dict[str, str]]      # Chat history
    user_query: str                     # Original user query
    intent: str                         # Parsed intent
    sql_query: str                      # Generated SQL
    query_result: str                   # Database results
    final_response: str                 # Formatted response
    error: str                          # Error messages
    tools_used: List[str]               # Tools used in process
```

## Workflow

The agents work in sequence:

1. **QueryUnderstandingAgent**: Parses user input → Intent
2. **SQLGeneratorAgent**: Intent + Schema → SQL Query
3. **DatabaseExecutorAgent**: SQL Query → Database Results
4. **ResponseFormatterAgent**: Results → Human-readable Response

## Benefits of Modular Architecture

### Maintainability
- Each agent has a single responsibility
- Easy to modify individual agents without affecting others
- Clear separation of concerns

### Testability
- Each agent can be tested independently
- Mock dependencies easily
- Unit tests for individual components

### Extensibility
- Easy to add new agents
- Simple to modify agent behavior
- Plugin-like architecture

### Debugging
- Clear error isolation
- Easy to trace issues to specific agents
- Better logging and monitoring

## Usage Examples

### Using Individual Agents
```python
from agents import QueryUnderstandingAgent, SQLGeneratorAgent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo")
query_agent = QueryUnderstandingAgent(llm)
sql_agent = SQLGeneratorAgent(llm)

# Use agents individually
state = {"user_query": "What are the top companies?"}
state = query_agent.run(state)
state = sql_agent.run(state)
```

### Using the Complete Chatbot
```python
from agents import create_chatbot

chatbot = create_chatbot()
response = chatbot.chat("What are the top 5 companies?")
```

## Adding New Agents

To add a new agent:

1. **Create new agent file**: `agents/new_agent.py`
2. **Inherit from BaseAgent**:
   ```python
   from agents.base_agent import BaseAgent, AgentState
   
   class NewAgent(BaseAgent):
       def run(self, state: AgentState) -> AgentState:
           # Implementation
           return state
   ```
3. **Update `__init__.py`** to export the new agent
4. **Update workflow** in `chatbot.py` if needed

## Configuration

Each agent can be configured independently:

```python
# Custom LLM for specific agents
custom_llm = ChatOpenAI(model="gpt-4", temperature=0.2)
query_agent = QueryUnderstandingAgent(custom_llm)

# Database executor doesn't need LLM
executor_agent = DatabaseExecutorAgent()
```

This modular architecture makes the system much more maintainable, testable, and extensible while preserving all the original functionality.
