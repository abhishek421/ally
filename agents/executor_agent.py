from typing import Dict, Any
from agents.base_agent import BaseAgent, AgentState
from tools.database_tools import get_database_tools


class DatabaseExecutorAgent(BaseAgent):
    """Agent responsible for executing SQL queries safely"""
    
    def __init__(self):
        # Database executor doesn't need LLM
        super().__init__(None)
        self.database_tools = get_database_tools()
        self.tool_node = None  # We'll use tools directly

    def run(self, state: AgentState) -> AgentState:
        """Execute the SQL query"""
        try:
            sql_query = state["sql_query"]
            
            # Use the database query tool
            database_tool = None
            for tool in self.database_tools:
                if tool.name == "database_query":
                    database_tool = tool
                    break
            
            if not database_tool:
                self._set_error(state, "Database query tool not available")
                return state
            
            # Execute the query
            result = database_tool._run(sql_query)
            
            # Update state
            state["query_result"] = result
            state["tools_used"].append("database_query")
            self._log_message(state, "assistant", f"Query executed. Result: {result}")
            
            return state
            
        except Exception as e:
            self._set_error(state, f"Query execution failed: {str(e)}")
            return state
