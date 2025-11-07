# tools/people_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.prisma_client import prisma_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta


class PeopleSearchParams(BaseModel):
    """Parameters for people search"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    company_id: Optional[str] = None
    privacy_level: Optional[str] = None
    limit: int = 50
    offset: int = 0


class PeopleTool(BaseTool):
    """Tool for people operations"""
    
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
                params = PeopleSearchParams(**kwargs)
                result = await self._search_people(params)
            elif query_type == QueryType.GET_BY_ID:
                person_id = kwargs.get('person_id')
                result = await self._get_person_by_id(person_id)
            elif query_type == QueryType.LIST:
                limit = kwargs.get('limit', 50)
                offset = kwargs.get('offset', 0)
                result = await self._list_people(limit, offset)
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_people_analytics()
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
    
    async def _search_people(self, params: PeopleSearchParams) -> Dict[str, Any]:
        """Search people with filters"""
        try:
            client = await prisma_client.get_client()
            
            # Build where clause
            where_clause = {"workspaceId": self.workspace_id}
            
            if params.first_name:
                where_clause["firstName"] = {"contains": params.first_name, "mode": "insensitive"}
            
            if params.last_name:
                where_clause["lastName"] = {"contains": params.last_name, "mode": "insensitive"}
            
            if params.job_title:
                where_clause["jobTitle"] = {"contains": params.job_title, "mode": "insensitive"}
            
            if params.email:
                where_clause["email"] = {
                    "some": {
                        "value": {"contains": params.email, "mode": "insensitive"}
                    }
                }
            
            if params.privacy_level:
                where_clause["privacyLevel"] = params.privacy_level

            if params.company_id:
                where_clause["metaData"] = {
                    "some": {
                        "companyId": params.company_id
                    }
                }

            # Execute search with pagination
            people = await client.people.find_many(
                where=where_clause,
                skip=params.offset,
                take=params.limit,
                include={
                    "email": True,
                    "phoneNumber": True,
                    "address": True,
                    "url": True,
                    "metaData": {
                        "include": {
                            "company": True
                        }
                    }
                },
                order={"createdAt": "desc"}
            )

            # Get total count
            total_count = await client.people.count(where=where_clause)
            
            return {
                "people": people,
                "total_count": total_count,
                "has_more": params.offset + len(people) < total_count,
                "limit": params.limit,
                "offset": params.offset
            }
        except Exception as e:
            self.logger.error(f"Error searching people: {e}")
            return {
                "people": [],
                "total_count": 0,
                "has_more": False,
                "limit": params.limit,
                "offset": params.offset
            }
    
    async def _get_person_by_id(self, person_id: str) -> Dict[str, Any]:
        """Get person by ID with all related data"""
        try:
            client = await prisma_client.get_client()
            
            person = await client.people.find_unique(
                where={
                    "id": person_id,
                    "workspaceId": self.workspace_id
                },
                include={
                    "email": True,
                    "phoneNumber": True,
                    "address": True,
                    "url": True,
                    "metaData": {
                        "include": {
                            "company": True
                        }
                    }
                }
            )
            
            if not person:
                return {}
            
            return {
                "id": person.id,
                "first_name": person.firstName,
                "last_name": person.lastName,
                "job_title": person.jobTitle,
                "privacy_level": person.privacyLevel,
                "created_at": person.createdAt.isoformat() if person.createdAt else None,
                "updated_at": person.updatedAt.isoformat() if person.updatedAt else None,
                "emails": person.email,
                "phone_numbers": person.phoneNumber,
                "addresses": person.address,
                "urls": person.url,
                "companies": person.metaData
            }
        except Exception as e:
            self.logger.error(f"Error getting person by ID {person_id}: {e}")
            return {}
    
    async def _list_people(self, limit: int, offset: int) -> Dict[str, Any]:
        """List people with pagination"""
        try:
            client = await prisma_client.get_client()
            
            people = await client.people.find_many(
                where={"workspaceId": self.workspace_id},
                skip=offset,
                take=limit,
                include={
                    "email": True,
                    "phoneNumber": True,
                    "address": True,
                    "url": True,
                    "metaData": {
                        "include": {
                            "company": True
                        }
                    }
                },
                order={"createdAt": "desc"}
            )

            total_count = await client.people.count(
                where={"workspaceId": self.workspace_id}
            )
            
            return {
                "people": people,
                "total_count": total_count,
                "has_more": offset + len(people) < total_count,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            self.logger.error(f"Error listing people: {e}")
            return {
                "people": [],
                "total_count": 0,
                "has_more": False,
                "limit": limit,
                "offset": offset
            }
    
    async def _get_people_analytics(self) -> Dict[str, Any]:
        """Get people analytics and metrics"""
        try:
            client = await prisma_client.get_client()
            
            # Get total people
            total_people = await client.people.count(
                where={"workspaceId": self.workspace_id}
            )

            # Get people by privacy level
            privacy_levels = await client.people.group_by(
                by=["privacyLevel"],
                where={"workspaceId": self.workspace_id},
                count={"id": True}
            )

            # Get people by job title (top 10)
            job_titles = await client.people.group_by(
                by=["jobTitle"],
                where={
                    "workspaceId": self.workspace_id,
                    "jobTitle": {"not": None}
                },
                count={"id": True},
                order={"_count": {"id": "desc"}},
                take=10
            )

            # Get recent people (last 30 days)
            thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)

            recent_people = await client.people.count(
                where={
                    "workspaceId": self.workspace_id,
                    "createdAt": {"gte": thirty_days_ago}
                }
            )
            
            return {
                "total_people": total_people,
                "by_privacy_level": {item["privacyLevel"]: item["_count"]["id"] for item in privacy_levels},
                "by_job_title": {item["jobTitle"]: item["_count"]["id"] for item in job_titles},
                "recent_people_30d": recent_people,
                "workspace_id": self.workspace_id
            }
        except Exception as e:
            self.logger.error(f"Error getting people analytics: {e}")
            return {
                "total_people": 0,
                "by_privacy_level": {},
                "by_job_title": {},
                "recent_people_30d": 0,
                "workspace_id": self.workspace_id
            }
