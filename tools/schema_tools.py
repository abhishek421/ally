from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from config.db_config import DatabaseConfig


class SchemaValidationInput(BaseModel):
    """Input for schema validation tool"""
    query: str = Field(description="SQL query to validate")


class SchemaValidationTool(BaseTool):
    """Tool for validating SQL queries against schema"""
    name: str = "schema_validation"
    description: str = "Validate if a SQL query is safe and follows the database schema"
    args_schema: type[BaseModel] = SchemaValidationInput
    
    def _run(self, query: str) -> str:
        """Validate the SQL query"""
        config = DatabaseConfig()
        
        try:
            # Check query safety
            if not config.validate_query_safety(query):
                return "Query validation failed: Query contains unsafe operations or is not a SELECT statement"
            
            # Basic syntax validation (could be enhanced with actual SQL parsing)
            query_lower = query.lower().strip()
            
            if not query_lower.startswith("select"):
                return "Query validation failed: Only SELECT queries are allowed"
            
            # Check for valid table names
            table_names = config.get_table_names()
            for table_name in table_names:
                if table_name.lower() in query_lower:
                    return f"Query validation passed: Query references valid table '{table_name}'"
            
            return "Query validation warning: Query doesn't reference any known tables"
            
        except Exception as e:
            return f"Error validating query: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool"""
        return self._run(query)


class ColumnInfoInput(BaseModel):
    """Input for column info tool"""
    table_name: str = Field(description="Name of the table")
    column_name: Optional[str] = Field(default=None, description="Name of the column. If None, returns all columns.")


class ColumnInfoTool(BaseTool):
    """Tool for getting detailed column information"""
    name: str = "column_info"
    description: str = "Get detailed information about table columns including data types and constraints"
    args_schema: type[BaseModel] = ColumnInfoInput
    
    def _run(self, table_name: str, column_name: Optional[str] = None) -> str:
        """Get column information"""
        config = DatabaseConfig()
        
        try:
            schema_info = config.get_table_schema_info(table_name)
            if not schema_info:
                return f"Table '{table_name}' not found in schema"
            
            if column_name:
                # Get info for specific column
                if column_name not in schema_info["columns"]:
                    return f"Column '{column_name}' not found in table '{table_name}'"
                
                col_info = schema_info["columns"][column_name]
                result = f"Column: {table_name}.{column_name}\n"
                result += f"Type: {col_info['type']}\n"
                result += f"Nullable: {col_info['nullable']}\n"
                result += f"Primary Key: {col_info['primary_key']}\n"
                result += f"Unique: {col_info['unique']}\n"
                
                if col_info["foreign_key"]:
                    result += f"Foreign Key: {col_info['foreign_key']['table']}.{col_info['foreign_key']['column']}\n"
                
                return result
            else:
                # Get info for all columns
                result = f"Columns in table '{table_name}':\n\n"
                for col_name, col_info in schema_info["columns"].items():
                    result += f"Column: {col_name}\n"
                    result += f"  Type: {col_info['type']}\n"
                    result += f"  Nullable: {col_info['nullable']}\n"
                    result += f"  Primary Key: {col_info['primary_key']}\n"
                    result += f"  Unique: {col_info['unique']}\n"
                    if col_info["foreign_key"]:
                        result += f"  Foreign Key: {col_info['foreign_key']['table']}.{col_info['foreign_key']['column']}\n"
                    result += "\n"
                
                return result
                
        except Exception as e:
            return f"Error getting column info: {str(e)}"
    
    async def _arun(self, table_name: str, column_name: Optional[str] = None) -> str:
        """Async version of the tool"""
        return self._run(table_name, column_name)


class RelationshipInfoInput(BaseModel):
    """Input for relationship info tool"""
    table_name: Optional[str] = Field(default=None, description="Name of the table to get relationships for. If None, returns all relationships.")


class RelationshipInfoTool(BaseTool):
    """Tool for getting table relationship information"""
    name: str = "relationship_info"
    description: str = "Get information about relationships between tables"
    args_schema: type[BaseModel] = RelationshipInfoInput
    
    def _run(self, table_name: Optional[str] = None) -> str:
        """Get relationship information"""
        config = DatabaseConfig()
        
        try:
            all_schema_info = config.get_all_schema_info()
            relationships = all_schema_info["relationships"]
            
            if table_name:
                # Get relationships for specific table
                table_relationships = []
                for rel in relationships:
                    if rel["from_table"] == table_name or rel["to_table"] == table_name:
                        table_relationships.append(rel)
                
                if not table_relationships:
                    return f"No relationships found for table '{table_name}'"
                
                result = f"Relationships for table '{table_name}':\n\n"
                for rel in table_relationships:
                    result += f"- {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
                    result += f"  Type: {rel['type']}\n\n"
                
                return result
            else:
                # Get all relationships
                if not relationships:
                    return "No relationships defined in the database schema"
                
                result = "Database Relationships:\n\n"
                for rel in relationships:
                    result += f"- {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
                    result += f"  Type: {rel['type']}\n\n"
                
                return result
                
        except Exception as e:
            return f"Error getting relationship info: {str(e)}"
    
    async def _arun(self, table_name: Optional[str] = None) -> str:
        """Async version of the tool"""
        return self._run(table_name)


class QuerySuggestionsInput(BaseModel):
    """Input for query suggestions tool"""
    intent: str = Field(description="The intent or type of query the user wants to make")


class QuerySuggestionsTool(BaseTool):
    """Tool for suggesting SQL queries based on intent"""
    name: str = "query_suggestions"
    description: str = "Suggest SQL queries based on user intent and available schema"
    args_schema: type[BaseModel] = QuerySuggestionsInput
    
    def _run(self, intent: str) -> str:
        """Suggest queries based on intent"""
        config = DatabaseConfig()
        table_names = config.get_table_names()
        
        intent_lower = intent.lower()
        
        suggestions = []
        
        if "top" in intent_lower and "companies" in intent_lower:
            if "subscription" in intent_lower or "recent" in intent_lower:
                suggestions.append("SELECT * FROM companies ORDER BY subscription_date DESC LIMIT 5;")
            else:
                suggestions.append("SELECT * FROM companies ORDER BY created_at DESC LIMIT 5;")
        
        elif "count" in intent_lower and "people" in intent_lower:
            if "country" in intent_lower:
                suggestions.append("SELECT country, COUNT(*) as count FROM companies GROUP BY country;")
            else:
                suggestions.append("SELECT COUNT(*) as total_people FROM people;")
        
        elif "country" in intent_lower and "companies" in intent_lower:
            suggestions.append("SELECT country, COUNT(*) as count FROM companies GROUP BY country;")
        
        elif "job" in intent_lower or "title" in intent_lower:
            suggestions.append("SELECT job_title, COUNT(*) as count FROM people GROUP BY job_title;")
        
        elif "born" in intent_lower or "birth" in intent_lower:
            suggestions.append("SELECT * FROM people WHERE date_of_birth >= '1990-01-01';")
        
        elif "cities" in intent_lower:
            suggestions.append("SELECT DISTINCT city FROM companies WHERE city IS NOT NULL;")
        
        elif "manager" in intent_lower:
            suggestions.append("SELECT * FROM people WHERE job_title LIKE '%Manager%';")
        
        elif "subscription" in intent_lower and "2020" in intent_lower:
            suggestions.append("SELECT * FROM companies WHERE subscription_date >= '2020-01-01';")
        
        elif "total" in intent_lower and "people" in intent_lower:
            suggestions.append("SELECT COUNT(*) as total_people FROM people;")
        
        else:
            # Generic suggestions
            suggestions.extend([
                f"SELECT * FROM {table_names[0]} LIMIT 10;",
                f"SELECT COUNT(*) FROM {table_names[0]};",
                f"SELECT * FROM {table_names[1]} LIMIT 10;" if len(table_names) > 1 else ""
            ])
        
        if suggestions:
            result = f"Based on your intent '{intent}', here are some suggested queries:\n\n"
            for i, suggestion in enumerate(suggestions, 1):
                if suggestion:  # Skip empty suggestions
                    result += f"{i}. {suggestion}\n"
        else:
            result = f"No specific suggestions for intent '{intent}'. Try asking about companies, people, countries, job titles, or subscription dates."
        
        return result
    
    async def _arun(self, intent: str) -> str:
        """Async version of the tool"""
        return self._run(intent)


# List of all schema tools
SCHEMA_TOOLS = [
    SchemaValidationTool(),
    ColumnInfoTool(),
    RelationshipInfoTool(),
    QuerySuggestionsTool()
]


def get_schema_tools() -> List[BaseTool]:
    """Get all schema tools"""
    return SCHEMA_TOOLS
