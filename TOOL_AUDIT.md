# Ally Tool Audit
> GraphQL API coverage mapping, gaps, merge candidates, and new tool suggestions.
> Generated: April 2026. Pick up from here.

---

## GraphQL → Tool Coverage Map

### PEOPLE
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `getWorkspacePeople` | `list_people_in_workspace`, `resolve_person_name` | ✅ |
| `getPerson` | `get_person_by_id` | ✅ |
| `getPeopleByGroup` | `list_people_in_group` | ✅ but filter/sort not exposed — see §Filter Gap |
| `getPeopleByWorkspaceView` | — | ❌ GAP — see §Filter Gap |
| `createPerson` | `create_person` | ✅ |
| `bulkCreatePeople` | `bulk_create_people` | ✅ |
| `updatePerson` | `update_person` | ✅ |
| `addPersonToCompany` | `add_person_to_company` | ✅ |
| `removePersonFromCompany` | `remove_person_from_company` | ✅ |
| `createGroupPeople` | `add_person_to_group` | ✅ |
| `deleteGroupPeople` / `deleteGroupPeoples` | `remove_person_from_group` | ✅ |
| `deletePeoples` | — | ❌ GAP |
| `getPersonProfileStats` | — | ❌ GAP |
| `doesPersonWithGivenURLExists` | — | ❌ (low priority) |
| Avatar mutations | — | ❌ (skip) |

### COMPANY
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `getWorkspaceCompany` | `list_companies_in_workspace`, `resolve_company_name` | ✅ |
| `getOneCompany` | `get_company_by_id` | ✅ |
| `getCompaniesByGroup` | `list_companies_in_group` | ✅ but filter/sort not exposed — see §Filter Gap |
| `getCompaniesByWorkspaceView` | — | ❌ GAP — see §Filter Gap |
| `createCompany` | `create_company` | ✅ |
| `bulkCreateCompanies` | `bulk_create_companies` | ✅ |
| `updateCompany` | `update_company` | ✅ |
| `createGroupCompany` | `add_company_to_group` | ✅ |
| `deleteGroupCompany` / `deleteGroupCompanies` | `remove_company_from_group` | ✅ |
| `deleteCompanies` | — | ❌ GAP |
| `getCompanyProfileStats` | — | ❌ GAP |
| `doesCompanyWithGivenURLExists` | — | ❌ (low priority) |
| Avatar mutations | — | ❌ (skip) |

### DEALS (entire domain unrepresented)
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `getDeals` | — | ❌ GAP — supports full filter/sort, see §Filter Gap |
| `getDeal` | — | ❌ GAP |
| `createDeal` | — | ❌ GAP |
| `updateDeal` | — | ❌ GAP |
| `deleteDeals` | — | ❌ GAP |
| `attachDeal` | — | ❌ GAP |
| `removeDeal` | — | ❌ GAP |

### GROUPS / VIEWS / COLUMNS
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `GetGroups` | `list_groups_in_workspace`, `get_group_by_id`, `search_group_by_name`, `resolve_group_name` | ✅ |
| `GetGroupWithPeopleColumns` / `GetGroupWithCompanyColumns` | `get_group_columns` | ✅ |
| `GetSelectOptionsByColumnId` | `get_column_options` | ✅ |
| Pipeline status options | `get_pipeline_status_options` | ✅ |
| Entities by status | `get_entities_by_status` | ✅ |
| Column name resolver | `resolve_column_by_name` | ✅ |
| `CreateGroup` | `create_group` | ✅ |
| `UpdateGroup` | `update_group` | ✅ |
| `CreateView` | `create_view_in_group` | ✅ |
| `update_column_value` mutation | — | ❌ GAP (listed in ONBOARDING as existing, not implemented) |
| `deleteGroups` / `deleteViews` | — | ❌ (low priority) |

### NOTES
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `notes` | `list_notes`, `get_note` | ✅ |
| `note` | `get_note` | ✅ |
| `createNote` | `create_note` | ✅ |
| `updateNote` | `update_note` | ✅ |
| `deleteNote` | `delete_note` | ✅ |
| Attachment queries/mutations | — | ❌ (skip for now) |

### REMINDERS
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `reminders` | `list_reminders` | ✅ |
| `reminder` | `get_reminder` | ✅ |
| `createReminder` | `create_reminder` | ✅ |
| `updateReminder` | `update_reminder` | ✅ |
| `deleteReminder` | `delete_reminder` | ✅ |
| `upcomingReminders` | — | ❌ GAP |
| `myReminders` | — | ❌ GAP |
| `addUserToReminder` / `removeUserFromReminder` | — | ❌ (low priority) |

### OBJECT MEMORY
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `objectMemories` | `get_object_memories` | ✅ |
| `createObjectMemory` | `save_object_memory` | ✅ |
| `updateObjectMemory` | — | ❌ GAP |
| `deleteObjectMemory` | — | ❌ GAP |

### EMAIL (CRM outreach)
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `GetPersonEmails` / `GetCompanyEmails` | `listEmailsFromPerson`, `listEmailsFromCompany`, `get_email_thread` | ✅ |
| `GetEmailTemplates` | `list_email_templates`, `search_email_templates` | ✅ |
| `CreateEmailDraft` + `SendEmailDraft` | `draft_email`, `send_email` | ✅ |
| Campaign emails (`emails`, `createEmail`, etc.) | — | ❌ (different system, skip) |

### WORKSPACE / USER
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `getEntityCustomInstructions` | `get_entity_instructions` | ✅ |
| `getWorkspaceCustomInstructions` | Used in `routes.py` (not a tool) | — |
| `getWorkspaceMembers` | — | ❌ GAP |
| `currentLoggedInUser` | Used in `routes.py` (not a tool) | — |

### MESSAGING / WHATSAPP (entire domain unrepresented)
| GraphQL API | Ally Tool | Status |
|-------------|-----------|--------|
| `messagingConversations` | — | ❌ GAP |
| `messagingMessages` | — | ❌ GAP |
| `sendMessagingTextMessage` | — | ❌ GAP |
| `sendMessagingTemplateMessage` | — | ❌ GAP |
| All other messaging mutations | — | ❌ (low priority) |

---

## Filter / Sort System — Key Finding

> The backend already has a fully built filter + sort engine. The agent just never uses it.
> This is the single highest-leverage gap in the entire tool layer.

### What the backend supports

Every entity listing query (`getCompaniesByGroup`, `getPeopleByGroup`, `getCompaniesByWorkspaceView`, `getPeopleByWorkspaceView`, `getDeals`) accepts a `FilterInput`:

```typescript
FilterInput {
  logicalOperator: AND | OR
  conditions: [{
    field: "global.{columnId}"    // workspace-level custom column
    field: "custom.{columnId}"    // group-scoped or deal column
    field: "name" | "createdAt"   // standard fields
    operator: greater_than | less_than | between | contains | is_one_of
              | this_week | this_month | this_year | before | after | ...
    value: string[]
  }]
  sortBy: [{ field: "global.{columnId}", order: "asc" | "desc" }]
}
```

Source: `backend/libs/features/company/src/lib/dto/filter-args.ts`

### What this unlocks

| Query example | How agent solves it today | How it should work |
|---|---|---|
| "Which company has highest revenue?" | N+1 `get_company_by_id` calls, wrong answer | `getCompaniesByGroup(filter: { sortBy: [{ field: "global.revenue_col_id", order: "desc" }] })` → 1 call |
| "Show companies added this week" | Can't — no date filter | `filter: { conditions: [{ field: "createdAt", operator: "this_week" }] }` → 1 call |
| "Find people with status = Qualified" | `get_entities_by_status` (SELECT only) | `getPeopleByGroup(filter: { conditions: [{ field: "global.status_col_id", operator: "is_one_of", value: ["Qualified"] }] })` → 1 call |
| "Deals over $50k not closed" | Impossible | `getDeals(filter: { logicalOperator: AND, conditions: [{ field: "custom.deal_size_id", operator: "greater_than", value: ["50000"] }, { field: "custom.status_id", operator: "not_equals", value: ["Closed"] }] })` → 1 call |

### Filter capability by query

| Query | Custom columns | Global columns | Sort | Time operators |
|---|---|---|---|---|
| `getCompaniesByGroup` | ✅ group-scoped | ✅ `global.*` | ✅ | ✅ |
| `getCompaniesByWorkspaceView` | ❌ | ✅ `global.*` only | ✅ | ✅ |
| `getPeopleByGroup` | ✅ group-scoped | ✅ `global.*` | ✅ | ✅ |
| `getPeopleByWorkspaceView` | ❌ | ✅ `global.*` only | ✅ | ✅ |
| `getDeals` | ✅ `custom.*` | ❌ | ✅ | ✅ |

### Tools needed to expose this

These are **tool upgrades + additions**, not new backend APIs:

| Tool | Change needed |
|------|---------------|
| `list_companies_in_group` | Add `filter` + `sort_by` params, pass through to `getCompaniesByGroup` |
| `list_people_in_group` | Add `filter` + `sort_by` params, pass through to `getPeopleByGroup` |
| `query_companies` (new) | New tool wrapping `getCompaniesByWorkspaceView` with full filter support |
| `query_people` (new) | New tool wrapping `getPeopleByWorkspaceView` with full filter support |
| `query_deals` (new) | New tool wrapping `getDeals` with full filter/sort — also unlocks entire deal domain |

The agent also needs to know column IDs before it can filter. Existing flow:
1. `get_group_columns(group_id)` → find column ID for "Revenue"
2. `list_companies_in_group(group_id, sort_by=[{field: "global.{id}", order: "desc"}])` → ranked result

Total: **2 tool calls** for any "rank/filter by custom column" query, regardless of workspace size.

---

## New Tools to Add

### Critical — Filter/Sort Exposure (no new backend work needed)
| Tool | GraphQL API | What it unlocks |
|------|-------------|-----------------|
| Upgrade `list_companies_in_group` | `getCompaniesByGroup` | Filter + sort by any custom column |
| Upgrade `list_people_in_group` | `getPeopleByGroup` | Filter + sort by any custom column |
| `query_companies` (new) | `getCompaniesByWorkspaceView` | Workspace-wide filtered company queries |
| `query_people` (new) | `getPeopleByWorkspaceView` | Workspace-wide filtered people queries |
| `query_deals` (new) | `getDeals` | Entire deal domain + filter/sort |

### High Priority — Missing CRUD
| Tool | GraphQL API | Reason |
|------|-------------|--------|
| `delete_person` | `deletePeoples` | Core CRM op — completely missing |
| `delete_company` | `deleteCompanies` | Core CRM op — completely missing |
| `update_column_value` | Column value mutation | In ONBOARDING as existing, not implemented |
| `create_deal` / `update_deal` / `attach_deal` | `createDeal`, `updateDeal`, `attachDeal` | Pipeline management |

### Medium Priority
| Tool | GraphQL API | Reason |
|------|-------------|--------|
| `get_profile_stats` | `getPersonProfileStats`, `getCompanyProfileStats` | Engagement summary in one call |
| `get_upcoming_reminders` | `upcomingReminders` | "What's due this week?" |
| `list_workspace_members` | `getWorkspaceMembers` | Ownership / assignment queries |
| `update_object_memory` | `updateObjectMemory` | Memories can be created but never corrected |
| `delete_object_memory` | `deleteObjectMemory` | Stale memories accumulate with no removal |

### Low Priority / Future
| Tool | GraphQL API | Reason |
|------|-------------|--------|
| `send_whatsapp_message` | `sendMessagingTextMessage` | WhatsApp outreach alongside email |
| `list_whatsapp_conversations` | `messagingConversations` | Messaging history access |

---

## Merge Candidates (Reduce Tool Count / Token Usage)

### 1. Unify 3 resolvers → 1
**Before:** `resolve_company_name`, `resolve_person_name`, `resolve_group_name` (3 always-loaded tools)  
**After:** `resolve_entity(name, entity_type: company|person|group)`  
**Saves:** ~2 tool definitions from always-loaded context (~100 tokens every request)

### 2. Group membership management → 1 tool
**Before:** `add_person_to_group`, `remove_person_from_group`, `add_company_to_group`, `remove_company_from_group` (4 tools)  
**After:** `manage_group_membership(entity_id, entity_type: person|company, group_id, action: add|remove)`  
**Saves:** 3 tool definitions. "Add person + company to same group" drops from 2 calls to 1.

### 3. list + search per entity type → find
**Before:** `list_companies_in_workspace` + `search_company_by_name` / `list_people_in_workspace` + `search_person_by_name`  
**After:** `find_companies(search?: string, group_id?: string)` / `find_people(search?: string, group_id?: string)`  
**Saves:** 2 tool definitions + eliminates separate list-then-search pattern.  
**Note:** Both already fall back to same underlying query — safe merge.

### 4. get_note + list_notes → get_notes
**Before:** Agent calls `list_notes(entity)` then `get_note(entity, search_text)` — two sequential tool calls  
**After:** `get_notes(entity_id, entity_type, search_text?: string)` — returns all or filtered  
**Saves:** Eliminates the two-step list-then-get pattern.

### 5. get_reminder + list_reminders → get_reminders
Same pattern as notes.  
**After:** `get_reminders(entity_id?: string, entity_type?: string, search_title?: string)`

### 6. Person-company linking → 1 tool
**Before:** `add_person_to_company`, `remove_person_from_company`  
**After:** `manage_company_relationship(person_id, company_id, action: add|remove)`  
**Saves:** 1 tool definition.

### 7. draft_email + send_email → compose_email
**Before:** `draft_email` then `send_email` — second call internally re-creates the draft, redundant GraphQL calls  
**After:** `compose_email(to, subject, body, template_id?)` — draft → confirm → send in one tool  
**Saves:** 1 tool call per email send + removes duplicated internal GraphQL calls.

---

## Intent Classification Upgrade

Current system (`intent.py`): pure regex. Maps keywords to `List[ToolCategory]`.

**Problem:** Multi-intent queries under-load tools. Example:
> "Find the best performing company in our pipeline and draft a follow-up email to their CEO"

Needs `COMPANIES + COLUMNS + PEOPLE + EMAIL`. Regex catches COMPANIES and EMAIL, misses COLUMNS and PEOPLE. Agent runs with wrong toolset, gives degraded answer.

**Proposed fix:** Replace regex with a lightweight LLM pre-classification call before the main agent runs.

```python
# Current flow
categories = classify_intent(message)  # regex, ~0ms, ~0 cost

# Proposed flow  
categories = await classify_intent_llm(message)  # LITE tier, ~200ms, ~$0.0001
```

- Use LITE tier model (same as greetings) — cheap, fast
- Single prompt: "Given this message, which tool categories are needed? Choose from: [list]. Return JSON array."
- Cache result — same message in same conversation doesn't re-classify
- Fallback to regex if LLM call fails

**What this unlocks:** Any natural language query that spans multiple domains routes correctly without the user having to phrase things in CRM-keyword language. The tools were always there — the router just wasn't smart enough to load them.

**Cost impact:** Adds one LITE call (~200 tokens) per non-greeting message. At current LITE pricing this is negligible. The main agent call already costs 10-50x more.

---

## Counts

| Metric | Number |
|--------|--------|
| Currently mapped APIs | ~45 |
| Filter/sort tools to upgrade (no backend work) | 5 |
| New tools to build (backend APIs exist) | ~10 |
| Merge candidates | 7 |
| Potential net tool definition reduction | ~10 |
| Query classes unlocked by filter exposure | All rank/filter/sort queries (currently impossible) |
