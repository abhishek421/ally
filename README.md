# Multi-Agent Database Chatbot

A sophisticated chatbot system built with Streamlit and LangGraph that allows users to query a PostgreSQL database using natural language. The system uses a multi-agent architecture where different agents handle query understanding, SQL generation, database execution, and response formatting.

## Features

- 🤖 **Multi-Agent Architecture**: Uses LangGraph to orchestrate specialized agents
- 🗄️ **PostgreSQL Integration**: Secure database connectivity with query validation
- 🔧 **Configurable Schema**: Easy-to-modify database schema via JSON configuration
- 📊 **Sample Data Generation**: Realistic sample data for testing and demos
- 💬 **Natural Language Interface**: Ask questions in plain English
- 🛡️ **Safe Query Execution**: Only SELECT queries allowed, with validation
- 🎨 **Modern UI**: Clean Streamlit interface with real-time chat

## Architecture

The system consists of four specialized agents:

1. **Query Understanding Agent**: Interprets user questions and determines intent
2. **SQL Generator Agent**: Converts natural language to SQL queries
3. **Database Executor Agent**: Safely executes queries and retrieves results
4. **Response Formatter Agent**: Formats results into human-readable responses

## Prerequisites

- Python 3.8+
- PostgreSQL database
- OpenAI API key

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd multi-agent-db-chatbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` with your configuration:
   ```env
   # OpenAI API Configuration
OPENAI_API_KEY=REDACTED
   
   # PostgreSQL Database Configuration
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=chatbot_db
   DB_USER=postgres
   DB_PASSWORD=your_password_here
   
   # Streamlit Configuration
   STREAMLIT_SERVER_PORT=8501
   ```

4. **Set up PostgreSQL database**
   ```bash
   # Create the database
   createdb chatbot_db
   
   # Or using psql
   psql -U postgres -c "CREATE DATABASE chatbot_db;"
   ```

## Usage

1. **Start the application**
   ```bash
   streamlit run app.py
   ```

2. **Open your browser** and navigate to `http://localhost:8501`

3. **Connect to database** using the sidebar button

4. **Load sample data** (optional) for testing

5. **Start chatting!** Ask questions like:
   - "What are the top 5 newly added companies?"
   - "How many people work in the Engineering department?"
   - "Which companies are in the Technology industry?"
   - "What is the average salary by role?"

## Configuration

### Database Schema

The database schema is defined in `config/schema.json`. You can modify this file to change table structures:

```json
{
  "tables": {
    "companies": {
      "columns": {
        "id": {"type": "INTEGER", "primary_key": true, "auto_increment": true},
        "name": {"type": "VARCHAR(255)", "nullable": false},
        "industry": {"type": "VARCHAR(100)", "nullable": true},
        "location": {"type": "VARCHAR(255)", "nullable": true},
        "created_at": {"type": "TIMESTAMP", "default": "CURRENT_TIMESTAMP"}
      }
    }
  }
}
```

### Sample Data

Sample data is generated using the Faker library. You can customize the data generation in `database/sample_data.py`:

- Modify company industries and locations
- Adjust people roles and departments
- Change salary ranges and other attributes

## Project Structure

```
multi-agent-db-chatbot/
├── agents/
│   ├── __init__.py              # Package initialization
│   ├── base_agent.py            # Base class for all agents
│   ├── query_agent.py           # Query understanding agent
│   ├── sql_agent.py             # SQL generation agent
│   ├── executor_agent.py        # Database execution agent
│   ├── formatter_agent.py       # Response formatting agent
│   ├── chatbot.py              # Main chatbot orchestrator
│   └── README.md               # Agent architecture documentation
├── config/
│   ├── db_config.py             # Database configuration management
│   └── schema.json              # Database schema definition
├── database/
│   ├── db_setup.py              # Database connection and management
│   └── sample_data.py           # Sample data generation
├── tools/
│   ├── database_tools.py         # Database query tools
│   └── schema_tools.py          # Schema inspection tools
├── app.py                       # Streamlit application
├── requirements.txt             # Python dependencies
├── env.example                  # Environment variables template
└── README.md                    # This file
```

## API Reference

### DatabaseManager

Main class for database operations:

```python
from database.db_setup import get_db_manager

db_manager = get_db_manager()
db_manager.connect()
db_manager.create_tables()
result = db_manager.execute_query("SELECT * FROM companies LIMIT 5")
```

### MultiAgentChatbot

Main chatbot class:

```python
from agents.chatbot import create_chatbot

chatbot = create_chatbot()
response = chatbot.chat("What are the top companies?")
```

### Individual Agents

You can also use agents individually:

```python
from agents import QueryUnderstandingAgent, SQLGeneratorAgent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo")
query_agent = QueryUnderstandingAgent(llm)
sql_agent = SQLGeneratorAgent(llm)

# Use agents independently
state = {"user_query": "What are the top companies?"}
state = query_agent.run(state)
state = sql_agent.run(state)
```

### DatabaseConfig

Schema configuration management:

```python
from config.db_config import DatabaseConfig

config = DatabaseConfig()
schema_info = config.get_all_schema_info()
```

## Customization

### Adding New Tables

1. Update `config/schema.json` with your new table definition
2. Modify `database/sample_data.py` to generate sample data for the new table
3. Restart the application

### Adding New Agents

1. Create a new agent file in `agents/` directory
2. Inherit from `BaseAgent` class
3. Implement the `run()` method
4. Update `agents/__init__.py` to export the new agent
5. Add to workflow in `chatbot.py` if needed

See `agents/README.md` for detailed documentation.

### Customizing Tools

1. Create new tools in the `tools/` directory
2. Add them to the appropriate agent
3. Update the agent's system prompt to use the new tools

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify connection parameters in `.env`
   - Ensure database exists

2. **OpenAI API Error**
   - Verify API key is correct
   - Check API quota and billing
   - Ensure internet connectivity

3. **Schema Errors**
   - Validate JSON syntax in `config/schema.json`
   - Check table and column names
   - Ensure foreign key relationships are correct

4. **Sample Data Issues**
   - Clear existing data before reloading
   - Check foreign key constraints
   - Verify data generation logic

### Debug Mode

Enable debug logging by setting the log level in `database/db_setup.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

- Only SELECT queries are allowed
- Query validation prevents SQL injection
- Database credentials are stored in environment variables
- No DDL or DML operations are permitted

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) for multi-agent orchestration
- [Streamlit](https://streamlit.io/) for the web interface
- [OpenAI](https://openai.com/) for language model capabilities
- [SQLAlchemy](https://www.sqlalchemy.org/) for database abstraction
