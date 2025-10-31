# ResponseFormatterAgent Documentation

## Overview

The `ResponseFormatterAgent` is the third and final agent in the AI Analyst pipeline. It takes the optimized query and extracted data from previous agents and generates a professional, well-formatted markdown response that directly answers the user's question.

## Purpose

- **Format Data**: Convert raw extracted data into a user-friendly, readable format
- **Generate Markdown**: Create professional markdown responses with proper structure
- **Include Raw Data**: Provide both formatted response and raw data for transparency
- **Handle Errors**: Gracefully handle formatting errors and provide fallback responses

## Architecture

### Input

The agent receives:
1. **Optimized Query** - The refined query from `QueryOptimizerAgent`
2. **Extracted Data** - Structured data from `DataExtractorAgent` containing:
   - Companies
   - People
   - Emails
   - Interactions
   - Groups
   - Workspace info

### Output

The agent returns a dictionary with:
```python
{
    "markdown_response": str,  # Professional markdown-formatted response
    "raw_data": dict,          # Original extracted data (unmodified)
    "metadata": {              # Processing information
        "processing_time_ms": int,
        "llm_call_time_ms": int,
        "response_length": int,
        "data_sources_count": int
    }
}
```

## How It Works

### 1. Data Preparation
- Converts extracted data to formatted JSON string
- Prepares the prompt with optimized query and data

### 2. LLM Processing
- Uses configured LLM provider to generate markdown response
- Temperature set to 0.3 for consistent but creative formatting
- Follows structured prompt guidelines for professional output

### 3. Response Cleaning
- Removes markdown code block wrappers if present
- Ensures clean, ready-to-display markdown

### 4. Metadata Generation
- Tracks processing time
- Counts data sources
- Records response metrics

## Response Format Guidelines

The agent generates responses following these principles:

### Structure
1. **Summary** - Brief overview (1-2 sentences)
2. **Main Content** - Organized sections with clear headings
3. **Data Presentation** - Tables, lists, or bullet points as appropriate
4. **Insights** - Key findings and metrics
5. **Recommendations** - Actionable next steps (when applicable)

### Markdown Features Used
- **Headers** - Hierarchical organization
- **Tables** - Structured data comparison
- **Lists** - Bullet points and numbered lists
- **Bold/Italic** - Emphasis on key points
- **Code blocks** - For IDs or technical details
- **Horizontal rules** - Section separation

## Configuration

### Environment Variables

```bash
# Required
RESPONSE_FORMATTER_PROVIDER=openai     # or 'anthropic', 'gemini'
RESPONSE_FORMATTER_MODEL=gpt-4        # Model to use

# Optional (provider-specific)
RESPONSE_FORMATTER_API_KEY=sk-...     # Overrides default provider key
```

### Default Behavior

If agent-specific variables aren't set, falls back to:
```bash
GLOBAL_LLM_PROVIDER=openai
GLOBAL_LLM_MODEL=gpt-4
```

## Usage

### Basic Usage

```python
from agents.response_formatter import ResponseFormatterAgent

# Initialize
formatter = ResponseFormatterAgent()

# Format response
result = formatter.format(
    optimized_query="The user is asking you to fetch all closed deals from Oct 2024",
    extracted_data={
        "companies": [...],
        "people": [...]
    }
)

# Access formatted response
print(result["markdown_response"])  # User-facing markdown
print(result["raw_data"])           # Original data
print(result["metadata"])           # Processing info
```

### With Custom LLM Provider

```python
from agents.response_formatter import ResponseFormatterAgent
from adapters.openai_provider import OpenAIProvider

# Create custom provider
custom_provider = OpenAIProvider(
    api_key="your-api-key",
    model="gpt-4-turbo"
)

# Initialize with custom provider
formatter = ResponseFormatterAgent(llm_provider=custom_provider)

result = formatter.format(optimized_query, extracted_data)
```

### In Pipeline Context

```python
# Inside LangGraph pipeline node
def _response_formatter_node(state: AgentState) -> AgentState:
    formatter = ResponseFormatterAgent()
    formatted_response = formatter.format(
        optimized_query=state['optimized_query'],
        extracted_data=state['extracted_data']
    )
    return {"final_response": formatted_response}
```

## Example Outputs

### Example 1: Closed Deals Report

**Input:**
```python
optimized_query = "Fetch all closed deals from Oct 2024"
extracted_data = {
    "companies": [
        {"name": "Acme Corp", "deal_value": 150000, "close_date": "2024-10-15"},
        {"name": "TechStart", "deal_value": 85000, "close_date": "2024-10-22"}
    ]
}
```

**Output (markdown_response):**
```markdown
## Closed Deals Summary - October 2024

We found **2 closed deals** in October 2024 with a total value of **$235,000**.

### Deal Overview

| Company | Deal Value | Close Date |
|---------|-----------|------------|
| Acme Corp | $150,000 | Oct 15, 2024 |
| TechStart | $85,000 | Oct 22, 2024 |

### Key Insights
- Average deal size: $117,500
- Largest deal: Acme Corp ($150,000)
- Deal velocity: 2 deals closed in October
```

### Example 2: Empty Data Handling

**Input:**
```python
optimized_query = "Find all meetings scheduled for tomorrow"
extracted_data = {"interactions": [], "people": []}
```

**Output (markdown_response):**
```markdown
## Meeting Schedule - Tomorrow

No meetings found scheduled for tomorrow.

### What This Means
- You currently have no scheduled meetings for tomorrow
- Your calendar is clear for the next day

### Suggestions
- Check if meetings might be scheduled under a different date
- Verify your calendar sync settings
```

## Error Handling

### Graceful Degradation

If LLM formatting fails, the agent:
1. Catches the exception
2. Logs the error
3. Returns a user-friendly error message
4. Still includes the raw data for manual inspection

```python
{
    "markdown_response": "# Error Processing Response\n\nI encountered an error...",
    "raw_data": {...},  # Original data preserved
    "metadata": {
        "error": "Error message details"
    }
}
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Missing API Key | Environment variable not set | Set `RESPONSE_FORMATTER_API_KEY` or provider key |
| Invalid Model | Model name incorrect | Check model availability for your provider |
| Timeout | Large data processing | Increase timeout or reduce data size |
| JSON Parse Error | Malformed extracted data | Validate data from DataExtractorAgent |

## Best Practices

### 1. Data Size Management
- Keep extracted data focused and relevant
- Don't pass unnecessarily large datasets
- Pre-filter data in DataExtractorAgent if needed

### 2. Query Context
- Provide clear, optimized queries
- Include time context and entities
- Be specific about expected output format

### 3. LLM Selection
- Use GPT-4 or Claude for best formatting quality
- GPT-3.5 works for simpler responses
- Consider cost vs. quality tradeoffs

### 4. Response Validation
- Check `metadata.response_length` for reasonable output
- Validate `data_sources_count` matches expectations
- Monitor `processing_time_ms` for performance

## Integration with Pipeline

The ResponseFormatterAgent is the third node in the LangGraph pipeline:

```
User Query
    ↓
QueryOptimizerAgent (refines query)
    ↓
DataExtractorAgent (extracts data)
    ↓
ResponseFormatterAgent (formats response) ← YOU ARE HERE
    ↓
Final Response to User
```

## Performance Considerations

### Processing Time
- LLM call: 1-5 seconds (depends on provider/model)
- Data preparation: <100ms
- Response cleaning: <50ms
- **Total**: Usually 1-6 seconds

### Optimization Tips
1. Use faster models for simple queries (gpt-3.5-turbo)
2. Cache frequently requested formatted responses
3. Implement streaming for real-time response display
4. Pre-process data to reduce LLM token usage

## Testing

### Unit Tests
```python
# Test basic formatting
def test_format_basic():
    formatter = ResponseFormatterAgent()
    result = formatter.format("test query", {"companies": []})
    assert "markdown_response" in result
    assert "raw_data" in result
    assert "metadata" in result

# Test error handling
def test_format_error_handling():
    formatter = ResponseFormatterAgent()
    result = formatter.format("test", None)  # Invalid data
    assert "Error" in result["markdown_response"]
```

### Integration Tests
See [examples/response_formatter_example.py](../examples/response_formatter_example.py) for comprehensive examples.

## Prompt Engineering

The agent uses a carefully crafted prompt template located at:
[prompts/response_formatter_prompt.py](../prompts/response_formatter_prompt.py)

Key aspects:
- Clear role definition
- Structured output guidelines
- Markdown formatting rules
- Data interpretation instructions
- Error handling guidance

## Future Enhancements

Potential improvements:
- [ ] Support for different output formats (HTML, PDF, plain text)
- [ ] Custom formatting templates per query type
- [ ] Response streaming for real-time updates
- [ ] A/B testing different formatting styles
- [ ] Automatic chart/graph generation from data
- [ ] Multi-language response support
- [ ] Response caching and versioning

## Related Documentation

- [QueryOptimizerAgent](./QUERY_OPTIMIZER_AGENT.md)
- [DataExtractorAgent](./DATA_EXTRACTOR_AGENT.md)
- [Pipeline Architecture](./PIPELINE_ARCHITECTURE.md)
- [LLM Provider Configuration](./LLM_PROVIDERS.md)

## Support

For issues or questions:
1. Check the [examples](../examples/response_formatter_example.py)
2. Review the [prompt template](../prompts/response_formatter_prompt.py)
3. Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
4. Contact the development team
