# database/dynamodb_client.py
import boto3
from typing import Optional
from botocore.config import Config
import logging
import os

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """DynamoDB client wrapper with connection pooling and reuse"""
    
    def __init__(self):
        self.resource_client: Optional[boto3.resource] = None
        self.service_client: Optional[boto3.client] = None
        
        # Use AWS_REGION environment variable (common across services)
        region = os.getenv("AWS_REGION", "us-east-1")
        
        # Connection pool configuration for optimal performance
        max_pool_connections = int(os.getenv("DYNAMODB_MAX_POOL_CONNECTIONS", "50"))
        connect_timeout = int(os.getenv("DYNAMODB_CONNECT_TIMEOUT", "10"))
        read_timeout = int(os.getenv("DYNAMODB_READ_TIMEOUT", "30"))
        
        self.config = Config(
            retries={'max_attempts': 3},
            region_name=region,
            # Connection pool settings
            max_pool_connections=max_pool_connections,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            # TCP keepalive for connection reuse
            tcp_keepalive=True,
        )
        
        self.region = region
        self.max_pool_connections = max_pool_connections
    
    def get_resource(self):
        """
        Get DynamoDB resource client instance (reuses connection pool).
        Resource client provides high-level abstraction.
        """
        if not self.resource_client:
            try:
                self.resource_client = boto3.resource('dynamodb', config=self.config)
                logger.info(
                    f"Initialized DynamoDB resource client with connection pooling "
                    f"(max_pool_connections={self.max_pool_connections})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize DynamoDB resource client: {e}")
                raise
        return self.resource_client
    
    def get_client(self):
        """
        Get DynamoDB service client instance (reuses connection pool).
        Service client provides low-level API access and better connection reuse.
        """
        if not self.service_client:
            try:
                self.service_client = boto3.client('dynamodb', config=self.config)
                logger.info(
                    f"Initialized DynamoDB service client with connection pooling "
                    f"(max_pool_connections={self.max_pool_connections})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize DynamoDB service client: {e}")
                raise
        return self.service_client
    
    def get_table(self, table_name: str):
        """
        Get DynamoDB table using resource client (uses connection pool).
        For high-throughput scenarios, consider using get_client() for direct API calls.
        """
        resource = self.get_resource()
        try:
            table = resource.Table(table_name)
            logger.debug(f"Accessed DynamoDB table: {table_name}")
            return table
        except Exception as e:
            logger.error(f"Failed to access DynamoDB table {table_name}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check DynamoDB connection health and pool status.
        This validates that connections can be acquired from the pool.
        """
        try:
            # Use service client for faster health check
            client = self.get_client()
            # Simple API call to test connection (uses pool)
            client.list_tables(Limit=1)
            return True
        except Exception as e:
            logger.error(f"DynamoDB health check failed: {e}")
            return False
    
    def get_pool_stats(self) -> dict:
        """Get connection pool configuration statistics"""
        return {
            "max_pool_connections": self.max_pool_connections,
            "region": self.region,
            "resource_client_initialized": self.resource_client is not None,
            "service_client_initialized": self.service_client is not None,
        }


# Global instance
dynamodb_client = DynamoDBClient()
