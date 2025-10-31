"""
Pydantic schemas for API request/response models
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    """
    Request model for query endpoint

    Note: workspace_id and user_id are now passed via headers:
    - X-Workspace-ID: Workspace identifier
    - X-User-ID: User identifier
    """
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Sanitize and validate query"""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    success: bool = Field(..., description="Whether the query was successful")
    query: str = Field(..., description="Original user query")
    result: Dict[str, Any] = Field(..., description="Formatted response data")
    execution_time_ms: int = Field(..., description="Query execution time in milliseconds")
    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: str = Field(..., description="Error code")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="Timestamp of check")


class ReadyResponse(BaseModel):
    """Readiness check response"""
    status: str = Field(..., description="Readiness status")
    services: Dict[str, str] = Field(..., description="Status of individual services")
    timestamp: str = Field(..., description="Timestamp of check")

