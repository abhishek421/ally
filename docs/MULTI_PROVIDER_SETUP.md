# Multi-Provider LLM Setup Guide

The CRM AI Copilot supports using different AI models from different providers for different tasks. This allows you to optimize for cost, performance, and capabilities.

## Supported Providers

| Provider | Models | Strengths |
|----------|--------|-----------|
| **OpenAI** | GPT-4, GPT-3.5 | Strong reasoning, JSON mode, reliable |
| **Anthropic** | Claude 3 (Opus, Sonnet, Haiku) | Long context, safety, nuanced understanding |
| **Google** | Gemini Pro, Gemini 1.5 Pro | Multimodal, fast, cost-effective |

## Quick Start

### 1. Install Provider SDKs

```bash
# Install all providers
pip install openai anthropic google-generativeai

# Or install only what you need
pip install openai  # Just OpenAI
pip install anthropic  # Just Anthropic
pip install google-generativeai  # Just Google
```

### 2. Configure API Keys

Add to your `.env` file:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google Gemini
GOOGLE_API_KEY=AIza...
```

### 3. Configure Model Routing

Set which model handles which task:

```bash
# Mix and match across providers!
PLANNER_MODEL=claude-3-opus-20240229      # Anthropic for planning
SUMMARY_MODEL=gpt-3.5-turbo               # OpenAI for summaries
REASONING_MODEL=gemini-1.5-pro            # Google for reasoning
FALLBACK_MODEL=gpt-3.5-turbo              # OpenAI for fallback
```

## Configuration Examples

### Example 1: All OpenAI (Default)

```bash
# .env
OPENAI_API_KEY=sk-...

PLANNER_MODEL=gpt-4-turbo-preview
SUMMARY_MODEL=gpt-3.5-turbo
REASONING_MODEL=gpt-4-turbo-preview
FALLBACK_MODEL=gpt-3.5-turbo
```

**Use case:** Simplicity, proven reliability, great JSON mode support

### Example 2: All Anthropic Claude

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...

PLANNER_MODEL=claude-3-opus-20240229
SUMMARY_MODEL=claude-3-haiku-20240307
REASONING_MODEL=claude-3-opus-20240229
FALLBACK_MODEL=claude-3-haiku-20240307
```

**Use case:** Long context windows, safety-focused, nuanced responses

### Example 3: All Google Gemini

```bash
# .env
GOOGLE_API_KEY=AIza...

PLANNER_MODEL=gemini-1.5-pro
SUMMARY_MODEL=gemini-pro
REASONING_MODEL=gemini-1.5-pro
FALLBACK_MODEL=gemini-pro
```

**Use case:** Cost-effective, fast responses, multimodal capabilities

### Example 4: Best of Each (Recommended)

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Strong reasoning for planning
PLANNER_MODEL=claude-3-opus-20240229

# Fast and cheap for summaries
SUMMARY_MODEL=gemini-pro

# Deep thinking for complex analysis
REASONING_MODEL=gpt-4-turbo-preview

# Reliable and cheap fallback
FALLBACK_MODEL=gpt-3.5-turbo
```

**Use case:** Optimize each task for its specific requirements

### Example 5: Cost-Optimized

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Use cheaper models while maintaining quality
PLANNER_MODEL=claude-3-sonnet-20240229    # Balanced cost/performance
SUMMARY_MODEL=gemini-pro                  # Very cost-effective
REASONING_MODEL=claude-3-sonnet-20240229  # Good reasoning, lower cost
FALLBACK_MODEL=gpt-3.5-turbo             # Cheap and reliable
```

**Use case:** Budget-conscious deployment with good quality

## Model Specifications

### OpenAI Models

| Model | Best For | Context | Cost |
|-------|----------|---------|------|
| `gpt-4-turbo-preview` | Complex reasoning, planning | 128K | $$$ |
| `gpt-4` | Reliable reasoning | 8K | $$$ |
| `gpt-3.5-turbo` | Fast responses, summaries | 16K | $ |

### Anthropic Claude 3

| Model | Best For | Context | Cost |
|-------|----------|---------|------|
| `claude-3-opus-20240229` | Highest intelligence | 200K | $$$ |
| `claude-3-sonnet-20240229` | Balanced performance | 200K | $$ |
| `claude-3-haiku-20240307` | Fast, cost-effective | 200K | $ |

### Google Gemini

| Model | Best For | Context | Cost |
|-------|----------|---------|------|
| `gemini-1.5-pro` | Long context, multimodal | 1M | $$ |
| `gemini-pro` | General purpose | 32K | $ |

## How It Works

The router automatically detects the provider from the model name prefix:

```python
# OpenAI models (prefix: "gpt")
gpt-4-turbo-preview → routes to OpenAI

# Anthropic models (prefix: "claude")
claude-3-opus-20240229 → routes to Anthropic

# Google models (prefix: "gemini")
gemini-1.5-pro → routes to Google
```

## Advanced Usage

### Dynamic Route Override

Change models at runtime:

```python
from src.llm.model import llm_router

# Switch planner to use Gemini
llm_router.set_route("planner", "gemini-1.5-pro")

# Now all planning uses Gemini
from src.llm.model import call_planner
plan = await call_planner("Find companies in SF")
```

### Custom Model Calls

Call any model directly:

```python
from src.llm.model import llm_router

# Use specific model regardless of route
response = await llm_router.call(
    route="reasoning",  # Just for logging
    prompt="Analyze this...",
    json_mode=True,
    max_tokens=2000
)
```

## Troubleshooting

### Provider Not Available

**Error:** `ValueError: Anthropic client not initialized`

**Solution:**
1. Check API key is set: `echo $ANTHROPIC_API_KEY`
2. Install SDK: `pip install anthropic`
3. Restart application

### Model Not Found

**Error:** `Model 'claude-3-opus' not found`

**Solution:** Use full model name with date suffix:
```bash
PLANNER_MODEL=claude-3-opus-20240229  # ✓ Correct
PLANNER_MODEL=claude-3-opus            # ✗ Wrong
```

### SDK Import Error

**Warning:** `Anthropic SDK not installed`

**Solution:**
```bash
pip install anthropic
# or
pip install -r requirements.txt
```

## Cost Optimization Tips

1. **Use cheaper models for simple tasks:**
   ```bash
   SUMMARY_MODEL=gemini-pro  # Very cheap
   FALLBACK_MODEL=gpt-3.5-turbo  # Cheap
   ```

2. **Use expensive models only for complex tasks:**
   ```bash
   PLANNER_MODEL=claude-3-opus-20240229  # Use only for planning
   REASONING_MODEL=gpt-4-turbo-preview   # Use only for deep reasoning
   ```

3. **Monitor usage:**
   - Check logs for which models are being called
   - Use provider dashboards to track costs
   - Consider switching to Sonnet/Haiku if Opus is too expensive

4. **A/B test performance:**
   ```bash
   # Test if cheaper model works well enough
   PLANNER_MODEL=claude-3-sonnet-20240229
   # vs
   PLANNER_MODEL=claude-3-opus-20240229
   ```

## Performance Comparison

Based on typical CRM tasks:

| Task | Best Choice | Reasoning |
|------|-------------|-----------|
| **Planning** | Claude 3 Opus or GPT-4 | Need strong reasoning |
| **Summarization** | Gemini Pro or GPT-3.5 | Speed and cost matter |
| **Reasoning** | Claude 3 Opus | Highest intelligence |
| **Fallback** | GPT-3.5 or Gemini Pro | Reliability and cost |

## Next Steps

1. Start with one provider (easiest: OpenAI)
2. Add other providers as needed
3. Experiment with different combinations
4. Monitor costs and quality
5. Optimize based on your use case

## Support

- OpenAI: https://platform.openai.com/docs
- Anthropic: https://docs.anthropic.com
- Google: https://ai.google.dev/docs

