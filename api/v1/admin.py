"""
Admin panel API endpoints for testing and debugging
"""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from database.prisma_client import prisma_client
from tools.tool_factory import ToolFactory
from tools.base_tool import QueryType
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ToolTestRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool (company, people, email, interaction, group, workspace)")
    query_type: str = Field(..., description="Query type (search, get_by_id, list, aggregate)")
    workspace_id: str = Field(..., description="Workspace ID")
    user_id: str = Field(..., description="User ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific parameters")


class ToolTestResponse(BaseModel):
    success: bool
    tool_name: str
    query_type: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None


class DatabaseStatsResponse(BaseModel):
    workspaces: int
    companies: int
    people: int
    interactions: int
    groups: int
    users: int
    workspace_members: int


class DatabaseRecordsResponse(BaseModel):
    table: str
    records: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


@router.post("/test-tool", response_model=ToolTestResponse)
async def test_tool(request: ToolTestRequest):
    """
    Test a specific tool with given parameters

    Args:
        request: Tool test request with tool name, query type, and parameters

    Returns:
        ToolTestResponse with execution results
    """
    logger.info(f"Testing tool: {request.tool_name}, query_type: {request.query_type}")

    try:
        # Validate and convert query_type
        try:
            query_type = QueryType(request.query_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query_type: {request.query_type}. Must be one of: search, get_by_id, list, aggregate"
            )

        # Create tool instance
        tool = ToolFactory.create_tool(
            tool_name=request.tool_name,
            workspace_id=request.workspace_id,
            user_id=request.user_id
        )

        # Execute tool
        result = await tool.execute(query_type, **request.params)

        return ToolTestResponse(
            success=result.success,
            tool_name=request.tool_name,
            query_type=request.query_type,
            result=result.data if result.success else None,
            error=result.error if not result.success else None,
            execution_time_ms=result.execution_time_ms
        )

    except Exception as e:
        logger.exception(f"Error testing tool {request.tool_name}: {e}")
        return ToolTestResponse(
            success=False,
            tool_name=request.tool_name,
            query_type=request.query_type,
            error=str(e)
        )


@router.get("/database/stats", response_model=DatabaseStatsResponse)
async def get_database_stats(workspace_id: Optional[str] = Query(None, description="Filter by workspace ID")):
    """
    Get database statistics (record counts)

    Args:
        workspace_id: Optional workspace ID to filter stats

    Returns:
        DatabaseStatsResponse with counts for each table
    """
    try:
        client = await prisma_client.get_client()

        # Build where clause for workspace filtering
        workspace_filter = {"workspaceId": workspace_id} if workspace_id else {}

        # Get counts for each table
        counts = await asyncio.gather(
            client.workspace.count(),
            client.company.count(where=workspace_filter if workspace_id else None),
            client.people.count(where=workspace_filter if workspace_id else None),
            client.interaction.count(where=workspace_filter if workspace_id else None),
            client.group.count(where=workspace_filter if workspace_id else None),
            client.user.count(),
            client.workspacemember.count(where=workspace_filter if workspace_id else None),
        )

        return DatabaseStatsResponse(
            workspaces=counts[0],
            companies=counts[1],
            people=counts[2],
            interactions=counts[3],
            groups=counts[4],
            users=counts[5],
            workspace_members=counts[6]
        )

    except Exception as e:
        logger.exception(f"Error getting database stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")


@router.get("/database/{table}", response_model=DatabaseRecordsResponse)
async def get_database_records(
    table: str,
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip")
):
    """
    Get records from a specific database table

    Args:
        table: Table name (workspace, company, people, interaction, group, user, workspaceMember)
        workspace_id: Optional workspace ID to filter records
        limit: Number of records to return (1-100)
        offset: Number of records to skip

    Returns:
        DatabaseRecordsResponse with records from the table
    """
    try:
        client = await prisma_client.get_client()

        # Map table names to Prisma models and serialize records
        table_lower = table.lower()

        if table_lower == "workspace":
            records = await client.workspace.find_many(
                skip=offset,
                take=limit,
                order={"createdAt": "desc"}
            )
            total = await client.workspace.count()

        elif table_lower == "company":
            where = {"workspaceId": workspace_id} if workspace_id else {}
            records = await client.company.find_many(
                where=where,
                skip=offset,
                take=limit,
                order={"createdAt": "desc"}
            )
            total = await client.company.count(where=where if where else None)

        elif table_lower == "people":
            where = {"workspaceId": workspace_id} if workspace_id else {}
            records = await client.people.find_many(
                where=where,
                skip=offset,
                take=limit,
                order={"createdAt": "desc"}
            )
            total = await client.people.count(where=where if where else None)

        elif table_lower == "interaction":
            where = {"workspaceId": workspace_id} if workspace_id else {}
            records = await client.interaction.find_many(
                where=where,
                skip=offset,
                take=limit,
                order={"createdAt": "desc"}
            )
            total = await client.interaction.count(where=where if where else None)

        elif table_lower == "group":
            where = {"workspaceId": workspace_id} if workspace_id else {}
            records = await client.group.find_many(
                where=where,
                skip=offset,
                take=limit,
                order={"createdAt": "desc"}
            )
            total = await client.group.count(where=where if where else None)

        elif table_lower == "user":
            records = await client.user.find_many(
                skip=offset,
                take=limit,
                order={"createdAt": "desc"}
            )
            total = await client.user.count()

        elif table_lower == "workspacemember":
            where = {"workspaceId": workspace_id} if workspace_id else {}
            records = await client.workspacemember.find_many(
                where=where,
                skip=offset,
                take=limit,
                order={"createdAt": "desc"},
                include={
                    "user": True,
                    "workspace": True
                }
            )
            total = await client.workspacemember.count(where=where if where else None)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid table: {table}. Must be one of: workspace, company, people, interaction, group, user, workspaceMember"
            )

        # Convert Prisma models to dictionaries
        records_dict = [record.dict() if hasattr(record, 'dict') else record.__dict__ for record in records]

        # Convert datetime objects to ISO strings
        def serialize_dates(obj):
            if isinstance(obj, dict):
                return {k: serialize_dates(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_dates(item) for item in obj]
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                return obj

        records_serialized = serialize_dates(records_dict)

        return DatabaseRecordsResponse(
            table=table,
            records=records_serialized,
            total=total,
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting records from {table}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get records: {str(e)}")


@router.get("/tools/list")
async def list_available_tools():
    """
    List all available tools and their supported operations

    Returns:
        Dictionary of tools with their supported operations
    """
    tools_info = {
        "company": {
            "name": "Company Tool",
            "supported_operations": ["search", "get_by_id", "list", "aggregate"],
            "description": "Manage and query company records"
        },
        "people": {
            "name": "People Tool",
            "supported_operations": ["search", "get_by_id", "list", "aggregate"],
            "description": "Manage and query people/contact records"
        },
        "email": {
            "name": "Email Tool",
            "supported_operations": ["search", "get_by_id", "list"],
            "description": "Query email records"
        },
        "interaction": {
            "name": "Interaction Tool",
            "supported_operations": ["search", "get_by_id", "list", "aggregate"],
            "description": "Query interaction history (emails, calls, meetings, etc.)"
        },
        "group": {
            "name": "Group Tool",
            "supported_operations": ["search", "get_by_id", "list"],
            "description": "Manage and query groups"
        },
        "workspace": {
            "name": "Workspace Tool",
            "supported_operations": ["get_by_id", "list"],
            "description": "Query workspace information and settings"
        }
    }

    return {
        "tools": tools_info,
        "query_types": {
            "search": "Search records with filters (name, email, etc.)",
            "get_by_id": "Get a specific record by ID",
            "list": "List all records (with optional filters)",
            "aggregate": "Aggregate data (counts, stats, etc.)"
        }
    }
