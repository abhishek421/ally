# LLM Provider Adapter Architecture

## Overview

The adapter architecture allows each agent in the AI Analyst RAG pipeline to use different LLM providers and models, configured via environment variables. This provides flexibility, cost optimization, and fault tolerance.

## Architecture Components

### 1. Base Provider (`adapters/llm_provider.py`)

Abstract base class that defines the interface all providers must implement:

```python
class LLMProvider(ABC):
    def chat(messages, **kwargs) -> str
    def validate_config() -> bool
```

### 2. Provider Implementations

**OpenAI Provider** (`adapters/llm_providers/openai_provider.py`)
- Supports GPT-3.5, GPT-4 models
- Uses OpenAI SDK
- Configuration: `OPENAI_API_KEY`

**Anthropic Provider** (`adapters/llm_providers/anthropic_provider.py`)
- Supports Claude models (Opus, Sonnet, Haiku)
- Uses Anthropic SDK
- Configuration: `ANTHROPIC_API_KEY`

**Google Gemini Provider** (`adapters/llm_providers/gemini_provider.py`)
- Supports Gemini Pro, Gemini Ultra models
- Uses Google Generative AI SDK
- Configuration: `GOOGLE_API_KEY`

### 3. Provider Factory (`adapters/provider_factory.py`)

Dynamically creates provider instances based on configuration:

```python
config = {
    'provider': 'openai',
    'model': 'gpt-4',
    'api_key': 'sk-...'
}
provider = LLMProviderFactory.create(config)
```

## Configuration Examples

### Example 1: All Agents Use OpenAI (Basic)
```env
OPENAI_API_KEY=sk-your-key-here
MODEL_NAME=gpt-4
```

### Example 2: Mix of Providers
```env
# Query Optimizer - Use OpenAI
QUERY_OPTIMIZER_PROVIDER=openai
QUERY_OPTIMIZER_MODEL=gpt-4
QUERY_OPTIMIZER_API_KEY=sk-your-key

# Data Extractor - Use Anthropic
DATA_EXTRACTOR_PROVIDER=anthropic
DATA_EXTRACTOR_MODEL=claude-3-opus
ANTHROPIC_API_KEY=sk-ant-your-key

# Or use Google Gemini
# DATA_EXTRACTOR_PROVIDER=gemini
# DATA_EXTRACTOR_MODEL=gemini-pro
# GOOGLE_API_KEY=your-google-key

# Response Formatter - Use cheaper model
RESPONSE_FORMATTER_PROVIDER=openai
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo
```

### Example 3: Cost Optimization
```env
# Use GPT-4 only for critical agent
QUERY_OPTIMIZER_MODEL=gpt-4

# Use cheaper models for other agents
DATA_EXTRACTOR_MODEL=gpt-3.5-turbo
RESPONSE_FORMATTER_MODEL=gpt-3.5-turbo
```

## Usage in Agents

### Before (Hardcoded):
```python
class QueryOptimizerAgent:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
```

### After (Injected Dependency):
```python
class QueryOptimizerAgent:
    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider or create_from_config()
        
    def _llm_optimization(self, user_query):
        response = self.llm_provider.chat(messages)
```

## Adding New Providers

To add a new LLM provider:

1. **Create Provider Class** (`adapters/your_provider.py`):
```python
from adapters.llm_provider import LLMProvider

class YourProvider(LLMProvider):
    def _initialize_client(self):
        # Initialize your SDK client
        
    def chat(self, messages, **kwargs):
        # Implement chat completion
        return response.content
```

2. **Register in Factory** (`adapters/provider_factory.py`):
```python
_providers = {
    'openai': OpenAIProvider,
    'anthropic': AnthropicProvider,
    'yourprovider': YourProvider  # Add this
}
```

3. **Use in Configuration**:
```env
QUERY_OPTIMIZER_PROVIDER=yourprovider
QUERY_OPTIMIZER_MODEL=your-model
YOURPROVIDER_API_KEY=your-key
```

## Benefits

1. **Flexibility**: Swap providers without code changes
2. **Cost Optimization**: Use cheaper models where appropriate
3. **Fault Tolerance**: Fallback to different providers
4. **Testing**: Easy to mock providers for testing
5. **Vendor Lock-in**: Avoid dependency on single provider

