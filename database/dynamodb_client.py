# database/dynamodb_client.py
import boto3
from typing import Optional
from botocore.config import Config
import logging
import os

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """DynamoDB client wrapper"""
    
    def __init__(self):
        self.client: Optional[boto3.resource] = None
        # Use AWS_REGION environment variable (common across services) - no defaults
        region = os.getenv("AWS_REGION")

        # Validate required configuration
        if not region:
            raise ValueError("AWS_REGION environment variable is required")

        self.config = Config(
            retries={'max_attempts': 3},
            region_name=region
        )
    
    def get_client(self):
        """Get DynamoDB client instance"""
        if not self.client:
            try:
                self.client = boto3.resource('dynamodb', config=self.config)
                logger.info("Initialized DynamoDB client")
            except Exception as e:
                logger.error(f"Failed to initialize DynamoDB client: {e}")
                raise
        return self.client
    
    def get_table(self, table_name: str):
        """Get DynamoDB table"""
        client = self.get_client()
        try:
            table = client.Table(table_name)
            logger.debug(f"Accessed DynamoDB table: {table_name}")
            return table
        except Exception as e:
            logger.error(f"Failed to access DynamoDB table {table_name}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check DynamoDB connection health"""
        try:
            client = self.get_client()
            # List tables to test connection
            list(client.tables.all())
            return True
        except Exception as e:
            logger.error(f"DynamoDB health check failed: {e}")
            return False


# Global instance
dynamodb_client = DynamoDBClient()
