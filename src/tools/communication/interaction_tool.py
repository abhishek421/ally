# tools/interaction_tool.py
from src.tools.base_tool import BaseTool, QueryType, ToolResult
from src.infrastructure.database.prisma_client import prisma_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta


class InteractionSearchParams(BaseModel):
    """Parameters for interaction search"""
    person_id: Optional[str] = None
    company_id: Optional[str] = None
    interaction_type: Optional[str] = None  # EMAIL, CALENDAR, CALL, etc.
    direction: Optional[str] = None  # INBOUND, OUTBOUND
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class InteractionTool(BaseTool):
    """Tool for interaction operations using PostgreSQL"""
    
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
                params = InteractionSearchParams(**kwargs)
                result = await self._search_interactions(params)
            elif query_type == QueryType.GET_BY_ID:
                interaction_id = kwargs.get('interaction_id')
                result = await self._get_interaction_by_id(interaction_id)
            elif query_type == QueryType.LIST:
                person_id = kwargs.get('person_id')
                limit = kwargs.get('limit', 50)
                offset = kwargs.get('offset', 0)
                result = await self._list_interactions_by_person(person_id, limit, offset)
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_interaction_analytics()
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
    
    async def _search_interactions(self, params: InteractionSearchParams) -> Dict[str, Any]:
        """Search interactions with filters"""
        try:
            client = await prisma_client.get_client()
            
            # Build where clause
            where_clause = {"workspaceId": self.workspace_id}
            
            if params.person_id:
                where_clause["peopleId"] = params.person_id
            
            if params.company_id:
                where_clause["companyId"] = params.company_id
            
            if params.interaction_type:
                where_clause["type"] = params.interaction_type
            
            if params.direction:
                where_clause["direction"] = params.direction
            
            if params.date_from:
                where_clause["date"] = {"gte": params.date_from}
            
            if params.date_to:
                if "date" in where_clause:
                    where_clause["date"]["lte"] = params.date_to
                else:
                    where_clause["date"] = {"lte": params.date_to}
            
            # Execute search with pagination
            interactions = await client.interaction.find_many(
                where=where_clause,
                skip=params.offset,
                take=params.limit,
                include={
                    "people": {
                        "select": {
                            "id": True,
                            "firstName": True,
                            "lastName": True,
                            "jobTitle": True
                        }
                    },
                    "company": {
                        "select": {
                            "id": True,
                            "name": True,
                            "description": True
                        }
                    }
                },
                order={"date": "desc"}
            )
            
            # Get total count
            total_count = await client.interaction.count(where=where_clause)
            
            return {
                "interactions": interactions,
                "total_count": total_count,
                "has_more": params.offset + len(interactions) < total_count,
                "limit": params.limit,
                "offset": params.offset
            }
        except Exception as e:
            self.logger.error(f"Error searching interactions: {e}")
            return {
                "interactions": [],
                "total_count": 0,
                "has_more": False,
                "limit": params.limit,
                "offset": params.offset
            }
    
    async def _get_interaction_by_id(self, interaction_id: str) -> Dict[str, Any]:
        """Get interaction by ID"""
        try:
            client = await prisma_client.get_client()
            
            interaction = await client.interaction.find_unique(
                where={
                    "id": interaction_id,
                    "workspaceId": self.workspace_id
                },
                include={
                    "people": {
                        "select": {
                            "id": True,
                            "firstName": True,
                            "lastName": True,
                            "jobTitle": True,
                            "email": True
                        }
                    },
                    "company": {
                        "select": {
                            "id": True,
                            "name": True,
                            "description": True,
                            "email": True
                        }
                    }
                }
            )
            
            if not interaction:
                return {}
            
            return {
                "id": interaction.id,
                "type": interaction.type,
                "direction": interaction.direction,
                "date": interaction.date.isoformat() if interaction.date else None,
                "subject": interaction.subject,
                "content": interaction.content,
                "created_at": interaction.createdAt.isoformat() if interaction.createdAt else None,
                "updated_at": interaction.updatedAt.isoformat() if interaction.updatedAt else None,
                "person": interaction.people,
                "company": interaction.company
            }
        except Exception as e:
            self.logger.error(f"Error getting interaction by ID {interaction_id}: {e}")
            return {}
    
    async def _list_interactions_by_person(self, person_id: str, limit: int, offset: int) -> Dict[str, Any]:
        """List interactions for a specific person"""
        try:
            client = await prisma_client.get_client()
            
            interactions = await client.interaction.find_many(
                where={
                    "workspaceId": self.workspace_id,
                    "peopleId": person_id
                },
                skip=offset,
                take=limit,
                include={
                    "people": {
                        "select": {
                            "id": True,
                            "firstName": True,
                            "lastName": True,
                            "jobTitle": True
                        }
                    },
                    "company": {
                        "select": {
                            "id": True,
                            "name": True,
                            "description": True
                        }
                    }
                },
                order={"date": "desc"}
            )
            
            total_count = await client.interaction.count(
                where={
                    "workspaceId": self.workspace_id,
                    "peopleId": person_id
                }
            )
            
            return {
                "interactions": interactions,
                "total_count": total_count,
                "has_more": offset + len(interactions) < total_count,
                "limit": limit,
                "offset": offset,
                "person_id": person_id
            }
        except Exception as e:
            self.logger.error(f"Error listing interactions for person {person_id}: {e}")
            return {
                "interactions": [],
                "total_count": 0,
                "has_more": False,
                "limit": limit,
                "offset": offset,
                "person_id": person_id
            }
    
    async def _get_interaction_analytics(self) -> Dict[str, Any]:
        """Get interaction analytics and metrics"""
        try:
            client = await prisma_client.get_client()
            
            # Get total interactions
            total_interactions = await client.interaction.count(
                where={"workspaceId": self.workspace_id}
            )
            
            # Get interactions by type
            interaction_types = await client.interaction.group_by(
                by=["type"],
                where={"workspaceId": self.workspace_id},
                _count={"id": True}
            )
            
            # Get interactions by direction
            interaction_directions = await client.interaction.group_by(
                by=["direction"],
                where={"workspaceId": self.workspace_id},
                _count={"id": True}
            )
            
            # Get recent interactions (last 30 days)
            thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            
            recent_interactions = await client.interaction.count(
                where={
                    "workspaceId": self.workspace_id,
                    "date": {"gte": thirty_days_ago}
                }
            )
            
            return {
                "total_interactions": total_interactions,
                "by_type": {item["type"]: item["_count"]["id"] for item in interaction_types},
                "by_direction": {item["direction"]: item["_count"]["id"] for item in interaction_directions},
                "recent_interactions_30d": recent_interactions,
                "workspace_id": self.workspace_id
            }
        except Exception as e:
            self.logger.error(f"Error getting interaction analytics: {e}")
            return {
                "total_interactions": 0,
                "by_type": {},
                "by_direction": {},
                "recent_interactions_30d": 0,
                "workspace_id": self.workspace_id
            }
