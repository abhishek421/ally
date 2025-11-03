"""
Main query endpoint for processing natural language queries
"""
import time
import logging
import uuid
from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional
from api.v1.schemas import QueryRequest, QueryResponse, ErrorResponse
# from api.dependencies import verify_token_dependency  # Commented out for now
from graph.pipeline import AnalystPipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    workspace_id: str = Header(..., alias="X-Workspace-ID", description="Workspace identifier"),
    user_id: str = Header(..., alias="X-User-ID", description="User identifier"),
    conversation_id: Optional[str] = Header(None, alias="X-Conversation-ID", description="Conversation identifier"),
    # token_claims: dict = Depends(verify_token_dependency)  # Commented out - JWT auth disabled
):
    """
    Process a natural language query through the AI Analyst pipeline

    Args:
        request: QueryRequest containing the query text
        workspace_id: Workspace identifier from header (X-Workspace-ID)
        user_id: User identifier from header (X-User-ID)

    Returns:
        QueryResponse with formatted results

    Raises:
        HTTPException: If query processing fails

    Note:
        JWT authentication is currently disabled. workspace_id and user_id
        are read directly from headers for simplified testing.
    """
    # Generate request ID for tracing
    request_id = str(uuid.uuid4())

    # Log request with request ID
    logger.info(
        f"Processing query (request_id={request_id}, workspace={workspace_id}, "
        f"user={user_id}, query_length={len(request.query)})"
    )

    start_time = time.time()

    try:
        # Ensure conversation exists and store messages
        from services.conversation import ensure_conversation, create_message

        conversation_id = await ensure_conversation(
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
            title_hint=request.query
        )

        # Store user message
        await create_message(
            conversation_id=conversation_id,
            role="USER",
            content=request.query,
            metadata={"workspace_id": workspace_id, "user_id": user_id}
        )

        # Retrieve conversation context (hybrid search with recency priority)
        from services.vector_store import retrieve_conversation_context
        
        try:
            context_messages = await retrieve_conversation_context(
                conversation_id=conversation_id,
                current_query=request.query,
                top_k=5  # Get top 5 relevant messages
            )
            logger.info(f"Retrieved {len(context_messages)} context messages")
        except Exception as e:
            logger.warning(f"Context retrieval failed: {e}, continuing without context")
            context_messages = []

        # Create pipeline instance
        pipeline = AnalystPipeline()

        # Execute pipeline with context (async call)
        result = await pipeline.run(
            user_query=request.query,
            workspace_id=workspace_id,
            user_id=user_id,
            context_messages=context_messages
        )

        # Store assistant message (keep metadata JSON-safe and minimal)
        assistant_text = result.get("response") if isinstance(result, dict) else str(result)
        await create_message(
            conversation_id=conversation_id,
            role="ASSISTANT",
            content=assistant_text,
            metadata={"workspace_id": workspace_id, "user_id": user_id}
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
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id
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

