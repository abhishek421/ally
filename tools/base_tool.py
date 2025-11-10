# tools/base_tool.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel
from enum import Enum
import asyncio
from datetime import datetime
import logging
from database.redis_client import redis_client

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Standardized tool result format"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    execution_time_ms: int
    cached: bool = False


class QueryType(str, Enum):
    """Types of queries tools can handle"""
    SEARCH = "search"
    GET_BY_ID = "get_by_id"
    LIST = "list"
    ANALYTICS = "analytics"
    GET_LATEST = "get_latest"
    GET_BY_THREAD = "get_by_thread"
    # TODO: Write operations not yet implemented
    # CREATE = "create"
    # UPDATE = "update"
    # DELETE = "delete"


class BaseTool(ABC):
    """Base class for all AI Analyst tools"""
    
    def __init__(self, workspace_id: str, user_id: str):
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.cache_ttl = 300  # 5 minutes default
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    @abstractmethod
    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        """Execute tool operation - subclasses must implement this"""
        pass

    async def execute_with_validation(self, query_type: QueryType, **kwargs) -> ToolResult:
        """
        Execute tool operation with workspace access validation
        This is the main entry point that should be called by agents
        """
        # Validate workspace access first
        has_access = await self._validate_workspace_access()
        if not has_access:
            return ToolResult(
                success=False,
                error=f"Access denied: User {self.user_id} does not have access to workspace {self.workspace_id}",
                execution_time_ms=0,
                metadata={
                    "workspace_id": self.workspace_id,
                    "user_id": self.user_id,
                    "operation": query_type.value
                }
            )

        # Execute the actual operation
        return await self.execute(query_type, **kwargs)
    
    @abstractmethod
    def get_supported_operations(self) -> List[QueryType]:
        """Return list of supported operations"""
        pass
    
    async def _validate_workspace_access(self) -> bool:
        """
        Validate user has access to workspace
        Checks if user is a member of the workspace
        """
        try:
            from database.prisma_client import prisma_client

            client = await prisma_client.get_client()

            # Check if user is a member of the workspace
            workspace_member = await client.workspacemember.find_first(
                where={
                    'workspaceId': self.workspace_id,
                    'userId': self.user_id
                }
            )

            if workspace_member is None:
                self.logger.warning(
                    f"Access denied: User {self.user_id} is not a member of workspace {self.workspace_id}"
                )
                return False

            self.logger.debug(
                f"Access validated: User {self.user_id} has access to workspace {self.workspace_id}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error validating workspace access: {e}")
            # Fail closed - deny access on error
            return False
    
    async def _cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for operation"""
        params = sorted(kwargs.items())
        return f"{self.__class__.__name__}:{operation}:{self.workspace_id}:{hash(str(params))}"
    
    async def _execute_with_cache(self, operation: str, **kwargs) -> ToolResult:
        """Execute operation with caching"""
        try:
            # Generate cache key
            cache_key = await self._cache_key(operation, **kwargs)
            
            # Try to get from cache first
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return ToolResult(
                    success=cached_result["success"],
                    data=cached_result["data"],
                    error=cached_result.get("error"),
                    metadata=cached_result.get("metadata", {}),
                    execution_time_ms=cached_result.get("execution_time_ms", 0),
                    cached=True
                )
            
            # Execute the operation
            self.logger.debug(f"Cache miss for key: {cache_key}")
            result = await self.execute(operation, **kwargs)
            
            # Cache the result if successful
            if result.success:
                cache_data = {
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "metadata": result.metadata,
                    "execution_time_ms": result.execution_time_ms
                }
                await redis_client.set(cache_key, cache_data, self.cache_ttl)
                self.logger.debug(f"Cached result for key: {cache_key}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in cached execution: {e}")
            # Fallback to direct execution
            return await self.execute(operation, **kwargs)
    
    def _log_operation(self, operation: str, success: bool, execution_time_ms: int, **kwargs):
        """Log tool operation"""
        self.logger.info(
            f"Tool operation: {operation}, "
            f"workspace: {self.workspace_id}, "
            f"user: {self.user_id}, "
            f"success: {success}, "
            f"execution_time_ms: {execution_time_ms}"
        )
    
    async def _handle_error(self, error: Exception, operation: str) -> ToolResult:
        """Handle errors consistently across tools"""
        error_msg = str(error)
        self.logger.error(f"Error in {operation}: {error_msg}")
        
        return ToolResult(
            success=False,
            error=error_msg,
            execution_time_ms=0,
            metadata={"operation": operation, "workspace_id": self.workspace_id}
        )
    
    async def clear_cache(self, operation: Optional[str] = None) -> int:
        """
        Clear cache for this tool using pattern matching
        Returns the number of keys deleted
        """
        try:
            if operation:
                # Clear specific operation cache
                pattern = f"{self.__class__.__name__}:{operation}:{self.workspace_id}:*"
            else:
                # Clear all cache for this tool
                pattern = f"{self.__class__.__name__}:*:{self.workspace_id}:*"

            self.logger.info(f"Clearing cache for pattern: {pattern}")

            # Get Redis client
            redis_conn = await redis_client.get_client()
            
            # If Redis is not configured, return 0 (no cache to clear)
            if redis_conn is None:
                self.logger.debug("Redis not configured - no cache to clear")
                return 0

            # Use SCAN to find matching keys (more efficient than KEYS for production)
            deleted_count = 0
            cursor = 0

            while True:
                # SCAN returns (cursor, keys) tuple
                cursor, keys = await redis_conn.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100  # Scan 100 keys at a time
                )

                if keys:
                    # Delete all matching keys
                    deleted = await redis_conn.delete(*keys)
                    deleted_count += deleted
                    self.logger.debug(f"Deleted {deleted} keys matching pattern: {pattern}")

                # Break when cursor returns to 0 (full iteration complete)
                if cursor == 0:
                    break

            self.logger.info(f"Cache cleared: {deleted_count} keys deleted for pattern: {pattern}")
            return deleted_count

        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return 0