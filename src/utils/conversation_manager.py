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

        Logic:
        1. If no summarization: Send all previous turns + current query
        2. If threshold hit: Summarize ALL previous messages, send only summary + current query
        3. If summary exists: Send summary + new turns (after summarization) + current query
        4. When threshold hit again: Summarize (old summary + all new messages), send new summary + current query

        Args:
            conversation_id: Unique conversation identifier
            current_query: Current user query

        Returns:
            Enriched query with context
        """
        # Get conversation history (current query should already be saved)
        all_messages = self.storage.get_conversation_history(conversation_id)
        summary_data = self.storage.get_summary(conversation_id)

        # Determine which messages are after summary (new turns after last summarization)
        # Exclude the current query from recent_messages (it will be added separately)
        summary_count = summary_data[1] if summary_data else 0
        all_recent_messages = all_messages[summary_count:] if summary_data else all_messages
        
        # Remove current query from recent messages if it's already there
        # (it was saved before this function was called)
        recent_messages = [
            msg for msg in all_recent_messages 
            if not (msg.role == "user" and msg.content == current_query)
        ]

        # Check if we need to summarize (including current query in token count for threshold check)
        # Create a temporary message for current query to count tokens
        from datetime import datetime
        temp_query_message = Message(role="user", content=current_query, timestamp=datetime.now())
        messages_with_query = recent_messages + [temp_query_message] if recent_messages else [temp_query_message]

        if self._should_summarize(messages_with_query, summary_data is not None):
            # When threshold is hit, summarize ALL recent messages (not keep any, and exclude current query)
            # This includes all messages after the last summary point (excluding current query)
            messages_to_summarize = recent_messages.copy() if recent_messages else []
            
            if messages_to_summarize:
                # If we have a previous summary, include it in the summarization
                # This creates an incremental summary: old summary + new messages
                if summary_data:
                    summary_message = Message(
                        role="system",
                        content=f"Previous conversation summary: {summary_data[0]}",
                        timestamp=recent_messages[0].timestamp if recent_messages else datetime.now(),
                    )
                    messages_to_summarize = [summary_message] + messages_to_summarize

                new_summary = self.summarizer.summarize(messages_to_summarize)
                # Update total summarized count: previous count + all new messages (excluding current query)
                total_summarized = (summary_data[1] if summary_data else 0) + len(recent_messages)
                
                # Save the new summary
                self.storage.save_summary(conversation_id, new_summary, total_summarized)
                
                # After summarization, clear recent messages (only send summary + current query)
                recent_messages = []
                summary_data = (new_summary, total_summarized)

        # Build context string
        # If summarization just happened: summary + current query only
        # If summary exists but no new summarization: summary + recent messages + current query
        # If no summary: all messages + current query
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

