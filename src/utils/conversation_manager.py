"""Conversation manager for context building and summarization."""

from typing import List, Optional

from ..config import get_settings
from .models import Message
from .storage import StorageInterface
from .summarizer import SummarizerInterface
from .tokenizer import TokenizerInterface
from .logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


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
        
        logger.info(
            "ConversationManager initialized",
            context_limit=context_limit,
            threshold_percentage=settings.context_threshold_percentage,
            calculated_threshold=self.token_threshold,
        )

    def get_context_for_query(
        self, conversation_id: str, current_query: str, workspace_id: Optional[str] = None
    ) -> str:
        """Get enriched context for a query.

        Logic:
        1. If no summarization: Send all previous turns + current query
        2. If threshold hit: Summarize ALL previous messages, send only summary + current query
        3. If summary exists: Send summary + new turns (after summarization) + current query
        4. When threshold hit again: Summarize (old summary + all new messages), send new summary + current query

        Args:
            conversation_id: Unique conversation identifier
            current_query: Current user query
            workspace_id: Workspace UUID (optional, will be queried if not provided)

        Returns:
            Enriched query with context
        """
        # Get conversation history (force reload to get latest assistant messages saved asynchronously)
        # This ensures we have all messages when checking the threshold
        logger.info(
            "Getting context for query",
            conversation_id=conversation_id,
            current_query_preview=current_query[:100] if current_query else "",
            query_length=len(current_query) if current_query else 0,
        )
        
        all_messages = self.storage.get_conversation_history(conversation_id, force_reload=True)
        logger.info(
            "Retrieved conversation history",
            conversation_id=conversation_id,
            total_messages=len(all_messages),
            message_details=[{"role": msg.role, "content_preview": msg.content[:50]} for msg in all_messages[-5:]],  # Last 5 messages
        )
        
        summary_data = self.storage.get_summary(conversation_id)
        logger.info(
            "Retrieved summary data",
            conversation_id=conversation_id,
            has_summary=summary_data is not None,
            summary_count=summary_data[1] if summary_data else 0,
            summary_preview=summary_data[0][:100] if summary_data and summary_data[0] else None,
        )

        # Handle new return format: (summary, message_count, start_message_id, end_message_id)
        summary_count = summary_data[1] if summary_data else 0
        previous_start_message_id = summary_data[2] if summary_data and len(summary_data) > 2 else None
        
        logger.info(
            "Processing messages after summary",
            conversation_id=conversation_id,
            summary_count=summary_count,
            total_messages=len(all_messages),
            messages_after_summary=len(all_messages) - summary_count,
        )
        
        # Determine which messages are after summary (new turns after last summarization)
        # Exclude the current query from recent_messages (it will be added separately)
        all_recent_messages = all_messages[summary_count:] if summary_data else all_messages
        
        # Remove current query from recent messages if it's already there
        # (it was saved before this function was called)
        recent_messages = [
            msg for msg in all_recent_messages 
            if not (msg.role == "user" and msg.content == current_query)
        ]
        
        logger.info(
            "Filtered recent messages",
            conversation_id=conversation_id,
            all_recent_count=len(all_recent_messages),
            recent_messages_count=len(recent_messages),
            recent_message_roles=[msg.role for msg in recent_messages],
        )

        # Check if we need to summarize (including current query in token count for threshold check)
        # IMPORTANT: When there's no summary, we should check ALL messages (not just recent)
        # because recent_messages excludes the current query, which might leave us with 0 messages
        # Create a temporary message for current query to count tokens
        from datetime import datetime
        temp_query_message = Message(role="user", content=current_query, timestamp=datetime.now())
        
        # If no summary exists, check ALL messages (including current query)
        # If summary exists, check only recent messages + current query
        if not summary_data:
            # No summary: check all messages + current query
            # But exclude duplicates of current query from all_messages
            messages_to_check = [
                msg for msg in all_messages 
                if not (msg.role == "user" and msg.content == current_query)
            ] + [temp_query_message]
        else:
            # Summary exists: check only recent messages + current query
            messages_to_check = recent_messages + [temp_query_message] if recent_messages else [temp_query_message]
        
        logger.info(
            "Preparing threshold check",
            conversation_id=conversation_id,
            has_summary=summary_data is not None,
            all_messages_count=len(all_messages),
            recent_messages_count=len(recent_messages),
            messages_to_check_count=len(messages_to_check),
            message_roles=[msg.role for msg in messages_to_check],
        )

        should_summarize = self._should_summarize(messages_to_check, summary_data is not None)
        logger.info(
            "Threshold check result",
            conversation_id=conversation_id,
            should_summarize=should_summarize,
        )
        
        if should_summarize:
            logger.info(
                "THRESHOLD HIT - Starting summarization",
                conversation_id=conversation_id,
                recent_messages_count=len(recent_messages),
            )
            
            # When threshold is hit, summarize ALL recent messages (not keep any, and exclude current query)
            # This includes all messages after the last summary point (excluding current query)
            messages_to_summarize = recent_messages.copy() if recent_messages else []
            
            logger.info(
                "Messages to summarize",
                conversation_id=conversation_id,
                count=len(messages_to_summarize),
                message_roles=[msg.role for msg in messages_to_summarize],
            )
            
            if messages_to_summarize:
                # If we have a previous summary, include it in the summarization
                # This creates an incremental summary: old summary + new messages
                if summary_data:
                    logger.info(
                        "Including previous summary in summarization",
                        conversation_id=conversation_id,
                        previous_summary_preview=summary_data[0][:100] if summary_data[0] else None,
                    )
                    summary_message = Message(
                        role="system",
                        content=f"Previous conversation summary: {summary_data[0]}",
                        timestamp=recent_messages[0].timestamp if recent_messages else datetime.now(),
                    )
                    messages_to_summarize = [summary_message] + messages_to_summarize

                logger.info(
                    "Calling summarizer",
                    conversation_id=conversation_id,
                    total_messages_to_summarize=len(messages_to_summarize),
                )
                
                # Calculate summarization input tokens (the prompt sent to summarizer)
                # Format messages for summarization (same as summarizer does)
                conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages_to_summarize])
                summarization_prompt = f"""Summarize the following conversation history. Focus on key topics, decisions, and important information that would be useful for future context. Keep the summary concise but comprehensive.

Conversation:
{conversation_text}

Summary:"""
                summarization_input_tokens = self.tokenizer.count_tokens(summarization_prompt)
                
                new_summary = self.summarizer.summarize(messages_to_summarize)
                
                logger.info(
                    "Summary generated",
                    conversation_id=conversation_id,
                    summary_length=len(new_summary),
                    summary_preview=new_summary[:200],
                )
                
                # Update total summarized count: previous count + all new messages (excluding current query)
                total_summarized = (summary_data[1] if summary_data else 0) + len(recent_messages)
                
                logger.info(
                    "Calculating summary metadata",
                    conversation_id=conversation_id,
                    previous_summarized=summary_data[1] if summary_data else 0,
                    new_messages_count=len(recent_messages),
                    total_summarized=total_summarized,
                )
                
                # Calculate summary tokens (output from summarizer)
                summary_output_tokens = self.tokenizer.count_tokens(new_summary)
                
                # Update conversation token usage with summarization tokens
                from ..utils.conversation_service import update_conversation_token_usage
                try:
                    update_conversation_token_usage(
                        conversation_id=conversation_id,
                        input_tokens=summarization_input_tokens,
                        output_tokens=summary_output_tokens,
                    )
                    logger.info(
                        "Updated conversation token usage with summarization",
                        conversation_id=conversation_id,
                        summarization_input_tokens=summarization_input_tokens,
                        summarization_output_tokens=summary_output_tokens,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to update conversation token usage for summarization",
                        conversation_id=conversation_id,
                        error=str(e),
                    )
                
                # Calculate summary tokens (for storage metadata - use output tokens)
                summary_tokens = summary_output_tokens
                
                # Get message IDs for DB storage
                # start_message_id: first message ever (use previous if exists, otherwise first message)
                start_message_id = previous_start_message_id
                if not start_message_id:
                    # First message ever - offset 0
                    if hasattr(self.storage, 'get_message_id_by_offset'):
                        start_message_id = self.storage.get_message_id_by_offset(conversation_id, 0)
                
                # end_message_id: last message before current query (offset = total_summarized - 1)
                end_message_id = None
                if total_summarized > 0:
                    if hasattr(self.storage, 'get_message_id_by_offset'):
                        end_message_id = self.storage.get_message_id_by_offset(
                            conversation_id, total_summarized - 1
                        )
                
                # Save the new summary (with DB persistence)
                logger.info(
                    "Saving summary to storage",
                    conversation_id=conversation_id,
                    summary_length=len(new_summary),
                    message_count=total_summarized,
                    workspace_id=workspace_id,
                    start_message_id=start_message_id,
                    end_message_id=end_message_id,
                    summary_tokens=summary_tokens,
                )
                
                self.storage.save_summary(
                    conversation_id=conversation_id,
                    summary=new_summary,
                    message_count=total_summarized,
                    workspace_id=workspace_id,
                    start_message_id=start_message_id,
                    end_message_id=end_message_id,
                    summary_tokens=summary_tokens,
                )
                
                logger.info(
                    "Summary saved successfully",
                    conversation_id=conversation_id,
                )
                
                # After summarization, clear recent messages (only send summary + current query)
                recent_messages = []
                summary_data = (new_summary, total_summarized, start_message_id, end_message_id)

        # Build context string
        # If summarization just happened: summary + current query only
        # If summary exists but no new summarization: summary + recent messages + current query
        # If no summary: all messages + current query
        summary_text = summary_data[0] if summary_data else None
        context = self._build_context_string(
            summary=summary_text,
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
            logger.info("No messages to check for summarization")
            return False

        # Count tokens for each message individually
        token_counts = []
        for i, msg in enumerate(messages):
            token_count = self.tokenizer.count_tokens(msg.content)
            token_counts.append({
                "index": i,
                "role": msg.role,
                "content_preview": msg.content[:50],
                "tokens": token_count,
            })
        
        total_tokens = sum(tc["tokens"] for tc in token_counts)
        
        should_summarize = total_tokens >= self.token_threshold
        
        # Log detailed threshold check
        logger.info(
            "THRESHOLD CHECK DETAILS",
            message_count=len(messages),
            token_counts=token_counts,
            total_tokens=total_tokens,
            threshold=self.token_threshold,
            threshold_percentage=f"{(total_tokens / self.token_threshold * 100):.1f}%",
            should_summarize=should_summarize,
            summary_exists=summary_exists,
            context_limit=settings.llm_context_limit,
            threshold_percentage_config=settings.context_threshold_percentage,
        )

        return should_summarize

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

