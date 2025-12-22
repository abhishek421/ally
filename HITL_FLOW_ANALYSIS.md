# Human-in-the-Loop (HITL) Flow Analysis

## Executive Summary

This document provides a comprehensive analysis of the Human-in-the-Loop (HITL) implementation in the Ally AI service. The implementation uses LangGraph's `interrupt()` pattern with PostgreSQL-backed checkpointing for state persistence, enabling the agent to pause execution and wait for user confirmation before performing sensitive operations.

---

## Table of Contents

1. [Current HITL Flow Architecture](#1-current-hitl-flow-architecture)
2. [HITL Trigger Conditions](#2-hitl-trigger-conditions)
3. [Technical Implementation Deep Dive](#3-technical-implementation-deep-dive)
4. [Critical Code Review](#4-critical-code-review)
5. [LangGraph Feature Evaluation](#5-langgraph-feature-evaluation)
6. [Implementation Gaps](#6-implementation-gaps)
7. [Alternative Implementation Approaches](#7-alternative-implementation-approaches)
8. [Value Proposition Gaps (User Perspective)](#8-value-proposition-gaps-user-perspective)
9. [Frontend Implementation Analysis](#9-frontend-implementation-analysis)
10. [Recommendations](#10-recommendations)

---

## 1. Current HITL Flow Architecture

### 1.1 High-Level Flow Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Frontend  │────▶│   /api/chat  │────▶│  stream_agent() │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
                                         ┌─────────────────┐
                                         │  Tool Execution │
                                         └────────┬────────┘
                                                   │
                           ┌───────────────────────┼───────────────────────┐
                           ▼                       ▼                       ▼
                    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
                    │   HITL      │         │   Direct    │         │   Continue  │
                    │  Required?  │         │   Execute   │         │   Agent     │
                    └──────┬──────┘         └─────────────┘         └─────────────┘
                           │ YES
                           ▼
                    ┌─────────────────┐
                    │   interrupt()   │
                    │   + Checkpoint  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  SSE Event:     │
                    │  confirmation_  │
                    │  required       │
                    └────────┬────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
   ┌─────────────┐                       ┌─────────────────┐
   │   Frontend  │                       │  State Persisted │
   │  Shows UI   │                       │  in PostgreSQL   │
   └──────┬──────┘                       └─────────────────┘
          │
          ▼
   ┌─────────────────┐
   │  POST /confirm  │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  resume_agent() │
   │  Command(resume)│
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  Tool Receives  │
   │  User Response  │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  Continue Flow  │
   │  or Cancel      │
   └─────────────────┘
```

### 1.2 Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Confirmation Types** | `src/tools/confirmation.py:14-19` | Defines 4 confirmation types: `CONFIRM_ACTION`, `SELECT_ONE`, `SELECT_MANY`, `CONFIRM_WITH_EDIT` |
| **Request/Response DTOs** | `src/tools/confirmation.py:22-103` | `ConfirmationRequest` and `ConfirmationResponse` dataclasses |
| **Core Interrupt** | `src/tools/confirmation.py:106-149` | `request_confirmation()` calls LangGraph's `interrupt()` |
| **Stream Handler** | `src/agent/graph.py:197-308` | `stream_agent()` detects `__interrupt__` chunks |
| **Resume Handler** | `src/agent/graph.py:310-414` | `resume_agent()` uses `Command(resume=...)` |
| **API Endpoints** | `src/api/routes.py:100-249` | `/chat` and `/chat/confirm` SSE endpoints |
| **Checkpointer** | `src/agent/graph.py:50-92` | PostgreSQL async checkpointer with fallback |

---

## 2. HITL Trigger Conditions

### 2.1 Currently Implemented Triggers

| Trigger | File:Line | Condition | Confirmation Type |
|---------|-----------|-----------|-------------------|
| **Entity Disambiguation** | `read_tools.py:964-984` | Multiple fuzzy matches with <15pt score gap | `SELECT_ONE` |
| **Create Company** | `create_tools.py:73-76` | Always before creation | `CONFIRM_ACTION` |
| **Create Person** | `create_tools.py:191-194` | Always before creation | `CONFIRM_ACTION` |
| **Create Group** | `create_tools.py:310-313` | Always before creation | `CONFIRM_ACTION` |
| **Update Company** | `update_tools.py:410-414` | Always before update | `CONFIRM_ACTION` |
| **Update Person** | `update_tools.py:506-510` | Always before update | `CONFIRM_ACTION` |
| **Column Value Update** | `update_tools.py:778-787` | Always for status changes | `CONFIRM_ACTION` |
| **Remove from Group** | `update_tools.py:113-117` | Always before removal | `CONFIRM_ACTION` |

### 2.2 Decision Logic Flowchart (Entity Resolution)

```
resolve_*_name(query)
        │
        ▼
┌───────────────────┐
│ Fuzzy Match Query │
│ Against All Items │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Calculate Scores  │
│ token_sort, partial,│
│ token_set, standard │
└─────────┬─────────┘
          │
          ▼
    ┌─────────────┐
    │ matches > 0 │───NO───▶ Return "Not Found"
    └──────┬──────┘
           │ YES
           ▼
    ┌─────────────────┐
    │ score_gap >= 15 │───YES──▶ Auto-select top match
    │  OR single match │
    └────────┬────────┘
             │ NO
             ▼
    ┌─────────────────┐
    │ request_entity_ │
    │ selection()     │
    │ (Shows options) │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ User Selects or │
    │ Cancels         │
    └─────────────────┘
```

---

## 3. Technical Implementation Deep Dive

### 3.1 The `request_confirmation()` Function

```python
# src/tools/confirmation.py:106-149
def request_confirmation(request: ConfirmationRequest) -> ConfirmationResponse:
    """Core function that pauses agent execution."""
    logger.info(f"Requesting confirmation: {request.title}")

    # This is the key LangGraph call - pauses execution
    response_data = interrupt(request.to_dict())

    # When resumed, parse the user's response
    if isinstance(response_data, dict):
        return ConfirmationResponse(
            confirmed=response_data.get("confirmed", False),
            selected_id=response_data.get("selected_id"),
            selected_ids=response_data.get("selected_ids"),
            feedback=response_data.get("feedback"),
            modified_data=response_data.get("modified_data"),
        )

    return ConfirmationResponse(confirmed=False)
```

**Key Points:**
- Uses LangGraph's `interrupt()` from `langgraph.types`
- Returns a `ConfirmationResponse` after resume
- Handles unexpected response types gracefully

### 3.2 Interrupt Detection in Streaming

```python
# src/agent/graph.py:239-250
async for chunk in agent.astream(...):
    # Check for interrupt FIRST (confirmation request from tools)
    if "__interrupt__" in chunk:
        interrupt_info = chunk["__interrupt__"]
        if interrupt_info and len(interrupt_info) > 0:
            interrupt_data = interrupt_info[0].value if hasattr(interrupt_info[0], 'value') else interrupt_info[0]
            yield {
                "type": "confirmation_required",
                "data": interrupt_data,
            }
            return  # Stop streaming, wait for user response
```

### 3.3 Resuming with Command Pattern

```python
# src/agent/graph.py:343-348
async for chunk in agent.astream(
    Command(resume=confirmation_response),  # Key resume pattern
    config=config,
    stream_mode="updates",
):
```

### 3.4 Checkpointer Lifecycle

```python
# src/agent/graph.py:50-92
async def get_checkpointer():
    global _checkpointer_context, _checkpointer

    if settings.DATABASE_URL_ALLY:
        _checkpointer_context = AsyncPostgresSaver.from_conn_string(...)
        _checkpointer = await _checkpointer_context.__aenter__()
        await _checkpointer.setup()  # Creates tables
        return _checkpointer

    # Fallback to in-memory (NOT production-safe)
    _memory_saver = MemorySaver()
    return _memory_saver
```

---

## 4. Critical Code Review

### 4.1 Strengths

#### A. Clean Separation of Concerns
- Confirmation logic is isolated in `confirmation.py`
- Tools only need to call helper functions
- Response parsing is centralized

#### B. Correct Use of Dynamic Interrupts
The implementation correctly uses `interrupt()` inside tools rather than static `interrupt_before`/`interrupt_after`:
```python
# CORRECT: Dynamic interrupt in tool
@tool
async def create_company(...):
    confirmation = request_create_confirmation(...)  # interrupt() inside
    if not confirmation.confirmed:
        return "Cancelled"
    # proceed with action
```

#### C. Proper Async Checkpointer
Uses `AsyncPostgresSaver` for production-grade persistence.

#### D. Nested Interrupt Handling
```python
# src/agent/graph.py:354-364
# Check for another interrupt FIRST (nested confirmation)
if "__interrupt__" in chunk:
    # Handle nested confirmations...
    return  # Stop and wait again
```

### 4.2 Issues & Risks

#### **CRITICAL: Exception Handling Around Interrupt**

❌ **Not Found:** The codebase does **not** wrap `interrupt()` in try/except, which is correct per LangGraph best practices.

However, there's a risk: If any tool wraps `request_confirmation()` in a try/except:

```python
# DANGEROUS PATTERN (not currently in code, but could be added):
try:
    confirmation = request_create_confirmation(...)
except Exception as e:
    # This would swallow the interrupt exception!
    return "Error occurred"
```

**Recommendation:** Add a code comment or lint rule to prevent this.

#### **MEDIUM: Missing Idempotency Before Interrupts**

Some tools perform API calls **before** the interrupt, which could cause issues on retry:

```python
# src/tools/update_tools.py:769-787
async def update_company_column_value(...):
    client = context.get_client()

    # API call BEFORE interrupt - runs again on resume!
    current_value_label, current_value_color = await _get_current_select_option_value(...)

    # Then interrupt
    confirmation = request_column_update_confirmation(...)
```

**Risk:** If the resume fails and retries, `_get_current_select_option_value()` runs again. While this is a read operation and safe, the pattern could cause issues if expanded.

**Recommendation:** Document that code before `interrupt()` must be idempotent.

#### **MEDIUM: No Interrupt Timeout/Expiry**

There's no mechanism to expire stale interrupts. If a user starts an action and never confirms:
- Checkpoint remains in PostgreSQL indefinitely
- Memory grows unbounded over time

**Recommendation:** Add a cleanup job for checkpoints older than N days.

#### **LOW: MemorySaver Fallback in Production**

```python
# src/agent/graph.py:86-92
if _memory_saver is None:
    _memory_saver = MemorySaver()
    logger.warning("Using in-memory checkpointer...")
```

This fallback is dangerous in production - interrupts won't survive server restarts.

**Recommendation:** Fail fast in production if PostgreSQL is unavailable.

#### **LOW: Hardcoded Score Gap Threshold**

```python
# src/tools/read_tools.py:964
if len(matches) == 1 or score_gap >= 15:
```

The `15` point threshold is magic number without configuration.

---

## 5. LangGraph Feature Evaluation

### 5.1 Features Used Correctly

| Feature | Usage | Verdict |
|---------|-------|---------|
| **Dynamic `interrupt()`** | `confirmation.py:135` | ✅ Correct - used inside tools, not compile-time |
| **`Command(resume=...)`** | `graph.py:346` | ✅ Correct - passes user response to resume |
| **`AsyncPostgresSaver`** | `graph.py:72` | ✅ Correct - production-grade persistence |
| **`stream_mode="updates"`** | `graph.py:234` | ✅ Correct - enables interrupt detection |
| **Thread-based isolation** | `graph.py:181-184` | ✅ Correct - `thread_id` = `conversation_id` |

### 5.2 Features NOT Used (Potential Opportunities)

| Feature | Current State | Potential Use |
|---------|---------------|---------------|
| **`interrupt_before`** | Not used | Could add for debugging in dev mode |
| **`interrupt_after`** | Not used | Could pause after all tool executions for audit |
| **Multi-interrupt resume** | Not used | Could batch multiple confirmations (LangGraph v0.4+) |
| **State rollback/replay** | Not used | Could allow "undo" for cancelled operations |
| **Checkpoint metadata** | Not used | Could store operation context for analytics |

### 5.3 LangGraph Best Practices Compliance

| Best Practice | Status | Notes |
|---------------|--------|-------|
| Avoid try/except around interrupt | ✅ Compliant | No wrapping found |
| Consistent interrupt ordering | ✅ Compliant | Each tool has single interrupt |
| JSON-serializable payloads | ✅ Compliant | Uses `.to_dict()` method |
| Idempotent pre-interrupt code | ⚠️ Partial | Some API calls before interrupt |
| Use persistent checkpointer | ✅ Compliant | PostgreSQL used |
| Handle resume values correctly | ✅ Compliant | Proper response parsing |

---

## 6. Implementation Gaps

### 6.1 Missing HITL Triggers

| Missing Case | Impact | User Expectation |
|--------------|--------|------------------|
| **Bulk operations** | HIGH | "Add 50 contacts to group" should confirm |
| **Permanent deletion** | CRITICAL | `delete_company()` doesn't exist but should have HITL |
| **Email/Communication actions** | HIGH | Sending emails needs confirmation |
| **Data export** | MEDIUM | Exporting sensitive data should confirm |
| **Permission changes** | HIGH | Changing privacy/sharing settings |
| **Irreversible changes** | HIGH | Merging duplicates, data migrations |

### 6.2 Missing Confirmation Types

The `CONFIRM_WITH_EDIT` type is defined but **never used**:

```python
class ConfirmationType(str, Enum):
    CONFIRM_WITH_EDIT = "confirm_with_edit"  # Defined but unused!
```

**Gap:** Users cannot modify draft data before confirmation.

### 6.3 Missing Feedback Loop

When user cancels:
```python
if not confirmation.confirmed:
    feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
    return f"Company creation cancelled by user.{feedback}"
```

The feedback is logged but **not acted upon**. The agent doesn't:
- Learn from cancellations
- Suggest modifications based on feedback
- Retry with adjusted parameters

### 6.4 No Batch Confirmation

Each entity gets individual confirmation. No way to:
- Confirm multiple items at once
- "Confirm all" for batch operations
- Selective approval from a list

---

## 7. Alternative Implementation Approaches

### 7.1 Approach Comparison

| Approach | Pros | Cons | When to Use |
|----------|------|------|-------------|
| **Current: Dynamic interrupt()** | Clean, in-tool logic, conditional | Requires careful exception handling | ✅ Best for current use case |
| **Static interrupt_before** | Simple, declarative | Can't be conditional, limited context | Debugging only |
| **Tool-level approval node** | Centralized logic | Complex graph structure | Very complex approval flows |
| **Client-side state machine** | UI-driven, no server state | No persistence, complex frontend | Simple apps |
| **Queue-based async** | Scales well, decoupled | Complex infrastructure | Enterprise/high-volume |

### 7.2 Alternative: Centralized Approval Node

```python
# Alternative architecture (NOT current implementation)
def build_graph():
    builder = StateGraph(State)

    # Centralized approval node
    builder.add_node("approval", approval_node)
    builder.add_node("tools", tool_executor)

    # All sensitive tools route through approval
    builder.add_conditional_edges(
        "tools",
        needs_approval,
        {True: "approval", False: "agent"}
    )
```

**Trade-offs:**
- ✅ Centralized approval logic
- ❌ Harder to customize per-tool
- ❌ More complex graph structure

### 7.3 Alternative: Event-Driven Confirmation

```python
# Publish-subscribe pattern
async def create_company(...):
    event = PendingActionEvent(
        action_type="create",
        entity_type="company",
        draft_data=draft_data,
    )
    await event_bus.publish(event)

    # Wait for approval event
    response = await event_bus.wait_for(
        f"approval:{event.id}",
        timeout=timedelta(hours=24)
    )
```

**Trade-offs:**
- ✅ Decoupled, async-native
- ✅ Can persist to message queue
- ❌ Complex infrastructure
- ❌ Harder to debug

### 7.4 Recommendation

**Keep current approach** with improvements:
1. Add missing confirmation triggers
2. Implement `CONFIRM_WITH_EDIT`
3. Add checkpoint expiry
4. Use feedback for retry suggestions

---

## 8. Value Proposition Gaps (User Perspective)

### 8.1 User Expectation Analysis

| User Scenario | Current Behavior | User Expectation | Gap |
|---------------|------------------|------------------|-----|
| "Create 10 companies from this list" | 10 individual confirmations | Single batch confirmation | 🔴 Major |
| "Delete company X" | Not implemented | Confirm with impact summary | 🔴 Critical |
| "Undo that last action" | Not possible | Rollback capability | 🔴 Major |
| "Change company name" | Shows `{name: "new"}` | Show `old → new` diff | 🟡 Minor |
| "Move 5 people to group Y" | 5 individual confirmations | Batch with item selection | 🔴 Major |
| "Merge John Smith duplicates" | Not implemented | Preview merge result | 🔴 Critical |
| "Send email to all contacts" | Not implemented | Recipient preview + confirm | 🔴 Critical |
| "Export contacts to CSV" | Not implemented | Confirm data scope | 🟡 Medium |

### 8.2 Confirmation UX Best Practices

#### What Users Expect from HITL:

1. **Clear Impact Statement**
   - ❌ Current: "I'll create company with: {name: Acme}"
   - ✅ Expected: "Create company 'Acme Corp' - this will be visible to all workspace members"

2. **Visual Diff for Updates**
   - ❌ Current: `{name: "new value"}`
   - ✅ Expected:
     ```
     Name: "Old Company" → "New Company"
     Email: (unchanged)
     Phone: (unchanged)
     ```

3. **Severity Indication**
   - ❌ Current: All confirmations look the same
   - ✅ Expected: Red warning for destructive, green for additive

4. **Undo Capability**
   - ❌ Current: No undo after confirmation
   - ✅ Expected: "Undo this action" option for N minutes

5. **Smart Defaults**
   - ❌ Current: Always requires explicit confirmation
   - ✅ Expected: "Skip confirmation for similar actions" preference

### 8.3 Recommended Confirmation Formats

#### For Creation:
```
┌────────────────────────────────────────┐
│ 🏢 Create Company                      │
├────────────────────────────────────────┤
│ Name: Acme Corporation                 │
│ Email: contact@acme.com               │
│ Phone: (555) 123-4567                  │
│                                        │
│ This company will be added to your    │
│ workspace and visible to all members.  │
├────────────────────────────────────────┤
│ [Cancel]              [Create Company] │
└────────────────────────────────────────┘
```

#### For Status Update:
```
┌────────────────────────────────────────┐
│ 📊 Update Status                       │
├────────────────────────────────────────┤
│ Company: OpenAI                        │
│ Group: Sales Pipeline                  │
│                                        │
│ Status: 🔵 New  →  🟢 Qualified        │
├────────────────────────────────────────┤
│ [Cancel]               [Update Status] │
└────────────────────────────────────────┘
```

#### For Batch Operations:
```
┌────────────────────────────────────────┐
│ 👥 Add to Group                        │
├────────────────────────────────────────┤
│ Adding 5 contacts to "VIP Customers":  │
│                                        │
│ ☑ John Smith                          │
│ ☑ Jane Doe                            │
│ ☑ Bob Wilson                          │
│ ☑ Alice Brown                         │
│ ☑ Charlie Davis                       │
│                                        │
│ [Select All] [Deselect All]           │
├────────────────────────────────────────┤
│ [Cancel]                [Add Selected] │
└────────────────────────────────────────┘
```

---

## 9. Frontend Implementation Analysis

### 9.1 Current Status

**Frontend code is NOT in this repository.** The frontend is a separate application (likely the main Allyos web app) that consumes this API.

### 9.2 Expected Frontend Integration Points

Based on the API contract:

#### SSE Event Types to Handle
```typescript
type SSEEvent =
  | { type: "tool_call"; data: { name: string; args: object } }
  | { type: "tool_result"; data: { name: string; result: string } }
  | { type: "response"; data: { content: string } }
  | { type: "confirmation_required"; data: ConfirmationRequest }
  | { type: "data_changed"; data: DataChange }
  | { type: "error"; data: { message: string } }
  | { type: "done"; data: {} };
```

#### Confirmation Request Structure
```typescript
interface ConfirmationRequest {
  confirmation_type: "confirm_action" | "select_one" | "select_many" | "confirm_with_edit";
  title: string;
  message: string;
  options?: Array<{
    id: string;
    label: string;
    description?: string;
    confidence?: "high" | "medium" | "low";
    metadata?: object;
  }>;
  draft_data?: Record<string, unknown>;
  entity_type?: "person" | "company" | "group";
  action_label?: string;
  allow_cancel_feedback?: boolean;
}
```

#### Confirmation Response Structure
```typescript
interface ConfirmationResponse {
  conversation_id: string;
  confirmed: boolean;
  selected_id?: string;
  selected_ids?: string[];
  feedback?: string;
  // modified_data not in API but defined in backend
}
```

### 9.3 Frontend Implementation Requirements

The frontend needs to implement:

1. **SSE Stream Consumer**
   - Parse and dispatch different event types
   - Handle connection drops and reconnection

2. **Confirmation Modal Component**
   - Render based on `confirmation_type`
   - Support multiple confirmation UIs:
     - Simple yes/no (`confirm_action`)
     - Radio button list (`select_one`)
     - Checkbox list (`select_many`)
     - Form with editable fields (`confirm_with_edit`)

3. **Draft Data Renderer**
   - Generic key-value display
   - Special rendering for status changes (`_is_status_change` flag)
   - Color badge support for select options

4. **Feedback Collection**
   - Optional text input on cancel
   - Submit feedback with confirmation response

### 9.4 Missing Frontend Features (Recommended)

1. **Loading States** - Show pending state while waiting for resume
2. **Timeout Handling** - User warning if confirmation takes too long
3. **Offline Support** - Queue confirmations for retry
4. **Keyboard Shortcuts** - Enter to confirm, Escape to cancel
5. **Accessibility** - ARIA labels, focus management
6. **Animation** - Smooth transitions for modal appear/dismiss

---

## 10. Recommendations

### 10.1 Immediate Fixes (P0)

| Issue | Fix | Effort |
|-------|-----|--------|
| Add checkpoint expiry | Background job to clean old checkpoints | 2 days |
| Implement delete confirmation | Add `delete_*` tools with HITL | 3 days |
| Fail fast in production | Remove MemorySaver fallback | 1 hour |

### 10.2 Short-term Improvements (P1)

| Issue | Fix | Effort |
|-------|-----|--------|
| Batch operations | Add `CONFIRM_BATCH` type with multi-select | 1 week |
| Visual diff for updates | Compare old/new values in confirmation | 3 days |
| Feedback actionability | Suggest retry based on feedback | 1 week |

### 10.3 Long-term Enhancements (P2)

| Issue | Fix | Effort |
|-------|-----|--------|
| Undo capability | Implement state rollback using checkpoints | 2 weeks |
| User preferences | "Skip similar confirmations" setting | 1 week |
| Analytics | Track confirmation rates, cancellation reasons | 1 week |
| Audit log | Log all confirmed/cancelled actions | 3 days |

### 10.4 Code Quality Improvements

1. **Add lint rule** to prevent try/except around interrupt calls
2. **Add tests** for:
   - Interrupt/resume roundtrip
   - Nested interrupts
   - Checkpoint persistence
   - Timeout scenarios
3. **Document** idempotency requirements for pre-interrupt code
4. **Configure** fuzzy match threshold externally

---

## Appendix A: File Reference

| File | Key Lines | Purpose |
|------|-----------|---------|
| `src/tools/confirmation.py` | All | Core HITL types and functions |
| `src/agent/graph.py` | 197-308, 310-414 | Stream/resume handlers |
| `src/api/routes.py` | 100-147, 197-249 | API endpoints |
| `src/tools/create_tools.py` | 73-80, 191-198 | Create confirmations |
| `src/tools/update_tools.py` | 113-121, 778-791 | Update/remove confirmations |
| `src/tools/read_tools.py` | 964-984 | Entity disambiguation |

## Appendix B: LangGraph Version Compatibility

This implementation requires:
- **LangGraph >= 0.2.0** for `AsyncPostgresSaver`
- **LangGraph >= 0.3.0** for dynamic `interrupt()` function
- **LangGraph >= 0.4.0** (optional) for multi-interrupt resume

Current dependencies should be verified against `requirements.txt` or `pyproject.toml`.

---

*Document generated: December 2024*
*Repository: analyst-ai (Ally AI Copilot)*
