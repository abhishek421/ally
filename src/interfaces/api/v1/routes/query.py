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
    user_id = "default_user" 
    
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
        
        try:
            async for chunk in graph_app.astream(current_state.model_dump(), config=config):
                pass
            
            final_state_snapshot = await graph_app.aget_state(config)
            
            if final_state_snapshot and final_state_snapshot.values:
                final_agent_state = AgentState(**final_state_snapshot.values)
                await service.store.save_state(conversation_id, final_agent_state)
                
                final_answer = "Processed query."
                if final_agent_state.final_response:
                    final_answer = str(final_agent_state.final_response)
                elif final_agent_state.messages:
                    last = final_agent_state.messages[-1]
                    if last.role == Role.ASSISTANT:
                        final_answer = last.content

                block_id = str(uuid.uuid4())
                yield format_sse({
                    "type": "block_start",
                    "block_id": block_id,
                    "block_type": "TEXT",
                    "order": 0,
                    "metadata": {},
                    "entity_mentions": []
                })
                
                yield format_sse({
                    "type": "block_delta",
                    "block_id": block_id,
                    "content": final_answer
                })
                
                yield format_sse({
                    "type": "block_complete",
                    "block_id": block_id,
                    "block_type": "TEXT",
                    "content": final_answer,
                    "order": 0,
                    "metadata": {},
                    "entity_mentions": []
                })
                blocks_count += 1
                
                # Persist Assistant Response to DB
                api_assistant_msg = ApiMessage(
                    id=message_id,
                    role="ASSISTANT",
                    timestamp=datetime.utcnow(),
                    blocks=[
                        {
                            "block_id": block_id,
                            "block_type": "TEXT",
                            "content": final_answer,
                            "order": 0,
                            "metadata": {},
                            "entity_mentions": []
                        }
                    ]
                )
                await service.persist_messages(conversation_id, [api_assistant_msg])
            
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
