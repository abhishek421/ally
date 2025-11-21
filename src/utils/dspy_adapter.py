"""Adapter to integrate our LLM adapters with dspy."""

from typing import Optional

import dspy
from langchain_core.language_models import BaseChatModel

from ..adapters import get_llm_adapter
from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LangChainDSPyLM(dspy.LM):
    """DSPy language model wrapper for LangChain adapters."""

    def __init__(self, langchain_model: BaseChatModel, model_name: str):
        """Initialize DSPy LM from LangChain model.

        Args:
            langchain_model: LangChain chat model instance
            model_name: Model name for identification
        """
        self.langchain_model = langchain_model
        self.model_name = model_name
        # Initialize parent with model name
        super().__init__(model_name)

    def __call__(self, prompt: str, **kwargs) -> str:
        """Call the language model.

        Args:
            prompt: Input prompt (can be string or list of messages)
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        try:
            # Handle both string prompts and message lists
            from langchain_core.messages import HumanMessage
            
            if isinstance(prompt, str):
                messages = [HumanMessage(content=prompt)]
            elif isinstance(prompt, list):
                # Already in message format
                messages = prompt
            else:
                messages = [HumanMessage(content=str(prompt))]
            
            response = self.langchain_model.invoke(messages, **kwargs)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error(f"LangChain model call failed: {self.model_name}", error=str(e))
            raise

    def generate(self, prompt: str, **kwargs) -> list[str]:
        """Generate multiple completions.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            List of generated texts
        """
        try:
            # For now, return single completion
            # Can be extended to support multiple completions
            result = self.__call__(prompt, **kwargs)
            return [result]
        except Exception as e:
            logger.error(f"LangChain model generate failed: {self.model_name}", error=str(e))
            raise

    def request(self, prompt: str, **kwargs) -> str:
        """Request completion from model (dspy interface).

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        return self.__call__(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs):
        """Stream model response.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        try:
            from langchain_core.messages import HumanMessage
            
            # Convert prompt to LangChain message format
            if isinstance(prompt, str):
                messages = [HumanMessage(content=prompt)]
            else:
                messages = prompt
            
            # Use LangChain's streaming if available
            if hasattr(self.langchain_model, "stream"):
                for chunk in self.langchain_model.stream(messages, **kwargs):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    else:
                        yield str(chunk)
            else:
                # Fallback to non-streaming
                result = self.__call__(prompt, **kwargs)
                yield result
        except Exception as e:
            logger.error(f"LangChain model stream failed: {self.model_name}", error=str(e))
            raise


def get_dspy_lm(model_name: Optional[str] = None, temperature: float = 0.7) -> dspy.LM:
    """Get dspy language model from our adapter system.

    Args:
        model_name: Model name. If None, uses settings.query_processing_model
        temperature: Sampling temperature

    Returns:
        dspy.LM instance
    """
    model_name = model_name or settings.query_processing_model
    if not model_name:
        raise ValueError("Model name is required. Set QUERY_PROCESSING_MODEL in environment.")

    # Get our LLM adapter
    adapter = get_llm_adapter(model_name=model_name, temperature=temperature)

    # Get the underlying LangChain model
    if hasattr(adapter, "llm"):
        langchain_model = adapter.llm
    else:
        raise ValueError(f"Adapter for {model_name} does not expose LangChain model")

    # Wrap in dspy LM
    return LangChainDSPyLM(langchain_model=langchain_model, model_name=model_name)

