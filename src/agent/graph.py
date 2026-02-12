"""LangGraph ReAct agent implementation."""

import logging
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt
import time

from src.config import get_settings
from src.agent.prompts import get_system_prompt
from src.tools import get_all_tools
from src.tools.base import ToolContext, parse_data_change

logger = logging.getLogger(__name__)


def _extract_text_content(content: Any) -> str:
    """Extract text from LLM response content.
    
    Handles different content formats from various providers:
    - OpenAI/Anthropic: Plain string
    - Gemini: List of content blocks like [{'type': 'text', 'text': '...', 'extras': {...}}]
    
    Args:
        content: The content from an LLM message
        
    Returns:
        Extracted text as a string
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        # Gemini returns list of content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                # Extract text from content block
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(block["text"])
                elif "text" in block:
                    text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts)
    
    # Fallback: convert to string
    return str(content)


# Global checkpointer and connection manager
_checkpointer_context = None
_checkpointer: AsyncPostgresSaver | MemorySaver | None = None
_memory_saver: MemorySaver | None = None
def get_llm():
    """Get the configured LLM instance.
    Returns:
        ChatOpenAI, ChatAnthropic, or ChatGoogleGenerativeAI instance based on configuration
    """
    settings = get_settings()
    if settings.is_openai:
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            streaming=True,
        )
    elif settings.is_gemini:
        logger.info(f"Initializing Gemini with model={settings.llm_model}, api_key={settings.google_api_key}")
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            api_key=settings.google_api_key,
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
async def is_first_message(conversation_id: str) -> bool:
    """Check if this is the first message in a conversation.
    
    Simple check: if any checkpoint exists for this conversation,
    it means we've already had at least one message exchange,
    so this is NOT the first message and we should NOT regenerate the title.
    
    Args:
        conversation_id: The conversation thread ID
        
    Returns:
        True if this is the first message (no checkpoint exists), False otherwise
    """
    try:
        checkpointer = await get_checkpointer()
        config = {"configurable": {"thread_id": conversation_id}}
        
        # Try to get existing checkpoint
        checkpoint = await checkpointer.aget(config)

        if checkpoint is None:
            return True

        # Check if there are any messages
        # Handle both dict and method for checkpoint.values (LangGraph API compatibility)
        values = checkpoint.values() if callable(checkpoint.values) else checkpoint.values
        messages = values.get("messages", []) if isinstance(values, dict) else []
        return len(messages) == 0
        
    except Exception as e:
        logger.warning(f"Error checking if first message: {e}")
        # If we can't determine, assume it's NOT the first (safer - prevents duplicate titles)
        return False

async def generate_conversation_title(user_query: str, assistant_response: str) -> str | None:
    """Generate a title for a conversation based on the first exchange.
    
    Uses ChatGPT-style approach: analyzes both the user's query AND
    the assistant's response to generate a meaningful title.
    The LLM decides if the conversation warrants a custom title or
    should use a default.
    
    Args:
        user_query: The user's first message
        assistant_response: The assistant's first response
        
    Returns:
        A generated title string, or None if generation fails
    """
    try:
        llm = get_llm()
        
        # Truncate long messages to avoid token waste
        query_truncated = user_query[:500] if len(user_query) > 500 else user_query
        response_truncated = assistant_response[:500] if len(assistant_response) > 500 else assistant_response
        
        title_prompt = f"""Generate a short, descriptive title (2-6 words) for this conversation.

The title should capture the main topic or intent.

If the conversation is just a greeting or too vague to summarize meaningfully,

return exactly: New Conversation

User: {query_truncated}

Assistant: {response_truncated}

Rules:

- 2-6 words maximum

- Be specific and descriptive

- Don't use quotes in the title

- Don't start with "Title:" or similar prefixes

- Just output the title, nothing else

Title:"""
        
        # Use invoke for a single quick response (non-streaming for speed)
        response = await llm.ainvoke(title_prompt)
        
        # Extract and clean up the title (handles Gemini's content block format)
        title = _extract_text_content(response.content).strip()
        
        # Remove any leading "Title:" or quotes
        title = re.sub(r'^(title:?\s*)', '', title, flags=re.IGNORECASE)
        title = title.strip('"\'')
        
        # Limit to reasonable length (database field is VARCHAR 255)
        if len(title) > 100:
            title = title[:97] + "..."
        
        # If we got an empty title, use default
        if not title:
            return "New Conversation"
        
        return title
        
    except Exception as e:
        logger.error(f"Error generating conversation title: {e}")
        return "New Conversation"


async def get_checkpointer():
    """Get the checkpointer for conversation persistence.
    
    Uses PostgreSQL if DATABASE_URL_ALLY is configured, otherwise falls back
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
    if settings.DATABASE_URL_ALLY:
        try:
            logger.info("Connecting to PostgreSQL for conversation persistence...")
            # Create the async context manager
            _checkpointer_context = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL_ALLY)
            # Enter the context to get the actual checkpointer
            _checkpointer = await _checkpointer_context.__aenter__()
            # Setup the checkpointer tables
            await _checkpointer.setup()
            logger.info("PostgreSQL checkpointer ready")
            return _checkpointer
        except Exception as e:
            logger.error(f"PostgreSQL checkpointer failed: {e}")
            logger.warning("Falling back to in-memory storage")
            _checkpointer_context = None
    else:
        logger.warning("DATABASE_URL_ALLY not configured - using in-memory storage")
    # Fallback to in-memory checkpointer
    if _memory_saver is None:
        _memory_saver = MemorySaver()
        logger.warning("Using in-memory checkpointer (history won't persist)")
    
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


def create_agent_for_context(
    context: ToolContext,
    checkpointer=None,
    is_new_conversation: bool = True,
):
    """Create a ReAct agent with tools configured for the given context.

    Args:
        context: Tool context with auth and workspace info
        checkpointer: Optional checkpointer for conversation memory
        is_new_conversation: Whether this is the first message (for greeting behavior)

    Returns:
        Compiled LangGraph agent
    """
    llm = get_llm()
    tools = get_all_tools(context)

    # Build dynamic system prompt with user context, workspace and group instructions
    system_prompt = get_system_prompt(
        user_first_name=context.user_first_name,
        is_new_conversation=is_new_conversation,
        workspace_instructions=context.workspace_instructions,
        group_instructions=context.group_instructions,
    )

    # Log personalization info
    user_name = context.user_first_name or "Unknown"
    conv_type = "new" if is_new_conversation else "continuing"
    instructions_info = []
    if context.workspace_instructions:
        instructions_info.append(f"workspace ({len(context.workspace_instructions)} chars)")
    if context.group_instructions:
        instructions_info.append(f"group ({len(context.group_instructions)} chars)")
    if instructions_info:
        logger.info(f"🤖 Creating agent for {user_name} ({conv_type} conversation) WITH {', '.join(instructions_info)} instructions")
    else:
        logger.info(f"🤖 Creating agent for {user_name} ({conv_type} conversation) WITHOUT custom instructions")

    # Create the agent using the prebuilt ReAct pattern
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer,
    )

    return agent


async def create_agent(context: ToolContext, is_new_conversation: bool = True):
    """Create a compiled agent with checkpointer.
    
    Args:
        context: Tool context with auth and workspace info
        is_new_conversation: Whether this is the first message (for greeting behavior)
        
    Returns:
        Compiled LangGraph agent with checkpointer
    """
    checkpointer = await get_checkpointer()
    return create_agent_for_context(context, checkpointer, is_new_conversation)


async def get_agent(context: ToolContext, is_new_conversation: bool = True):
    """Create an agent for the given context.
    Note: We don't cache agents because tools are bound to specific
    auth contexts. Each request creates a fresh agent with the correct
    auth token for GraphQL calls.
    Args:
        context: Tool context with auth and workspace info
        is_new_conversation: Whether this is the first message (for greeting behavior)
    Returns:
        Compiled LangGraph agent
    """
    return await create_agent(context, is_new_conversation)


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


def _get_result_summary(result: str) -> str:
    """Extract a human-readable summary from tool result.
    Args:
        result: The tool result string
    Returns:
        A short summary like "0 results", "1 match", "success", etc.
    """
    if not result:
        return "empty"
    result_lower = result.lower()
    # Check for "not found" patterns
    if "could not find" in result_lower or "no matches" in result_lower:
        return "0 results"
    # Check for count patterns like "Found 5 companies" or "3 results"
    count_match = re.search(r'found\s+(\d+)', result_lower)
    if count_match:
        count = int(count_match.group(1))
        return f"{count} result{'s' if count != 1 else ''}"
    # Check for "Showing X of Y" pattern
    showing_match = re.search(r'showing\s+(\d+)\s+of\s+(\d+)', result_lower)
    if showing_match:
        showing, total = showing_match.groups()
        return f"{showing}/{total} results"
    # Check for success patterns
    if any(word in result_lower for word in ["success", "created", "added", "updated", "removed"]):
        return "success"
    # Check for error patterns
    if "error" in result_lower or "failed" in result_lower:
        return "error"
    # Default: return truncated result
    return result[:30] + "..." if len(result) > 30 else result


async def stream_agent(
    context: ToolContext,
    message: str,
    conversation_id: str,
):
    """Stream agent response for a message.
    This generator yields events as the agent processes the request,
    including thinking steps, tool calls, and the final response.
    When a tool requests user confirmation via interrupt(), this function
    yields a confirmation_required event and stops. The caller should then
    use resume_agent() to continue execution after user responds.
    Args:
        context: Tool context with auth and workspace info
        message: User message
        conversation_id: Conversation thread ID
    Yields:
        Event dictionaries with type and data
    """
    # Check if this is a new conversation (for greeting behavior)
    is_new = await is_first_message(conversation_id)
    
    # Create agent with appropriate greeting behavior
    agent = await get_agent(context, is_new_conversation=is_new)
    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }
    # Track tool calls for summary logging
    tool_calls_summary = []

    # Heartbeat configuration
    last_heartbeat_time = time.time()
    heartbeat_interval = 1.5  # seconds
    has_seen_tool_result = False

    try:
        # Stream using updates mode to get step-by-step progress
        async for chunk in agent.astream(
            {
                "messages": [{"role": "user", "content": message}],
            },
            config=config,
            stream_mode="updates",
        ):
            # Check for heartbeat
            current_time = time.time()
            if current_time - last_heartbeat_time > heartbeat_interval:
                status = "Analyzing results..." if has_seen_tool_result else "Thinking..."
                yield {
                    "type": "thinking",
                    "data": {"status": status},
                }
                last_heartbeat_time = current_time

            # Check for interrupt FIRST (confirmation request from tools)
            if "__interrupt__" in chunk:
                # ... interrupt handling ...
                interrupt_info = chunk["__interrupt__"]
                if interrupt_info and len(interrupt_info) > 0:
                    interrupt_data = interrupt_info[0].value if hasattr(interrupt_info[0], 'value') else interrupt_info[0]
                    logger.info(f"⏸️  CONFIRMATION REQUIRED: {interrupt_data.get('title', 'Unknown')}")
                    yield {
                        "type": "confirmation_required",
                        "data": interrupt_data,
                    }
                    return
            
            # Process each update chunk
            for node_name, node_output in chunk.items():
                if node_name == "__interrupt__":
                    continue
                if node_name == "agent":
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            # Agent decided to call tools
                            # Reset status flag when new tool calls are made
                            has_seen_tool_result = False
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get("name")
                                logger.info(f"   🔧 TOOL CALL: {tool_name}")
                                yield {
                                    "type": "tool_call",
                                    "data": {
                                        "name": tool_name,
                                        "args": tool_call.get("args", {}),
                                    },
                                }
                        elif hasattr(msg, "content") and msg.content:
                            # Reset status flag when content arrives
                            has_seen_tool_result = False
                            text_content = _extract_text_content(msg.content)
                            if text_content:
                                content_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                                logger.info(f"   💬 RESPONSE: {content_preview}")
                                yield {
                                    "type": "response",
                                    "data": {"content": text_content},
                                }
                elif node_name == "tools":
                    # Tool execution results
                    # Mark that we have seen tool results
                    has_seen_tool_result = True
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "content"):
                            tool_content = _extract_text_content(msg.content)
                            cleaned_result, change_data = parse_data_change(tool_content)
                            tool_name = getattr(msg, "name", "unknown")
                            result_info = _get_result_summary(cleaned_result)
                            tool_calls_summary.append(f"{tool_name} → {result_info}")
                            logger.info(f"   ✅ TOOL RESULT: {tool_name} → {result_info}")
                            yield {
                                "type": "tool_result",
                                "data": {
                                    "name": tool_name,
                                    "result": cleaned_result,
                                },
                            }
                            if change_data:
                                yield {
                                    "type": "data_changed",
                                    "data": change_data,
                                }
        # Signal completion
        yield {"type": "done", "data": {}}
        
    except Exception as e:
        logger.error(f"Error in stream_agent: {e}")
        yield {"type": "error", "data": {"message": str(e)}}
        yield {"type": "done", "data": {}}


async def resume_agent(
    context: ToolContext,
    conversation_id: str,
    confirmation_response: dict,
):
    """Resume agent execution after user confirmation.
    This function continues the agent from where it was interrupted,
    passing the user's confirmation response to the tool that requested it.
    Args:
        context: Tool context with auth and workspace info
        conversation_id: Conversation thread ID
        confirmation_response: User's response to the confirmation request
            - confirmed: bool - whether user confirmed
            - selected_id: str | None - selected option for SELECT_ONE
            - selected_ids: list[str] | None - selected options for SELECT_MANY
            - feedback: str | None - optional feedback from user
    Yields:
        Event dictionaries with type and data (same as stream_agent)
    """
    # Resume is always a continuing conversation (not new)
    agent = await get_agent(context, is_new_conversation=False)
    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }
    confirmed = confirmation_response.get("confirmed", False)
    logger.info(f"▶️  RESUME: confirmed={confirmed}")

    # Heartbeat configuration
    last_heartbeat_time = time.time()
    heartbeat_interval = 1.5  # seconds
    has_seen_tool_result = False

    try:
        # Get interrupt IDs from the agent's state snapshot
        state_snapshot = await agent.aget_state(config)
        
        # ... (interrupt logic) ...
        pending_interrupts = []
        if state_snapshot and hasattr(state_snapshot, 'tasks'):
            for task in state_snapshot.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    for intr in task.interrupts:
                        if hasattr(intr, 'id') and intr.id:
                            pending_interrupts.append(intr.id)
        
        # Build the resume command
        if len(pending_interrupts) > 1:
            resume_value = {intr_id: confirmation_response for intr_id in pending_interrupts}
        elif len(pending_interrupts) == 1:
            resume_value = {pending_interrupts[0]: confirmation_response}
        else:
            resume_value = confirmation_response
        
        # Resume the agent
        async for chunk in agent.astream(
            Command(resume=resume_value),
            config=config,
            stream_mode="updates",
        ):
            # Check for heartbeat
            current_time = time.time()
            if current_time - last_heartbeat_time > heartbeat_interval:
                status = "Analyzing results..." if has_seen_tool_result else "Thinking..."
                yield {
                    "type": "thinking",
                    "data": {"status": status},
                }
                last_heartbeat_time = current_time

            # Check for another interrupt FIRST (nested confirmation)
            if "__interrupt__" in chunk:
                interrupt_info = chunk["__interrupt__"]
                if interrupt_info and len(interrupt_info) > 0:
                    interrupt_data = interrupt_info[0].value if hasattr(interrupt_info[0], 'value') else interrupt_info[0]
                    logger.info(f"⏸️  CONFIRMATION REQUIRED: {interrupt_data.get('title', 'Unknown')}")
                    yield {
                        "type": "confirmation_required",
                        "data": interrupt_data,
                    }
                    return
            
            # Process chunks
            for node_name, node_output in chunk.items():
                if node_name == "__interrupt__":
                    continue
                if node_name == "agent":
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            has_seen_tool_result = False
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get("name")
                                yield {
                                    "type": "tool_call",
                                    "data": {
                                        "name": tool_name,
                                        "args": tool_call.get("args", {}),
                                    },
                                }
                        elif hasattr(msg, "content") and msg.content:
                            has_seen_tool_result = False
                            text_content = _extract_text_content(msg.content)
                            if text_content:
                                content_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                                logger.info(f"   💬 RESPONSE: {content_preview}")
                                yield {
                                    "type": "response",
                                    "data": {"content": text_content},
                                }
                elif node_name == "tools":
                    has_seen_tool_result = True
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "content"):
                            tool_content = _extract_text_content(msg.content)
                            cleaned_result, _ = parse_data_change(tool_content)
                            tool_name = getattr(msg, "name", "unknown")
                            yield {
                                "type": "tool_result",
                                "data": {
                                    "name": tool_name,
                                    "result": cleaned_result,
                                },
                            }
        # Signal completion
        yield {"type": "done", "data": {}}
        
    except Exception as e:
        logger.error(f"Error resuming agent: {e}")
        yield {"type": "error", "data": {"message": str(e)}}
        yield {"type": "done", "data": {}}
