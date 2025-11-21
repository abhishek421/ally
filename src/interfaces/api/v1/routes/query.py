"""
Main query endpoint for processing natural language queries
"""
import time
import logging
import uuid
import json
from fastapi import APIRouter, HTTPException, status, Header, BackgroundTasks, Depends, Response
from fastapi.responses import StreamingResponse
from typing import Optional
from src.interfaces.api.v1.schemas.schemas import QueryRequest, QueryResponse, ErrorResponse
from src.interfaces.api.v1.middleware.dependencies import get_current_user_id
from src.core.workflows.graphs.pipeline import AnalystPipeline

logger = logging.getLogger(__name__)

router = APIRouter()


async def _handle_streaming(request: QueryRequest, workspace_id: str, user_id: str, access_token: str):
    """Handle streaming query with SSE"""
    from src.application.services.conversation.conversation_service import ensure_conversation, get_message_count
    from src.application.services.blocks.models import StreamEvent, Block, BlockType
    from src.application.services.blocks.block_manager import save_message_with_blocks
    from src.application.services.conversation.conversation_state import ConversationState
    from src.core.agents.orchestration.orchestrator import OrchestratorAgent
    from src.infrastructure.database.prisma_client import prisma_client

    request_id = str(uuid.uuid4())

    logger.info(
        f"Streaming query (request_id={request_id}, workspace={workspace_id}, "
        f"user={user_id}, query_length={len(request.query)})"
    )

    async def generate_stream():
        """Generate SSE stream"""
        try:
            # Performance tracking
            perf_start = time.time()
            logger.info(f"[PERF] {request_id} - Stream started at {perf_start:.3f}")

            # Create conversation and store user message
            perf_conv_start = time.time()
            conversation_id = await ensure_conversation(
                workspace_id=workspace_id,
                user_id=user_id,
                conversation_id=request.conversation_id,
                title_hint=request.query
            )
            perf_conv_end = time.time()
            logger.info(f"[PERF] {request_id} - Conversation created in {(perf_conv_end - perf_conv_start)*1000:.0f}ms")

            # Store user message as blocks
            user_message_id = str(uuid.uuid4())

            # Convert entity mentions to dict if present
            entity_mentions_dict = None
            if request.entity_mentions:
                entity_mentions_dict = [
                    {
                        "entityId": mention.entityId,
                        "entityType": mention.entityType,
                        "name": mention.name,
                        "span": {
                            "start": mention.span.start,
                            "end": mention.span.end
                        }
                    }
                    for mention in request.entity_mentions
                ]

            user_block = Block(
                block_id=str(uuid.uuid4()),
                block_type=BlockType.TEXT,
                content=request.query,
                order=0,
                metadata={"workspace_id": workspace_id, "user_id": user_id},
                entity_mentions=entity_mentions_dict
            )
            perf_save_start = time.time()
            await save_message_with_blocks(
                conversation_id=conversation_id,
                message_id=user_message_id,
                role="USER",
                blocks=[user_block]
            )
            perf_save_end = time.time()
            logger.info(f"[PERF] {request_id} - User message saved in {(perf_save_end - perf_save_start)*1000:.0f}ms")

            # Create assistant message ID
            message_id = str(uuid.uuid4())

            # Send message_start event
            perf_first_event = time.time()
            yield f"data: {json.dumps(StreamEvent.message_start(message_id, conversation_id).to_dict())}\n\n"
            logger.info(f"[PERF] {request_id} - First event (message_start) sent in {(perf_first_event - perf_start)*1000:.0f}ms from stream start")

            # Get conversation context
            message_count = await get_message_count(conversation_id)
            is_first = (message_count == 1)

            context_messages = []
            if not is_first:
                perf_ctx_start = time.time()
                try:
                    client = await prisma_client.get_client()
                    messages = await client.conversationmessage.find_many(
                        where={"conversationId": conversation_id},
                        order={"timestamp": "desc"},
                        take=11
                    )

                    if messages:
                        # Rebuild context from ALL blocks (not just text)
                        context_messages = []
                        for msg in reversed(messages[1:]):
                            blocks = await client.messageblock.find_many(
                                where={"messageId": msg.id},
                                order={"order": "asc"}
                            )
                            
                            # Convert all blocks to serializable format
                            all_blocks = []
                            metadata = None
                            
                            for block in blocks:
                                block_dict = {
                                    "block_type": block.blockType,
                                    "content": block.content,
                                    "order": block.order
                                }
                                
                                # Include metadata if present
                                if block.metadata:
                                    block_dict["metadata"] = block.metadata
                                    # Extract query_context from TEXT blocks for conversation state
                                    if block.blockType == "TEXT" and isinstance(block.metadata, dict):
                                        if "query_context" in block.metadata:
                                            metadata = block.metadata
                                
                                # Include entity_mentions if present
                                if block.entityMentions:
                                    block_dict["entity_mentions"] = block.entityMentions
                                
                                all_blocks.append(block_dict)

                            context_messages.append({
                                "role": msg.role,
                                "blocks": all_blocks,  # ALL blocks
                                "metadata": metadata  # For conversation state rebuild
                            })
                        perf_ctx_end = time.time()
                        logger.info(f"[PERF] {request_id} - Retrieved {len(context_messages)} context messages in {(perf_ctx_end - perf_ctx_start)*1000:.0f}ms")
                except Exception as e:
                    logger.warning(f"Context retrieval failed: {e}")
                    context_messages = []

            # Initialize conversation state
            conversation_state = ConversationState()
            if context_messages:
                conversation_state.rebuild_from_messages(context_messages)
            conversation_state.set_last_query(request.query)

            # Stream blocks from orchestrator
            perf_orch_start = time.time()
            logger.info(f"[PERF] {request_id} - Starting orchestrator at {(perf_orch_start - perf_start)*1000:.0f}ms from stream start")
            orchestrator = OrchestratorAgent()
            blocks = []
            first_orch_event = True

            async for event in orchestrator.stream_orchestrate(
                user_query=request.query,
                workspace_id=workspace_id,
                user_id=user_id,
                access_token=access_token,
                context_messages=context_messages,
                conversation_state=conversation_state,
                entity_mentions=entity_mentions_dict
            ):
                # Log first orchestrator event
                if first_orch_event:
                    perf_first_orch = time.time()
                    logger.info(f"[PERF] {request_id} - First orchestrator event in {(perf_first_orch - perf_orch_start)*1000:.0f}ms")
                    first_orch_event = False

                # Send event as SSE
                yield f"data: {json.dumps(event.to_dict())}\n\n"

                # Collect blocks for saving
                if event.type.value == "block_complete":
                    # Event data now only includes metadata/entity_mentions if they have values
                    # So we can use them directly, or None if not present
                    # Handle both None and empty dict/list cases for safety
                    event_metadata = event.data.get("metadata")
                    event_entity_mentions = event.data.get("entity_mentions")

                    block_metadata = None
                    if event_metadata is not None:
                        if isinstance(event_metadata, dict) and event_metadata:
                            block_metadata = event_metadata

                    block_entity_mentions = None
                    if event_entity_mentions is not None:
                        if isinstance(event_entity_mentions, list) and event_entity_mentions:
                            block_entity_mentions = event_entity_mentions

                    block = Block(
                        block_id=event.data["block_id"],
                        block_type=BlockType(event.data["block_type"]),
                        content=event.data["content"],
                        order=event.data["order"],
                        metadata=block_metadata,
                        entity_mentions=block_entity_mentions
                    )

                    blocks.append(block)

            # Save message with blocks to database
            if blocks:
                perf_final_save_start = time.time()
                await save_message_with_blocks(
                    conversation_id=conversation_id,
                    message_id=message_id,
                    role="ASSISTANT",
                    blocks=blocks
                )
                perf_final_save_end = time.time()
                logger.info(f"[PERF] {request_id} - Saved {len(blocks)} blocks in {(perf_final_save_end - perf_final_save_start)*1000:.0f}ms")

            # Send completion event
            perf_end = time.time()
            yield f"data: {json.dumps(StreamEvent.message_complete(message_id, len(blocks)).to_dict())}\n\n"

            logger.info(f"[PERF] {request_id} - TOTAL STREAM TIME: {(perf_end - perf_start)*1000:.0f}ms")
            logger.info(f"Stream complete (request_id={request_id}, blocks={len(blocks)})")

        except Exception as e:
            error_message = str(e)
            logger.error(
                f"Streaming failed (request_id={request_id}, error={error_message})",
                exc_info=True
            )
            yield f"data: {json.dumps(StreamEvent.error(error_message, 'STREAM_ERROR').to_dict())}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/query")
async def process_query(
    request: QueryRequest,
    workspace_id: str = Header(..., alias="X-Workspace-ID", description="Workspace identifier"),
    user_id: str = Depends(get_current_user_id),
    authorization: str = Header(..., description="Bearer token for API access"),
):
    """
    Process a natural language query - always returns SSE stream with block-based messages

    Returns blocks in order: THINKING → TEXT → TABLE

    Example SSE stream:
        data: {"type":"message_start","message_id":"...","conversation_id":"..."}
        data: {"type":"block_complete","block_id":"...","block_type":"THINKING",...}
        data: {"type":"block_complete","block_id":"...","block_type":"TEXT",...}
        data: {"type":"block_complete","block_id":"...","block_type":"TABLE",...}
        data: {"type":"message_complete","message_id":"...","blocks_count":3}

    Args:
        request: QueryRequest containing the query text
        workspace_id: Workspace identifier from header (X-Workspace-ID)
        user_id: User identifier from Cognito token (automatically extracted)
        authorization: Authorization header with Bearer token

    Returns:
        StreamingResponse with SSE events

    Raises:
        HTTPException: If query processing fails or authentication fails
    """
    # Extract access token from Authorization header
    from src.interfaces.api.v1.middleware.dependencies import get_bearer_token
    access_token = get_bearer_token(authorization)

    # Always stream - simpler architecture
    return await _handle_streaming(request, workspace_id, user_id, access_token)
