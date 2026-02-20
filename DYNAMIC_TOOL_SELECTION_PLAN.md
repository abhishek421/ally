# Dynamic Tool Selection for Ally Agent

## RFC: Reducing Tool Token Overhead via Intent-Based Tool Filtering

**Author:** Abhi
**Date:** February 2026
**Status:** Proposal

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Current Architecture](#current-architecture)
- [Impact Analysis](#impact-analysis)
- [Industry Research](#industry-research)
- [Proposed Solution](#proposed-solution)
- [Implementation Plan](#implementation-plan)
- [Tool Category Mapping](#tool-category-mapping)
- [Intent Classification](#intent-classification)
- [Fallback & Safety](#fallback--safety)
- [Expected Results](#expected-results)
- [Risks & Mitigations](#risks--mitigations)
- [Future Improvements](#future-improvements)

---

## Problem Statement

We currently have **56 tools** registered with the Ally agent. Every single request — regardless of whether the user asks "List all companies" or "Create a reminder" — sends **all 56 tool definitions** (names, descriptions, parameter schemas) to the LLM. This is wasteful, expensive, and degrades quality.

### The Numbers

| Metric | Value |
|--------|-------|
| Total tools | **56** |
| Tool source files | 7 files, **6,108 lines** |
| Estimated tokens per tool definition | ~200-500 tokens (name + description + JSON schema) |
| Estimated total tool tokens per request | **15,000 - 30,000 tokens** |
| Typical conversation context | ~2,000 - 5,000 tokens |
| System prompt (base + instructions) | ~3,000 - 5,000 tokens |
| **Tool definitions as % of total input** | **~60-75%** |

The majority of every request's input tokens are tool definitions that are irrelevant to the user's query.

---

## Current Architecture

```
User Message
    ↓
routes.py: Resolve user profile, workspace/group instructions
    ↓
graph.py: get_all_tools(context)  ← Loads ALL 56 tools, every time
    ↓
create_react_agent(model=llm, tools=ALL_56_TOOLS, prompt=system_prompt)
    ↓
LLM receives: system_prompt + 56 tool schemas + conversation history
    ↓
LLM selects tool(s) and responds
```

The bottleneck is `get_all_tools()` in `src/tools/__init__.py`:

```python
def get_all_tools(context: ToolContext) -> list:
    tools = []
    tools.extend(get_read_tools(context))       # 28 tools
    tools.extend(get_create_tools(context))     # 4 tools
    tools.extend(get_update_tools(context))     # 12 tools
    tools.extend(get_research_tools(context))   # 1 tool
    tools.extend(get_context_tools(context))    # 1 tool
    tools.extend(get_reminder_tools(context))   # 5 tools
    tools.extend(get_note_tools(context))       # 5 tools
    return tools  # 56 tools total
```

---

## Impact Analysis

### Why This Hurts Us

**1. Token Cost**
Every request wastes ~15,000-30,000 tokens on irrelevant tool definitions. At scale, this adds up significantly in API costs.

**2. Response Quality**
Research shows that LLMs degrade in tool selection accuracy when presented with too many options:
- Models may pick the wrong tool among similar-sounding options
- Models may "hallucinate" tool names when overwhelmed
- Models sometimes take no action at all when selection is ambiguous
- The Berkeley Function Calling Leaderboard tests a maximum of 37 functions — we have 56

**3. Latency**
More input tokens = slower time-to-first-token. Tool definitions are processed on every LLM call, including intermediate ReAct steps (the agent may make 3-5 LLM calls per request).

**4. Context Window Pressure**
Tool definitions crowd out useful context — conversation history, custom instructions, and the system prompt compete for the same context window. With 56 tools, we have less room for what actually matters.

---

## Industry Research

### How This Problem is Solved at Scale

#### 1. Anthropic — Deferred Tool Search
Anthropic's own recommendation for 30+ tools: don't load them all upfront. Instead, let the model "search" for tools dynamically. Their implementation reduced token usage from **~77K to ~8.7K tokens (85% reduction)**.

> *Source: [MCP and the "too many tools" problem](https://demiliani.com/2025/09/04/model-context-protocol-and-the-too-many-tools-problem/)*

#### 2. LangGraph — Dynamic Tool Binding
LangGraph's official documentation demonstrates a pattern where tools are stored in a registry and only relevant tools are bound to the model based on the current state:

```python
def select_tools(state):
    """Dynamically select tools based on the last message."""
    relevant_tools = retriever.invoke(state["messages"][-1].content)
    return {"selected_tools": relevant_tools}
```

> *Source: [LangGraph - How to handle large numbers of tools](https://langchain-ai.github.io/langgraph/how-tos/many-tools/)*

#### 3. AutoTool (Research, Nov 2025)
Academic research proposing statistical methods over LLM inference for tool selection. Found "tool usage inertia" — tool selections follow predictable sequential patterns. Achieved efficient selection across 1,000+ tools.

> *Source: [AutoTool: Efficient Tool Selection for LLM Agents](https://arxiv.org/html/2511.14650v1)*

#### 4. Dynamic ReAct (Research, Sep 2025)
Proposed search-and-load mechanism for ReAct agents in large-tool environments. Achieved **50% reduction in tool loading** while maintaining task completion accuracy.

> *Source: [Dynamic ReAct: Scalable Tool Selection](https://arxiv.org/html/2509.20386v1)*

#### 5. Microsoft Foundry — Best Practices
Microsoft recommends: "Use dynamic tool activation — filter tools evaluated for a given context, narrowing down the set of tools ahead of time for a given interaction."

> *Source: [Tool best practices - Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/tool-best-practice)*

### Industry Thresholds

| Source | Recommended Max Tools |
|--------|----------------------|
| Anthropic | 30 (use deferred search beyond) |
| Cursor IDE | Hard limit of 40 |
| Berkeley Benchmark | Tests up to 37 |
| General consensus | 10-15 for optimal accuracy |

**We have 56. We need to act.**

---

## Proposed Solution

### Intent-Based Tool Filtering

We classify the user's intent **before** creating the agent, then load only the relevant tool categories. This is the simplest, most reliable approach for our scale and existing architecture.

### New Architecture

```
User Message
    ↓
routes.py: Resolve user profile, workspace/group instructions
    ↓
NEW → classify_intent(user_message) → returns list of tool categories
    ↓
NEW → get_tools_for_intent(context, categories) → returns 8-15 relevant tools
    ↓
create_react_agent(model=llm, tools=FILTERED_TOOLS, prompt=system_prompt)
    ↓
LLM receives: system_prompt + 8-15 tool schemas + conversation history
    ↓
LLM selects tool(s) and responds
```

### Why This Approach

| Approach | Complexity | Token Savings | Accuracy Risk | Fits Our Scale? |
|----------|-----------|---------------|---------------|-----------------|
| **Intent Classification (proposed)** | Low | 50-70% | Low | Yes (56 tools, 7 clear categories) |
| Embedding-based retrieval | Medium | 70-85% | Medium | Overkill for 56 tools |
| Hierarchical meta-tools | High | 60-80% | Medium | Requires agent redesign |
| Full deferred search (Anthropic-style) | High | 85% | Low | Better for 100+ tools |

Intent classification is the best fit because:
- Our 56 tools fall into **7 clean, non-overlapping categories**
- The categories map directly to user intent (read, create, update, notes, reminders, research)
- Implementation requires minimal changes to existing code
- No new infrastructure (embeddings, vector stores) needed
- Easy to test and validate

---

## Implementation Plan

### Phase 1: Tool Category Registry

**File:** `src/tools/__init__.py`

Define tool categories with their getter functions:

```python
from enum import Enum
from typing import Callable

class ToolCategory(str, Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    RESEARCH = "research"
    CONTEXT = "context"
    NOTES = "notes"
    REMINDERS = "reminders"

# Registry mapping categories to their tool getters
TOOL_REGISTRY: dict[ToolCategory, Callable] = {
    ToolCategory.READ: get_read_tools,
    ToolCategory.CREATE: get_create_tools,
    ToolCategory.UPDATE: get_update_tools,
    ToolCategory.RESEARCH: get_research_tools,
    ToolCategory.CONTEXT: get_context_tools,
    ToolCategory.NOTES: get_note_tools,
    ToolCategory.REMINDERS: get_reminder_tools,
}

# Tools that should ALWAYS be included (needed for name resolution)
ALWAYS_INCLUDE = {ToolCategory.READ}

def get_tools_for_categories(
    context: ToolContext,
    categories: list[ToolCategory],
) -> list:
    """Load only the tools for the specified categories."""
    # Always include READ tools (resolvers are needed for almost everything)
    all_categories = set(categories) | ALWAYS_INCLUDE

    tools = []
    for category in all_categories:
        getter = TOOL_REGISTRY[category]
        tools.extend(getter(context))

    return tools
```

> **Note on READ tools (28 tools):** The read category is the largest at 28 tools. As a follow-up optimization (Phase 3), we can split this into sub-categories: `READ_CORE` (resolvers + list/search, ~12 tools), `READ_EMAIL` (~6 tools), `READ_COLUMNS` (~5 tools), `READ_DETAIL` (~5 tools). For Phase 1, we keep READ as a single always-included category for safety.

---

### Phase 2: Intent Classifier

**New file:** `src/agent/intent.py`

Two options for classification — we recommend starting with **Option A** (rule-based) and upgrading to **Option B** (LLM-based) if needed.

#### Option A: Rule-Based Classification (Recommended Start)

Fast, zero-cost, deterministic. Handles 80%+ of queries correctly.

```python
import re
from src.tools import ToolCategory

# Keyword patterns mapped to tool categories
INTENT_PATTERNS: dict[ToolCategory, list[str]] = {
    ToolCategory.CREATE: [
        r"\bcreate\b", r"\badd\s+(?:a\s+)?(?:new\s+)?(?:company|person|contact|group|view)\b",
        r"\bmake\s+(?:a\s+)?(?:new\s+)?\b", r"\bset\s*up\b", r"\bnew\s+(?:company|person|contact|group)\b",
    ],
    ToolCategory.UPDATE: [
        r"\bupdate\b", r"\bchange\b", r"\bmodify\b", r"\bedit\b", r"\brename\b",
        r"\bmove\b", r"\bremove\b", r"\bdelete\s+(?:from|company|person)\b",
        r"\bset\s+(?:status|stage|priority)\b", r"\bassign\b", r"\bunlink\b",
        r"\badd\s+(?:to\s+group|to\s+company)\b",
    ],
    ToolCategory.NOTES: [
        r"\bnote\b", r"\bnotes\b", r"\bjot\b", r"\bmemo\b",
        r"\bwrite\s+(?:a\s+)?(?:note|memo)\b", r"\bannotate\b",
    ],
    ToolCategory.REMINDERS: [
        r"\bremind\b", r"\breminder\b", r"\breminders\b", r"\bschedule\b",
        r"\bdue\s+date\b", r"\bfollow\s*up\b", r"\balarm\b", r"\bdeadline\b",
    ],
    ToolCategory.RESEARCH: [
        r"\bresearch\b", r"\bsearch\s+(?:the\s+)?(?:web|internet|online)\b",
        r"\bfind\s+(?:out|info|information)\b", r"\blook\s*up\b",
        r"\bwhat\s+(?:is|are|does)\b.*\b(?:industry|market|funding|revenue)\b",
    ],
    ToolCategory.CONTEXT: [
        r"\binstructions?\b", r"\bguidelines?\b", r"\bworkspace\s+(?:rules|settings)\b",
    ],
}

def classify_intent(message: str) -> list[ToolCategory]:
    """
    Classify user message into tool categories using keyword matching.
    Returns list of matched categories. Falls back to all categories
    if no match is found.
    """
    message_lower = message.lower().strip()
    matched = set()

    for category, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                matched.add(category)
                break

    # Fallback: if nothing matched, it's likely a read/general query
    if not matched:
        return [ToolCategory.READ]

    return list(matched)
```

#### Option B: LLM-Based Classification (Future Upgrade)

Uses a fast, cheap LLM call (~100 tokens in, ~20 tokens out) to classify intent. More accurate for ambiguous queries.

```python
import json
from src.config import settings

CLASSIFICATION_PROMPT = """Classify this CRM assistant query into tool categories.

Categories:
- read: Listing, searching, viewing, getting details about companies/people/groups/emails
- create: Creating new companies, people, groups, views
- update: Updating, modifying, changing, moving, removing entities or their fields/status
- notes: Creating, viewing, editing, deleting notes
- reminders: Creating, viewing, editing, deleting reminders or follow-ups
- research: Web search, external information lookup, market research

Return ONLY a JSON array of matching category names. Example: ["read", "update"]

Query: "{message}"
Categories:"""

async def classify_intent_llm(message: str) -> list[ToolCategory]:
    """
    Use a fast LLM call to classify intent.
    Uses a small/fast model (e.g., GPT-4o-mini, Claude Haiku, Gemini Flash).
    """
    # Use a cheap, fast model for classification — NOT the main agent model
    response = await fast_llm.ainvoke(
        CLASSIFICATION_PROMPT.format(message=message)
    )

    categories = json.loads(response.content)
    return [ToolCategory(c) for c in categories]
```

#### Recommended Hybrid Approach

```python
async def classify_intent_hybrid(message: str) -> list[ToolCategory]:
    """
    Try rule-based first. If ambiguous or no match, fall back to LLM.
    """
    rule_result = classify_intent(message)

    # If rule-based returned a clear match, use it (fast path)
    if rule_result != [ToolCategory.READ]:  # READ is the default/fallback
        return rule_result

    # For ambiguous queries, use LLM classification
    # Only if message is complex enough to warrant it
    if len(message.split()) > 5:
        try:
            return await classify_intent_llm(message)
        except Exception:
            pass  # Fall through to rule-based result

    return rule_result
```

---

### Phase 3: Integration into Agent Graph

**File:** `src/agent/graph.py`

Modify `stream_agent()` to use filtered tools:

```python
# BEFORE (current code)
async def stream_agent(message: str, context: ToolContext, ...):
    tools = get_all_tools(context)  # Always 56 tools
    agent = create_react_agent(model=llm, tools=tools, ...)
    ...

# AFTER (with intent-based filtering)
async def stream_agent(message: str, context: ToolContext, ...):
    # Step 1: Classify intent
    categories = classify_intent(message)  # or classify_intent_hybrid()

    # Step 2: Load only relevant tools
    tools = get_tools_for_categories(context, categories)

    # Log for observability
    logger.info(
        f"Intent: {[c.value for c in categories]}, "
        f"Tools loaded: {len(tools)}/{56}"
    )

    # Step 3: Create agent with filtered tools
    agent = create_react_agent(model=llm, tools=tools, ...)
    ...
```

For `resume_agent()` (confirmation flow), we need to preserve the original categories:

```python
async def resume_agent(conversation_id: str, confirmation_response: dict, context: ToolContext, ...):
    # On resume, we need the same tools that were used in the original request.
    # Option 1: Store categories in the conversation state
    # Option 2: Load all tools on resume (safe fallback, confirmations are quick)
    tools = get_all_tools(context)  # Safe: resume is a single follow-up step
    ...
```

---

### Phase 4: Split READ Tools (Follow-up Optimization)

The READ category (28 tools) is still large. Split it into sub-categories:

```python
class ReadSubCategory(str, Enum):
    CORE = "read_core"        # resolvers + list + search (~12 tools)
    EMAIL = "read_email"      # email-related tools (~6 tools)
    COLUMNS = "read_columns"  # column/status/pipeline tools (~5 tools)
    DETAIL = "read_detail"    # get_*_by_id, get_current_page (~5 tools)
```

| Sub-Category | Tools | When to Include |
|-------------|-------|-----------------|
| `read_core` | `resolve_*_name`, `list_*_in_workspace`, `search_*_by_name`, `list_*_in_group` | Always (resolvers needed everywhere) |
| `read_email` | `listEmailsFromPerson`, `listEmailsFromCompany`, `get_email_thread`, `list_email_templates`, `search_email_templates`, `draft_email`, `send_email` | Only when query mentions email/send/draft |
| `read_columns` | `get_group_columns`, `get_column_options`, `get_pipeline_status_options`, `get_entities_by_status`, `resolve_column_by_name` | Only when query mentions status/column/pipeline/stage |
| `read_detail` | `get_company_by_id`, `get_person_by_id`, `get_group_by_id`, `get_current_page` | Only when query asks for details or page context |

This would bring the always-included tools from 28 down to ~12.

---

## Tool Category Mapping

### Complete Tool → Category Mapping (All 56 Tools)

#### READ — 28 tools (always included in Phase 1)

| Tool | Sub-Category |
|------|-------------|
| `resolve_company_name` | core |
| `resolve_person_name` | core |
| `resolve_group_name` | core |
| `list_companies_in_workspace` | core |
| `list_people_in_workspace` | core |
| `list_groups_in_workspace` | core |
| `list_companies_in_group` | core |
| `list_people_in_group` | core |
| `search_company_by_name` | core |
| `search_person_by_name` | core |
| `search_group_by_name` | core |
| `get_current_page` | core |
| `get_company_by_id` | detail |
| `get_person_by_id` | detail |
| `get_group_by_id` | detail |
| `listEmailsFromPerson` | email |
| `listEmailsFromCompany` | email |
| `get_email_thread` | email |
| `list_email_templates` | email |
| `search_email_templates` | email |
| `draft_email` | email |
| `send_email` | email |
| `get_group_columns` | columns |
| `get_column_options` | columns |
| `get_pipeline_status_options` | columns |
| `get_entities_by_status` | columns |
| `resolve_column_by_name` | columns |

#### CREATE — 4 tools

| Tool |
|------|
| `create_company` |
| `create_person` |
| `create_group` |
| `create_view_in_group` |

#### UPDATE — 12 tools

| Tool |
|------|
| `update_company` |
| `update_person` |
| `update_group` |
| `update_company_column_value` |
| `update_person_column_value` |
| `update_company_status` |
| `update_person_status` |
| `add_company_to_group` |
| `remove_company_from_group` |
| `add_person_to_group` |
| `remove_person_from_group` |
| `add_person_to_company` |
| `remove_person_from_company` |

#### NOTES — 5 tools

| Tool |
|------|
| `create_note` |
| `list_notes` |
| `get_note` |
| `update_note` |
| `delete_note` |

#### REMINDERS — 5 tools

| Tool |
|------|
| `create_reminder` |
| `list_reminders` |
| `get_reminder` |
| `update_reminder` |
| `delete_reminder` |

#### RESEARCH — 1 tool

| Tool |
|------|
| `web_search` |

#### CONTEXT — 1 tool

| Tool |
|------|
| `get_entity_instructions` |

---

## Intent Classification

### Example Query → Category Mapping

| User Query | Detected Categories | Tools Loaded |
|-----------|-------------------|-------------|
| "List all companies" | `[read]` | 28 (read) |
| "Create a new company called Acme" | `[read, create]` | 32 (read + create) |
| "Update John's job title" | `[read, update]` | 40 (read + update) |
| "Add a note for Acme Corp" | `[read, notes]` | 33 (read + notes) |
| "Set a reminder to follow up with Sarah tomorrow" | `[read, reminders]` | 33 (read + reminders) |
| "Research competitors in the AI space" | `[read, research]` | 29 (read + research) |
| "Move Acme from Leads to Qualified" | `[read, update]` | 40 (read + update) |
| "Send an email to John about the proposal" | `[read]` | 28 (read — emails are in read) |
| "Create a note and set a reminder for Acme" | `[read, notes, reminders]` | 38 (read + notes + reminders) |
| "Hello!" / "Thanks!" | `[read]` | 28 (read — default fallback) |

### With Phase 4 (READ split) — Projected

| User Query | Tools Loaded |
|-----------|-------------|
| "List all companies" | ~12 (read_core) |
| "Create a new company called Acme" | ~16 (read_core + create) |
| "Add a note for Acme Corp" | ~17 (read_core + notes) |
| "Set a reminder for tomorrow" | ~17 (read_core + reminders) |
| "Send an email to John" | ~19 (read_core + read_email) |
| "Change Acme's status to Qualified" | ~24 (read_core + read_columns + update) |

---

## Fallback & Safety

### Safety Mechanisms

1. **Default fallback**: If the classifier detects no intent, fall back to `[READ]` (safe — user is probably asking a question)

2. **Resume always loads all tools**: When resuming after confirmation (`resume_agent()`), load all 56 tools. This is safe because resume is typically a single follow-up step and we can't predict what the agent might need next.

3. **Conversation history consideration**: For multi-turn conversations, consider the full conversation context, not just the last message. If the user said "create a company" and then "also add a reminder," the second message should include reminders even though the first turn used create.

   ```python
   # For multi-turn: classify based on latest message + recent context
   def classify_with_history(
       current_message: str,
       recent_messages: list[str],  # last 2-3 messages
   ) -> list[ToolCategory]:
       # Classify current message
       current_categories = classify_intent(current_message)

       # Also check if recent messages suggest ongoing tool usage
       for msg in recent_messages:
           current_categories.extend(classify_intent(msg))

       return list(set(current_categories))
   ```

4. **Observability**: Log intent classification results for monitoring:
   ```python
   logger.info(f"Query: '{message[:50]}...' → Categories: {categories} → Tools: {len(tools)}")
   ```

5. **A/B testing**: Run the filtered agent alongside the full-tool agent to compare quality before fully switching over.

---

## Expected Results

### Token Savings Estimate

| Scenario | Current (56 tools) | Phase 1 (category filter) | Phase 4 (read split) |
|----------|-------------------|--------------------------|---------------------|
| "List companies" | ~25,000 tokens | ~12,000 tokens (read only) | ~5,000 tokens |
| "Create a company" | ~25,000 tokens | ~14,000 tokens (read + create) | ~7,000 tokens |
| "Add a note" | ~25,000 tokens | ~13,000 tokens (read + notes) | ~7,000 tokens |
| "Update status" | ~25,000 tokens | ~17,000 tokens (read + update) | ~10,000 tokens |
| **Average savings** | baseline | **~45-55% reduction** | **~65-75% reduction** |

### Other Benefits

| Metric | Expected Improvement |
|--------|---------------------|
| **API cost** | 45-75% reduction in input token costs |
| **Latency** | Faster time-to-first-token (fewer tokens to process) |
| **Accuracy** | Fewer irrelevant tools = less confusion for the LLM |
| **Context budget** | More room for conversation history and custom instructions |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Classifier misses a needed category | Medium | Agent can't find the right tool | Default fallback to READ; log misses; refine patterns |
| Multi-step queries span categories | Medium | Second step fails if tools not loaded | Include recent message history in classification |
| New tools added without updating classifier | Low | New tools never get loaded | CI check: every tool must have a category mapping |
| Rule-based patterns are too rigid | Low | False negatives on novel phrasing | Upgrade to hybrid (rule + LLM) classification |
| Resume flow breaks with filtered tools | Low | Confirmation fails | Always load all tools on resume |

---

## Future Improvements

### Short-term (after Phase 1 is stable)
- **Phase 4: Split READ** into sub-categories to further reduce the always-included set from 28 to ~12
- **Metrics dashboard**: Track tool token usage, classification accuracy, and tool selection distribution
- **Fine-tune patterns**: Use production query logs to improve keyword patterns

### Medium-term
- **LLM-based classification**: Upgrade to hybrid approach for ambiguous queries (use a cheap model like GPT-4o-mini / Claude Haiku / Gemini Flash)
- **Conversation-aware classification**: Factor in conversation history for multi-turn intent detection
- **Tool description optimization**: Shorten tool descriptions and parameter schemas to reduce per-tool token cost

### Long-term (100+ tools)
- **Embedding-based retrieval**: Vector similarity search over tool descriptions (like LangGraph's registry pattern)
- **Tool usage analytics**: Learn which tools are frequently used together and pre-bundle them
- **Deferred tool loading**: Anthropic-style tool search where the agent explicitly requests tools it needs

---

## Implementation Checklist

- [ ] **Phase 1**: Create `ToolCategory` enum and `TOOL_REGISTRY` in `__init__.py`
- [ ] **Phase 1**: Implement `get_tools_for_categories()` function
- [ ] **Phase 2**: Create `src/agent/intent.py` with rule-based `classify_intent()`
- [ ] **Phase 2**: Write unit tests for intent classification (cover all tool categories)
- [ ] **Phase 3**: Modify `stream_agent()` in `graph.py` to use filtered tools
- [ ] **Phase 3**: Keep `resume_agent()` loading all tools (safe fallback)
- [ ] **Phase 3**: Add logging for intent classification and tool counts
- [ ] **Testing**: Run side-by-side comparison with full tools vs filtered tools
- [ ] **Testing**: Test multi-turn conversations with category switching
- [ ] **Testing**: Test edge cases (greetings, ambiguous queries, multi-intent)
- [ ] **Phase 4** (follow-up): Split READ tools into sub-categories
- [ ] **Phase 4** (follow-up): Implement hybrid classification with LLM fallback

---

## References

- [LangGraph - How to handle large numbers of tools](https://langchain-ai.github.io/langgraph/how-tos/many-tools/)
- [How many tools can an AI Agent have?](https://achan2013.medium.com/how-many-tools-functions-can-an-ai-agent-has-21e0a82b7847)
- [AutoTool: Efficient Tool Selection for LLM Agents](https://arxiv.org/html/2511.14650v1)
- [MCP and the "too many tools" problem](https://demiliani.com/2025/09/04/model-context-protocol-and-the-too-many-tools-problem/)
- [How to Prevent MCP Tool Overload](https://www.lunar.dev/post/why-is-there-mcp-tool-overload-and-how-to-solve-it-for-your-ai-agents)
- [Dynamic ReAct: Scalable Tool Selection](https://arxiv.org/html/2509.20386v1)
- [Mastering Tool Calling: Best Practices for 2025](https://sparkco.ai/blog/mastering-tool-calling-best-practices-for-2025)
- [Tool best practices - Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/tool-best-practice)

---

*This plan is scoped for incremental delivery. Phase 1-3 can be shipped together as a single PR. Phase 4 is a follow-up optimization.*
