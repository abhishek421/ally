"""
OpenAI Provider Adapter
"""
import logging
from typing import List, Dict
from adapters.llm_provider import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self._logger = logging.getLogger(__name__)
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        from openai import OpenAI
        self._client = OpenAI(api_key=self.api_key)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to OpenAI
        
        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            The response content as a string
        """
        self.validate_config()
        
        # Set default temperature if not provided
        temperature = kwargs.get('temperature', 0.3)
        max_tokens = kwargs.get('max_tokens')
        
        try:
            self._logger.debug(f"Calling OpenAI model: {self.model}")
            
            # Build parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            response = self._client.chat.completions.create(**params)
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self._logger.exception(f"OpenAI API call failed: {e}")
            raise

