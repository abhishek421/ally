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

### Using uv (Recommended)

1. Install [uv](https://github.com/astral-sh/uv) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Sync dependencies (creates virtual environment automatically):
```bash
uv sync
```

3. Copy environment file:
```bash
cp .env.example .env
```

4. Update `.env` with your configuration.

### Using pip (Alternative)

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

### Using uv

Run the Streamlit web interface:
```bash
uv run streamlit run streamlit_app.py
```

Run the API server:
```bash
uv run python api_server.py
```

Run the CLI application:
```bash
uv run python -m src.main
```

### Using pip

Run the Streamlit web interface:
```bash
streamlit run streamlit_app.py
```

Run the API server:
```bash
python api_server.py
```

Run the CLI application:
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

