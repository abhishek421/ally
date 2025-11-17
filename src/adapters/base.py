"""Base LLM adapter interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Iterator


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters."""

    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke LLM synchronously.

        Args:
            prompt: Input prompt text
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """Invoke LLM asynchronously.

        Args:
            prompt: Input prompt text
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Stream LLM response.

        Args:
            prompt: Input prompt text
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        pass

    @abstractmethod
    async def astream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream LLM response asynchronously.

        Args:
            prompt: Input prompt text
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        pass

