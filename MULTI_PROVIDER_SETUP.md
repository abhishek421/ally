# Multi-Provider LLM Setup Guide

This guide helps you set up the chatbot with different LLM providers.

## Quick Setup

### 1. OpenAI (Default)
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export LLM_PROVIDER=openai
export LLM_MODEL_NAME=gpt-3.5-turbo
OPENAI_API_KEY=REDACTED
```

### 2. Google Gemini
```bash
# Install additional dependency
pip install langchain-google-genai

# Set environment variables
export LLM_PROVIDER=gemini
export LLM_MODEL_NAME=gemini-1.5-pro
export GOOGLE_API_KEY=your_google_key_here
```

### 3. Anthropic Claude
```bash
# Install additional dependency
pip install langchain-anthropic

# Set environment variables
export LLM_PROVIDER=claude
export LLM_MODEL_NAME=claude-3-sonnet-20240229
export ANTHROPIC_API_KEY=your_anthropic_key_here
```

## Testing Your Setup

Run the test script to verify your configuration:

```bash
python test_multi_provider.py
```

## Supported Models

### OpenAI
- `gpt-4` - Most capable
- `gpt-4-turbo` - Latest GPT-4
- `gpt-3.5-turbo` - Fast and cost-effective
- `gpt-3.5-turbo-16k` - Longer context

### Google Gemini
- `gemini-pro` - Standard model
- `gemini-pro-vision` - With vision capabilities
- `gemini-1.5-pro` - Latest Pro model
- `gemini-1.5-flash` - Fast model

### Anthropic Claude
- `claude-3-opus-20240229` - Most capable
- `claude-3-sonnet-20240229` - Balanced
- `claude-3-haiku-20240307` - Fast and efficient
- `claude-3-5-sonnet-20241022` - Latest Sonnet

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Provider name (openai, gemini, claude) | openai |
| `LLM_MODEL_NAME` | Model name | gpt-3.5-turbo |
| `LLM_TEMPERATURE` | Response randomness (0.0-1.0) | 0.1 |
OPENAI_API_KEY=REDACTED
| `GOOGLE_API_KEY` | Google API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |

## Troubleshooting

### Import Errors
If you get import errors for Gemini or Claude:
```bash
pip install langchain-google-genai  # For Gemini
pip install langchain-anthropic     # For Claude
```

### API Key Errors
Make sure you have the correct API key for your chosen provider:
- OpenAI: Get key from https://platform.openai.com/api-keys
- Google: Get key from https://makersuite.google.com/app/apikey
- Anthropic: Get key from https://console.anthropic.com/

### Model Not Found
Check that your model name is correct and you have access to it in your API account.
