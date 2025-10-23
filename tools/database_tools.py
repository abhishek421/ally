from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from database.db_setup import get_db_manager
from config.db_config import DatabaseConfig


class DatabaseQueryInput(BaseModel):
    """Input for database query tool"""
    query: str = Field(description="SQL SELECT query to execute")


class DatabaseQueryTool(BaseTool):
    """Tool for executing database queries"""
    name: str = "database_query"
    description: str = "Execute a SQL SELECT query on the database. Use this to retrieve data from tables."
    args_schema: type[BaseModel] = DatabaseQueryInput
    
    def _run(self, query: str) -> str:
        """Execute the database query"""
        db_manager = get_db_manager()
        
        try:
            result = db_manager.execute_query(query)
            if result is None:
                return "Error: Failed to execute query or query returned no results"
            
            if not result:
                return "Query executed successfully but returned no results"
            
            # Format results as a readable string
            if len(result) == 1:
                return f"Query result: {result[0]}"
            else:
                formatted_results = []
                for i, row in enumerate(result, 1):
                    formatted_results.append(f"Row {i}: {row}")
                return f"Query returned {len(result)} rows:\n" + "\n".join(formatted_results)
                
        except Exception as e:
            return f"Error executing query: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool"""
        return self._run(query)


class SchemaInfoInput(BaseModel):
    """Input for schema info tool"""
    table_name: Optional[str] = Field(default=None, description="Name of the table to get info for. If None, returns info for all tables.")


class SchemaInfoTool(BaseTool):
    """Tool for getting database schema information"""
    name: str = "schema_info"
    description: str = "Get information about database tables and their structure. Use this to understand what data is available."
    args_schema: type[BaseModel] = SchemaInfoInput
    
    def _run(self, table_name: Optional[str] = None) -> str:
        """Get schema information"""
        db_manager = get_db_manager()
        config = DatabaseConfig()
        
        try:
            if table_name:
                # Get info for specific table
                schema_info = config.get_table_schema_info(table_name)
                if not schema_info:
                    return f"Table '{table_name}' not found in schema"
                
                result = f"Table: {table_name}\n"
                result += "Columns:\n"
                for col_name, col_info in schema_info["columns"].items():
                    result += f"  - {col_name}: {col_info['type']}"
                    if col_info["primary_key"]:
                        result += " (PRIMARY KEY)"
                    if col_info["unique"]:
                        result += " (UNIQUE)"
                    if not col_info["nullable"]:
                        result += " (NOT NULL)"
                    result += "\n"
                
                if schema_info["relationships"]:
                    result += "\nRelationships:\n"
                    for rel in schema_info["relationships"]:
                        result += f"  - {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
                
                return result
            else:
                # Get info for all tables
                all_schema_info = config.get_all_schema_info()
                result = "Database Schema:\n\n"
                
                for table_name, table_info in all_schema_info["tables"].items():
                    result += f"Table: {table_name}\n"
                    result += "Columns:\n"
                    for col_name, col_info in table_info["columns"].items():
                        result += f"  - {col_name}: {col_info['type']}"
                        if col_info["primary_key"]:
                            result += " (PRIMARY KEY)"
                        if col_info["unique"]:
                            result += " (UNIQUE)"
                        if not col_info["nullable"]:
                            result += " (NOT NULL)"
                        result += "\n"
                    result += "\n"
                
                return result
                
        except Exception as e:
            return f"Error getting schema info: {str(e)}"
    
    async def _arun(self, table_name: Optional[str] = None) -> str:
        """Async version of the tool"""
        return self._run(table_name)


class TableStatsInput(BaseModel):
    """Input for table stats tool"""
    table_name: str = Field(description="Name of the table to get statistics for")


class TableStatsTool(BaseTool):
    """Tool for getting table statistics"""
    name: str = "table_stats"
    description: str = "Get basic statistics about a table (row count, column info, etc.)"
    args_schema: type[BaseModel] = TableStatsInput
    
    def _run(self, table_name: str) -> str:
        """Get table statistics"""
        db_manager = get_db_manager()
        
        try:
            # Check if table exists
            if not db_manager.check_table_exists(table_name):
                return f"Table '{table_name}' does not exist"
            
            # Get row count
            row_count = db_manager.get_table_row_count(table_name)
            if row_count is None:
                return f"Could not get row count for table '{table_name}'"
            
            # Get table info
            table_info = db_manager.get_table_info(table_name)
            if not table_info:
                return f"Could not get table info for '{table_name}'"
            
            result = f"Table: {table_name}\n"
            result += f"Row count: {row_count}\n"
            result += f"Number of columns: {len(table_info['columns'])}\n"
            result += "Columns:\n"
            
            for col in table_info["columns"]:
                result += f"  - {col['column_name']}: {col['data_type']}"
                if col["is_nullable"] == "NO":
                    result += " (NOT NULL)"
                result += "\n"
            
            return result
            
        except Exception as e:
            return f"Error getting table stats: {str(e)}"
    
    async def _arun(self, table_name: str) -> str:
        """Async version of the tool"""
        return self._run(table_name)


class SampleQueriesTool(BaseTool):
    """Tool for getting sample queries"""
    name: str = "sample_queries"
    description: str = "Get sample queries that can be asked to the database"
    
    def _run(self) -> str:
        """Get sample queries"""
        from database.sample_data import get_sample_data_generator
        
        sample_generator = get_sample_data_generator()
        queries = sample_generator.get_sample_queries()
        
        result = "Here are some sample queries you can ask:\n\n"
        for i, query in enumerate(queries, 1):
            result += f"{i}. {query}\n"
        
        return result
    
    async def _arun(self) -> str:
        """Async version of the tool"""
        return self._run()


# List of all available tools
DATABASE_TOOLS = [
    DatabaseQueryTool(),
    SchemaInfoTool(),
    TableStatsTool(),
    SampleQueriesTool()
]


def get_database_tools() -> List[BaseTool]:
    """Get all database tools"""
    return DATABASE_TOOLS
