# Tools Architecture Implementation

This document describes the implementation of the Tools Architecture Plan for the AI Analyst RAG system.

## 🏗️ Architecture Overview

The tools architecture follows distributed design principles with clear separation of concerns:

- **BaseTool**: Abstract base class for all tools
- **Database Clients**: Prisma (PostgreSQL), DynamoDB, and Redis clients
- **Tool Implementations**: Specialized tools for different data sources
- **Tool Factory**: Registry and factory pattern for tool creation
- **Caching Layer**: Redis-based caching for performance optimization

## 📁 File Structure

```
tools/
├── __init__.py              # Package exports
├── base_tool.py            # Abstract base class
├── workspace_tool.py       # Workspace operations
├── company_tool.py         # Company CRUD operations
├── people_tool.py          # People/contacts operations
├── emails_tool.py          # Email operations (DynamoDB)
├── interaction_tool.py     # Interaction operations (PostgreSQL)
├── group_tool.py           # Group management
└── tool_factory.py         # Tool factory and registry

database/
├── prisma_client.py        # PostgreSQL client wrapper
├── dynamodb_client.py      # DynamoDB client wrapper
└── redis_client.py         # Redis client wrapper

examples/
└── tool_usage_example.py   # Usage examples
```

## 🛠️ Core Components

### BaseTool Abstract Class

All tools inherit from `BaseTool` which provides:

- **Standardized Result Format**: `ToolResult` with success/error handling
- **Query Types**: Enum for different operation types (SEARCH, GET_BY_ID, etc.)
- **Caching**: Redis-based caching with TTL
- **Logging**: Structured logging for all operations
- **Error Handling**: Consistent error handling across tools

### Database Clients

#### Prisma Client (PostgreSQL)
- Connection management with async/await
- Health checks
- Automatic reconnection
- Workspace-scoped queries

#### DynamoDB Client
- Boto3 wrapper with retry configuration
- Table access abstraction
- Health checks
- Error handling

#### Redis Client
- Async Redis operations
- JSON serialization/deserialization
- TTL support
- Health checks

### Tool Implementations

#### WorkspaceTool
- Workspace metadata and settings
- User access validation
- Basic workspace information

#### CompanyTool
- Company search with filters (name, domain, privacy level)
- CRUD operations
- Analytics and metrics
- Related data inclusion (emails, addresses, etc.)

#### PeopleTool
- People search with filters (name, job title, email)
- Contact information management
- Company relationships
- Analytics by job title and privacy level

#### EmailTool (DynamoDB)
- Email search by person, integration, or content
- DynamoDB query optimization
- Date range filtering
- Direction filtering (sent/received)

#### InteractionTool (PostgreSQL)
- Non-email interactions (calls, meetings, notes)
- Person and company relationships
- Type and direction filtering
- Analytics by interaction type

#### GroupTool
- Group management (PEOPLE, COMPANY, DEAL)
- Privacy and favorite settings
- Member management
- Group analytics

### Tool Factory

The `ToolFactory` provides:

- **Tool Creation**: Factory method for creating tool instances
- **Registry**: Central registry of available tools
- **Tool Information**: Metadata about each tool
- **Dynamic Registration**: Ability to register new tools at runtime

## 🚀 Usage Examples

### Basic Tool Usage

```python
from tools import ToolFactory, QueryType, CompanySearchParams

# Create a tool
company_tool = ToolFactory.create_tool("company", "workspace-123", "user-456")

# Search companies
search_params = CompanySearchParams(name="Tech", limit=10)
result = await company_tool.execute(QueryType.SEARCH, **search_params.dict())

if result.success:
    print(f"Found {len(result.data['companies'])} companies")
else:
    print(f"Error: {result.error}")
```

### Using Caching

```python
# First execution (cache miss)
result1 = await company_tool.execute(QueryType.ANALYTICS)

# Second execution (cache hit - much faster)
result2 = await company_tool.execute(QueryType.ANALYTICS)

print(f"Cached: {result2.cached}")
```

### Tool Factory Operations

```python
# Get available tools
tools = ToolFactory.get_available_tools()
print(f"Available tools: {tools}")

# Get tool information
tool_info = ToolFactory.get_tool_info("company")
print(f"Company tool info: {tool_info}")
```

## 🔧 Configuration

### Environment Variables

```bash
# Database connections
DATABASE_URL="postgresql://user:password@localhost:5432/analyst_db"
DYNAMODB_TABLE_NAME="EmailSync"
REDIS_URL="redis://localhost:6379"

# AWS Configuration (for DynamoDB)
AWS_ACCESS_KEY_ID="your_access_key"
AWS_SECRET_ACCESS_KEY="your_secret_key"
AWS_REGION="us-east-1"
```

### Tool Configuration

Each tool can be configured with:

- **Cache TTL**: Default 5 minutes, customizable per tool
- **Logging Level**: Configurable per tool class
- **Database Connections**: Shared client instances
- **Workspace Isolation**: All operations scoped to workspace

## 📊 Performance Considerations

### Caching Strategy

- **Cache Keys**: Structured keys with workspace and operation info
- **TTL**: 5 minutes default, customizable per operation
- **Cache Invalidation**: Manual cache clearing available
- **Fallback**: Graceful degradation when cache is unavailable

### Database Optimization

- **PostgreSQL**: Proper indexes, pagination, selective includes
- **DynamoDB**: Optimized partition/sort keys, GSI usage
- **Redis**: Efficient serialization, connection pooling

### Error Handling

- **Graceful Degradation**: Tools continue working if databases are unavailable
- **Retry Logic**: Built into database clients
- **Circuit Breaker**: Prevents cascading failures
- **Comprehensive Logging**: Structured logs for debugging

## 🔒 Security Features

### Workspace Isolation

- All queries scoped to workspace_id
- User permission validation (placeholder for future implementation)
- Data access audit logging

### Input Validation

- Pydantic models for all input parameters
- SQL injection prevention (Prisma handles this)
- DynamoDB injection prevention
- Rate limiting per workspace (future implementation)

## 📈 Monitoring and Observability

### Metrics Tracked

- Tool execution time
- Database query performance
- Cache hit/miss rates
- Error rates by tool
- Workspace usage patterns

### Logging Format

```json
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

## 🧪 Testing

### Unit Tests

Each tool should have comprehensive unit tests covering:

- Successful operations
- Error handling
- Input validation
- Cache behavior
- Database interactions

### Integration Tests

- End-to-end tool execution
- Database connectivity
- Cache functionality
- Error scenarios

### Performance Tests

- Load testing with multiple concurrent operations
- Cache performance validation
- Database query optimization verification

## 🔄 Future Enhancements

### Planned Features

1. **Advanced Caching**: Pattern-based cache invalidation
2. **Rate Limiting**: Per-workspace rate limiting
3. **Metrics Collection**: Prometheus/StatsD integration
4. **Circuit Breaker**: Advanced failure handling
5. **Tool Composition**: Ability to chain tools together
6. **Real-time Updates**: WebSocket support for live data
7. **Batch Operations**: Bulk operations for efficiency

### Extensibility

The architecture is designed to be easily extensible:

- New tools can be added by inheriting from `BaseTool`
- Database clients can be extended for new data sources
- Caching strategies can be customized per tool
- New query types can be added to the `QueryType` enum

## 📚 API Reference

### BaseTool Methods

- `execute(query_type, **kwargs)`: Execute tool operation
- `get_supported_operations()`: Get list of supported operations
- `clear_cache(operation=None)`: Clear tool cache

### ToolResult Properties

- `success`: Boolean indicating operation success
- `data`: Operation result data
- `error`: Error message if operation failed
- `metadata`: Additional operation metadata
- `execution_time_ms`: Operation execution time
- `cached`: Whether result was served from cache

### QueryType Values

- `SEARCH`: Search operations with filters
- `GET_BY_ID`: Get single record by ID
- `LIST`: List records with pagination
- `CREATE`: Create new records
- `UPDATE`: Update existing records
- `DELETE`: Delete records
- `ANALYTICS`: Get analytics and metrics

This implementation provides a solid foundation for the AI Analyst Service tools, following distributed design principles while maintaining simplicity and performance.
