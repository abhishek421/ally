"""Database connection and session management."""

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Global engine and session factory
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_database_url() -> str:
    """Get database URL from settings.
    
    Raises:
        ValueError: If database_url is not set in environment variables
    """
    if not settings.database_url:
        raise ValueError(
            "DATABASE_URL is required. Please set it in your .env file. "
            "Example: DATABASE_URL=postgresql://user:password@localhost:5433/dbname"
        )
    return settings.database_url


def get_engine() -> Engine:
    """Get or create database engine with connection pooling.
    
    The engine uses a connection pool to efficiently manage database connections.
    Connections are reused across multiple tool calls, and stale connections
    are automatically recycled.
    """
    global _engine
    if _engine is None:
        database_url = get_database_url()
        _engine = create_engine(
            database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=settings.db_pool_recycle,  # Recycle connections after this many seconds
            pool_timeout=settings.db_pool_timeout,  # Wait time for connection from pool
            echo=settings.db_echo,  # Log SQL queries (for debugging)
            connect_args={
                "connect_timeout": settings.db_connect_timeout,  # Connection timeout
                "application_name": "analyst_ai",  # For database monitoring
            },
        )
        logger.info(
            "Database engine created",
            database_url=database_url.split("@")[-1],
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _SessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Get database session context manager."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        # Set default schema to public
        session.execute(text("SET search_path TO public"))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection() -> bool:
    """Test database connection."""
    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
    except Exception as e:
        logger.error("Database connection test failed", error=str(e))
        return False

