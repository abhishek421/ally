# tools/company_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.prisma_client import prisma_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta


class CompanySearchParams(BaseModel):
    """Parameters for company search"""
    name: Optional[str] = None
    description: Optional[str] = None
    privacy_level: Optional[str] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class CompanyTool(BaseTool):
    """Tool for company operations"""
    
    def get_supported_operations(self) -> List[QueryType]:
        return [
            QueryType.SEARCH,
            QueryType.GET_BY_ID,
            QueryType.LIST,
            QueryType.ANALYTICS,
            # TODO: Write operations not yet implemented
            # QueryType.CREATE,
            # QueryType.UPDATE,
        ]
    
    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        start_time = datetime.now()
        
        try:
            if query_type == QueryType.SEARCH:
                params = CompanySearchParams(**kwargs)
                result = await self._search_companies(params)
            elif query_type == QueryType.GET_BY_ID:
                company_id = kwargs.get('company_id')
                result = await self._get_company_by_id(company_id)
            elif query_type == QueryType.LIST:
                limit = kwargs.get('limit', 50)
                offset = kwargs.get('offset', 0)
                result = await self._list_companies(limit, offset)
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_company_analytics()
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
    
    async def _search_companies(self, params: CompanySearchParams) -> Dict[str, Any]:
        """Search companies with filters"""
        try:
            client = await prisma_client.get_client()
            
            # Build where clause
            where_clause = {"workspaceId": self.workspace_id}
            
            if params.name:
                where_clause["name"] = {"contains": params.name, "mode": "insensitive"}

            if params.description:
                where_clause["description"] = {"contains": params.description, "mode": "insensitive"}

            if params.privacy_level:
                where_clause["privacyLevel"] = params.privacy_level

            # Add date range filters
            if params.created_from or params.created_to:
                date_filter = {}
                if params.created_from:
                    date_filter["gte"] = params.created_from
                if params.created_to:
                    date_filter["lte"] = params.created_to
                where_clause["createdAt"] = date_filter

            # Execute search with pagination
            companies = await client.company.find_many(
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
                            "people": True
                        }
                    }
                },
                order={"createdAt": "desc"}
            )
            
            # Get total count
            total_count = await client.company.count(where=where_clause)
            
            return {
                "companies": companies,
                "total_count": total_count,
                "has_more": params.offset + len(companies) < total_count,
                "limit": params.limit,
                "offset": params.offset
            }
        except Exception as e:
            self.logger.error(f"Error searching companies: {e}")
            return {
                "companies": [],
                "total_count": 0,
                "has_more": False,
                "limit": params.limit,
                "offset": params.offset
            }
    
    async def _get_company_by_id(self, company_id: str) -> Dict[str, Any]:
        """Get company by ID with all related data"""
        try:
            client = await prisma_client.get_client()
            
            company = await client.company.find_unique(
                where={
                    "id": company_id,
                    "workspaceId": self.workspace_id
                },
                include={
                    "email": True,
                    "phoneNumber": True,
                    "address": True,
                    "url": True,
                    "metaData": {
                        "include": {
                            "people": True
                        }
                    }
                }
            )
            
            if not company:
                return {}
            
            return {
                "id": company.id,
                "name": company.name,
                "description": company.description,
                "privacy_level": company.privacyLevel,
                "created_at": company.createdAt.isoformat() if company.createdAt else None,
                "updated_at": company.updatedAt.isoformat() if company.updatedAt else None,
                "emails": company.email,
                "phone_numbers": company.phoneNumber,
                "addresses": company.address,
                "urls": company.url,
                "people": company.metaData
            }
        except Exception as e:
            self.logger.error(f"Error getting company by ID {company_id}: {e}")
            return {}
    
    async def _list_companies(self, limit: int, offset: int) -> Dict[str, Any]:
        """List companies with pagination"""
        try:
            client = await prisma_client.get_client()
            
            companies = await client.company.find_many(
                where={"workspaceId": self.workspace_id},
                skip=offset,
                take=limit,
                include={
                    "email": True,
                    "phoneNumber": True,
                    "address": True,
                    "url": True
                },
                order={"createdAt": "desc"}
            )
            
            total_count = await client.company.count(
                where={"workspaceId": self.workspace_id}
            )
            
            return {
                "companies": companies,
                "total_count": total_count,
                "has_more": offset + len(companies) < total_count,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            self.logger.error(f"Error listing companies: {e}")
            return {
                "companies": [],
                "total_count": 0,
                "has_more": False,
                "limit": limit,
                "offset": offset
            }
    
    async def _get_company_analytics(self) -> Dict[str, Any]:
        """Get company analytics and metrics"""
        try:
            client = await prisma_client.get_client()
            
            # Get total companies
            total_companies = await client.company.count(
                where={"workspaceId": self.workspace_id}
            )
            
            # Get companies by privacy level
            privacy_levels = await client.company.group_by(
                by=["privacyLevel"],
                where={"workspaceId": self.workspace_id},
                count={"id": True}
            )
            
            # Get recent companies (last 30 days)
            thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            
            recent_companies = await client.company.count(
                where={
                    "workspaceId": self.workspace_id,
                    "createdAt": {"gte": thirty_days_ago}
                }
            )
            
            return {
                "total_companies": total_companies,
                "by_privacy_level": {item["privacyLevel"]: item["_count"]["id"] for item in privacy_levels},
                "recent_companies_30d": recent_companies,
                "workspace_id": self.workspace_id
            }
        except Exception as e:
            self.logger.error(f"Error getting company analytics: {e}")
            return {
                "total_companies": 0,
                "by_privacy_level": {},
                "recent_companies_30d": 0,
                "workspace_id": self.workspace_id
            }
