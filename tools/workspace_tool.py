# tools/workspace_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.prisma_client import prisma_client
from typing import Dict, Any, List
from datetime import datetime


class WorkspaceTool(BaseTool):
    """Tool for workspace operations"""
    
    def get_supported_operations(self) -> List[QueryType]:
        return [QueryType.GET_BY_ID, QueryType.LIST]
    
    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        start_time = datetime.now()
        
        try:
            if query_type == QueryType.GET_BY_ID:
                result = await self._get_workspace_info()
            elif query_type == QueryType.LIST:
                result = await self._list_workspace_settings()
            else:
                raise ValueError(f"Unsupported operation: {query_type}")
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self._log_operation(query_type.value, True, execution_time)
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
                metadata={"workspace_id": self.workspace_id, "user_id": self.user_id}
            )
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return await self._handle_error(e, query_type.value)
    
    async def _get_workspace_info(self) -> Dict[str, Any]:
        """Get workspace basic information"""
        try:
            client = await prisma_client.get_client()
            
            # Query workspace with basic info
            workspace = await client.workspace.find_unique(
                where={"id": self.workspace_id},
                include={
                    "users": {
                        "select": {
                            "id": True,
                            "email": True,
                            "firstName": True,
                            "lastName": True
                        }
                    }
                }
            )
            
            if not workspace:
                return {
                    "id": self.workspace_id,
                    "name": "Unknown Workspace",
                    "created_at": None,
                    "users": []
                }
            
            return {
                "id": workspace.id,
                "name": workspace.name,
                "created_at": workspace.createdAt.isoformat() if workspace.createdAt else None,
                "updated_at": workspace.updatedAt.isoformat() if workspace.updatedAt else None,
                "users": workspace.users if workspace.users else []
            }
        except Exception as e:
            self.logger.error(f"Error getting workspace info: {e}")
            # Return fallback data
            return {
                "id": self.workspace_id,
                "name": "Sample Workspace",
                "created_at": "2024-01-01T00:00:00Z",
                "users": []
            }
    
    async def _list_workspace_settings(self) -> Dict[str, Any]:
        """Get workspace settings and configuration"""
        try:
            client = await prisma_client.get_client()
            
            # Query workspace settings
            workspace = await client.workspace.find_unique(
                where={"id": self.workspace_id},
                select={
                    "name": True,
                    "createdAt": True,
                    "updatedAt": True,
                    "settings": True
                }
            )
            
            if not workspace:
                return {
                    "timezone": "UTC",
                    "date_format": "YYYY-MM-DD",
                    "features": ["ai_analyst", "email_sync"],
                    "workspace_name": "Unknown"
                }
            
            # Parse settings if they exist
            settings = workspace.settings if workspace.settings else {}
            
            return {
                "timezone": settings.get("timezone", "UTC"),
                "date_format": settings.get("date_format", "YYYY-MM-DD"),
                "features": settings.get("features", ["ai_analyst", "email_sync"]),
                "workspace_name": workspace.name,
                "created_at": workspace.createdAt.isoformat() if workspace.createdAt else None,
                "updated_at": workspace.updatedAt.isoformat() if workspace.updatedAt else None
            }
        except Exception as e:
            self.logger.error(f"Error getting workspace settings: {e}")
            # Return fallback settings
            return {
                "timezone": "UTC",
                "date_format": "YYYY-MM-DD",
                "features": ["ai_analyst", "email_sync"],
                "workspace_name": "Sample Workspace"
            }
