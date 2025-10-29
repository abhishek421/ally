# database/prisma_client.py
from prisma import Prisma
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class PrismaClient:
    """Prisma client wrapper with connection management"""
    
    def __init__(self):
        self.client: Optional[Prisma] = None
        self._connection_lock = asyncio.Lock()
    
    async def connect(self):
        """Connect to PostgreSQL database"""
        async with self._connection_lock:
            if not self.client:
                try:
                    self.client = Prisma()
                    await self.client.connect()
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
        """Get Prisma client instance"""
        if not self.client:
            await self.connect()
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
