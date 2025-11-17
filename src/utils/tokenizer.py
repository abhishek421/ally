"""Token counting abstraction."""

from abc import ABC, abstractmethod
from typing import Protocol

from ..config import get_settings

settings = get_settings()


class TokenizerInterface(ABC):
    """Abstract interface for token counting."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        pass


class TiktokenTokenizer(TokenizerInterface):
    """Tiktoken-based token counter."""

    def __init__(self, model: str = "gpt-4"):
        """Initialize tiktoken tokenizer.

        Args:
            model: Model name to use for tokenization
        """
        try:
            import tiktoken

            self.encoding = tiktoken.encoding_for_model(model)
        except ImportError:
            raise ImportError("tiktoken is required. Install it with: pip install tiktoken")
        except KeyError:
            # Fallback to cl100k_base encoding if model not found
            import tiktoken

            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))


def get_tokenizer() -> TokenizerInterface:
    """Get tokenizer instance based on configuration.

    Returns:
        TokenizerInterface implementation
    """
    tokenizer_type = settings.tokenizer_type.lower()

    if tokenizer_type == "tiktoken":
        # Use the main LLM model for tokenization
        model = settings.llm_model or "gpt-4"
        return TiktokenTokenizer(model=model)
    else:
        raise ValueError(f"Unknown tokenizer type: {tokenizer_type}")

