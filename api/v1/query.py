"""
Main query endpoint for processing natural language queries
"""
import time
import logging
import uuid
from fastapi import APIRouter, HTTPException, status, Header, BackgroundTasks, Depends, Response
from typing import Optional
from api.v1.schemas import QueryRequest, QueryResponse, ErrorResponse
from api.dependencies import get_current_user_id
from graph.pipeline import AnalystPipeline

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
    background_tasks: BackgroundTasks,
    response: Response,
    workspace_id: str = Header(..., alias="X-Workspace-ID", description="Workspace identifier"),
    user_id: str = Depends(get_current_user_id),
):
    """
    Process a natural language query through the AI Analyst pipeline

    Args:
        request: QueryRequest containing the query text
        workspace_id: Workspace identifier from header (X-Workspace-ID)
        user_id: User identifier from Cognito token (automatically extracted)

    Returns:
        QueryResponse with formatted results

    Raises:
        HTTPException: If query processing fails or authentication fails
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
        # Create conversation and store user message IMMEDIATELY
        # This allows frontend to get conversation_id right away via response headers
        from services.conversation import ensure_conversation, create_message

        conversation_id = await ensure_conversation(
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=request.conversation_id,
            title_hint=request.query
        )

        # Store user message immediately
        await create_message(
            conversation_id=conversation_id,
            role="USER",
            content=request.query,
            metadata={"workspace_id": workspace_id, "user_id": user_id}
        )

        # Set conversation_id in response headers immediately
        # Frontend can read this header without waiting for full response body
        response.headers["X-Conversation-ID"] = conversation_id

        # Fast-path routing for meta queries (help, greetings, etc.)
        from agents.query_router import QueryRouter
        from config.config_manager import ConfigManager

        config_manager = ConfigManager()
        router = QueryRouter(config_manager=config_manager)
        fast_response = await router.route(request.query)

        if fast_response:
            # Meta query - store assistant message and return quickly
            await create_message(
                conversation_id=conversation_id,
                role="ASSISTANT",
                content=fast_response["response"],
                metadata=fast_response.get("metadata", {})
            )

            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Fast-path response delivered (request_id={request_id}, "
                f"conversation_id={conversation_id}, "
                f"execution_time_ms={execution_time_ms})"
            )
            return QueryResponse(
                success=True,
                query=request.query,
                result=fast_response,
                execution_time_ms=execution_time_ms,
                workspace_id=workspace_id,
                user_id=user_id,
                conversation_id=conversation_id
            )

        # Regular data query - continue with full pipeline

        # Retrieve recent conversation history from database
        from database.prisma_client import prisma_client
        from services.conversation import get_message_count

        # Check if this is the first message
        message_count = await get_message_count(conversation_id)
        is_first = (message_count == 1)  # Just the user message we stored above

        # Retrieve recent messages from database for context
        context_messages = []
        if not is_first:
            try:
                client = await prisma_client.get_client()
                # Get last 10 messages (excluding the current user message we just stored)
                messages = await client.conversationmessage.find_many(
                    where={"conversationId": conversation_id},
                    order={"timestamp": "desc"},
                    take=11  # Get 11 to exclude the current one
                )

                # Skip the first one (current user message) and reverse to chronological order
                if messages:
                    context_messages = [
                        {"role": msg.role, "content": msg.content}
                        for msg in reversed(messages[1:])
                    ]
                    logger.info(f"Retrieved {len(context_messages)} messages from conversation history")
            except Exception as e:
                logger.warning(f"Context retrieval failed: {e}, continuing without context")
                context_messages = []
        else:
            logger.info("First message in conversation - no context to retrieve")

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

        # Store assistant message in background (saves 200-500ms)
        # Don't wait for DB write before returning response to user
        background_tasks.add_task(
            create_message,
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

