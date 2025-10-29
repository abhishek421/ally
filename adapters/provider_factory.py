"""
LLM Provider Factory - Creates provider instances based on configuration
"""
import logging
from typing import Dict, Any
from adapters.llm_provider import LLMProvider
from adapters.llm_providers import OpenAIProvider, AnthropicProvider, GeminiProvider


class LLMProviderFactory:
    """Factory class for creating LLM provider instances"""
    
    # Registry of available providers
    _providers = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'gemini': GeminiProvider,
    }
    
    @classmethod
    def create(cls, config: Dict[str, Any]) -> LLMProvider:
        """
        Create a provider instance based on configuration
        
        Args:
            config: Dictionary containing provider configuration
                   - provider: str (name of provider)
                   - model: str (model name)
                   - api_key: str (API key)
                   - **kwargs: Additional provider-specific params
        
        Returns:
            BaseLLMProvider instance
            
        Example:
            config = {
                'provider': 'openai',
                'model': 'gpt-4',
                'api_key': 'sk-...'
            }
            provider = LLMProviderFactory.create(config)
        """
        logger = logging.getLogger(__name__)
        
        # Extract provider name
        provider_name = config.get('provider', 'openai').lower()
        
        # Get provider class
        provider_class = cls._providers.get(provider_name)
        
        if not provider_class:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {list(cls._providers.keys())}"
            )
        
        # Extract configuration
        api_key = config.get('api_key', '')
        model = config.get('model', '')
        additional_params = {k: v for k, v in config.items() 
                           if k not in ['provider', 'api_key', 'model']}
        
        logger.info(f"Creating {provider_name} provider with model {model}")
        
        # Create and return provider instance
        return provider_class(
            api_key=api_key,
            model=model,
            **additional_params
        )
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new provider class
        
        Args:
            name: Provider name
            provider_class: Provider class (subclass of LLMProvider)
        """
        if not issubclass(provider_class, LLMProvider):
            raise TypeError(
                "Provider class must be a subclass of LLMProvider"
            )
        
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def list_providers(cls):
        """List all registered providers"""
        return list(cls._providers.keys())

