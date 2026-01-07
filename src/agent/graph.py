"""LangGraph ReAct agent implementation."""

import logging
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt

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
openai_api_key="REDACTED"
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
    activeURL: str | None = None,
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
        activeURL: Current active URL from frontend

    Yields:
        Event dictionaries with type and data
    """
    agent = await get_agent(context)

    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }

    # Track tool calls for summary logging
    tool_calls_summary = []

    # DIRECT INTERCEPTION: Handle location questions immediately if we have activeURL
    message_lower = message.lower().strip()
    is_location_question = any(
        phrase in message_lower
        for phrase in ["where am i", "what page", "current page", "what page am i", "where are we", "what page is this"]
    )
    
    if is_location_question and activeURL:
        # Extract group ID from URL
        url_parts = activeURL.split('/')
        group_id = None
        view_type = None
        view_id = None
        
        if '/apps/groups/' in activeURL:
            try:
                groups_idx = url_parts.index('groups')
                if len(url_parts) > groups_idx + 1:
                    group_id = url_parts[groups_idx + 1]
                if len(url_parts) > groups_idx + 3:
                    view_type = url_parts[groups_idx + 2]  # 'pipeline' or 'table'
                    view_id = url_parts[groups_idx + 3]
            except (ValueError, IndexError):
                pass
        
        # Try to fetch group name if we have a group ID
        group_name = None
        view_name = None
        if group_id:
            try:
                client = context.get_client()
                
                # Fetch group details
                query = """
                query GetGroups($workspaceId: String!) {
                    getGroups(workspaceId: $workspaceId) {
                        id
                        name
                        emoji
                        views {
                            id
                            name
                            type
                        }
                    }
                }
                """
                result = await client.query(query, {"workspaceId": context.workspace_id})
                groups = result.get("getGroups", [])
                group = next((g for g in groups if g.get("id") == group_id), None)
                
                if group:
                    emoji = group.get("emoji", "")
                    group_name = f"{emoji} {group.get('name', 'Unknown')}".strip()
                    
                    # If we have a view ID, try to find the view name
                    if view_id and view_type:
                        views = group.get("views", [])
                        view = next((v for v in views if v.get("id") == view_id), None)
                        if view:
                            view_name = view.get("name", view_type)
                
                await client.close()
            except Exception as e:
                logger.warning(f"Error fetching group name for location question: {e}")
                # Fall through to generic response
        
        # Build response with group name if available
        if group_name:
            if view_name and view_type:
                response_text = f"You are on the **{group_name}** group, viewing the **{view_name}** {view_type} view."
            elif view_type:
                response_text = f"You are on the **{group_name}** group, viewing a {view_type} view."
            else:
                response_text = f"You are on the **{group_name}** group."
        else:
            # Fallback to URL if we couldn't fetch group name
            response_text = f"You are on `{activeURL}`"
        
        yield {
            "type": "response",
            "data": {
                "content": response_text,
            },
        }
        yield {"type": "done", "data": {}}
        return  # Exit early, don't process through LLM

    # Prepare messages with activeURL context
    messages_with_context = []
    
    # Check if this is a new conversation and fetch user's first name
    user_first_name = None
    is_new_chat = False
    try:
        # Check if conversation is new by checking checkpointer state
        checkpointer = await get_checkpointer()
        config = {"configurable": {"thread_id": conversation_id}}
        state = await checkpointer.aget(config)
        
        # If no state or no messages, it's new
        if not state or not state.values.get("messages"):
            is_new_chat = True
        else:
            messages = state.values.get("messages", [])
            user_or_assistant_messages = [
                msg for msg in messages
                if hasattr(msg, "type") and msg.type in ["human", "ai", "user", "assistant"]
            ]
            # If no user/assistant messages yet, it's new
            is_new_chat = len(user_or_assistant_messages) == 0
        
        if is_new_chat:
            # Fetch user's first name for new chats
            client = context.get_client()
            try:
                user_first_name = await client.get_current_user_first_name()
                if user_first_name:
                    logger.info(f"👤 [USER CONTEXT] New chat detected, user's first name: {user_first_name}")
            except Exception as e:
                logger.warning(f"Failed to fetch user's first name: {e}")
            finally:
                await client.close()
    except Exception as e:
        logger.warning(f"Error checking if conversation is new: {e}")
    
    # Add system message with user context for new chats - MUST BE FIRST
    if is_new_chat and user_first_name:
        user_context_message = f"""🚨 CRITICAL: NEW CHAT - USER GREETING REQUIRED 🚨

**THIS IS A BRAND NEW CONVERSATION - NO PREVIOUS MESSAGES**

The user's first name is: **{user_first_name}**

**MANDATORY INSTRUCTION - YOU MUST FOLLOW THIS:**
Your FIRST response MUST start with a warm, natural greeting that includes the user's first name "{user_first_name}".

**GREETING STYLE - CHOOSE NATURALLY:**
You can use any of these greeting styles naturally (don't force one):
- "Hey, {user_first_name}!"
- "Hi {user_first_name}!"
- "Hello {user_first_name}!"
- "Hey {user_first_name}!"
- Or any other natural variation that feels appropriate

**IMPORTANT:**
- Choose the greeting style that feels most natural for the conversation
- Match the user's tone if they started with a greeting (e.g., if they said "hey", you can say "Hey, {user_first_name}!")
- Make it feel warm and personal, not robotic or forced
- After the greeting, immediately proceed to help with their request

**EXAMPLES:**
- User says: "hey i want to see the leads records"
- You could respond: "Hey, {user_first_name}! Here are your leads records..." (then show data)
- Or: "Hi {user_first_name}! Here are your leads records..." (then show data)

- User says: "show me companies"
- You could respond: "Hello {user_first_name}! Here are the companies..." (then show data)
- Or: "Hey {user_first_name}! Here are the companies..." (then show data)

**DO NOT:**
- Skip the greeting with their name
- Start with just "Here are..." without greeting
- Forget to use their name in the first response
- Use the exact same greeting every time - vary it naturally

This is ONLY for NEW chats. After this first message, you can use their name naturally but don't need to greet every time."""
        
        # Insert at the beginning - this is critical
        messages_with_context.insert(0, {
            "role": "system",
            "content": user_context_message
        })
        logger.info(f"✅ [USER CONTEXT] Added greeting instruction for new chat with user: {user_first_name}")
    elif is_new_chat:
        # New chat but couldn't fetch name - still be friendly
        messages_with_context.insert(0, {
            "role": "system",
            "content": "🚨 CRITICAL: This is a NEW conversation with no previous messages. You MUST greet the user warmly in your first response. Be friendly, conversational, and helpful."
        })
    
    # Add system message with activeURL context if available
    if activeURL:
        # Parse URL to extract useful information
        url_parts = activeURL.split('/')
        group_id = None
        view_id = None
        view_type = None
        
        # Try to extract groupId and viewId from URL pattern: /apps/groups/{groupId}/pipeline|table/{viewId}
        if '/apps/groups/' in activeURL:
            try:
                groups_idx = url_parts.index('groups')
                if len(url_parts) > groups_idx + 1:
                    group_id = url_parts[groups_idx + 1]
                if len(url_parts) > groups_idx + 3:
                    view_type = url_parts[groups_idx + 2]  # 'pipeline' or 'table'
                    view_id = url_parts[groups_idx + 3]
            except (ValueError, IndexError):
                pass
        
        context_message = f"""🚨 CRITICAL: ACTIVE URL CONTEXT 🚨

The user is currently viewing this page: {activeURL}

**YOU MUST USE THIS URL TO ANSWER LOCATION QUESTIONS**

When the user asks:
- "what page am I on?"
- "where am I?"
- "which page am I on?"
- "what page are we on?"

**YOU MUST RESPOND WITH THE ACTIVE URL ABOVE: {activeURL}**

**URL Breakdown:**
- Full URL: {activeURL}
{f"- Group ID: {group_id}" if group_id else ""}
{f"- View Type: {view_type}" if view_type else ""}
{f"- View ID: {view_id}" if view_id else ""}

**How to Use This Context:**
1. **For location questions**: Directly tell the user they are on: {activeURL}
2. **For "this group" references**: If user says "this group", "current group", "here", use the groupId from URL ({group_id if group_id else "N/A"})
3. **For named group references**: If user mentions a group BY NAME (e.g., "leads", "sales"), you MUST use `resolve_group_name()` first - DO NOT use the URL groupId
4. **For context-aware actions**: Extract groupId/viewId from the URL to understand the user's context

**CRITICAL RULE**: 
- User says "this group" → Use groupId from URL: {group_id if group_id else "N/A"}
- User says "leads group" or "show data on leads" → MUST call `resolve_group_name("leads")` first, ignore URL groupId
- NEVER use placeholder IDs like "abc-123" - always resolve names to real IDs

**IMPORTANT**: If the user asks about their location or current page, you MUST use the activeURL provided above. Do NOT say "I don't know" or "I can't see your screen" - you have the URL context!"""
        
        # logger.info(f"📝 [AGENT] Adding system message with activeURL context: {activeURL}")
        messages_with_context.append({
            "role": "system",
            "content": context_message
        })
    # Add user message
    messages_with_context.append({"role": "user", "content": message})

    # Build initial state with all required fields
    initial_state = {
        "messages": messages_with_context,
        "workspace_id": context.workspace_id,
        "user_id": context.user_id,
        "auth_token": context.auth_token,
        "activeURL": activeURL,
    }

    try:
        # Stream using updates mode to get step-by-step progress
        async for chunk in agent.astream(
            initial_state,
            config=config,
            stream_mode="updates",
        ):
            
            # Check for interrupt FIRST (confirmation request from tools)
            if "__interrupt__" in chunk:
                interrupt_info = chunk["__interrupt__"]
                if interrupt_info and len(interrupt_info) > 0:
                    interrupt_data = interrupt_info[0].value if hasattr(interrupt_info[0], 'value') else interrupt_info[0]
                    yield {
                        "type": "confirmation_required",
                        "data": interrupt_data,
                    }
                    return  # Stop streaming, wait for user response

            # Process each update chunk
            for node_name, node_output in chunk.items():
                if node_name == "__interrupt__":
                    continue  # Already handled above

                if node_name == "agent":
                    # This is the LLM response
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            # Agent decided to call tools
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
                            # Agent response - truncate for logging
                            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            logger.info(f"   💬 RESPONSE: {content_preview}")
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
                            tool_name = getattr(msg, "name", "unknown")

                            # Calculate result count/size for logging
                            result_info = _get_result_summary(cleaned_result)
                            tool_calls_summary.append(f"{tool_name} → {result_info}")
                            logger.info(f"   ✅ TOOL RESULT: {tool_name} → {result_info}")

                            # Yield the tool result (with cleaned content)
                            yield {
                                "type": "tool_result",
                                "data": {
                                    "name": tool_name,
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
    agent = await get_agent(context)

    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }

    confirmed = confirmation_response.get("confirmed", False)
    logger.info(f"▶️  RESUME: confirmed={confirmed}")

    try:
        # Resume the agent by invoking with a Command that provides the interrupt response
        # The response will be passed to the tool that called interrupt()
        async for chunk in agent.astream(
            Command(resume=confirmation_response),
            config=config,
            stream_mode="updates",
        ):
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
                    return  # Stop streaming, wait for user response

            # Process each update chunk (same logic as stream_agent)
            for node_name, node_output in chunk.items():
                if node_name == "__interrupt__":
                    continue  # Already handled above

                if node_name == "agent":
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
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
                            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            logger.info(f"   💬 RESPONSE: {content_preview}")
                            yield {
                                "type": "response",
                                "data": {"content": msg.content},
                            }
                elif node_name == "tools":
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "content"):
                            cleaned_result, change_data = parse_data_change(msg.content)
                            tool_name = getattr(msg, "name", "unknown")
                            result_info = _get_result_summary(cleaned_result)
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
        logger.error(f"Error resuming agent: {e}")
        yield {"type": "error", "data": {"message": str(e)}}
        yield {"type": "done", "data": {}}

