# database/prisma_client.py
from prisma import Prisma
from typing import Optional
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class PrismaClient:
    """Prisma client wrapper with connection management and idle timeout handling"""

    def __init__(self):
        self.client: Optional[Prisma] = None
        self._connection_lock = asyncio.Lock()
        self._last_activity = 0  # Track last successful DB operation
        # Reconnect after 4 minutes of idle (before typical 5 min server timeout)
        self._max_idle_seconds = 240

    async def connect(self):
        """Connect to PostgreSQL database"""
        async with self._connection_lock:
            if not self.client:
                try:
                    self.client = Prisma()
                    await self.client.connect()
                    self._last_activity = time.time()
                    logger.info("Connected to PostgreSQL database")
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
        Get Prisma client instance.
        Proactively reconnects if idle too long to prevent server-side timeout.
        Also handles connection loss gracefully.
        """
        if not self.client:
            await self.connect()
        else:
            # Check if connection has been idle for too long
            idle_time = time.time() - self._last_activity
            if idle_time > self._max_idle_seconds:
                logger.info(f"Connection idle for {idle_time:.0f}s, proactively reconnecting to prevent timeout...")
                try:
                    await self.disconnect()
                except Exception:
                    pass
                await self.connect()
            else:
                # Validate connection is still alive
                try:
                    await self.client.query_raw("SELECT 1")
                    self._last_activity = time.time()
                except Exception as e:
                    logger.warning(f"Connection validation failed: {e}. Reconnecting...")
                    try:
                        await self.disconnect()
                    except Exception:
                        pass
                    await self.connect()

        # Update last activity timestamp
        self._last_activity = time.time()
        return self.client

    async def health_check(self) -> bool:
        """Check database connection health"""
        try:
            client = await self.get_client()
            # Simple query to test connection
            await client.query_raw("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global instance
prisma_client = PrismaClient()
