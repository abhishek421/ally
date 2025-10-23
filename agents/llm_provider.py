"""
LLM Provider Factory
Supports multiple LLM providers: OpenAI, Google Gemini, Anthropic Claude
"""

import os
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, model_name: str, api_key: str, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.kwargs = kwargs
    
    @abstractmethod
    def create_llm(self):
        """Create and return the LLM instance"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation"""
    
    def create_llm(self):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            temperature=self.kwargs.get('temperature', 0.1)
        )
    
    def get_provider_name(self) -> str:
        return "OpenAI"


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""
    
    def create_llm(self):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=self.kwargs.get('temperature', 0.1)
            )
        except ImportError:
            raise ImportError(
                "langchain_google_genai is required for Gemini support. "
                "Install it with: pip install langchain-google-genai"
            )
    
    def get_provider_name(self) -> str:
        return "Google Gemini"


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider implementation"""
    
    def create_llm(self):
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.model_name,
                anthropic_api_key=self.api_key,
                temperature=self.kwargs.get('temperature', 0.1)
            )
        except ImportError:
            raise ImportError(
                "langchain_anthropic is required for Claude support. "
                "Install it with: pip install langchain-anthropic"
            )
    
    def get_provider_name(self) -> str:
        return "Anthropic Claude"


class LLMProviderFactory:
    """Factory class for creating LLM providers"""
    
    PROVIDERS = {
        'openai': OpenAIProvider,
        'gemini': GeminiProvider,
        'claude': ClaudeProvider,
        'google': GeminiProvider,  # Alias for Gemini
        'anthropic': ClaudeProvider  # Alias for Claude
    }
    
    @classmethod
    def create_provider(cls, provider_name: str, model_name: str, api_key: str, **kwargs) -> LLMProvider:
        """Create an LLM provider instance"""
        provider_name = provider_name.lower()
        
        if provider_name not in cls.PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider_name}. "
                f"Supported providers: {list(cls.PROVIDERS.keys())}"
            )
        
        provider_class = cls.PROVIDERS[provider_name]
        return provider_class(model_name, api_key, **kwargs)
    
    @classmethod
    def get_supported_providers(cls) -> Dict[str, list]:
        """Get supported providers and their models"""
        return {
            'openai': [
                'gpt-4',
                'gpt-4-turbo',
                'gpt-3.5-turbo',
                'gpt-3.5-turbo-16k'
            ],
            'gemini': [
                'gemini-pro',
                'gemini-pro-vision',
                'gemini-1.5-pro',
                'gemini-1.5-flash'
            ],
            'claude': [
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307',
                'claude-3-5-sonnet-20241022'
            ]
        }
    
    @classmethod
    def create_llm_from_env(cls) -> tuple:
        """Create LLM instance from environment variables"""
        # Get provider and model from environment
        provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
        model_name = os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        
        # Get API key based on provider
        api_key = None
        if provider_name in ['openai']:
OPENAI_API_KEY=REDACTED
        elif provider_name in ['gemini', 'google']:
            api_key = os.getenv("GOOGLE_API_KEY")
        elif provider_name in ['claude', 'anthropic']:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError(
                f"API key not found for provider '{provider_name}'. "
                f"Please set the appropriate environment variable."
            )
        
        # Create provider and LLM
        provider = cls.create_provider(
            provider_name, 
            model_name, 
            api_key, 
            temperature=temperature
        )
        
        llm = provider.create_llm()
        return llm, provider.get_provider_name()


def get_llm_instance() -> tuple:
    """Convenience function to get LLM instance from environment"""
    return LLMProviderFactory.create_llm_from_env()
