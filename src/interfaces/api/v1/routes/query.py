import json
import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, List
from fastapi import APIRouter, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.schemas import QueryRequest, Conversation, BlockType, Message as ApiMessage
from src.graph import graph_app
from src.application.services.conversation.service import ConversationService
from src.memory.session_store import create_session_store
from src.config.logger import logger
from src.utils.types import Message as InternalMessage, Role
from src.memory.state import AgentState
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.repository import ConversationRepository

from src.tools.graphql_client import gql_request

router = APIRouter(tags=["query"])

# Dependency to get conversation service
async def get_conversation_service(
    db_session: AsyncSession = Depends(get_db_session)
) -> ConversationService:
    store = create_session_store()
    repo = ConversationRepository(db_session)
    return ConversationService(store, repo)

def format_sse(event: dict) -> str:
    """Format dictionary as SSE string."""
    return f"data: {json.dumps(event)}\n\n"

@router.post("/query")
async def process_query(
    payload: QueryRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-ID"),
    authorization: str = Header(None),
    service: ConversationService = Depends(get_conversation_service)
) -> StreamingResponse:
    
    # 1. Handle Conversation
    # Fetch user details from GraphQL if auth token is present
    user_id = "550e8400-e29b-41d4-a716-446655440000" # Default fallback
    user_details = None
    
    if authorization:
        try:
            user_query = """
                query CurrentLoggedInUser {
                    currentLoggedInUser {
                        id
                        email
                        firstName
                        lastName
                        role
                        avatarUrl
                        workspaces {
                            id
                            name
                        }
                    }
                }
            """
            user_data = await gql_request(user_query, auth_token=authorization)
            if user_data and "currentLoggedInUser" in user_data:
                user_details = user_data["currentLoggedInUser"]
                if user_details: # Check if not null
                    user_id = user_details.get("id", user_id)
                    logger.info(f"Authenticated user: {user_details.get('email')}")
                else:
                    logger.warning("currentLoggedInUser returned null")
        except Exception as e:
            logger.warning(f"Failed to fetch user details: {e}")
            
    conversation_id = payload.conversation_id
    if not conversation_id:
        title = payload.query[:50] + "..." if len(payload.query) > 50 else payload.query
        conversation = await service.create_conversation(user_id, x_workspace_id, title)
        conversation_id = conversation.id
    else:
        conversation = await service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.workspace_id != x_workspace_id:
             raise HTTPException(status_code=403, detail="Access denied")

    # 2. Prepare State
    current_state = await service.store.load_state(conversation_id)
    
    if not current_state.conversation_id or current_state.conversation_id == conversation_id:
        current_state.conversation_id = conversation_id
        current_state.user_id = user_id
        current_state.workspace_id = x_workspace_id
        current_state.user_details = user_details
    
    current_state.graphql_auth_token = authorization
    
    # Create Internal Message for Agent
    new_message_id = str(uuid.uuid4())
    new_message = InternalMessage(
        role=Role.USER,
        content=payload.query,
        timestamp=datetime.utcnow()
    )
    current_state.messages.append(new_message)
    
    # Persist User Message to DB
    # We need to map InternalMessage to Schema Message
    api_user_msg = ApiMessage(
        id=new_message_id,
        role="USER",
        timestamp=new_message.timestamp,
        blocks=[
            # Assuming simple text block for user query
             {
                "block_id": str(uuid.uuid4()),
                "block_type": "TEXT",
                "content": payload.query,
                "order": 0,
                "metadata": {},
                "entity_mentions": payload.entity_mentions or []
             }
        ]
    )
    await service.persist_messages(conversation_id, [api_user_msg])

    current_state.reasoning = []
    current_state.tool_calls = []
    current_state.parallel_results = {}
    current_state.retrieved_memories = []
    current_state.final_response = None
    
    # 3. Stream Generator
    async def event_generator() -> AsyncGenerator[str, None]:
        message_id = str(uuid.uuid4())
        yield format_sse({
            "type": "message_start", 
            "message_id": message_id, 
            "conversation_id": conversation_id
        })
        
        blocks_count = 0
        config = {"configurable": {"thread_id": conversation_id}}
        
        # Track block IDs to update them (Planner -> Final Thinking, Executor -> Final Tool Log)
        thinking_block_id = str(uuid.uuid4())
        tool_log_block_id = str(uuid.uuid4())
        
        has_streamed_thinking = False
        has_streamed_tool_log = False

        try:
            # Stream events from graph
            async for chunk in graph_app.astream(current_state.model_dump(), config=config):
                for node_name, node_state in chunk.items():
                    
                    # ---------------------------------------------------------
                    # 1. PLANNER -> Stream "Thinking..."
                    # ---------------------------------------------------------
                    if node_name == "planner":
                        plan = node_state.get("plan", {})
                        if plan:
                            # Use the plan summary or a default message
                            content = plan.get("summary", "Planning execution...")
                            
                            yield format_sse({
                                "type": "block_start",
                                "block_id": thinking_block_id,
                                "block_type": "THINKING",
                                "order": blocks_count, # Should be 0 usually
                                "metadata": {},
                                "entity_mentions": []
                            })
                            yield format_sse({
                                "type": "block_delta",
                                "block_id": thinking_block_id,
                                "content": content
                            })
                            yield format_sse({
                                "type": "block_complete",
                                "block_id": thinking_block_id,
                                "block_type": "THINKING",
                                "content": content,
                                "order": blocks_count,
                                "metadata": {},
                                "entity_mentions": []
                            })
                            
                            if not has_streamed_thinking:
                                blocks_count += 1
                                has_streamed_thinking = True

                    # ---------------------------------------------------------
                    # 2. EXECUTOR -> Stream "Tool Logs"
                    # ---------------------------------------------------------
                    elif node_name == "executor":
                        execution_results = node_state.get("execution_results", {})
                        results = execution_results.get("results", [])
                        
                        if results:
                            content = json.dumps(results)
                            
                            # If we haven't streamed tool log yet, start it
                            # If we have, we are overwriting/updating it (which is fine, it's a replace in the Map)
                            yield format_sse({
                                "type": "block_start",
                                "block_id": tool_log_block_id,
                                "block_type": "TOOL_LOG",
                                "order": blocks_count,
                                "metadata": {},
                                "entity_mentions": []
                            })
                            yield format_sse({
                                "type": "block_delta",
                                "block_id": tool_log_block_id,
                                "content": content
                            })
                            yield format_sse({
                                "type": "block_complete",
                                "block_id": tool_log_block_id,
                                "block_type": "TOOL_LOG",
                                "content": content,
                                "order": blocks_count,
                                "metadata": {},
                                "entity_mentions": []
                            })
                            
                            if not has_streamed_tool_log:
                                blocks_count += 1
                                has_streamed_tool_log = True

                    # ---------------------------------------------------------
                    # 3. FORMAT RESPONSE -> Stream Final Blocks
                    # ---------------------------------------------------------
                    elif node_name == "format_response":
                        final_response_data = node_state.get("final_response", {})
                        messages = final_response_data.get("messages", [])
                        
                        # Save final state logic (kept from original)
                        # We need to get the final state from the graph explicitly if we want to save it properly
                        # But node_state IS the state update.
                        # The original code did graph_app.aget_state(config) to save.
                        # We should do that after the loop to be safe and consistent.
                        
                        api_blocks = []
                        
                        for i, block in enumerate(messages):
                            raw_type = block.get("type", "markdown")
                            content = block.get("content", "")
                            
                            # Map block types
                            block_type = "TEXT"
                            metadata = {}
                            current_block_id = str(uuid.uuid4()) # Default new ID
                            
                            if raw_type == "thinking":
                                block_type = "THINKING"
                                # Reuse ID to update the "Planning..." block
                                if has_streamed_thinking:
                                    current_block_id = thinking_block_id
                                    # Adjust order to match the original one (which was 0)
                                    # But wait, 'i' here is the order in final response.
                                    # If 'thinking' is first in final response, 'i' is 0. Matches.
                                    
                            elif raw_type == "tool_log":
                                block_type = "TOOL_LOG"
                                if isinstance(content, list) or isinstance(content, dict):
                                    content = json.dumps(content)
                                    
                                # Reuse ID to update
                                if has_streamed_tool_log:
                                    current_block_id = tool_log_block_id
                                        
                            elif raw_type.startswith("entity_") and raw_type.endswith("_list"):
                                block_type = "ENTITY_LIST"
                                entity_type = raw_type.replace("entity_", "").replace("_list", "")
                                metadata = {"entity_type": entity_type}
                                if isinstance(content, list):
                                    content = "\n".join([json.dumps(item) for item in content])
                                        
                            elif raw_type == "markdown":
                                block_type = "TEXT"
                            
                            # Ensure content is string
                            if not isinstance(content, str):
                                content = json.dumps(content)

                            # Stream the block
                            yield format_sse({
                                "type": "block_start",
                                "block_id": current_block_id,
                                "block_type": block_type,
                                "order": i, # Use 'i' from final list to ensure correct final order
                                "metadata": metadata,
                                "entity_mentions": []
                            })
                            
                            yield format_sse({
                                "type": "block_delta",
                                "block_id": current_block_id,
                                "content": content
                            })
                            
                            yield format_sse({
                                "type": "block_complete",
                                "block_id": current_block_id,
                                "block_type": block_type,
                                "content": content,
                                "order": i,
                                "metadata": metadata,
                                "entity_mentions": []
                            })
                            
                            api_blocks.append({
                                "block_id": current_block_id,
                                "block_type": block_type,
                                "content": content,
                                "order": i,
                                "metadata": metadata,
                                "entity_mentions": []
                            })
                            
                            # Update blocks_count for message_complete event
                            if i >= blocks_count:
                                blocks_count = i + 1
                        
                        # Persist Assistant Response to DB
                        api_assistant_msg = ApiMessage(
                            id=message_id,
                            role="ASSISTANT",
                            timestamp=datetime.utcnow(),
                            blocks=api_blocks
                        )
                        await service.persist_messages(conversation_id, [api_assistant_msg])

            # Save final state after loop
            final_state_snapshot = await graph_app.aget_state(config)
            if final_state_snapshot and final_state_snapshot.values:
                final_agent_state = AgentState(**final_state_snapshot.values)
                await service.store.save_state(conversation_id, final_agent_state)
            
            yield format_sse({
                "type": "message_complete",
                "message_id": message_id,
                "blocks_count": blocks_count
            })
            
        except Exception as e:
            logger.error(f"Error streaming query: {e}", exc_info=True)
            yield format_sse({
                "type": "error", 
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
