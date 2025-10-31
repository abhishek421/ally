# tools/group_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.prisma_client import prisma_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta


class GroupSearchParams(BaseModel):
    """Parameters for group search"""
    name: Optional[str] = None
    group_type: Optional[str] = None  # PEOPLE, COMPANY, DEAL
    is_private: Optional[bool] = None
    is_favourite: Optional[bool] = None
    limit: int = 50
    offset: int = 0


class GroupTool(BaseTool):
    """Tool for group operations"""
    
    def get_supported_operations(self) -> List[QueryType]:
        return [
            QueryType.SEARCH,
            QueryType.GET_BY_ID,
            QueryType.LIST,
            QueryType.ANALYTICS
        ]
    
    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        start_time = datetime.now()
        
        try:
            if query_type == QueryType.SEARCH:
                params = GroupSearchParams(**kwargs)
                result = await self._search_groups(params)
            elif query_type == QueryType.GET_BY_ID:
                group_id = kwargs.get('group_id')
                result = await self._get_group_by_id(group_id)
            elif query_type == QueryType.LIST:
                group_type = kwargs.get('group_type')
                limit = kwargs.get('limit', 50)
                offset = kwargs.get('offset', 0)
                result = await self._list_groups(group_type, limit, offset)
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_group_analytics()
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
    
    async def _search_groups(self, params: GroupSearchParams) -> Dict[str, Any]:
        """Search groups with filters"""
        try:
            client = await prisma_client.get_client()
            
            # Build where clause
            where_clause = {"workspaceId": self.workspace_id}
            
            if params.name:
                where_clause["name"] = {"contains": params.name, "mode": "insensitive"}
            
            if params.group_type:
                where_clause["type"] = params.group_type
            
            if params.is_private is not None:
                where_clause["isPrivate"] = params.is_private
            
            if params.is_favourite is not None:
                where_clause["isFavourite"] = params.is_favourite
            
            # Execute search with pagination
            groups = await client.group.find_many(
                where=where_clause,
                skip=params.offset,
                take=params.limit,
                include={
                    "groupPeople": {
                        "include": {
                            "people": {
                                "select": {
                                    "id": True,
                                    "firstName": True,
                                    "lastName": True,
                                    "jobTitle": True
                                }
                            }
                        }
                    },
                    "groupCompany": {
                        "include": {
                            "company": {
                                "select": {
                                    "id": True,
                                    "name": True,
                                    "description": True
                                }
                            }
                        }
                    }
                },
                order={"createdAt": "desc"}
            )
            
            # Get total count
            total_count = await client.group.count(where=where_clause)
            
            return {
                "groups": groups,
                "total_count": total_count,
                "has_more": params.offset + len(groups) < total_count,
                "limit": params.limit,
                "offset": params.offset
            }
        except Exception as e:
            self.logger.error(f"Error searching groups: {e}")
            return {
                "groups": [],
                "total_count": 0,
                "has_more": False,
                "limit": params.limit,
                "offset": params.offset
            }
    
    async def _get_group_by_id(self, group_id: str) -> Dict[str, Any]:
        """Get group by ID with members"""
        try:
            client = await prisma_client.get_client()
            
            group = await client.group.find_unique(
                where={
                    "id": group_id,
                    "workspaceId": self.workspace_id
                },
                include={
                    "groupPeople": {
                        "include": {
                            "people": {
                                "select": {
                                    "id": True,
                                    "firstName": True,
                                    "lastName": True,
                                    "jobTitle": True,
                                    "email": True,
                                    "phoneNumber": True
                                }
                            }
                        }
                    },
                    "groupCompany": {
                        "include": {
                            "company": {
                                "select": {
                                    "id": True,
                                    "name": True,
                                    "description": True,
                                    "email": True,
                                    "phoneNumber": True
                                }
                            }
                        }
                    }
                }
            )
            
            if not group:
                return {}
            
            return {
                "id": group.id,
                "name": group.name,
                "type": group.type,
                "description": group.description,
                "is_private": group.isPrivate,
                "is_favourite": group.isFavourite,
                "created_at": group.createdAt.isoformat() if group.createdAt else None,
                "updated_at": group.updatedAt.isoformat() if group.updatedAt else None,
                "people": group.groupPeople,
                "companies": group.groupCompany
            }
        except Exception as e:
            self.logger.error(f"Error getting group by ID {group_id}: {e}")
            return {}
    
    async def _list_groups(self, group_type: str, limit: int, offset: int) -> Dict[str, Any]:
        """List groups with pagination"""
        try:
            client = await prisma_client.get_client()
            
            # Build where clause
            where_clause = {"workspaceId": self.workspace_id}
            if group_type:
                where_clause["type"] = group_type
            
            groups = await client.group.find_many(
                where=where_clause,
                skip=offset,
                take=limit,
                include={
                    "groupPeople": {
                        "include": {
                            "people": {
                                "select": {
                                    "id": True,
                                    "firstName": True,
                                    "lastName": True,
                                    "jobTitle": True
                                }
                            }
                        }
                    },
                    "groupCompany": {
                        "include": {
                            "company": {
                                "select": {
                                    "id": True,
                                    "name": True,
                                    "description": True
                                }
                            }
                        }
                    }
                },
                order={"createdAt": "desc"}
            )
            
            total_count = await client.group.count(where=where_clause)
            
            return {
                "groups": groups,
                "total_count": total_count,
                "has_more": offset + len(groups) < total_count,
                "limit": limit,
                "offset": offset,
                "group_type": group_type
            }
        except Exception as e:
            self.logger.error(f"Error listing groups: {e}")
            return {
                "groups": [],
                "total_count": 0,
                "has_more": False,
                "limit": limit,
                "offset": offset,
                "group_type": group_type
            }
    
    async def _get_group_analytics(self) -> Dict[str, Any]:
        """Get group analytics and metrics"""
        try:
            client = await prisma_client.get_client()
            
            # Get total groups
            total_groups = await client.group.count(
                where={"workspaceId": self.workspace_id}
            )
            
            # Get groups by type
            group_types = await client.group.group_by(
                by=["type"],
                where={"workspaceId": self.workspace_id},
                _count={"id": True}
            )
            
            # Get groups by privacy
            private_groups = await client.group.count(
                where={
                    "workspaceId": self.workspace_id,
                    "isPrivate": True
                }
            )
            
            public_groups = await client.group.count(
                where={
                    "workspaceId": self.workspace_id,
                    "isPrivate": False
                }
            )
            
            # Get favourite groups
            favourite_groups = await client.group.count(
                where={
                    "workspaceId": self.workspace_id,
                    "isFavourite": True
                }
            )
            
            # Get recent groups (last 30 days)
            thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            
            recent_groups = await client.group.count(
                where={
                    "workspaceId": self.workspace_id,
                    "createdAt": {"gte": thirty_days_ago}
                }
            )
            
            return {
                "total_groups": total_groups,
                "by_type": {item["type"]: item["_count"]["id"] for item in group_types},
                "by_privacy": {
                    "private": private_groups,
                    "public": public_groups
                },
                "favourite_groups": favourite_groups,
                "recent_groups_30d": recent_groups,
                "workspace_id": self.workspace_id
            }
        except Exception as e:
            self.logger.error(f"Error getting group analytics: {e}")
            return {
                "total_groups": 0,
                "by_type": {},
                "by_privacy": {"private": 0, "public": 0},
                "favourite_groups": 0,
                "recent_groups_30d": 0,
                "workspace_id": self.workspace_id
            }
