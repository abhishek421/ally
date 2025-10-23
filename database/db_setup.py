import os
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from config.db_config import DatabaseConfig

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, schema_file: str = "config/schema.json"):
        self.config = DatabaseConfig(schema_file)
        self.engine = None
        self.session = None
        self._connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from environment variables"""
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "chatbot_db")
        username = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        
        # Force TCP connection and add connection parameters
        return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}?sslmode=disable"
    
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            # Create engine with explicit connection parameters
            self.engine = create_engine(
                self._connection_string, 
                echo=False,
                connect_args={
                    "host": os.getenv("DB_HOST", "localhost"),
                    "port": os.getenv("DB_PORT", "5432"),
                    "sslmode": "disable"
                }
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            
            logger.info("Database connection established successfully")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.session:
            self.session.close()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connection closed")
    
    def create_database(self) -> bool:
        """Create database if it doesn't exist"""
        try:
            # Connect to postgres database to create the target database
            db_name = os.getenv("DB_NAME", "chatbot_db")
            temp_connection_string = self._connection_string.replace(f"/{db_name}", "/postgres")
            
            temp_engine = create_engine(temp_connection_string)
            
            with temp_engine.connect() as conn:
                # Check if database exists
                result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
                if not result.fetchone():
                    # Create database
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    logger.info(f"Database '{db_name}' created successfully")
                else:
                    logger.info(f"Database '{db_name}' already exists")
            
            temp_engine.dispose()
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to create database: {e}")
            return False
    
    def create_tables(self) -> bool:
        """Create all tables based on schema configuration"""
        try:
            if not self.engine:
                logger.error("No database connection available")
                return False
            
            metadata = self.config.get_sqlalchemy_metadata()
            metadata.create_all(self.engine)
            
            logger.info("All tables created successfully")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to create tables: {e}")
            return False
    
    def drop_tables(self) -> bool:
        """Drop all tables (use with caution!)"""
        try:
            if not self.engine:
                logger.error("No database connection available")
                return False
            
            metadata = self.config.get_sqlalchemy_metadata()
            metadata.drop_all(self.engine)
            
            logger.info("All tables dropped successfully")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to drop tables: {e}")
            return False
    
    def execute_query(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Execute a SELECT query and return results"""
        try:
            if not self.engine:
                logger.error("No database connection available")
                return None
            
            # Validate query safety
            if not self.config.validate_query_safety(query):
                logger.error("Query failed safety validation")
                return None
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                columns = result.keys()
                rows = result.fetchall()
                
                # Convert to list of dictionaries
                return [dict(zip(columns, row)) for row in rows]
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to execute query: {e}")
            return None
    
    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific table"""
        try:
            if not self.engine:
                logger.error("No database connection available")
                return None
            
            query = f"""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
            """
            
            result = self.execute_query(query)
            if result:
                return {
                    "table_name": table_name,
                    "columns": result
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return None
    
    def get_all_tables_info(self) -> Dict[str, Any]:
        """Get information about all tables"""
        tables_info = {}
        
        for table_name in self.config.get_table_names():
            table_info = self.get_table_info(table_name)
            if table_info:
                tables_info[table_name] = table_info
        
        return tables_info
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        try:
            if not self.engine:
                return False
            
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = :table_name
            );
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"table_name": table_name})
                return result.scalar()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to check table existence: {e}")
            return False
    
    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """Get row count for a specific table"""
        try:
            if not self.engine:
                return None
            
            query = f"SELECT COUNT(*) FROM {table_name}"
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                return result.scalar()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get row count: {e}")
            return None
    
    def initialize_database(self) -> bool:
        """Complete database initialization process"""
        logger.info("Starting database initialization...")
        
        # Create database
        if not self.create_database():
            return False
        
        # Connect to the database
        if not self.connect():
            return False
        
        # Create tables
        if not self.create_tables():
            return False
        
        logger.info("Database initialization completed successfully")
        return True
    
    def reset_database(self) -> bool:
        """Reset database by dropping and recreating all tables"""
        logger.info("Resetting database...")
        
        if not self.connect():
            return False
        
        if not self.drop_tables():
            return False
        
        if not self.create_tables():
            return False
        
        logger.info("Database reset completed successfully")
        return True


# Global database manager instance
db_manager = DatabaseManager()


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    return db_manager
