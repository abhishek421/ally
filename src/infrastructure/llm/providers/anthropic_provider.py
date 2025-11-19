"""
Anthropic Provider Adapter
"""
import logging
from typing import List, Dict
from src.infrastructure.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) LLM provider implementation"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self._logger = logging.getLogger(__name__)
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Anthropic client"""
        from anthropic import Anthropic
        self._client = Anthropic(api_key=self.api_key)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to Anthropic
        
        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            The response content as a string
        """
        self.validate_config()
        
        # Set default temperature if not provided
        temperature = kwargs.get('temperature', 0.3)
        max_tokens = kwargs.get('max_tokens', 4096)
        
        try:
            self._logger.debug(f"Calling Anthropic model: {self.model}")
            
            # Anthropic uses 'messages' in a specific format
            # Convert messages to Anthropic format
            anthropic_messages = []
            system_message = None
            
            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                elif msg['role'] in ['user', 'assistant']:
                    anthropic_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
            
            # Build parameters
            params = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            if system_message:
                params["system"] = system_message
            
            response = self._client.messages.create(**params)
            
            # Extract text from Anthropic response
            text_content = ""
            for block in response.content:
                if block.type == 'text':
                    text_content += block.text
            
            return text_content.strip()
            
        except Exception as e:
            self._logger.exception(f"Anthropic API call failed: {e}")
            raise

