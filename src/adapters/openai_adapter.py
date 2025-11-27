"""OpenAI LLM adapter implementation."""

from typing import AsyncIterator, Iterator, Optional

from langchain_openai import ChatOpenAI

from ..config import get_settings
from .base import LLMAdapter

settings = get_settings()


class OpenAIAdapter(LLMAdapter):
    """OpenAI LLM adapter using LangChain."""

    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float = 0, max_tokens: Optional[int] = None):
        """Initialize OpenAI adapter.

        Args:
            model: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')
            api_key: OpenAI API key. If None, uses settings.
            temperature: Sampling temperature
            max_tokens: Maximum tokens for response. If None, uses settings.llm_max_tokens
        """
        self.model_name = model
        api_key = api_key or settings.openai_api_key
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in environment.")

        # Use provided max_tokens or fall back to settings
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke OpenAI model synchronously.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        response = self.llm.invoke(prompt, **kwargs)
        return response.content

    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """Invoke OpenAI model asynchronously.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        response = await self.llm.ainvoke(prompt, **kwargs)
        return response.content

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Stream OpenAI response.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks
        """
        for chunk in self.llm.stream(prompt, **kwargs):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)

    async def astream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream OpenAI response asynchronously.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks
        """
        async for chunk in self.llm.astream(prompt, **kwargs):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)

