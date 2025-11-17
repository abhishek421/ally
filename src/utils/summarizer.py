"""Summarization service abstraction."""

from abc import ABC, abstractmethod
from typing import List

from ..adapters import get_llm_adapter
from ..config import get_settings
from .models import Message

settings = get_settings()


class SummarizerInterface(ABC):
    """Abstract interface for text summarization."""

    @abstractmethod
    def summarize(self, messages: List[Message]) -> str:
        """Summarize a list of messages.

        Args:
            messages: List of messages to summarize

        Returns:
            Summary text
        """
        pass


class LLMSummarizer(SummarizerInterface):
    """LLM-based summarizer using adapter system."""

    def __init__(self, model: str | None = None):
        """Initialize LLM summarizer.

        Args:
            model: Model name to use for summarization. If None, uses config.
        """
        self.model_name = model or settings.summary_model or "gpt-4o-mini"
        self.adapter = get_llm_adapter(model_name=self.model_name, temperature=0)

    def summarize(self, messages: List[Message]) -> str:
        """Summarize messages using LLM adapter.

        Args:
            messages: List of messages to summarize

        Returns:
            Summary text
        """
        if not messages:
            return ""

        # Format messages for summarization
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])

        prompt = f"""Summarize the following conversation history. Focus on key topics, decisions, and important information that would be useful for future context. Keep the summary concise but comprehensive.

Conversation:
{conversation_text}

Summary:"""

        return self.adapter.invoke(prompt)


def get_summarizer() -> SummarizerInterface:
    """Get summarizer instance based on configuration.

    Returns:
        SummarizerInterface implementation
    """
    # For now, always use LLM summarizer
    # Can be extended to support other summarization methods
    return LLMSummarizer()

