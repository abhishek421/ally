# Business Analyst Persona - Documentation

## Overview

The **Business Analyst Persona** provides overarching CRM domain knowledge and business intelligence context that informs all agent operations. It serves as the foundational layer of business understanding that helps agents interpret queries accurately and generate meaningful insights.

## Purpose

The persona addresses several key challenges:

1. **Domain Knowledge**: Provides deep CRM expertise (sales, marketing, customer success terminology)
2. **Query Understanding**: Helps interpret ambiguous business terms and implicit requirements
3. **Business Logic**: Applies CRM best practices and industry standards
4. **Context Awareness**: Understands business relationships and dependencies
5. **General Intelligence**: Enables agents to answer non-data queries about CRM concepts

## Components

### 1. `BUSINESS_ANALYST_PERSONA`
**Location**: [`prompts/business_analyst_persona.py`](../prompts/business_analyst_persona.py)

**Content**:
- CRM Fundamentals (leads, contacts, companies, deals, etc.)
- Sales Metrics & KPIs (MRR, close rate, pipeline value, etc.)
- Sales Stages & Processes
- Marketing & Lead Management
- Customer Success concepts
- Time-Based Analysis terminology
- Business Analysis terms
- Communication style guidelines
- Query interpretation rules
- Contextual awareness patterns
- Business intelligence principles
- Red flags and opportunity signals

**Use Case**: Prepend to agent system prompts to provide comprehensive CRM domain knowledge

### 2. `BUSINESS_ANALYST_SYSTEM_CONTEXT`
**Location**: [`prompts/business_analyst_persona.py`](../prompts/business_analyst_persona.py)

**Content**:
- System role definition
- Workspace context
- Capabilities summary
- Response principles

**Use Case**: Shorter system context for agents that need role clarity without full domain knowledge

## Integration Patterns

### Pattern 1: Full Persona Integration (Recommended for Query Optimizer)

```python
from config.settings import BUSINESS_ANALYST_PERSONA_PROMPT, QUERY_OPTIMIZATION_TEMPLATE

# Combine persona with agent-specific prompt
full_system_prompt = f"{BUSINESS_ANALYST_PERSONA_PROMPT}\n\n{QUERY_OPTIMIZATION_TEMPLATE}"

# Use in LLM call
response = llm_provider.generate(
    messages=[
        {"role": "system", "content": full_system_prompt.format(date_context=date_context, user_query=user_query)}
    ]
)
```

**Why**: Query Optimizer benefits most from understanding CRM terminology to correctly parse and optimize user queries.

### Pattern 2: System Context Integration (Recommended for Response Formatter)

```python
from config.settings import BUSINESS_ANALYST_SYSTEM_PROMPT, RESPONSE_FORMATTER_TEMPLATE

# Combine system context with agent-specific prompt
full_system_prompt = f"{BUSINESS_ANALYST_SYSTEM_PROMPT}\n\n{RESPONSE_FORMATTER_TEMPLATE}"

# Use in LLM call
response = llm_provider.generate(
    messages=[
        {"role": "system", "content": full_system_prompt.format(optimized_query=query, extracted_data=data)}
    ]
)
```

**Why**: Response Formatter needs business context to generate insights and recommendations but doesn't need full domain definitions.

### Pattern 3: Direct Usage (For General Q&A or Fallback)

```python
from config.settings import BUSINESS_ANALYST_PERSONA_PROMPT

# Use persona directly for general CRM questions
response = llm_provider.generate(
    messages=[
        {"role": "system", "content": BUSINESS_ANALYST_PERSONA_PROMPT},
        {"role": "user", "content": "What is pipeline coverage and why does it matter?"}
    ]
)
```

**Why**: Enables the system to answer general CRM questions without data retrieval.

## Usage in Current Architecture

### Current Agent Prompts

1. **QueryOptimizerAgent** ([`agents/query_optimizer.py`](../agents/query_optimizer.py))
   - **Should Use**: `BUSINESS_ANALYST_PERSONA_PROMPT` prepended to `QUERY_OPTIMIZATION_TEMPLATE`
   - **Reason**: Needs to understand business terminology to correctly parse user intent

2. **DataExtractorAgent** ([`agents/data_extractor.py`](../agents/data_extractor.py))
   - **Should Use**: `BUSINESS_ANALYST_SYSTEM_PROMPT` prepended to `DATA_EXTRACTOR_PROMPT_TEMPLATE` (optional)
   - **Reason**: Primarily technical but benefits from understanding business context for tool selection

3. **ResponseFormatterAgent** ([`agents/response_formatter.py`](../agents/response_formatter.py))
   - **Should Use**: `BUSINESS_ANALYST_PERSONA_PROMPT` prepended to `RESPONSE_FORMATTER_TEMPLATE`
   - **Reason**: Needs full business context to generate insights and recommendations

## Implementation Example

### Before (Without Persona)
```python
class QueryOptimizerAgent:
    def __init__(self, llm_provider, template):
        self.llm_provider = llm_provider
        self.template = template

    def optimize(self, user_query, date_context):
        prompt = self.template.format(
            date_context=date_context,
            user_query=user_query
        )
        return self.llm_provider.generate([{"role": "system", "content": prompt}])
```

### After (With Persona)
```python
from config.settings import BUSINESS_ANALYST_PERSONA_PROMPT

class QueryOptimizerAgent:
    def __init__(self, llm_provider, template, use_persona=True):
        self.llm_provider = llm_provider
        self.template = template
        self.use_persona = use_persona

        # Prepend persona to template
        if self.use_persona:
            self.full_template = f"{BUSINESS_ANALYST_PERSONA_PROMPT}\n\n{self.template}"
        else:
            self.full_template = self.template

    def optimize(self, user_query, date_context):
        prompt = self.full_template.format(
            date_context=date_context,
            user_query=user_query
        )
        return self.llm_provider.generate([{"role": "system", "content": prompt}])
```

## Benefits

### 1. Improved Query Understanding
**Before**: "Show me pipeline health"
- Agent might not understand what metrics constitute "health"

**After**: With persona
- Agent understands pipeline health = stage distribution + velocity + coverage + win rates
- Generates comprehensive query covering all relevant metrics

### 2. Better Term Recognition
**Before**: "Find stale deals"
- Unclear what "stale" means, might interpret inconsistently

**After**: With persona
- "Stale" = No activity for 60+ days (defined in persona)
- Consistent interpretation across all queries

### 3. Contextual Awareness
**Before**: "Who are my top customers?"
- Returns list of companies by revenue only

**After**: With persona
- Understands "top customers" implies multiple dimensions
- Returns companies ranked by revenue, with deal count, engagement, and recency
- Identifies concentration risk if applicable

### 4. Actionable Insights
**Before**: "23 closed deals worth $847,500"
- Raw data only

**After**: With persona
- Adds average deal size calculation
- Compares to previous period
- Identifies top performers
- Provides recommendations based on patterns

### 5. General CRM Q&A
**Before**: Can only answer data queries
- "What is CAC?" → Cannot answer (no data operation)

**After**: With persona
- "What is CAC?" → Explains Customer Acquisition Cost
- "How do I improve close rate?" → Provides CRM best practices
- "What is a good pipeline coverage?" → Gives industry benchmarks

## Configuration

The persona is available in [`config/settings.py`](../config/settings.py):

```python
from config.settings import (
    BUSINESS_ANALYST_PERSONA_PROMPT,      # Full domain knowledge
    BUSINESS_ANALYST_SYSTEM_PROMPT,       # Shorter system context
    QUERY_OPTIMIZATION_TEMPLATE,
    DATA_EXTRACTOR_PROMPT_TEMPLATE
)
```

## Best Practices

### 1. **When to Use Full Persona**
- Agents that parse natural language (Query Optimizer)
- Agents that generate business insights (Response Formatter)
- General Q&A endpoints (future chatbot interface)

### 2. **When to Use System Context**
- Agents that need role awareness but not full domain definitions
- APIs with token constraints
- Performance-critical operations

### 3. **When to Skip Persona**
- Pure technical operations (database queries, API calls)
- Operations that don't involve natural language
- Testing isolated components

### 4. **Combining Prompts**
Always prepend persona to agent-specific prompts:
```python
full_prompt = f"{PERSONA}\n\n{AGENT_SPECIFIC_PROMPT}"
```

Never interleave - keep persona as foundational context.

### 5. **Token Management**
- Full persona ≈ 2,000 tokens
- System context ≈ 300 tokens
- Consider trade-offs for your use case
- For most CRM queries, the improved accuracy justifies the token cost

## Maintenance

### Updating the Persona

When updating CRM domain knowledge:

1. Edit [`prompts/business_analyst_persona.py`](../prompts/business_analyst_persona.py)
2. Add new terms, metrics, or business logic
3. Update examples if needed
4. No code changes needed (automatically picked up via imports)

### Version Control

The persona should evolve with your CRM:
- Add industry-specific terminology as needed
- Update default interpretations based on user feedback
- Refine business logic rules based on actual patterns

### Testing

Test persona effectiveness by:
1. **Query Understanding**: Track how many queries are correctly parsed
2. **Insight Quality**: Evaluate if responses include meaningful insights
3. **User Satisfaction**: Monitor if users find responses helpful
4. **Edge Cases**: Test with ambiguous or unclear queries

## Examples

### Example 1: Query Understanding

**User Query**: "Show me at-risk customers"

**Without Persona**:
```json
{
  "intent": "search",
  "entities": {"companies": ["at-risk"]},
  "filters": {}
}
```
❌ Misinterprets "at-risk" as a company name

**With Persona**:
```json
{
  "intent": "analyze",
  "entities": {
    "companies": ["status:customer"],
    "deals": [],
    "interactions": ["low_frequency"]
  },
  "filters": {"engagement": "low", "sort_by": "revenue_desc"},
  "optimized_query": "Find high-value customers with declining engagement (no interactions in 30+ days or negative signals) ranked by revenue."
}
```
✅ Correctly interprets business concept

### Example 2: Response Generation

**Extracted Data**:
```json
[
  {"company": "TechCorp", "revenue": 125000, "deals": 8, "last_activity": "2024-10-28"},
  {"company": "StartupXYZ", "revenue": 85000, "deals": 5, "last_activity": "2024-08-15"}
]
```

**Without Persona**:
```markdown
## Top Customers

| Company | Revenue | Deals |
|---------|---------|-------|
| TechCorp | 125000 | 8 |
| StartupXYZ | 85000 | 5 |
```
❌ No insights, just raw data

**With Persona**:
```markdown
## Top Customer Analysis

**Summary**: 2 customers account for $210,000 in revenue. One customer shows engagement risk.

### Revenue Distribution

| Company | Revenue | Deals | Last Activity | Status |
|---------|---------|-------|---------------|--------|
| TechCorp | $125,000 | 8 | 3 days ago | ✅ Active |
| StartupXYZ | $85,000 | 5 | 77 days ago | ⚠️ At Risk |

### Key Insights
- **Engagement Risk**: StartupXYZ has had no activity for 77 days despite $85K revenue
- **High Performance**: TechCorp shows strong engagement (8 deals, recent activity)
- **Revenue Concentration**: 60% from TechCorp (potential risk)

**Recommendations**:
- **Immediate**: Schedule check-in with StartupXYZ to prevent churn
- **Upsell**: TechCorp's high engagement indicates expansion opportunity
- **Diversification**: Reduce dependency on top customer
```
✅ Adds insights, context, and actionable recommendations

## Summary

The Business Analyst Persona is a critical component that transforms your AI Analyst from a data retrieval system into a true business intelligence advisor. By providing comprehensive CRM domain knowledge, it enables:

- More accurate query interpretation
- Richer, insight-driven responses
- Consistent business terminology
- Actionable recommendations
- General CRM Q&A capabilities

**Next Steps**:
1. Review the persona content in [`prompts/business_analyst_persona.py`](../prompts/business_analyst_persona.py)
2. Integrate into your agents using the patterns above
3. Test with real user queries
4. Refine based on feedback and observed patterns

For questions or improvements, refer to the main [AI Analyst Service Roadmap](archive/AI_ANALYST_SERVICE_ROADMAP.md).
