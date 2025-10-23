import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime, Date, Numeric, ForeignKey, Index
from sqlalchemy.sql import func


@dataclass
class ColumnDefinition:
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    auto_increment: bool = False
    default: Optional[str] = None
    unique: bool = False
    foreign_key: Optional[Dict[str, str]] = None


@dataclass
class TableDefinition:
    name: str
    columns: Dict[str, ColumnDefinition]
    indexes: List[Dict[str, Any]] = None


class DatabaseConfig:
    def __init__(self, schema_file: str = "config/schema.json"):
        self.schema_file = schema_file
        self.schema_data = self._load_schema()
        self.tables = self._parse_tables()
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load schema configuration from JSON file"""
        if not os.path.exists(self.schema_file):
            raise FileNotFoundError(f"Schema file not found: {self.schema_file}")
        
        with open(self.schema_file, 'r') as f:
            return json.load(f)
    
    def _parse_tables(self) -> Dict[str, TableDefinition]:
        """Parse schema data into TableDefinition objects"""
        tables = {}
        
        for table_name, table_config in self.schema_data.get("tables", {}).items():
            columns = {}
            
            for col_name, col_config in table_config.get("columns", {}).items():
                columns[col_name] = ColumnDefinition(
                    name=col_name,
                    type=col_config.get("type", "VARCHAR(255)"),
                    nullable=col_config.get("nullable", True),
                    primary_key=col_config.get("primary_key", False),
                    auto_increment=col_config.get("auto_increment", False),
                    default=col_config.get("default"),
                    unique=col_config.get("unique", False),
                    foreign_key=col_config.get("foreign_key")
                )
            
            tables[table_name] = TableDefinition(
                name=table_name,
                columns=columns,
                indexes=table_config.get("indexes", [])
            )
        
        return tables
    
    def get_table_names(self) -> List[str]:
        """Get list of all table names"""
        return list(self.tables.keys())
    
    def get_table_definition(self, table_name: str) -> Optional[TableDefinition]:
        """Get table definition by name"""
        return self.tables.get(table_name)
    
    def get_table_schema_info(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table"""
        table_def = self.get_table_definition(table_name)
        if not table_def:
            return {}
        
        schema_info = {
            "table_name": table_name,
            "columns": {},
            "relationships": []
        }
        
        # Add column information
        for col_name, col_def in table_def.columns.items():
            schema_info["columns"][col_name] = {
                "type": col_def.type,
                "nullable": col_def.nullable,
                "primary_key": col_def.primary_key,
                "unique": col_def.unique,
                "foreign_key": col_def.foreign_key
            }
        
        # Add relationship information
        relationships = self.schema_data.get("relationships", [])
        for rel in relationships:
            if rel["from_table"] == table_name or rel["to_table"] == table_name:
                schema_info["relationships"].append(rel)
        
        return schema_info
    
    def get_all_schema_info(self) -> Dict[str, Any]:
        """Get complete schema information for all tables"""
        schema_info = {
            "tables": {},
            "relationships": self.schema_data.get("relationships", [])
        }
        
        for table_name in self.get_table_names():
            schema_info["tables"][table_name] = self.get_table_schema_info(table_name)
        
        return schema_info
    
    def update_schema(self, new_schema: Dict[str, Any]) -> None:
        """Update schema configuration"""
        self.schema_data = new_schema
        self.tables = self._parse_tables()
        
        # Save updated schema to file
        with open(self.schema_file, 'w') as f:
            json.dump(self.schema_data, f, indent=2)
    
    def get_sqlalchemy_metadata(self) -> MetaData:
        """Convert schema to SQLAlchemy metadata"""
        metadata = MetaData()
        
        for table_name, table_def in self.tables.items():
            columns = []
            
            for col_name, col_def in table_def.columns.items():
                # Map type strings to SQLAlchemy types
                sqlalchemy_type = self._get_sqlalchemy_type(col_def.type)
                
                # Create column
                column = Column(
                    col_name,
                    sqlalchemy_type,
                    nullable=col_def.nullable,
                    primary_key=col_def.primary_key,
                    autoincrement=col_def.auto_increment,
                    unique=col_def.unique
                )
                
                # Add default value
                if col_def.default == "CURRENT_TIMESTAMP":
                    column.default = func.now()
                elif col_def.default:
                    column.default = col_def.default
                
                columns.append(column)
            
            # Create table
            table = Table(table_name, metadata, *columns)
            
            # Add indexes
            for index_config in table_def.indexes:
                index_columns = [getattr(table.c, col) for col in index_config["columns"]]
                Index(f"idx_{table_name}_{'_'.join(index_config['columns'])}", *index_columns)
        
        return metadata
    
    def _get_sqlalchemy_type(self, type_str: str):
        """Convert string type to SQLAlchemy type"""
        type_mapping = {
            "INTEGER": Integer,
            "VARCHAR": String,
            "TIMESTAMP": DateTime,
            "DATE": Date,
            "DECIMAL": Numeric,
            "TEXT": String
        }
        
        # Handle VARCHAR with length
        if type_str.startswith("VARCHAR"):
            return String
        
        # Handle DECIMAL with precision
        if type_str.startswith("DECIMAL"):
            return Numeric
        
        return type_mapping.get(type_str, String)
    
    def validate_query_safety(self, query: str) -> bool:
        """Basic validation to ensure query is safe (no DDL/DML operations)"""
        query_lower = query.lower().strip()
        
        # Allow only SELECT queries
        if not query_lower.startswith("select"):
            return False
        
        # Block dangerous operations
        dangerous_keywords = [
            "drop", "delete", "insert", "update", "alter", "create", 
            "truncate", "grant", "revoke", "exec", "execute"
        ]
        
        for keyword in dangerous_keywords:
            if keyword in query_lower:
                return False
        
        return True
