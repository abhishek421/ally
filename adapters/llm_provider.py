"""
LLM Provider - Abstract interface for all LLM providers
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class LLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initialize the LLM provider
        
        Args:
            api_key: API key for the provider
            model: Model name to use
            **kwargs: Additional provider-specific parameters
        """
        self.api_key = api_key
        self.model = model
        self.kwargs = kwargs
        self._client = None
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to the LLM
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            The response content as a string
        """
        pass
    
    @abstractmethod
    def _initialize_client(self):
        """Initialize the provider-specific client"""
        pass
    
    def validate_config(self) -> bool:
        """
        Validate that the provider is configured correctly
        
        Returns:
            True if configuration is valid
        """
        if not self.api_key:
            raise ValueError(f"API key is required for {self.__class__.__name__}")
        if not self.model:
            raise ValueError(f"Model name is required for {self.__class__.__name__}")
        return True
    
    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model})"

