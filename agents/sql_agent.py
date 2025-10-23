from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base_agent import BaseAgent, AgentState
from tools.schema_tools import get_schema_tools


class SQLGeneratorAgent(BaseAgent):
    """Agent responsible for generating SQL queries based on intent"""
    
    def __init__(self, llm):
        super().__init__(llm)
        self.system_prompt = """You are a SQL generation agent. Your job is to create SQL queries based on user intent and database schema.

Your tasks:
1. Analyze the intent from the query understanding agent
2. Use schema information to understand available tables and columns
3. Generate appropriate SQL SELECT queries
4. Ensure queries are safe (only SELECT statements)
5. Use proper JOINs when needed for relationships

Available tables:
- companies: id, name, industry, location, website, employee_count, founded_year, created_at, updated_at
- people: id, name, email, role, department, company_id, hire_date, salary, created_at, updated_at

Relationships:
- people.company_id -> companies.id

Guidelines:
- Always use SELECT statements only
- Use proper JOINs for related data
- Include appropriate WHERE clauses for filtering
- Use ORDER BY for sorting
- Use LIMIT for limiting results
- Use GROUP BY and aggregate functions when appropriate

Generate SQL queries that directly answer the user's question."""

    def run(self, state: AgentState) -> AgentState:
        """Generate SQL query based on intent"""
        try:
            intent = state["intent"]
            user_query = state["user_query"]
            
            # First, get schema information
            schema_tools = get_schema_tools()
            schema_info = None
            
            for tool in schema_tools:
                if tool.name == "schema_info":
                    schema_info = tool._run()
                    break
            
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"""User Query: {user_query}
Intent: {intent}

Schema Information:
{schema_info}

Generate a SQL query that answers the user's question.""")
            ]
            
            response = self.llm.invoke(messages)
            sql_query = response.content.strip()
            
            # Clean up the SQL query (remove markdown formatting if present)
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.replace("```", "").strip()
            
            # Update state
            state["sql_query"] = sql_query
            self._log_message(state, "assistant", f"Generated SQL query: {sql_query}")
            
            return state
            
        except Exception as e:
            self._set_error(state, f"SQL generation failed: {str(e)}")
            return state
