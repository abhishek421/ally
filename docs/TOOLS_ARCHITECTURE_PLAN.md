# Tools Architecture Plan - AI Analyst Service

## 🎯 Overview

This document outlines the comprehensive Tools architecture for the AI Analyst Service, following distributed design principles, YAGNI (You Aren't Gonna Need It), and leveraging the dual-database architecture (PostgreSQL + DynamoDB).

## 🏗️ Architecture Principles

### Core Design Principles
1. **YAGNI**: Implement only what's needed now, avoid over-engineering
2. **Distributed**: Clear separation of concerns with reusable components
3. **Database-Agnostic**: Abstract database operations behind interfaces
4. **Workspace Isolation**: All operations scoped to workspace
5. **Error Resilience**: Graceful handling of failures
6. **Performance**: Efficient queries with proper caching

### Database Distribution Strategy
- **PostgreSQL**: Core CRM data (workspaces, companies, people, groups, interactions)
- **DynamoDB**: Email content and email-specific interactions
- **Redis**: Caching layer for frequently accessed data

## 📁 Tools Architecture

### Base Tool Structure

```python
# tools/base_tool.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel
from enum import Enum
import asyncio
from datetime import datetime

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
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ANALYTICS = "analytics"

class BaseTool(ABC):
    """Base class for all AI Analyst tools"""
    
    def __init__(self, workspace_id: str, user_id: str):
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.cache_ttl = 300  # 5 minutes default
    
    @abstractmethod
    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        """Execute tool operation"""
        pass
    
    @abstractmethod
    def get_supported_operations(self) -> List[QueryType]:
        """Return list of supported operations"""
        pass
    
    async def _validate_workspace_access(self) -> bool:
        """Validate user has access to workspace"""
        # TODO: Implement workspace access validation
        return True
    
    async def _cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for operation"""
        params = sorted(kwargs.items())
        return f"{self.__class__.__name__}:{operation}:{self.workspace_id}:{hash(str(params))}"
    
    async def _execute_with_cache(self, operation: str, **kwargs) -> ToolResult:
        """Execute operation with caching"""
        # TODO: Implement Redis caching
        return await self.execute(operation, **kwargs)
```

## 🛠️ Core Tools Implementation

### 1. Workspace Tool

**Purpose**: Workspace metadata, settings, and validation

```python
# tools/workspace_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import Dict, Any

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
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _get_workspace_info(self) -> Dict[str, Any]:
        """Get workspace basic information"""
        # TODO: Implement Prisma query
        return {
            "id": self.workspace_id,
            "name": "Sample Workspace",
            "created_at": "2024-01-01T00:00:00Z"
        }
    
    async def _list_workspace_settings(self) -> Dict[str, Any]:
        """Get workspace settings and configuration"""
        # TODO: Implement Prisma query
        return {
            "timezone": "UTC",
            "date_format": "YYYY-MM-DD",
            "features": ["ai_analyst", "email_sync"]
        }
```

### 2. Company Tool

**Purpose**: Company CRUD operations and search

```python
# tools/company_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class CompanySearchParams(BaseModel):
    """Parameters for company search"""
    name: Optional[str] = None
    domain: Optional[str] = None
    privacy_level: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CompanyTool(BaseTool):
    """Tool for company operations"""
    
    def get_supported_operations(self) -> List[QueryType]:
        return [
            QueryType.SEARCH,
            QueryType.GET_BY_ID,
            QueryType.LIST,
            QueryType.CREATE,
            QueryType.UPDATE,
            QueryType.ANALYTICS
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
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _search_companies(self, params: CompanySearchParams) -> Dict[str, Any]:
        """Search companies with filters"""
        # TODO: Implement Prisma query with filters
        # Use indexes: workspaceId, name, privacyLevel
        return {
            "companies": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_company_by_id(self, company_id: str) -> Dict[str, Any]:
        """Get company by ID with all related data"""
        # TODO: Implement Prisma query with includes
        # Include: emails, phoneNumbers, addresses, urls, peopleMetaData
        return {}
    
    async def _list_companies(self, limit: int, offset: int) -> Dict[str, Any]:
        """List companies with pagination"""
        # TODO: Implement Prisma query with pagination
        return {
            "companies": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_company_analytics(self) -> Dict[str, Any]:
        """Get company analytics and metrics"""
        # TODO: Implement analytics queries
        return {
            "total_companies": 0,
            "by_privacy_level": {},
            "recent_activity": []
        }
```

### 3. People Tool

**Purpose**: People/contacts operations and search

```python
# tools/people_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class PeopleSearchParams(BaseModel):
    """Parameters for people search"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
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
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _search_people(self, params: PeopleSearchParams) -> Dict[str, Any]:
        """Search people with filters"""
        # TODO: Implement Prisma query with filters
        # Use indexes: workspaceId, firstName+lastName, jobTitle, privacyLevel
        return {
            "people": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_person_by_id(self, person_id: str) -> Dict[str, Any]:
        """Get person by ID with all related data"""
        # TODO: Implement Prisma query with includes
        # Include: emails, phoneNumbers, addresses, urls, companyMetaData
        return {}
    
    async def _list_people(self, limit: int, offset: int) -> Dict[str, Any]:
        """List people with pagination"""
        # TODO: Implement Prisma query with pagination
        return {
            "people": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_people_analytics(self) -> Dict[str, Any]:
        """Get people analytics and metrics"""
        # TODO: Implement analytics queries
        return {
            "total_people": 0,
            "by_privacy_level": {},
            "by_job_title": {},
            "recent_activity": []
        }
```

### 4. Email Tool (DynamoDB)

**Purpose**: Email content and interactions from DynamoDB

```python
# tools/email_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import boto3
from datetime import datetime, timedelta

class EmailSearchParams(BaseModel):
    """Parameters for email search"""
    person_id: Optional[str] = None
    integration_id: Optional[str] = None
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    direction: Optional[str] = None  # 'sent' or 'received'
    limit: int = 50

class EmailTool(BaseTool):
    """Tool for email operations using DynamoDB"""
    
    def __init__(self, workspace_id: str, user_id: str):
        super().__init__(workspace_id, user_id)
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table('EmailSync')
    
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
                params = EmailSearchParams(**kwargs)
                result = await self._search_emails(params)
            elif query_type == QueryType.GET_BY_ID:
                message_id = kwargs.get('message_id')
                result = await self._get_email_by_id(message_id)
            elif query_type == QueryType.LIST:
                person_id = kwargs.get('person_id')
                limit = kwargs.get('limit', 50)
                result = await self._list_emails_by_person(person_id, limit)
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_email_analytics()
            else:
                raise ValueError(f"Unsupported operation: {query_type}")
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _search_emails(self, params: EmailSearchParams) -> Dict[str, Any]:
        """Search emails using DynamoDB queries"""
        # TODO: Implement DynamoDB query logic
        # Use PK patterns: WORKSPACE#{workspaceId}#PERSON#{personId}
        # Use GSI1 for integration-based queries
        return {
            "emails": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_email_by_id(self, message_id: str) -> Dict[str, Any]:
        """Get specific email by message ID"""
        # TODO: Implement DynamoDB query by GSI1
        return {}
    
    async def _list_emails_by_person(self, person_id: str, limit: int) -> Dict[str, Any]:
        """List emails for a specific person"""
        # TODO: Implement DynamoDB query
        # PK = WORKSPACE#{workspaceId}#PERSON#{personId}
        return {
            "emails": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_email_analytics(self) -> Dict[str, Any]:
        """Get email analytics and metrics"""
        # TODO: Implement analytics queries
        return {
            "total_emails": 0,
            "by_direction": {},
            "by_integration": {},
            "recent_activity": []
        }
```

### 5. Interaction Tool (PostgreSQL)

**Purpose**: Non-email interactions (calls, meetings, notes)

```python
# tools/interaction_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

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
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _search_interactions(self, params: InteractionSearchParams) -> Dict[str, Any]:
        """Search interactions with filters"""
        # TODO: Implement Prisma query with filters
        # Use indexes: workspaceId+date, peopleId, companyId, type+direction
        return {
            "interactions": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_interaction_by_id(self, interaction_id: str) -> Dict[str, Any]:
        """Get interaction by ID"""
        # TODO: Implement Prisma query
        return {}
    
    async def _list_interactions_by_person(self, person_id: str, limit: int, offset: int) -> Dict[str, Any]:
        """List interactions for a specific person"""
        # TODO: Implement Prisma query with pagination
        return {
            "interactions": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_interaction_analytics(self) -> Dict[str, Any]:
        """Get interaction analytics and metrics"""
        # TODO: Implement analytics queries
        return {
            "total_interactions": 0,
            "by_type": {},
            "by_direction": {},
            "recent_activity": []
        }
```

### 6. Group Tool

**Purpose**: Group management and organization

```python
# tools/group_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

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
            
            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _search_groups(self, params: GroupSearchParams) -> Dict[str, Any]:
        """Search groups with filters"""
        # TODO: Implement Prisma query with filters
        # Use indexes: workspaceId, name, type+isPrivate
        return {
            "groups": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_group_by_id(self, group_id: str) -> Dict[str, Any]:
        """Get group by ID with members"""
        # TODO: Implement Prisma query with includes
        # Include: groupPeople, groupCompanies based on type
        return {}
    
    async def _list_groups(self, group_type: str, limit: int, offset: int) -> Dict[str, Any]:
        """List groups with pagination"""
        # TODO: Implement Prisma query with pagination
        return {
            "groups": [],
            "total_count": 0,
            "has_more": False
        }
    
    async def _get_group_analytics(self) -> Dict[str, Any]:
        """Get group analytics and metrics"""
        # TODO: Implement analytics queries
        return {
            "total_groups": 0,
            "by_type": {},
            "by_privacy": {},
            "recent_activity": []
        }
```

## 🔧 Tool Factory and Registry

### Tool Factory

```python
# tools/tool_factory.py
from typing import Dict, Type
from tools.base_tool import BaseTool
from tools.workspace_tool import WorkspaceTool
from tools.company_tool import CompanyTool
from tools.people_tool import PeopleTool
from tools.email_tool import EmailTool
from tools.interaction_tool import InteractionTool
from tools.group_tool import GroupTool

class ToolFactory:
    """Factory for creating tool instances"""
    
    _tool_registry: Dict[str, Type[BaseTool]] = {
        'workspace': WorkspaceTool,
        'company': CompanyTool,
        'people': PeopleTool,
        'email': EmailTool,
        'interaction': InteractionTool,
        'group': GroupTool,
    }
    
    @classmethod
    def create_tool(cls, tool_name: str, workspace_id: str, user_id: str) -> BaseTool:
        """Create a tool instance"""
        if tool_name not in cls._tool_registry:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool_class = cls._tool_registry[tool_name]
        return tool_class(workspace_id, user_id)
    
    @classmethod
    def get_available_tools(cls) -> List[str]:
        """Get list of available tools"""
        return list(cls._tool_registry.keys())
    
    @classmethod
    def register_tool(cls, name: str, tool_class: Type[BaseTool]):
        """Register a new tool"""
        cls._tool_registry[name] = tool_class
```

## 🗄️ Database Integration

### Prisma Client Setup

```python
# database/prisma_client.py
from prisma import Prisma
from typing import Optional
import asyncio

class PrismaClient:
    """Prisma client wrapper with connection management"""
    
    def __init__(self):
        self.client: Optional[Prisma] = None
    
    async def connect(self):
        """Connect to PostgreSQL database"""
        if not self.client:
            self.client = Prisma()
            await self.client.connect()
    
    async def disconnect(self):
        """Disconnect from database"""
        if self.client:
            await self.client.disconnect()
            self.client = None
    
    async def get_client(self) -> Prisma:
        """Get Prisma client instance"""
        if not self.client:
            await self.connect()
        return self.client

# Global instance
prisma_client = PrismaClient()
```

### DynamoDB Client Setup

```python
# database/dynamodb_client.py
import boto3
from typing import Optional
from botocore.config import Config

class DynamoDBClient:
    """DynamoDB client wrapper"""
    
    def __init__(self):
        self.client: Optional[boto3.resource] = None
        self.config = Config(
            retries={'max_attempts': 3},
            region_name='us-east-1'  # TODO: Make configurable
        )
    
    def get_client(self):
        """Get DynamoDB client instance"""
        if not self.client:
            self.client = boto3.resource('dynamodb', config=self.config)
        return self.client
    
    def get_table(self, table_name: str):
        """Get DynamoDB table"""
        client = self.get_client()
        return client.Table(table_name)

# Global instance
dynamodb_client = DynamoDBClient()
```

## 🚀 Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Implement BaseTool abstract class
- [ ] Setup Prisma client and database connection
- [ ] Setup DynamoDB client
- [ ] Implement ToolFactory
- [ ] Basic error handling and logging

### Phase 2: Essential Tools (Week 2)
- [ ] WorkspaceTool implementation
- [ ] CompanyTool basic operations (search, get_by_id, list)
- [ ] PeopleTool basic operations
- [ ] Basic caching with Redis

### Phase 3: Advanced Tools (Week 3)
- [ ] EmailTool DynamoDB integration
- [ ] InteractionTool PostgreSQL integration
- [ ] GroupTool implementation
- [ ] Analytics operations for all tools

### Phase 4: Optimization (Week 4)
- [ ] Advanced caching strategies
- [ ] Query optimization
- [ ] Error recovery mechanisms
- [ ] Performance monitoring

## 📊 Performance Considerations

### Database Query Optimization
- **PostgreSQL**: Use proper indexes, limit result sets, use pagination
- **DynamoDB**: Optimize partition/sort keys, use GSI efficiently
- **Redis**: Cache frequently accessed data, implement TTL strategies

### Caching Strategy
```python
# Cache keys pattern
CACHE_PATTERNS = {
    'workspace': 'workspace:{workspace_id}',
    'company': 'company:{workspace_id}:{company_id}',
    'person': 'person:{workspace_id}:{person_id}',
    'email_list': 'emails:{workspace_id}:{person_id}:{limit}:{offset}',
    'analytics': 'analytics:{workspace_id}:{tool_name}:{date_range}'
}
```

### Error Handling
- Graceful degradation when databases are unavailable
- Retry mechanisms for transient failures
- Circuit breaker pattern for external services
- Comprehensive logging for debugging

## 🔒 Security Considerations

### Workspace Isolation
- All queries scoped to workspace_id
- User permission validation
- Data access audit logging

### Input Validation
- Pydantic models for all input parameters
- SQL injection prevention (Prisma handles this)
- DynamoDB injection prevention
- Rate limiting per workspace

## 📈 Monitoring and Observability

### Metrics to Track
- Tool execution time
- Database query performance
- Cache hit/miss rates
- Error rates by tool
- Workspace usage patterns

### Logging Strategy
```python
# Structured logging format
{
    "timestamp": "2024-01-01T00:00:00Z",
    "level": "INFO",
    "tool": "CompanyTool",
    "operation": "search",
    "workspace_id": "uuid",
    "user_id": "uuid",
    "execution_time_ms": 150,
    "success": true,
    "cache_hit": false
}
```

This architecture provides a solid foundation for the AI Analyst Service tools, following distributed design principles while maintaining simplicity and performance.
