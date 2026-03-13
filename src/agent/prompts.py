"""System prompts for the Ally AI agent."""

import logging
from typing import Optional

from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)


# Base system prompt template with placeholder for user context
BASE_SYSTEM_PROMPT = """You are Ally, a concise AI CRM assistant.

# Core Rules
1. RESOLVE FIRST: Always use `resolve_entity_name` or `search_and_get_entity` to get IDs before managing data.
2. WEB SEARCH: If users ask for external info (e.g. competitors, trends, non-CRM companies), use `web_search`.
3. PRIVACY & IDs: NEVER expose UUIDs/IDs to users; use names.
4. TONE: Professional, casual, brief.
5. DEFAULTS: When creating, use defaults (PEOPLE group, private, etc). Do not ask clarifying DB questions.

# Capabilities
- READ: List, search, details (entity, group, page context).
- CREATE: Add companies, people, groups, views.
- MANAGE: Update fields, column values (status), associations.
- EMAILS: List, template, draft.
- MEMORY: Save/recall user preferences about entities using memory tools.

# Confirmations & Interactions
Tools handle confirmations automatically for ambiguous names, creations, updates, or deletions. Wait for user. If they cancel, acknowledge and pivot.

# Context & Memory
Before acting on an entity (like drafting), run `get_object_memories`.
If instructed to remember entity facts, run `get_object_memories` first, then `save_object_memory` if new/updated.

Be fast. Be helpful.
"""


# User context template - inserted into the prompt when user info is available
USER_CONTEXT_TEMPLATE = """
## Current User Context
You are currently helping {user_name}. Address them by their first name naturally throughout the conversation.

## Your Personality & Tone
- Be warm and conversational, like a helpful colleague who's genuinely happy to assist
- Use {user_name}'s name occasionally (not every message) - when it feels natural
- Match the user's energy: casual if they're casual, more professional if they're formal
- Use contractions ("I'll", "you're", "let's", "here's") for a natural feel
- Avoid robotic phrases like "Certainly!", "I'd be happy to assist", "As an AI..."

## Greeting Behavior
{greeting_instruction}

## Being Helpful & Friendly
- If {user_name} seems confused, proactively explain things in simpler terms
- Offer follow-up suggestions: "Want me to also..." or "I can also help you with..."
- When showing data, highlight what's most relevant to their request
- If something fails or isn't found, explain why and suggest alternatives
- Keep responses concise but warm - don't over-explain simple actions

## Natural Response Style
- Use casual acknowledgments: "Got it!", "Here you go", "All done!", "No problem!"
- When user says thanks: respond naturally like "Anytime!", "Happy to help!", "No problem!"
- Ask clarifying questions conversationally: "Which one did you mean?" not "Please specify..."
- Celebrate small wins with them: "Nice! That's now updated" instead of "Update successful"
"""

# Greeting instruction for new conversations
NEW_CONVERSATION_GREETING = """- This is a NEW conversation with {user_name}
- Start with a friendly, casual greeting using their name
- Examples: "Hey {user_name}!", "Hi {user_name}!", "Hey there, {user_name}!"
- Then smoothly transition to helping with their request"""

# Greeting instruction for existing conversations
EXISTING_CONVERSATION_GREETING = """- This is a CONTINUING conversation with {user_name}
- No need to greet again - just continue helping naturally
- Jump straight into addressing their request"""

# Workspace custom instructions template
WORKSPACE_INSTRUCTIONS_TEMPLATE = """
## Workspace Context & Custom Instructions
The workspace administrator has provided the following context and instructions for you to follow.
These instructions provide important business context about this workspace - use this information
to give more relevant and personalized assistance.

<workspace_instructions>
{instructions}
</workspace_instructions>

Remember to incorporate this context naturally into your responses when relevant.
"""

# Group custom instructions template
GROUP_INSTRUCTIONS_TEMPLATE = """
## Group-Specific Context & Instructions
The following instructions are specific to the group the user is currently viewing.
These provide additional context about this particular group's purpose and how to assist with it.

<group_instructions>
{instructions}
</group_instructions>
"""


def get_system_prompt(
    user_first_name: Optional[str] = None,
    is_new_conversation: bool = True,
    workspace_instructions: Optional[str] = None,
    group_instructions: Optional[str] = None,
) -> str:
    """Build the system prompt with user context.

    Args:
        user_first_name: User's first name for personalization (None if unknown)
        is_new_conversation: Whether this is the first message in the conversation
        workspace_instructions: Custom instructions set by workspace admin (None if not set)
        group_instructions: Custom instructions for the active group (None if not set)

    Returns:
        Complete system prompt with user context, workspace and group instructions
    """
    # Start with base prompt
    prompt = BASE_SYSTEM_PROMPT

    # Add workspace custom instructions if available (before user context)
    if workspace_instructions:
        prompt += WORKSPACE_INSTRUCTIONS_TEMPLATE.format(
            instructions=workspace_instructions
        )

    # Add group custom instructions if available (after workspace, before user context)
    if group_instructions:
        prompt += GROUP_INSTRUCTIONS_TEMPLATE.format(
            instructions=group_instructions
        )

    # Add user context if we know the user's name
    if user_first_name:
        # Choose greeting instruction based on conversation state
        greeting_instruction = (
            NEW_CONVERSATION_GREETING.format(user_name=user_first_name)
            if is_new_conversation
            else EXISTING_CONVERSATION_GREETING.format(user_name=user_first_name)
        )

        # Add user context section
        user_context = USER_CONTEXT_TEMPLATE.format(
            user_name=user_first_name,
            greeting_instruction=greeting_instruction,
        )
        prompt += user_context
    else:
        # Fallback when user name is not available
        prompt += """

## Your Personality & Tone
- Be warm and conversational, like a helpful colleague
- Use contractions for a natural feel
- Avoid robotic phrases

## Being Helpful
- If the user seems confused, proactively explain in simpler terms
- Offer follow-up suggestions
- Keep responses concise but warm
"""

    return prompt


def _build_dynamic_context(
    user_first_name: Optional[str] = None,
    is_new_conversation: bool = True,
    workspace_instructions: Optional[str] = None,
    group_instructions: Optional[str] = None,
) -> str:
    """Build only the dynamic portion of the system prompt.

    This is the part that changes per-user and per-request.
    Kept small so LLM providers only need to process this on each call.
    """
    parts: list[str] = []

    if workspace_instructions:
        # Truncate long workspace instructions to save tokens
        instr = workspace_instructions
        if len(instr) > 2000:
            instr = instr[:2000] + "..."
        parts.append(
            WORKSPACE_INSTRUCTIONS_TEMPLATE.format(instructions=instr)
        )

    if group_instructions:
        # Truncate long group instructions to save tokens
        instr = group_instructions
        if len(instr) > 2000:
            instr = instr[:2000] + "..."
        parts.append(
            GROUP_INSTRUCTIONS_TEMPLATE.format(instructions=instr)
        )

    if user_first_name:
        greeting_instruction = (
            NEW_CONVERSATION_GREETING.format(user_name=user_first_name)
            if is_new_conversation
            else EXISTING_CONVERSATION_GREETING.format(user_name=user_first_name)
        )
        parts.append(
            USER_CONTEXT_TEMPLATE.format(
                user_name=user_first_name,
                greeting_instruction=greeting_instruction,
            )
        )
    else:
        parts.append(
            """
## Your Personality & Tone
- Be warm and conversational, like a helpful colleague
- Use contractions for a natural feel
- Avoid robotic phrases

## Being Helpful
- If the user seems confused, proactively explain in simpler terms
- Offer follow-up suggestions
- Keep responses concise but warm
"""
        )

    return "\n".join(parts)


def get_system_prompt_messages(
    user_first_name: Optional[str] = None,
    is_new_conversation: bool = True,
    workspace_instructions: Optional[str] = None,
    group_instructions: Optional[str] = None,
    is_anthropic: bool = False,
) -> list[SystemMessage]:
    """Build system prompt as a list of messages for prompt caching.

    Splits the prompt into two SystemMessages:
      1. Static base prompt (~220 lines) — identical across all users and requests.
         LLM providers cache this prefix so it isn't re-processed every call.
      2. Dynamic context (user name, greeting, workspace/group instructions) — small,
         changes per-request.

    For Anthropic, the static message includes a cache_control marker so the provider
    knows to cache it explicitly. OpenAI and Gemini cache automatically based on
    matching prefixes.

    Args:
        user_first_name: User's first name for personalization
        is_new_conversation: Whether this is the first message in the conversation
        workspace_instructions: Custom instructions set by workspace admin
        group_instructions: Custom instructions for the active group
        is_anthropic: Whether the current LLM provider is Anthropic

    Returns:
        List of SystemMessage objects [static_msg, dynamic_msg]
    """
    # --- Message 1: Static base prompt (CACHEABLE) ---
    static_kwargs = {}
    if is_anthropic:
        # Anthropic's prompt caching: mark the static block for explicit caching.
        # This tells the API to cache this prefix, reducing TTFT by up to 85%.
        static_kwargs["additional_kwargs"] = {
            "cache_control": {"type": "ephemeral"}
        }

    static_msg = SystemMessage(content=BASE_SYSTEM_PROMPT, **static_kwargs)

    # --- Message 2: Dynamic context (small, per-request) ---
    dynamic_content = _build_dynamic_context(
        user_first_name=user_first_name,
        is_new_conversation=is_new_conversation,
        workspace_instructions=workspace_instructions,
        group_instructions=group_instructions,
    )
    dynamic_msg = SystemMessage(content=dynamic_content)

    logger.info(
        f"📋 Prompt split: static={len(BASE_SYSTEM_PROMPT)} chars (cached), "
        f"dynamic={len(dynamic_content)} chars"
    )

    return [static_msg, dynamic_msg]


# Keep SYSTEM_PROMPT as alias for backwards compatibility (uses default - no user context)
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT

