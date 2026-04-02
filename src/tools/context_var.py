"""Per-request ToolContext injection via contextvars.

This allows tools to be created once (at startup) but access the
correct auth context for each request. The context is set before
agent invocation and read by tools at call-time.

contextvars is async-safe — each asyncio task gets its own copy,
so concurrent requests won't interfere with each other.
"""

import contextvars
from src.tools.base import ToolContext

_current_context: contextvars.ContextVar[ToolContext] = contextvars.ContextVar(
    "tool_context"
)


def set_tool_context(ctx: ToolContext) -> None:
    """Set the ToolContext for the current async task / request."""
    _current_context.set(ctx)


def get_tool_context() -> ToolContext:
    """Get the ToolContext for the current async task / request.

    Raises LookupError if called before set_tool_context().
    """
    return _current_context.get()
