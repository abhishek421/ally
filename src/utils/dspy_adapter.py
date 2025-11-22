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

    def __call__(self, *args, **kwargs) -> str:
        """Call the language model.

        Args:
            *args: Positional arguments (may contain prompt as first arg)
            **kwargs: Keyword arguments (may contain prompt or other parameters)

        Returns:
            Generated text
        """
        try:
            from langchain_core.messages import HumanMessage
            
            # Extract prompt from args or kwargs
            prompt = None
            
            # First, check if prompt is in positional args
            if args:
                prompt = args[0]
            # Then check kwargs
            elif "prompt" in kwargs:
                prompt = kwargs.pop("prompt")
            elif "messages" in kwargs:
                # If messages are provided directly, use them
                messages = kwargs.pop("messages")
                response = self.langchain_model.invoke(messages, **kwargs)
                return response.content if hasattr(response, "content") else str(response)
            else:
                # Try to find prompt-like values in kwargs
                # dspy might pass the full prompt text in various ways
                for key in ["input", "text", "content", "query", "instruction", "context"]:
                    if key in kwargs:
                        value = kwargs[key]
                        if isinstance(value, str) and len(value.strip()) > 0:
                            prompt = kwargs.pop(key)
                            break
                        elif isinstance(value, list) and len(value) > 0:
                            # Could be a list of messages
                            messages = kwargs.pop(key)
                            response = self.langchain_model.invoke(messages, **kwargs)
                            return response.content if hasattr(response, "content") else str(response)
                
                if prompt is None:
                    # Last resort: look for any string value that looks like a prompt
                    for key, value in list(kwargs.items()):
                        if isinstance(value, str) and len(value.strip()) > 20:
                            prompt = kwargs.pop(key)
                            logger.debug(f"Extracted prompt from kwargs key '{key}'")
                            break
            
            if prompt is None:
                # Log for debugging
                logger.warning(
                    f"__call__ invoked without prompt. Args: {args}, Kwargs keys: {list(kwargs.keys())}"
                )
                # If still no prompt, raise a clear error
                raise ValueError(
                    f"No prompt provided to language model. "
                    f"Args: {args}, Kwargs keys: {list(kwargs.keys())}. "
                    f"dspy should call request() method instead of __call__() directly."
                )
            
            # Convert prompt to messages format
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
            logger.error(f"LangChain model call failed: {self.model_name}", error=str(e), exc_info=True)
            raise

    def generate(self, *args, **kwargs) -> list[str]:
        """Generate multiple completions.

        Args:
            *args: Positional arguments (may contain prompt)
            **kwargs: Additional parameters

        Returns:
            List of generated texts
        """
        try:
            # For now, return single completion
            # Can be extended to support multiple completions
            result = self.__call__(*args, **kwargs)
            return [result]
        except Exception as e:
            logger.error(f"LangChain model generate failed: {self.model_name}", error=str(e))
            raise

    def request(self, *args, **kwargs) -> str:
        """Request completion from model (dspy interface).
        
        This is the primary method dspy uses to call the LM.

        Args:
            *args: Positional arguments (may contain prompt)
            **kwargs: Additional parameters (may contain prompt)

        Returns:
            Generated text
        """
        # Call __call__ which handles prompt extraction from args/kwargs
        return self.__call__(*args, **kwargs)

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

