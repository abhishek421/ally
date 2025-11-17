"""Factory for creating LLM adapters based on model name."""

from typing import Optional

from ..config import get_settings
from .base import LLMAdapter
from .claude_adapter import ClaudeAdapter
from .gemini_adapter import GeminiAdapter
from .openai_adapter import OpenAIAdapter

settings = get_settings()


def detect_provider(model_name: str) -> str:
    """Detect LLM provider from model name.

    Args:
        model_name: Model name (e.g., 'gpt-4', 'gemini-pro', 'claude-3-opus')

    Returns:
        Provider name: 'openai', 'gemini', or 'claude'

    Raises:
        ValueError: If provider cannot be detected
    """
    model_lower = model_name.lower()

    # OpenAI patterns
    if any(
        model_lower.startswith(prefix)
        for prefix in ["gpt-", "o1-", "o3-", "gpt-4.1-", "gpt-4o", "gpt-3.5"]
    ):
        return "openai"

    # Gemini patterns
    if any(
        model_lower.startswith(prefix)
        for prefix in ["gemini-", "gemma-", "gemini-pro", "gemini-1.5"]
    ):
        return "gemini"

    # Claude patterns
    if any(
        model_lower.startswith(prefix)
        for prefix in ["claude-", "sonnet-", "opus-", "haiku-", "claude-3"]
    ):
        return "claude"

    raise ValueError(
        f"Unknown model provider for '{model_name}'. "
        "Supported providers: OpenAI (gpt-*, o1-*, o3-*), "
        "Gemini (gemini-*, gemma-*), Claude (claude-*, sonnet-*, opus-*, haiku-*)"
    )


def get_llm_adapter(
    model_name: Optional[str] = None,
    temperature: float = 0,
    api_key: Optional[str] = None,
) -> LLMAdapter:
    """Get appropriate LLM adapter based on model name.

    Args:
        model_name: Model name. If None, uses settings.llm_model
        temperature: Sampling temperature
        api_key: Optional API key override

    Returns:
        LLMAdapter instance

    Raises:
        ValueError: If provider not supported or API key missing
    """
    model_name = model_name or settings.llm_model
    if not model_name:
        raise ValueError("Model name is required. Set LLM_MODEL in environment or pass model_name.")

    provider = detect_provider(model_name)

    if provider == "openai":
        return OpenAIAdapter(model=model_name, api_key=api_key, temperature=temperature)
    elif provider == "gemini":
        return GeminiAdapter(model=model_name, api_key=api_key, temperature=temperature)
    elif provider == "claude":
        return ClaudeAdapter(model=model_name, api_key=api_key, temperature=temperature)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

