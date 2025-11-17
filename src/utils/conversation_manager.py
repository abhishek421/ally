"""Conversation manager for context building and summarization."""

from typing import List, Optional

from ..config import get_settings
from .models import Message
from .storage import StorageInterface
from .summarizer import SummarizerInterface
from .tokenizer import TokenizerInterface

settings = get_settings()


class ConversationManager:
    """Manages conversation history, summarization, and context building."""

    def __init__(
        self,
        storage: StorageInterface,
        tokenizer: TokenizerInterface,
        summarizer: SummarizerInterface,
    ):
        """Initialize conversation manager.

        Args:
            storage: Storage interface for conversation data
            tokenizer: Tokenizer for counting tokens
            summarizer: Summarizer for creating summaries
        """
        self.storage = storage
        self.tokenizer = tokenizer
        self.summarizer = summarizer

        # Calculate threshold
        context_limit = settings.llm_context_limit
        threshold_percentage = settings.context_threshold_percentage / 100.0
        self.token_threshold = int(context_limit * threshold_percentage)

    def get_context_for_query(self, conversation_id: str, current_query: str) -> str:
        """Get enriched context for a query.

        Args:
            conversation_id: Unique conversation identifier
            current_query: Current user query

        Returns:
            Enriched query with context
        """
        # Get conversation history (current query should already be saved)
        all_messages = self.storage.get_conversation_history(conversation_id)
        summary_data = self.storage.get_summary(conversation_id)

        # Determine which messages are after summary
        summary_count = summary_data[1] if summary_data else 0
        recent_messages = all_messages[summary_count:] if summary_data else all_messages

        # Check if we need to summarize (including current query in token count)
        # Create a temporary message for current query to count tokens
        from datetime import datetime
        temp_query_message = Message(role="user", content=current_query, timestamp=datetime.now())
        messages_with_query = recent_messages + [temp_query_message] if recent_messages else [temp_query_message]

        if self._should_summarize(messages_with_query, summary_data is not None):
            # Create summary of messages before the most recent ones
            # Keep the last 2-3 messages for context, summarize the rest
            keep_recent_count = 2
            messages_to_summarize = recent_messages[:-keep_recent_count] if len(recent_messages) > keep_recent_count else []
            
            if messages_to_summarize:
                # If we have a previous summary, include it in the summarization
                if summary_data:
                    summary_message = Message(
                        role="system",
                        content=f"Previous conversation summary: {summary_data[0]}",
                        timestamp=recent_messages[0].timestamp if recent_messages else datetime.now(),
                    )
                    messages_to_summarize = [summary_message] + messages_to_summarize

                new_summary = self.summarizer.summarize(messages_to_summarize)
                total_summarized = (summary_data[1] if summary_data else 0) + len(messages_to_summarize)
                
                # Save the new summary
                self.storage.save_summary(conversation_id, new_summary, total_summarized)
                
                # Update recent messages to only include the last few
                recent_messages = recent_messages[-keep_recent_count:] if len(recent_messages) > keep_recent_count else recent_messages
                summary_data = (new_summary, total_summarized)

        # Build context string (current query is already in recent_messages if it was saved)
        # But we want to show it explicitly, so we'll handle it in _build_context_string
        context = self._build_context_string(
            summary=summary_data[0] if summary_data else None,
            recent_messages=recent_messages,
            current_query=current_query,
        )

        return context

    def _should_summarize(self, messages: List[Message], summary_exists: bool) -> bool:
        """Determine if summarization is needed.

        Args:
            messages: List of recent messages
            summary_exists: Whether a summary already exists

        Returns:
            True if summarization is needed
        """
        if not messages:
            return False

        # Count tokens for all messages
        total_tokens = sum(self.tokenizer.count_tokens(msg.content) for msg in messages)

        return total_tokens > self.token_threshold

    def _build_context_string(
        self,
        summary: Optional[str],
        recent_messages: List[Message],
        current_query: str,
    ) -> str:
        """Build the final context string.

        Args:
            summary: Optional summary of older messages
            recent_messages: Recent messages after summary point
            current_query: Current user query

        Returns:
            Enriched query with context
        """
        context_parts = []

        # Add summary if exists
        if summary:
            context_parts.append(f"Previous conversation summary:\n{summary}\n")

        # Add recent messages
        if recent_messages:
            context_parts.append("Recent conversation history:")
            for msg in recent_messages:
                context_parts.append(f"{msg.role}: {msg.content}")

        # Add current query
        context_parts.append(f"\nCurrent query: {current_query}")

        return "\n".join(context_parts)

    def save_user_query(self, conversation_id: str, query: str) -> None:
        """Save user query to conversation history.

        Args:
            conversation_id: Unique conversation identifier
            query: User query text
        """
        from datetime import datetime

        message = Message(role="user", content=query, timestamp=datetime.now())
        self.storage.save_message(conversation_id, message)

    def save_assistant_response(self, conversation_id: str, response: str) -> None:
        """Save assistant response to conversation history.

        Args:
            conversation_id: Unique conversation identifier
            response: Assistant response text
        """
        from datetime import datetime

        message = Message(role="assistant", content=response, timestamp=datetime.now())
        self.storage.save_message(conversation_id, message)

