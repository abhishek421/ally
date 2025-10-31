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
                   - provider: str (name of provider, required)
                   - model: str (model name, required)
                   - api_key: str (API key, required)
                   - **kwargs: Additional provider-specific params

        Returns:
            BaseLLMProvider instance

        Raises:
            ValueError: If required configuration is missing

        Example:
            config = {
                'provider': 'openai',
                'model': 'gpt-4',
                'api_key': 'sk-...'
            }
            provider = LLMProviderFactory.create(config)
        """
        logger = logging.getLogger(__name__)

        # Extract provider name (required)
        provider_name = config.get('provider')
        if not provider_name:
            raise ValueError(
                "Provider name is required in configuration. "
                "Please specify 'provider' in the config dictionary."
            )
        provider_name = provider_name.lower()
        
        # Get provider class
        provider_class = cls._providers.get(provider_name)
        
        if not provider_class:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {list(cls._providers.keys())}"
            )
        
        # Extract configuration (required fields)
        model = config.get('model')
        if not model:
            raise ValueError(
                f"Model name is required for provider '{provider_name}'. "
                "Please specify 'model' in the config dictionary."
            )

        api_key = config.get('api_key', '')
        if not api_key:
            logger.warning(
                f"API key is empty for provider '{provider_name}'. "
                "Make sure to set the appropriate environment variable."
            )

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

