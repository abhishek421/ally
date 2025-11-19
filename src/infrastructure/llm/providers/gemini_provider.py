"""
Google Gemini Provider Adapter
"""
import logging
from typing import List, Dict
from src.infrastructure.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self._logger = logging.getLogger(__name__)
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Gemini client"""
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self._client = genai.GenerativeModel(self.model)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to Google Gemini
        
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
            self._logger.debug(f"Calling Gemini model: {self.model}")
            
            # Gemini has a different API structure
            # Extract system message and user content
            system_instruction = None
            user_content = ""
            
            for msg in messages:
                if msg['role'] == 'system':
                    system_instruction = msg['content']
                elif msg['role'] == 'user':
                    user_content += msg['content'] + "\n"
                elif msg['role'] == 'assistant':
                    # Gemini supports conversation history
                    user_content += f"[Previous response: {msg['content']}]\n"
            
            # Build generation config
            generation_config = {
                "temperature": temperature
            }
            
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            # Generate content
            response = self._client.generate_content(
                user_content,
                generation_config=generation_config
            )
            
            return response.text.strip()
            
        except Exception as e:
            self._logger.exception(f"Gemini API call failed: {e}")
            raise

