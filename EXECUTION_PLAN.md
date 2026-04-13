# Ally Tool Audit — Execution Plan & Progress Tracker
> Reference: TOOL_AUDIT.md
> Started: April 2026
> How to use: Update STATUS field when starting/finishing each task. Add session notes at bottom.

---

## Status Legend
- `[ ]` — not started
- `[~]` — in progress
- `[x]` — done
- `[-]` — skipped / deferred

---

## Phase 1 — Filter / Sort Exposure
> Highest leverage. No backend changes. Pure tool layer additions/upgrades.
> Unlocks: rank by custom column, filter by date/status/value, all analytical list queries.

### Pre-work (do once before any Phase 1 task)
- [ ] **P1-0** — Read `src/tools/read_tools.py` sections for `list_companies_in_group` and `list_people_in_group` to understand current GraphQL query shapes and return formatting. Confirm the `filter` arg shape expected by `getCompaniesByGroup` / `getPeopleByGroup`.
  - Files: `src/tools/read_tools.py`
  - Backend ref: `backend/libs/features/company/src/lib/dto/filter-args.ts`

---

### Tasks

- [ ] **P1-1** — Upgrade `list_companies_in_group`
  - File: `src/tools/read_tools.py`
  - Change: Add optional `filter_conditions` and `sort_by` params. Build `FilterInput` dict and pass to `getCompaniesByGroup` GraphQL query.
  - Param shape:
    ```python
    filter_conditions: list[dict] | None  
    # [{"field": "global.{col_id}", "operator": "greater_than", "value": ["1000"]}]
    sort_by: list[dict] | None            
    # [{"field": "global.{col_id}", "order": "desc"}]
    ```
  - Notes: Keep existing behavior when both params are None (backward compatible).

- [ ] **P1-2** — Upgrade `list_people_in_group`
  - File: `src/tools/read_tools.py`
  - Change: Same as P1-1, pass `FilterInput` to `getPeopleByGroup`.
  - Notes: Identical pattern to P1-1.

- [ ] **P1-3** — New tool `query_companies`
  - File: `src/tools/read_tools.py`
  - Wraps: `getCompaniesByWorkspaceView`
  - Purpose: Workspace-wide company query with full filter/sort. Use when user isn't scoped to a specific group.
  - Params: `filter_conditions`, `sort_by`, `page`, `limit`
  - Register in: `get_company_read_tools()` in `read_tools.py` + `__init__.py` exports
  - Notes: Global columns only (`global.{col_id}`) — document this limitation in the tool docstring.

- [ ] **P1-4** — New tool `query_people`
  - File: `src/tools/read_tools.py`
  - Wraps: `getPeopleByWorkspaceView`
  - Purpose: Workspace-wide people query with full filter/sort.
  - Params: `filter_conditions`, `sort_by`, `page`, `limit`
  - Register in: `get_people_read_tools()` + `__init__.py`
  - Notes: Same global-columns-only limitation as P1-3.

- [ ] **P1-5** — New tool `query_deals` (+ deal read tools)
  - File: `src/tools/read_tools.py` (or new `deal_tools.py`)
  - Wraps: `getDeals`, `getDeal`
  - Tools to create: `list_deals(filter_conditions, sort_by, column_id, page, limit)` and `get_deal(deal_id)`
  - Register: Add new `ToolCategory.DEALS` in `__init__.py`, add to `TOOL_REGISTRY`, add intent patterns in `src/agent/intent.py`
  - Notes: `getDeals` requires `columnId` (pipeline column) — agent needs to call `get_group_columns` first to get it. Document this in tool docstring.

- [ ] **P1-6** — Update intent patterns for filter queries
  - File: `src/agent/intent.py`
  - Change: Add patterns that load COLUMNS alongside COMPANIES/PEOPLE when query implies filtering/sorting by a column value. Examples: "best", "highest", "lowest", "most", "ranked", "sorted by", "filter by", "over $", "less than".
  - Notes: These patterns ensure `get_group_columns` + `resolve_column_by_name` are available when needed for filter construction.

---

## Phase 2 — Missing CRUD
> Fills critical gaps. Each is a self-contained addition.

- [ ] **P2-1** — New tool `delete_person`
  - File: `src/tools/update_tools.py` (destructive ops live here)
  - Wraps: `deletePeoples` mutation
  - Must use: `request_delete_confirmation()` before executing
  - Params: `person_id: str`, `person_name: str` (for confirmation display)
  - Register: `get_update_tools()`
  - Intent patterns: add "delete person", "remove contact", "remove person" to `intent.py` → UPDATE

- [ ] **P2-2** — New tool `delete_company`
  - File: `src/tools/update_tools.py`
  - Wraps: `deleteCompanies` mutation
  - Must use: `request_delete_confirmation()` before executing
  - Params: `company_id: str`, `company_name: str`
  - Register: `get_update_tools()`
  - Intent patterns: add "delete company", "remove company" → UPDATE

- [ ] **P2-3** — Verify / implement `update_column_value`
  - File: `src/tools/update_tools.py`
  - Status: `update_company_column_value` and `update_person_column_value` exist (lines 675, 814) but ONBOARDING says `update_column_value` is missing. Read both functions — confirm they're registered and working, or unify into one `update_column_value(entity_id, entity_type, column_id, value)` tool.
  - Action: Read lines 675–952 of `update_tools.py` first, then decide.

- [ ] **P2-4** — Deal CRUD tools
  - File: `src/tools/create_tools.py` (create), `src/tools/update_tools.py` (update/delete/attach)
  - Tools:
    - `create_deal(name, column_id)` → wraps `createDeal`
    - `update_deal(deal_id, name)` → wraps `updateDeal`
    - `delete_deal(deal_id, deal_name)` → wraps `deleteDeals`, needs confirmation
    - `attach_deal(deal_id, person_id?, company_id?)` → wraps `attachDeal`
    - `remove_deal(deal_id, person_id?, company_id?)` → wraps `removeDeal`
  - Register: Under `ToolCategory.DEALS` created in P1-5
  - Notes: `createDeal` requires `columnId` (the pipeline column) — agent must resolve it first.

---

## Phase 3 — Medium Priority Additions
> Each independently useful. No dependencies on Phase 1 or 2.

- [x] **P3-1** — New tool `get_profile_stats`
  - File: `src/tools/read_tools.py`
  - Wraps: `getPersonProfileStats` + `getCompanyProfileStats`
  - Params: `entity_id: str`, `entity_type: "PERSON" | "COMPANY"`
  - Returns: notes count, reminders count, interaction count, last interaction date
  - Register: add to both `get_company_read_tools()` and `get_people_read_tools()`
  - Unlocks: "How engaged are we with Acme?" in one call instead of fetching full entity

- [x] **P3-2** — New tool `get_upcoming_reminders`
  - File: `src/tools/reminder_tools.py`
  - Wraps: `upcomingReminders` query
  - Params: `limit: int = 10`
  - Returns: time-sorted list of upcoming reminders with entity links
  - Register: `get_reminder_tools()`
  - Unlocks: "What do I have coming up?" / "What's due this week?"

- [x] **P3-3** — New tool `list_workspace_members`
  - File: `src/tools/read_tools.py`
  - Wraps: `getWorkspaceMembers`
  - Params: none (uses workspace_id from context)
  - Returns: list of members with id, name, email, role
  - Register: add to `get_resolver_tools()` (small, always useful) or a new WORKSPACE category
  - Unlocks: "Who's on my team?", ownership/assignment queries

- [x] **P3-4** — New tools `update_object_memory` + `delete_object_memory`
  - File: `src/tools/memory_tools.py`
  - Wraps: `updateObjectMemory`, `deleteObjectMemory`
  - `update_object_memory(memory_id, new_text, category?)` — call `get_object_memories` first to find ID
  - `delete_object_memory(memory_id)` — confirm stale memory ID with `get_object_memories` first
  - Register: `get_memory_tools()`

---

## Phase 4 — Tool Merges
> Refactoring. Do after all additions are stable. Each merge = deprecate old + introduce new.
> Strategy: add new merged tool first, then remove old ones in same PR.

- [x] **P4-1** — Unify resolvers: 3 → 1
  - Replace: `resolve_company_name`, `resolve_person_name`, `resolve_group_name`
  - New: `resolve_entity(name: str, entity_type: "company" | "person" | "group") -> str`
  - File: `src/tools/read_tools.py`
  - Impact: Always-loaded tools drop from 3 definitions to 1. ~100 token saving every request.
  - Update: `get_resolver_tools()`, all callers inside other tools that call resolve_* internally

- [x] **P4-2** — Group membership → 1 tool
  - Replace: `add_person_to_group`, `remove_person_from_group`, `add_company_to_group`, `remove_company_from_group`
  - New: `manage_group_membership(entity_id, entity_type: "person"|"company", group_id, action: "add"|"remove")`
  - File: `src/tools/update_tools.py`
  - Update: `get_update_tools()`, intent patterns

- [x] **P4-3** — list + search → find (companies + people)
  - Replace: `list_companies_in_workspace` + `search_company_by_name` → `find_companies(search?, group_id?)`
  - Replace: `list_people_in_workspace` + `search_person_by_name` → `find_people(search?, group_id?)`
  - File: `src/tools/read_tools.py`
  - Notes: Both pairs already fall back to same underlying GraphQL query. Safe merge.
  - Update: `get_company_read_tools()`, `get_people_read_tools()`

- [x] **P4-4** — Notes: get + list → single tool
  - Replace: `list_notes` + `get_note` → `get_notes(entity_id, entity_type, search_text?)`
  - File: `src/tools/note_tools.py`
  - Update: `get_note_tools()`

- [x] **P4-5** — Reminders: get + list → single tool
  - Replace: `list_reminders` + `get_reminder` → `get_reminders(entity_id?, entity_type?, search_title?)`
  - File: `src/tools/reminder_tools.py`
  - Update: `get_reminder_tools()`

- [x] **P4-6** — Person-company linking → 1 tool
  - Replace: `add_person_to_company` + `remove_person_from_company`
  - New: `manage_company_relationship(person_id, company_id, action: "add"|"remove")`
  - File: `src/tools/update_tools.py`

- [x] **P4-7** — Email: draft + send → compose
  - Replace: `draft_email` + `send_email`
  - New: `compose_email(to, subject, body, template_id?)` — handles draft → confirm → send internally
  - File: `src/tools/read_tools.py` (email section)
  - Notes: `send_email` currently re-creates the draft internally — eliminate that duplication.
  - Update: `get_email_tools()`

---

## Phase 5 — Intent Classification Upgrade
> Architectural change. Do last when all tools are stable.

- [x] **P5-1** — Replace regex classifier with LLM-based classifier
  - File: `src/agent/intent.py`
  - Change: Replace `classify_intent(message)` regex implementation with async LLM call using LITE tier.
  - Prompt: single-shot classification — given message, return JSON array of ToolCategory values.
  - Fallback: if LLM call fails or times out, fall back to current regex.
  - Model: same LITE tier used for greetings (~200 tokens in, ~50 out, ~$0.0001/call)
  - Keep: `is_greeting()` check — still regex (zero cost fast-path before LLM fires)
  - Update: `src/agent/graph.py` — `classify_intent` call is async now if not already

---

## File Change Index
> Quick reference — which files get touched in which phase.

| File | Phases |
|------|--------|
| `src/tools/read_tools.py` | P1-1, P1-2, P1-3, P1-4, P1-5, P3-1, P3-3, P4-1, P4-3, P4-7 |
| `src/tools/update_tools.py` | P2-1, P2-2, P2-3, P2-4, P4-2, P4-6 |
| `src/tools/create_tools.py` | P2-4 |
| `src/tools/note_tools.py` | P4-4 |
| `src/tools/reminder_tools.py` | P3-2, P4-5 |
| `src/tools/memory_tools.py` | P3-4 |
| `src/tools/__init__.py` | P1-3, P1-4, P1-5, P4-1, P4-2, P4-3, P4-4, P4-5, P4-6, P4-7 |
| `src/agent/intent.py` | P1-6, P2-1, P2-2, P5-1 |
| `src/agent/graph.py` | P5-1 (if classify_intent becomes async) |

---

## Session Log
> Add an entry each session: date, tasks completed, blockers, next task to pick up.

### Session 1 — April 2026
- Created TOOL_AUDIT.md and EXECUTION_PLAN.md
- Mapped all GraphQL APIs to existing tools
- Identified filter/sort system already exists in backend
- Identified 3 structural gaps beyond the audit (aggregation, time-scoped activity, intent classification)

### Session 2 — April 2026
- Completed entire Phase 1 (P1-0 through P1-6)
- Upgraded `list_companies_in_group` + `list_people_in_group` with filter/sort params + inline column value display
- Added `query_companies` + `query_people` tools (workspace-wide filtered queries)
- Created `deal_tools.py` with `list_deals` + `get_deal`, registered `ToolCategory.DEALS`
- Added 30 analytical intent patterns (best/highest/top N/this week/etc.) that auto-load COLUMNS alongside entity types
- 67 total tools now registered (was ~54)
- All tests passing
### Session 6 — April 2026
- Completed Phase 5 (P5-1)
- `classify_intent` is now async — calls LITE-tier LLM with a 3s timeout
- Module-level cached LLM instance (initialized once, reused on all requests)
- Regex classifier renamed to `_regex_classify` — fires automatically on LLM timeout/error
- Prompt covers all 13 categories with examples for edge cases (analytical, delete, attach)
- `graph.py` updated: `await classify_intent(message)` (one-character change, no architecture impact)
- ALL 5 PHASES COMPLETE

### Session 5 — April 2026
- Completed Phase 4 (P4-1 through P4-7)
- P4-1: 3 resolver tools → `resolve_entity(name, entity_type)` (dispatches to internal helpers)
- P4-2: 4 group-membership tools → `manage_group_membership(entity_id, entity_type, group_id, action)`
- P4-3: `list_companies_in_workspace` + `search_company_by_name` → `find_companies(search?, page, limit)` (same for people)
- P4-4: `list_notes` + `get_note` → `get_notes(entity_name, entity_type, search_text?, limit)`
- P4-5: `list_reminders` + `get_reminder` → `get_reminders(entity_name?, entity_type?, search_title?, limit)`
- P4-6: `add_person_to_company` + `remove_person_from_company` → `manage_company_relationship(person_id, company_id, action)`
- P4-7: `draft_email` + `send_email` → `compose_email(to, subject, body, mode?, ...)` 
- Updated `prompts.py` and `deal_tools.py` docstrings to reference `resolve_entity`
- Net tool count: reduced from 74 → ~62 exposed tools (old helpers kept as internal async defs)
- **Next:** Phase 5 — P5-1 LLM intent classifier

### Session 4 — April 2026
- Completed Phase 3 (P3-1 through P3-4)
- Added `get_profile_stats` to `read_tools.py` — wraps `getPersonProfileStats` + `getCompanyProfileStats`, registered in both `_COMPANY_NAMES` and `_PEOPLE_NAMES`
- Added `list_workspace_members` to `read_tools.py` — wraps `getWorkspaceMembers`, registered in `_RESOLVER_NAMES` (always loaded)
- Added `get_upcoming_reminders` to `reminder_tools.py` — wraps `upcomingReminders`, sorted by due date
- Added `update_object_memory` + `delete_object_memory` to `memory_tools.py`
- **Next:** ALL PHASES COMPLETE ✓

### Session 3 — April 2026
- Completed Phase 2 (P2-1 through P2-4)
- Added `delete_person`, `delete_company` to `update_tools.py` — both with confirmation dialogs and DELETED change markers
- Verified `update_company_column_value` + `update_person_column_value` exist and are registered (P2-3 was a false gap)
- Added full deal CRUD to `deal_tools.py`: `create_deal`, `update_deal`, `delete_deal`, `attach_deal`, `remove_deal`
- Updated intent patterns: broadened UPDATE to catch "delete" + "attach"; added `ToolCategory.DEALS` to analytical co-load
- 74 total tools now registered (was 67)
- All tests passing
- **Next:** Start Phase 4 — tool merges (P4-1 through P4-7)
