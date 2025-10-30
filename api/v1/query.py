"""
Main query endpoint for processing natural language queries
"""
import time
import logging
import uuid
from fastapi import APIRouter, HTTPException, status, Depends, Request
from api.v1.schemas import QueryRequest, QueryResponse, ErrorResponse
from api.dependencies import verify_token_dependency
from graph.pipeline import AnalystPipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    token_claims: dict = Depends(verify_token_dependency)
):
    """
    Process a natural language query through the AI Analyst pipeline
    
    Args:
        request: QueryRequest containing query, workspace_id, and user_id
        token_claims: Verified JWT token claims (validated but not used for IDs)
        
    Returns:
        QueryResponse with formatted results
        
    Raises:
        HTTPException: If query processing fails
    """
    # Generate request ID for tracing
    request_id = str(uuid.uuid4())
    
    # Log request with request ID
    logger.info(
        f"Processing query (request_id={request_id}, workspace={request.workspace_id}, "
        f"user={request.user_id}, query_length={len(request.query)})"
    )
    
    start_time = time.time()
    
    try:
        # Create pipeline instance
        pipeline = AnalystPipeline()
        
        # Execute pipeline (synchronous call)
        # Note: pipeline.run() is synchronous, so we call it directly
        # In production, consider wrapping in run_in_executor for better async handling
        result = pipeline.run(
            user_query=request.query,
            workspace_id=request.workspace_id,
            user_id=request.user_id
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"Query processed successfully (request_id={request_id}, "
            f"execution_time_ms={execution_time_ms})"
        )
        
        return QueryResponse(
            success=True,
            query=request.query,
            result=result,
            execution_time_ms=execution_time_ms,
            workspace_id=request.workspace_id,
            user_id=request.user_id
        )
        
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        error_message = str(e)
        
        logger.error(
            f"Query processing failed (request_id={request_id}, "
            f"execution_time_ms={execution_time_ms}, error={error_message})",
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Query processing failed",
                "detail": error_message,
                "code": "QUERY_PROCESSING_ERROR",
                "request_id": request_id
            }
        )

