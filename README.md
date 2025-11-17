# LangGraph Orchestration Application

A production-grade LangGraph-based orchestration system with modular node architecture.

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── builder.py          # Graph construction logic
│   │   └── state.py            # State schema definitions
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── base.py             # Base node class
│   │   └── query_builder_node.py # Query Builder Node
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py           # Logging configuration
│   │   └── exceptions.py       # Custom exceptions
│   └── config/
│       ├── __init__.py
│       └── settings.py         # Configuration management
├── tests/
│   ├── __init__.py
│   ├── test_nodes.py
│   └── test_graph.py
├── data/
│   ├── input/
│   └── output/
├── logs/
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy environment file:
```bash
cp .env.example .env
```

4. Update `.env` with your configuration.

## Usage

Run the application:
```bash
python -m src.main
```

## Testing

Run tests:
```bash
pytest tests/
```

## Development

Format code:
```bash
black src/ tests/
```

Lint code:
```bash
ruff check src/ tests/
```

