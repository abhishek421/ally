# database/redis_client.py
import redis.asyncio as redis
from typing import Optional, Any
import json
import logging
import os

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with connection pooling for optimal performance"""
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, db: Optional[int] = None):
        # Use environment variables (common across services) with defaults
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.db = db if db is not None else int(os.getenv("REDIS_DB", "0"))
        
        # Connection pool configuration
        self.pool_size = int(os.getenv("REDIS_POOL_SIZE", "50"))
        self.pool_timeout = int(os.getenv("REDIS_POOL_TIMEOUT", "5"))
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "100"))
        
        self.client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
    
    async def connect(self):
        """Connect to Redis with connection pooling"""
        if not self.connection_pool:
            try:
                # Create connection pool for optimal performance
                self.connection_pool = redis.ConnectionPool(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    max_connections=self.max_connections,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30,  # Check connection health every 30s
                )
                
                # Create Redis client using the connection pool
                self.client = redis.Redis(
                    connection_pool=self.connection_pool,
                    decode_responses=True
                )
                
                # Test connection
                await self.client.ping()
                logger.info(
                    f"Connected to Redis at {self.host}:{self.port} "
                    f"with connection pooling (max_connections={self.max_connections})"
                )
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.connection_pool = None
                self.client = None
                raise
    
    async def disconnect(self):
        """Disconnect from Redis and close connection pool"""
        if self.client:
            try:
                await self.client.close()
                self.client = None
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")
        
        if self.connection_pool:
            try:
                await self.connection_pool.aclose()
                self.connection_pool = None
                logger.info("Disconnected from Redis and closed connection pool")
            except Exception as e:
                logger.error(f"Error closing Redis connection pool: {e}")
    
    async def get_client(self) -> redis.Redis:
        """
        Get Redis client instance (reuses connections from pool).
        Connection pooling ensures efficient connection reuse across requests.
        """
        if not self.client or not self.connection_pool:
            await self.connect()
        return self.client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        try:
            client = await self.get_client()
            serialized_value = json.dumps(value)
            await client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            client = await self.get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def health_check(self) -> bool:
        """
        Check Redis connection health and pool status.
        This validates that connections can be acquired from the pool.
        """
        try:
            client = await self.get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def get_pool_stats(self) -> dict:
        """
        Get connection pool statistics (only serializable configuration values).
        Note: Redis ConnectionPool doesn't expose reliable runtime connection counts
        in a serializable format, so we only return configuration values.
        """
        if self.connection_pool:
            return {
                "max_connections": self.max_connections,
                "pool_size": self.pool_size,
                "pool_timeout": self.pool_timeout,
                "connected": self.client is not None,
                "host": self.host,
                "port": self.port,
                "db": self.db,
            }
        return {
            "max_connections": self.max_connections,
            "pool_size": self.pool_size,
            "connected": False
        }


# Global instance
redis_client = RedisClient()
