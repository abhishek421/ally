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
from config.settings import CONTEXT_K_RECENT, CONTEXT_R_RETRIEVED

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean_response(result: dict) -> dict:
    """
    Remove internal debugging metadata from response for cleaner API output

    Keeps only user-facing data:
    - response: The AI answer
    - data: The actual query results
    - (optionally) minimal metadata for debugging

    Args:
        result: Raw result from pipeline

    Returns:
        Cleaned result dict
    """
    if not isinstance(result, dict):
        return result

    # Start with a clean dict
    cleaned = {}

    # Always include the AI response
    if "response" in result:
        cleaned["response"] = result["response"]

    # Include the actual data, but clean it too
    if "data" in result:
        data = result["data"]
        if isinstance(data, dict):
            # Remove internal metadata fields (those starting with _)
            cleaned["data"] = {
                k: v for k, v in data.items()
                if not k.startswith("_")
            }
        else:
            cleaned["data"] = data

    # Optionally include minimal metadata (not the full orchestration details)
    if "metadata" in result and isinstance(result["metadata"], dict):
        # Only include high-level metadata, not internal processing details
        cleaned["metadata"] = {
            k: v for k, v in result["metadata"].items()
            if k in ["data_sources_count", "response_length"]
        }

    return cleaned


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    workspace_id: str = Header(..., alias="X-Workspace-ID", description="Workspace identifier"),
    user_id: str = Header(..., alias="X-User-ID", description="User identifier"),
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
        # Fast-path routing for meta queries (help, greetings, etc.)
        from agents.query_router import QueryRouter
        router = QueryRouter()
        fast_response = router.route(request.query)

        if fast_response:
            # Meta query - return instant response
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Fast-path response delivered (request_id={request_id}, "
                f"execution_time_ms={execution_time_ms})"
            )
            return QueryResponse(
                success=True,
                query=request.query,
                result=fast_response,
                execution_time_ms=execution_time_ms,
                workspace_id=workspace_id,
                user_id=user_id,
                conversation_id=request.conversation_id or "N/A"
            )

        # Regular data query - continue with full pipeline
        # Ensure conversation exists and store messages
        from services.conversation import ensure_conversation, create_message

        conversation_id = await ensure_conversation(
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=request.conversation_id,
            title_hint=request.query
        )

        # Store user message
        await create_message(
            conversation_id=conversation_id,
            role="USER",
            content=request.query,
            metadata={"workspace_id": workspace_id, "user_id": user_id}
        )

        # Retrieve conversation context (hybrid search: K=10 recent + R=5 retrieved)
        from services.vector_store import retrieve_conversation_context
        
        try:
            context_messages = await retrieve_conversation_context(
                conversation_id=conversation_id,
                current_query=request.query,
                k_recent=CONTEXT_K_RECENT,
                r_retrieved=CONTEXT_R_RETRIEVED
            )
            logger.info(f"Retrieved {len(context_messages)} context messages (K={CONTEXT_K_RECENT}, R={CONTEXT_R_RETRIEVED})")
        except Exception as e:
            logger.warning(f"Context retrieval failed: {e}, continuing without context")
            context_messages = []

        # Create pipeline instance with orchestrator enabled
        from graph.pipeline import create_pipeline
        pipeline = create_pipeline(enable_reactive=True, enable_orchestrator=True)

        # Execute pipeline with context (async call)
        result = await pipeline.run(
            user_query=request.query,
            workspace_id=workspace_id,
            user_id=user_id,
            context_messages=context_messages
        )

        # Store assistant message with compact metadata
        # Extract compact query context (IDs and references only, not full data)
        from utils.metadata_extractor import extract_compact_query_context, extract_performance_metadata

        # Handle both successful responses and clarification requests
        if isinstance(result, dict) and result.get("status") == "needs_clarification":
            assistant_text = result.get("clarification_question", "I need more information to answer your question.")
        else:
            assistant_text = result.get("response") if isinstance(result, dict) else str(result)

        # Ensure assistant_text is not None
        if not assistant_text:
            assistant_text = "I couldn't generate a response. Please try again."

        query_context = extract_compact_query_context(result)
        performance_metadata = extract_performance_metadata(result)

        # Log what we're storing (for monitoring/debugging)
        if query_context.get("tools_executed"):
            logger.info(
                f"Storing compact metadata: tools={query_context['tools_executed']}, "
                f"results={list(query_context.get('result_summary', {}).keys())}"
            )

        await create_message(
            conversation_id=conversation_id,
            role="ASSISTANT",
            content=assistant_text,
            metadata={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "query_context": query_context,
                "performance": performance_metadata
            }
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Query processed successfully (request_id={request_id}, "
            f"execution_time_ms={execution_time_ms})"
        )

        # Clean up response - remove internal metadata for production
        cleaned_result = _clean_response(result)

        return QueryResponse(
            success=True,
            query=request.query,
            result=cleaned_result,
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

