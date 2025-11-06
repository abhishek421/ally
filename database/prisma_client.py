# database/prisma_client.py
from prisma import Prisma
from typing import Optional
import asyncio
import logging
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)


class PrismaClient:
    """Prisma client wrapper with connection management and pooling"""
    
    def __init__(self):
        self.client: Optional[Prisma] = None
        self._connection_lock = asyncio.Lock()
        self._ensure_connection_pool_config()
    
    def _ensure_connection_pool_config(self):
        """
        Ensure DATABASE_URL has connection pool parameters.
        Adds them if missing to optimize connection reuse.
        """
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            return
        
        try:
            # Parse the URL
            parsed = urlparse(database_url)
            query_params = parse_qs(parsed.query)
            
            # Default pool configuration (can be overridden via env vars)
            pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
            pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
            max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
            
            # Add connection pool parameters if not present
            updated = False
            if "connection_limit" not in query_params:
                query_params["connection_limit"] = [str(pool_size)]
                updated = True
            if "pool_timeout" not in query_params:
                query_params["pool_timeout"] = [str(pool_timeout)]
                updated = True
            if "max_overflow" not in query_params:
                query_params["max_overflow"] = [str(max_overflow)]
                updated = True
            
            if updated:
                # Reconstruct URL with pool parameters
                new_query = urlencode(query_params, doseq=True)
                new_parsed = parsed._replace(query=new_query)
                new_url = urlunparse(new_parsed)
                
                # Update environment variable
                os.environ["DATABASE_URL"] = new_url
                logger.info(
                    f"Enhanced DATABASE_URL with connection pool settings: "
                    f"connection_limit={pool_size}, pool_timeout={pool_timeout}, max_overflow={max_overflow}"
                )
            else:
                logger.debug("DATABASE_URL already has connection pool parameters")
                
        except Exception as e:
            logger.warning(f"Could not enhance DATABASE_URL with pool config: {e}")
    
    async def connect(self):
        """Connect to PostgreSQL database with connection pooling"""
        async with self._connection_lock:
            if not self.client:
                try:
                    # Prisma automatically uses connection pooling via DATABASE_URL parameters
                    self.client = Prisma()
                    await self.client.connect()
                    
                    # Log connection pool info
                    pool_size = os.getenv("DB_POOL_SIZE", "20")
                    logger.info(
                        f"Connected to PostgreSQL database with connection pooling "
                        f"(pool_size={pool_size})"
                    )
                except Exception as e:
                    logger.error(f"Failed to connect to PostgreSQL: {e}")
                    raise
    
    async def disconnect(self):
        """Disconnect from database"""
        async with self._connection_lock:
            if self.client:
                try:
                    await self.client.disconnect()
                    self.client = None
                    logger.info("Disconnected from PostgreSQL database")
                except Exception as e:
                    logger.error(f"Error disconnecting from PostgreSQL: {e}")
    
    async def get_client(self) -> Prisma:
        """
        Get Prisma client instance (reuses pooled connection).
        Connection pooling is handled automatically by Prisma via DATABASE_URL.
        """
        if not self.client:
            await self.connect()
        return self.client
    
    async def health_check(self) -> bool:
        """
        Check database connection health and pool status.
        This validates that connections can be acquired from the pool.
        """
        try:
            client = await self.get_client()
            # Simple query to test connection (uses pool)
            await client.query_raw("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_pool_stats(self) -> dict:
        """
        Get connection pool statistics.
        Note: Prisma doesn't expose pool stats directly, but this provides
        configuration information.
        """
        return {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "connected": self.client is not None
        }


# Global instance
prisma_client = PrismaClient()
