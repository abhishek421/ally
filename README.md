# Multi-Agent Database Chatbot

A sophisticated chatbot system built with Streamlit and LangGraph that allows users to query a PostgreSQL database using natural language. The system uses a multi-agent architecture where different agents handle query understanding, SQL generation, database execution, and response formatting.

## Features

- 🤖 **Multi-Agent Architecture**: Uses LangGraph to orchestrate specialized agents
- 🗄️ **PostgreSQL Integration**: Secure database connectivity with query validation
- 🔧 **Configurable Schema**: Easy-to-modify database schema via JSON configuration
- 📊 **CSV Data Upload**: Upload your own data via CSV files with automatic schema mapping
- 💬 **Natural Language Interface**: Ask questions in plain English
- 🛡️ **Safe Query Execution**: Only SELECT queries allowed, with validation
- 🎨 **Modern UI**: Clean Streamlit interface with real-time chat and file upload

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
   # LLM Provider Configuration
   LLM_PROVIDER=openai
   LLM_MODEL_NAME=gpt-3.5-turbo
   LLM_TEMPERATURE=0.1
   
   # OpenAI API Configuration
OPENAI_API_KEY=REDACTED
   
   # Google Gemini API Configuration (if using Gemini)
   GOOGLE_API_KEY=your_google_api_key_here
   
   # Anthropic Claude API Configuration (if using Claude)
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   
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

4. **Upload your CSV data**:
   - **Companies CSV**: Upload with columns: Customer Id, First Name, Last Name, Company, City, Country, Phone 1, Phone 2, Email, Subscription Date, Website
   - **People CSV**: Upload with columns: User Id, First Name, Last Name, Sex, Email, Phone, Date of birth, Job Title

5. **Start chatting!** Ask questions like:
   - "What are the top 5 companies by subscription date?"
   - "How many people are there in each country?"
   - "Which companies are in Chile?"
   - "What are the different job titles?"
   - "Show me all people born after 1990"

## Configuration

### Multi-Provider LLM Support

This chatbot supports multiple LLM providers, allowing you to choose the best model for your needs and budget.

#### **Supported Providers:**

1. **OpenAI** (Default)
   - Models: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`, `gpt-3.5-turbo-16k`
OPENAI_API_KEY=REDACTED

2. **Google Gemini**
   - Models: `gemini-pro`, `gemini-pro-vision`, `gemini-1.5-pro`, `gemini-1.5-flash`
   - API Key: `GOOGLE_API_KEY`
   - Requires: `pip install langchain-google-genai`

3. **Anthropic Claude**
   - Models: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, `claude-3-haiku-20240307`, `claude-3-5-sonnet-20241022`
   - API Key: `ANTHROPIC_API_KEY`
   - Requires: `pip install langchain-anthropic`

#### **Configuration Examples:**

**Using OpenAI (Default):**
```env
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4
OPENAI_API_KEY=REDACTED
```

**Using Google Gemini:**
```env
LLM_PROVIDER=gemini
LLM_MODEL_NAME=gemini-1.5-pro
GOOGLE_API_KEY=your_google_key_here
```

**Using Anthropic Claude:**
```env
LLM_PROVIDER=claude
LLM_MODEL_NAME=claude-3-sonnet-20240229
ANTHROPIC_API_KEY=your_anthropic_key_here
```

#### **Additional Configuration:**
- `LLM_TEMPERATURE`: Controls randomness (0.0 to 1.0, default: 0.1)
- `LLM_PROVIDER`: Provider name (openai, gemini, claude, google, anthropic)

The provider and model information is displayed in the Streamlit interface under "Environment Check" so you can verify your configuration.

### Database Schema

The database schema is defined in `config/schema.json`. The current schema supports CSV data upload with the following structure:

**Companies Table:**
- `id` (Primary Key, Auto-increment)
- `customer_id`, `first_name`, `last_name`, `company`, `city`, `country`
- `phone_1`, `phone_2`, `email`, `subscription_date`, `website`
- `created_at`, `updated_at` (Auto-generated timestamps)

**People Table:**
- `id` (Primary Key, Auto-increment)
- `user_id`, `first_name`, `last_name`, `sex`, `email`, `phone`
- `date_of_birth`, `job_title`
- `created_at`, `updated_at` (Auto-generated timestamps)

You can modify the schema in `config/schema.json` to match your specific data structure:

```json
{
  "tables": {
    "companies": {
      "columns": {
        "id": {"type": "INTEGER", "primary_key": true, "auto_increment": true},
        "customer_id": {"type": "VARCHAR(255)", "nullable": true},
        "company": {"type": "VARCHAR(255)", "nullable": true},
        "created_at": {"type": "TIMESTAMP", "default": "CURRENT_TIMESTAMP"}
      }
    }
  }
}
```

### CSV Data Upload

The system automatically processes CSV files and maps them to the database schema:

1. **Automatic Column Mapping**: CSV headers are automatically mapped to database columns
2. **Date Parsing**: Dates are automatically parsed and converted to proper database format
3. **Data Validation**: Invalid data is handled gracefully with error reporting
4. **Timestamp Management**: `created_at` and `updated_at` fields are automatically populated

### CSV Upload Workflow

1. **Connect to Database**: Use the "Connect to Database" button in the sidebar
2. **Reset Schema** (if needed): Click "Reset Database Schema" to update table structure
3. **Upload Companies CSV**: Select your companies CSV file and click "Upload Companies Data"
4. **Upload People CSV**: Select your people CSV file and click "Upload People Data"
5. **Verify Upload**: Check the data statistics to confirm successful upload
6. **Start Querying**: Use natural language to ask questions about your data

**Supported CSV Formats:**
- **Companies**: Customer Id, First Name, Last Name, Company, City, Country, Phone 1, Phone 2, Email, Subscription Date, Website
- **People**: User Id, First Name, Last Name, Sex, Email, Phone, Date of birth, Job Title

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
│   ├── llm_provider.py          # Multi-provider LLM factory
│   └── README.md               # Agent architecture documentation
├── config/
│   ├── db_config.py             # Database configuration management
│   └── schema.json              # Database schema definition
├── database/
│   ├── db_setup.py              # Database connection and management
│   ├── csv_processor.py         # CSV file processing and data insertion
│   └── sample_data.py           # Legacy sample data generation (deprecated)
├── tools/
│   ├── database_tools.py         # Database query tools
│   └── schema_tools.py          # Schema inspection tools
├── tests/
│   ├── __init__.py              # Tests package initialization
│   ├── run_tests.py             # Test runner script
│   ├── test_db_connection.py    # Database connection tests
│   ├── test_model_config.py     # LLM model configuration tests
│   ├── test_multi_provider.py   # Multi-provider LLM support tests
│   └── test_config.ini          # Test configuration
├── app.py                       # Streamlit application
├── requirements.txt             # Python dependencies
├── env.example                  # Environment variables template
├── MULTI_PROVIDER_SETUP.md      # Multi-provider setup guide
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
2. Modify `database/csv_processor.py` to handle CSV processing for the new table
3. Update the UI in `app.py` to include upload functionality for the new table
4. Restart the application

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

## Testing

The project includes a comprehensive test suite located in the `tests/` directory.

### Running Tests

**Run all tests:**
```bash
python tests/run_tests.py
```

**Run specific test suites:**
```bash
# Database connection tests
python tests/run_tests.py db

# LLM model configuration tests  
python tests/run_tests.py model

# Multi-provider LLM support tests
python tests/run_tests.py provider
```

**Run individual test files:**
```bash
python tests/test_db_connection.py
python tests/test_model_config.py
python tests/test_multi_provider.py
```

### Test Structure

```
tests/
├── __init__.py                 # Tests package initialization
├── run_tests.py               # Test runner script
├── test_db_connection.py      # Database connection and setup tests
├── test_model_config.py       # LLM model configuration tests
└── test_multi_provider.py     # Multi-provider LLM support tests
```

### Test Coverage

- **Database Tests**: Connection, table creation, query execution
- **Model Configuration**: Provider switching, model validation
- **Multi-Provider Support**: OpenAI, Gemini, Claude integration
- **Environment Validation**: API key validation, configuration checks

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify connection parameters in `.env`
   - Ensure database exists
   - Run: `python tests/test_db_connection.py`

2. **LLM Provider Errors**
   - Verify API key is correct for your chosen provider
   - Check API quota and billing
   - Ensure internet connectivity
   - Run: `python tests/test_multi_provider.py`

3. **Schema Errors**
   - Validate JSON syntax in `config/schema.json`
   - Check table and column names
   - Ensure foreign key relationships are correct

4. **CSV Upload Issues**
   - Ensure CSV files have the correct column headers
   - Check that database schema matches CSV structure
   - Use "Reset Database Schema" button if schema is outdated
   - Verify CSV file format and encoding (UTF-8 recommended)

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






# Multi-User Multi-Chat LLM Chatbot Memory Architecture

## Components Overview
| Component | Role | Stores |
|---------|------|--------|
| **SQL DB** | Manages users and chat session list | user table, chat_sessions table |
| **Vector DB** | Stores chat messages + embeddings | text + `user_id` + `chat_id` metadata |
| **Redis (optional)** | Caches frequent Q&A and recent chat | speed optimization |

## Data Model

### SQL: `users`
| Column | Example | Purpose |
|--------|---------|---------|
| user_id (pk) | `u_101` | identifies person |
| name | "Amit" | optional |
| email | "amit@example.com" | for login |

### SQL: `chat_sessions`
| Column | Example | Purpose |
|--------|---------|---------|
| chat_id (pk) | `chat_9asf1` | one conversation |
| user_id (fk)` | `u_101` | belongs to user |
| title | "GST Filing Help" | displayed in sidebar |
| created_at | timestamp | UI sorting |
| updated_at | timestamp | last active time |

### Vector DB stored message format
```json
{
  "id": "msg_001",
  "text": "How to reply to GST notice?",
  "embedding": [...],
  "metadata": {
    "user_id": "u_101",
    "chat_id": "chat_9asf1",
    "role": "user",
    "timestamp": 1730458000
  }
}
```

---

## Conversation Flow Scenarios

### 1. User Opens Chatbot
- App fetches user from SQL
- Fetches chat list:
```
SELECT * FROM chat_sessions WHERE user_id = u_101 ORDER BY updated_at DESC;
```

### 2. User Creates New Chat
```
INSERT INTO chat_sessions (chat_id, user_id, title)
VALUES ("chat_9asf1", "u_101", "Untitled Chat");
```

### 3. User Sends First Message
1. Convert message to embedding
2. Store to Vector DB
3. Retrieve relevant history (none yet)
4. LLM responds
5. Store response
6. Update chat title based on context

### 4. Continuing Conversation
Steps repeated:
```
Embed → Store → Retrieve top_k by chat_id & user_id → LLM → Save response → Update timestamps
```

### 5. Cached Responses (Redis)
If a repeated question matches:
```
if redis.has(question_hash): return redis.get(question_hash)
else: compute → store → return
```

---

## Why This Works

| Requirement | Covered By |
|------------|-----------|
| Multi-user access with login | SQL DB |
| Multiple chat sessions per user | SQL DB + chat_id metadata |
| Conversation memory & recall | Vector DB |
| Fast repeated answers | Redis |
| Prevents token overflow | Retrieve relevant history only |

---

## Final Summary

**User & Chat metadata → SQL DB**  
**Messages → Vector DB (with `user_id` + `chat_id`)**  
**Caching (optional) → Redis**  

This supports:
- Multiple users
- Multiple chats per user
- Long-term memory
- Fast response time


