"""LangGraph ReAct agent implementation."""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from src.config import get_settings
from src.agent.prompts import SYSTEM_PROMPT
from src.tools import get_all_tools
from src.tools.base import ToolContext, parse_data_change

logger = logging.getLogger(__name__)

# Global checkpointer and connection manager
_checkpointer_context = None
_checkpointer: AsyncPostgresSaver | MemorySaver | None = None
_memory_saver: MemorySaver | None = None


def get_llm():
    """Get the configured LLM instance.
    
    Returns:
        ChatOpenAI or ChatAnthropic instance based on configuration
    """
    settings = get_settings()
    
    if settings.is_openai:
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            streaming=True,
        )
    else:
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=0.7,
            streaming=True,
        )


async def get_checkpointer():
    """Get the checkpointer for conversation persistence.
    
    Uses PostgreSQL if DATABASE_URL is configured, otherwise falls back
    to in-memory checkpointer.
    
    Returns:
        AsyncPostgresSaver or MemorySaver instance
    """
    global _checkpointer_context, _checkpointer, _memory_saver
    
    settings = get_settings()
    
    # If already initialized, return cached checkpointer
    if _checkpointer is not None:
        return _checkpointer
    
    # Try PostgreSQL if configured
    if settings.database_url:
        try:
            logger.info(f"Attempting to connect to PostgreSQL for conversation persistence...")
            # Create the async context manager
            _checkpointer_context = AsyncPostgresSaver.from_conn_string(settings.database_url)
            # Enter the context to get the actual checkpointer
            _checkpointer = await _checkpointer_context.__aenter__()
            # Setup the checkpointer tables
            await _checkpointer.setup()
            logger.info("PostgreSQL checkpointer initialized successfully - conversations will persist!")
            return _checkpointer
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
            logger.warning("Falling back to in-memory storage - conversations will NOT persist across restarts!")
            _checkpointer_context = None
    else:
        logger.warning("DATABASE_URL not configured - using in-memory storage")
    
    # Fallback to in-memory checkpointer
    if _memory_saver is None:
        _memory_saver = MemorySaver()
        logger.warning("Using in-memory checkpointer (conversation history will NOT persist across restarts)")
    
    _checkpointer = _memory_saver
    return _checkpointer


async def cleanup_checkpointer():
    """Cleanup the checkpointer connection on shutdown."""
    global _checkpointer_context, _checkpointer
    
    if _checkpointer_context is not None:
        try:
            await _checkpointer_context.__aexit__(None, None, None)
            logger.info("PostgreSQL checkpointer connection closed")
        except Exception as e:
            logger.error(f"Error closing checkpointer connection: {e}")
        finally:
            _checkpointer_context = None
            _checkpointer = None


def create_agent_for_context(context: ToolContext, checkpointer=None):
    """Create a ReAct agent with tools configured for the given context.
    
    Args:
        context: Tool context with auth and workspace info
        checkpointer: Optional checkpointer for conversation memory
        
    Returns:
        Compiled LangGraph agent
    """
    llm = get_llm()
    tools = get_all_tools(context)
    
    # Create the agent using the prebuilt ReAct pattern
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    
    return agent


async def create_agent(context: ToolContext):
    """Create a compiled agent with checkpointer.
    
    Args:
        context: Tool context with auth and workspace info
        
    Returns:
        Compiled LangGraph agent with checkpointer
    """
    checkpointer = await get_checkpointer()
    return create_agent_for_context(context, checkpointer)


async def get_agent(context: ToolContext):
    """Create an agent for the given context.
    
    Note: We don't cache agents because tools are bound to specific
    auth contexts. Each request creates a fresh agent with the correct
    auth token for GraphQL calls.
    
    Args:
        context: Tool context with auth and workspace info
        
    Returns:
        Compiled LangGraph agent
    """
    logger.info(f"Creating new agent for workspace {context.workspace_id}")
    return await create_agent(context)


async def invoke_agent(
    context: ToolContext,
    message: str,
    conversation_id: str,
) -> dict[str, Any]:
    """Invoke the agent with a message.
    
    Args:
        context: Tool context with auth and workspace info
        message: User message
        conversation_id: Conversation thread ID
        
    Returns:
        Agent response
    """
    agent = await get_agent(context)
    
    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }
    
    result = await agent.ainvoke(
        {
            "messages": [{"role": "user", "content": message}],
        },
        config=config,
    )
    
    return result


async def stream_agent(
    context: ToolContext,
    message: str,
    conversation_id: str,
):
    """Stream agent response for a message.
    
    This generator yields events as the agent processes the request,
    including thinking steps, tool calls, and the final response.
    
    Args:
        context: Tool context with auth and workspace info
        message: User message
        conversation_id: Conversation thread ID
        
    Yields:
        Event dictionaries with type and data
    """
    agent = await get_agent(context)
    
    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }
    
    # Stream using updates mode to get step-by-step progress
    async for chunk in agent.astream(
        {
            "messages": [{"role": "user", "content": message}],
        },
        config=config,
        stream_mode="updates",
    ):
        # Process each update chunk
        for node_name, node_output in chunk.items():
            if node_name == "agent":
                # This is the LLM response
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        # Agent decided to call tools
                        for tool_call in msg.tool_calls:
                            yield {
                                "type": "tool_call",
                                "data": {
                                    "name": tool_call.get("name"),
                                    "args": tool_call.get("args", {}),
                                },
                            }
                    elif hasattr(msg, "content") and msg.content:
                        # Agent response
                        yield {
                            "type": "response",
                            "data": {"content": msg.content},
                        }
            elif node_name == "tools":
                # Tool execution results
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content"):
                        # Parse result to extract any data change metadata
                        cleaned_result, change_data = parse_data_change(msg.content)
                        
                        # Yield the tool result (with cleaned content)
                        yield {
                            "type": "tool_result",
                            "data": {
                                "name": getattr(msg, "name", "unknown"),
                                "result": cleaned_result,
                            },
                        }
                        
                        # If there was a data change, emit a separate event for frontend cache invalidation
                        if change_data:
                            yield {
                                "type": "data_changed",
                                "data": change_data,
                            }
    
    # Signal completion
    yield {"type": "done", "data": {}}

