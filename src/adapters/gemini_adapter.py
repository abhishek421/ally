"""Google Gemini LLM adapter implementation."""

from typing import AsyncIterator, Iterator, Optional

from ..config import get_settings
from .base import LLMAdapter

settings = get_settings()


class GeminiAdapter(LLMAdapter):
    """Google Gemini LLM adapter using LangChain."""

    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float = 0, max_tokens: Optional[int] = None):
        """Initialize Gemini adapter.

        Args:
            model: Model name (e.g., 'gemini-pro', 'gemini-1.5-pro')
            api_key: Google API key. If None, uses settings.
            temperature: Sampling temperature
            max_tokens: Maximum tokens for response. If None, uses settings.llm_max_tokens
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is required for Gemini adapter. "
                "Install it with: pip install langchain-google-genai"
            )

        self.model_name = model
        api_key = api_key or settings.google_api_key
        if not api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY in environment.")

        # Use provided max_tokens or fall back to settings
        # Gemini uses max_output_tokens parameter
        max_output_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke Gemini model synchronously.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        response = self.llm.invoke(prompt, **kwargs)
        return response.content

    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """Invoke Gemini model asynchronously.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        response = await self.llm.ainvoke(prompt, **kwargs)
        return response.content

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Stream Gemini response.

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
        """Stream Gemini response asynchronously.

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

