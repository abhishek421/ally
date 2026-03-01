import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt

from src.config import get_settings
from src.agent.prompts import get_system_prompt, get_system_prompt_messages
from src.tools import get_all_tools, get_tools_for_categories
from src.tools.base import ToolContext, parse_data_change
from src.tools.context_var import set_tool_context
from src.agent.intent import classify_intent

logger = logging.getLogger(__name__)

def get_context_window(model_name: str) -> int:
    """Get the context window limit for a given model name."""
    settings = get_settings()
    windows = settings.model_context_windows
    
    if model_name in windows:
        return windows[model_name]
    
    for key, value in windows.items():
        if model_name.startswith(key):
            return value
            
    return settings.default_context_window


def compute_budget_status(total_tokens: int, model_name: str) -> dict:
    """Compute the budget status for a conversation.
    
    Returns a dict with model, limit, used, remaining, percentage_used,
    and status ("ok" | "warning" | "blocked").
    """
    settings = get_settings()
    limit = get_context_window(model_name)
    remaining = max(0, limit - total_tokens)
    percentage_used = min(100.0, (total_tokens / limit) * 100) if limit > 0 else 0
    
    warning_pct = settings.context_warning_threshold * 100   # 70
    limit_pct = settings.context_limit_threshold * 100       # 80
    
    if percentage_used >= limit_pct:
        status = "blocked"
    elif percentage_used >= warning_pct:
        status = "warning"
    else:
        status = "ok"
    
    return {
        "model": model_name,
        "limit": limit,
        "used": total_tokens,
        "remaining": remaining,
        "percentage_used": round(percentage_used, 2),
        "status": status,
    }


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

# Cached LLM singleton
_cached_llm = None

# Cached compiled agent (graph compiled once, reused for all requests)
_cached_agent = None


def get_llm():
    """Get the configured LLM instance (cached singleton).
    Returns:
        ChatOpenAI, ChatAnthropic, or ChatGoogleGenerativeAI instance based on configuration
    """
    global _cached_llm
    if _cached_llm is not None:
        return _cached_llm

    settings = get_settings()
    if settings.is_openai:
        _cached_llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            streaming=True,
        )
    elif settings.is_gemini:
        logger.info(f"Initializing Gemini with model={settings.llm_model}")
        _cached_llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            api_key=settings.google_api_key,
            temperature=0.7,
            streaming=True,
        )
    else:
        _cached_llm = ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=0.7,
            streaming=True,
        )

    logger.info(f"🤖 LLM initialized: {settings.llm_model} (cached)")
    return _cached_llm
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

async def generate_conversation_title(user_query: str, assistant_response: str) -> tuple[str | None, dict | None]:
    """Generate a title for a conversation based on the first exchange.
    
    Uses ChatGPT-style approach: analyzes both the user's query AND
    the assistant's response to generate a meaningful title.
    The LLM decides if the conversation warrants a custom title or
    should use a default.
    
    Args:
        user_query: The user's first message
        assistant_response: The assistant's first response
        
    Returns:
        Tuple of (title string, token usage dict or None)
    """
    title_token_usage = None
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
        
        # Extract token usage from title generation
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            title_token_usage = {
                "input_tokens": response.usage_metadata.get("input_tokens", 0),
                "output_tokens": response.usage_metadata.get("output_tokens", 0),
                "total_tokens": response.usage_metadata.get("total_tokens", 0),
            }
        
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
            return "New Conversation", title_token_usage
        
        # Log title generation telemetry
        if title_token_usage:
            telemetry = {
                "event": "token_usage",
                "request_type": "title_generation",
                "model": getattr(llm, "model_name", "unknown"),
                "tokens": title_token_usage
            }
            logger.info(f"📊 TELEMETRY: {json.dumps(telemetry)}")
        

        return title, title_token_usage
        
    except Exception as e:
        logger.error(f"Error generating conversation title: {e}")
        return "New Conversation", title_token_usage


async def get_conversation_usage(conversation_id: str) -> dict:
    """Fetch history and calculate cumulative token usage from metadata.
    
    Args:
        conversation_id: The thread ID to check
        
    Returns:
        Dict with input_tokens, output_tokens, total_tokens
    """
    try:
        checkpointer = await get_checkpointer()
        config = {"configurable": {"thread_id": conversation_id}}
        
        # Get the latest state from checkpointer
        state_data = await checkpointer.aget(config)
        if not state_data:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            
        # LangGraph savers return a CheckpointTuple; the checkpoint is in the 'checkpoint' key/attr
        checkpoint = state_data.get("checkpoint") if isinstance(state_data, dict) else getattr(state_data, "checkpoint", state_data)
        
        # messages are usually in channel_values
        channel_values = checkpoint.get("channel_values") if isinstance(checkpoint, dict) else getattr(checkpoint, "channel_values", {})
        messages = channel_values.get("messages", [])
        
        total_input = 0
        total_output = 0
        
        for msg in messages:
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                total_input += msg.usage_metadata.get("input_tokens", 0)
                total_output += msg.usage_metadata.get("output_tokens", 0)
        
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output
        }
    except Exception as e:
        logger.warning(f"Error calculating conversation usage: {e}")
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}



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

    Uses a cached compiled graph if available. Only the prompt and
    per-request context (via set_tool_context) change between calls.

    Args:
        context: Tool context with auth and workspace info
        checkpointer: Optional checkpointer for conversation memory
        is_new_conversation: Whether this is the first message (for greeting behavior)

    Returns:
        Compiled LangGraph agent
    """
    global _cached_agent

    # Inject per-request context so tools can access auth dynamically
    set_tool_context(context)

    llm = get_llm()

    # Build system prompt as a list of messages for prompt caching.
    # Message 1 = static base prompt (cacheable by LLM providers).
    # Message 2 = dynamic context (user name, workspace/group instructions).
    settings = get_settings()
    system_messages = get_system_prompt_messages(
        user_first_name=context.user_first_name,
        is_new_conversation=is_new_conversation,
        workspace_instructions=context.workspace_instructions,
        group_instructions=context.group_instructions,
        is_anthropic=settings.is_anthropic,
    )

    # Build a prompt callable that prepends system messages to state messages.
    # create_react_agent accepts a Callable[[state], messages] for the prompt param.
    def prompt_fn(state):
        return system_messages + state["messages"]

    # Log personalization info
    user_name = context.user_first_name or "Unknown"
    conv_type = "new" if is_new_conversation else "continuing"
    instructions_info = []
    if context.workspace_instructions:
        instructions_info.append(f"workspace ({len(context.workspace_instructions)} chars)")
    if context.group_instructions:
        instructions_info.append(f"group ({len(context.group_instructions)} chars)")

    if _cached_agent is not None:
        # Reuse the cached agent — only the prompt & context change
        if instructions_info:
            logger.info(f"♻️  Reusing cached agent for {user_name} ({conv_type}) WITH {', '.join(instructions_info)} instructions")
        else:
            logger.info(f"♻️  Reusing cached agent for {user_name} ({conv_type}) WITHOUT custom instructions")

        # Update the prompt on the cached agent
        # Since create_react_agent compiles the graph, we rebuild with updated prompt
        # but reuse the same LLM and tools (the expensive parts)
        pass  # The agent is rebuilt below with cached LLM + tools

    # Build tools once (they use get_tool_context() internally)
    tools = get_all_tools()

    # Create the agent using the prebuilt ReAct pattern
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt_fn,
        checkpointer=checkpointer,
    )

    if _cached_agent is None:
        logger.info(f"🤖 Agent compiled for first time [prompt caching ON]")

    _cached_agent = agent
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
    """Get an agent for the given context.

    Injects per-request auth context via set_tool_context() so that
    tools can access the correct auth token, workspace ID, etc.

    Args:
        context: Tool context with auth and workspace info
        is_new_conversation: Whether this is the first message (for greeting behavior)

    Returns:
        Compiled LangGraph agent
    """
    set_tool_context(context)
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
    
    # Classify intent and load only relevant tools
    categories = classify_intent(message)
    logger.info(
        f"🎯 Intent: {[c.value for c in categories]}"
    )

    # Create agent (reuses cached graph + LLM, injects fresh context)
    agent = await get_agent(context, is_new_conversation=is_new)
    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }
    # Track tool calls for summary logging
    tool_calls_summary = []

    # Token usage tracking
    request_token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    llm_call_count = 0

    # Heartbeat configuration
    last_heartbeat_time = time.time()
    heartbeat_interval = 1.5  # seconds
    has_seen_tool_result = False

    # PRE-REQUEST BUDGET CHECK
    settings = get_settings()
    history_usage = await get_conversation_usage(conversation_id)
    pre_check = compute_budget_status(history_usage["total_tokens"], settings.llm_model)
    
    if pre_check["status"] == "blocked":
        logger.warning(
            f"🚫 BUDGET EXCEEDED for conversation {conversation_id}: "
            f"{pre_check['percentage_used']}% used ({pre_check['used']}/{pre_check['limit']} tokens)"
        )
        yield {
            "type": "context_window_status",
            "data": pre_check,
        }
        yield {
            "type": "error",
            "data": {
                "message": "This conversation has reached its context limit. Please start a new conversation for best results."
            },
        }
        yield {"type": "done", "data": {}}
        return

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
                        # Extract token usage from AIMessage
                        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                            usage = msg.usage_metadata
                            request_token_usage["input_tokens"] += usage.get("input_tokens", 0)
                            request_token_usage["output_tokens"] += usage.get("output_tokens", 0)
                            request_token_usage["total_tokens"] += usage.get("total_tokens", 0)
                            llm_call_count += 1

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
        # Signal completion FIRST so the frontend unlocks the input immediately.
        # Metadata events (token_usage, context_window_status) follow as
        # non-blocking tail events that the frontend processes independently.
        done_time = time.time()
        logger.info(f"✅ DONE event emitted — UI unlocked")
        yield {"type": "done", "data": {}}

        # Emit token usage summary and telemetry (after done — no user-perceived delay)
        if llm_call_count > 0:
            logger.info(
                f"📊 TOKEN USAGE: {request_token_usage['input_tokens']} input "
                f"+ {request_token_usage['output_tokens']} output "
                f"= {request_token_usage['total_tokens']} total "
                f"({llm_call_count} LLM call{'s' if llm_call_count != 1 else ''})"
            )
            
            # Log structured telemetry
            settings = get_settings()
            telemetry = {
                "event": "token_usage",
                "request_type": "chat",
                "conversation_id": conversation_id,
                "model": settings.llm_model,
                "tokens": request_token_usage,
                "llm_calls": llm_call_count
            }
            logger.info(f"📊 TELEMETRY: {json.dumps(telemetry)}")

            yield {
                "type": "token_usage",
                "data": {
                    **request_token_usage,
                    "llm_calls": llm_call_count,
                },
            }

            # Emit Context Window Status
            post_history = await get_conversation_usage(conversation_id)
            cumulative_total = post_history["total_tokens"] + request_token_usage["total_tokens"]
            budget_status = compute_budget_status(cumulative_total, settings.llm_model)
            
            yield {
                "type": "context_window_status",
                "data": budget_status,
            }
            post_done_ms = (time.time() - done_time) * 1000
            logger.info(f"📊 Post-done metadata completed in {post_done_ms:.0f}ms (invisible to user)")
        
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

    # Token usage tracking
    request_token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    llm_call_count = 0

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
                        # Extract token usage from AIMessage
                        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                            usage = msg.usage_metadata
                            request_token_usage["input_tokens"] += usage.get("input_tokens", 0)
                            request_token_usage["output_tokens"] += usage.get("output_tokens", 0)
                            request_token_usage["total_tokens"] += usage.get("total_tokens", 0)
                            llm_call_count += 1

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
        # Signal completion FIRST so the frontend unlocks the input immediately.
        done_time = time.time()
        logger.info(f"✅ DONE event emitted — UI unlocked")
        yield {"type": "done", "data": {}}

        # Emit token usage summary and telemetry (after done — no user-perceived delay)
        if llm_call_count > 0:
            logger.info(
                f"📊 TOKEN USAGE: {request_token_usage['input_tokens']} input "
                f"+ {request_token_usage['output_tokens']} output "
                f"= {request_token_usage['total_tokens']} total "
                f"({llm_call_count} LLM call{'s' if llm_call_count != 1 else ''})"
            )
            
            # Log structured telemetry
            settings = get_settings()
            telemetry = {
                "event": "token_usage",
                "request_type": "chat_resume",
                "conversation_id": conversation_id,
                "model": settings.llm_model,
                "tokens": request_token_usage,
                "llm_calls": llm_call_count
            }
            logger.info(f"📊 TELEMETRY: {json.dumps(telemetry)}")

            yield {
                "type": "token_usage",
                "data": {
                    **request_token_usage,
                    "llm_calls": llm_call_count,
                },
            }

            # Emit Context Window Status
            post_history = await get_conversation_usage(conversation_id)
            cumulative_total = post_history["total_tokens"] + request_token_usage["total_tokens"]
            budget_status = compute_budget_status(cumulative_total, settings.llm_model)
            
            yield {
                "type": "context_window_status",
                "data": budget_status,
            }
            post_done_ms = (time.time() - done_time) * 1000
            logger.info(f"📊 Post-done metadata completed in {post_done_ms:.0f}ms (invisible to user)")
        
    except Exception as e:
        logger.error(f"Error resuming agent: {e}")
        yield {"type": "error", "data": {"message": str(e)}}
        yield {"type": "done", "data": {}}
