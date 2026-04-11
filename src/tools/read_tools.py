"""READ tools for querying companies, people, and groups."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.context_var import get_tool_context
from src.tools.base import (
    ToolContext,
    LIST_MAX_RESULTS,
    format_company,
    format_company_compact,
    format_person,
    format_person_compact,
    format_group,
    format_group_compact,
    format_email,
    fuzzy_match_entities,
    get_best_match,
    format_fuzzy_suggestions,
)
from src.tools.confirmation import (
    request_entity_selection,
    ConfirmationType,
    ConfirmationRequest,
    ConfirmationResponse,
    request_confirmation,
)

try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    GraphInterrupt = None

logger = logging.getLogger(__name__)


def get_read_tools() -> list:
    """Get all READ tools.

    Returns:
        List of tool functions
    """
    
    async def list_companies_in_workspace(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
    ) -> str:
        """List companies in the workspace (compact). Use get_company_by_id for full details."""
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetWorkspaceCompany(
            $workspaceId: ID!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getWorkspaceCompany(
                workspaceId: $workspaceId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id
                    name
                    description
                    emails { value isPrimary }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
            })

            data = result.get("getWorkspaceCompany", {})
            companies = data.get("data") or []
            meta = data.get("meta") or {}

            if not companies:
                return "No companies found in this workspace."

            total = meta.get("total", len(companies))
            current_page = meta.get("page", 1)
            lines = [f"Found {total} companies (showing page {current_page}):"]
            for company in companies:
                lines.append(format_company_compact(company))

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} or search to narrow down)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error listing companies: {e}")
            return f"Error listing companies: {str(e)}"
        finally:
            await client.close()

    async def list_people_in_workspace(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
    ) -> str:
        """List people/contacts in the workspace (compact). Use get_person_by_id for full details."""
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetWorkspacePeople(
            $workspaceId: ID!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getWorkspacePeople(
                workspaceId: $workspaceId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id
                    firstName
                    lastName
                    jobTitle
                    emails { value isPrimary }
                    companyMetaData {
                        company { name }
                    }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
            })

            data = result.get("getWorkspacePeople", {})
            people = data.get("data") or []
            meta = data.get("meta") or {}

            if not people:
                return "No people found in this workspace."

            total = meta.get("total", len(people))
            current_page = meta.get("page", 1)
            lines = [f"Found {total} people (showing page {current_page}):"]
            for person in people:
                lines.append(format_person_compact(person))

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} or search to narrow down)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error listing people: {e}")
            return f"Error listing people: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_groups_in_workspace() -> str:
        """List all groups in the workspace (compact). Use get_group_by_id for full details."""
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                name
                type
                emoji
            }
        }
        """

        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
            })

            groups = result.get("getGroups") or []

            if not groups:
                return "No groups found in this workspace."

            total = len(groups)
            shown = groups[:LIST_MAX_RESULTS]
            lines = [f"Found {total} groups:"]
            for group in shown:
                lines.append(format_group_compact(group))

            if total > LIST_MAX_RESULTS:
                lines.append(f"(Showing first {LIST_MAX_RESULTS} of {total} — use resolve_group_name to find a specific group)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error listing groups: {e}")
            return f"Error listing groups: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_companies_in_group(
        group_id: str,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        filter_conditions: Optional[list] = None,
        sort_by: Optional[list] = None,
    ) -> str:
        """List companies in a specific group (compact). Use get_company_by_id for full details.

        Supports optional server-side filtering and sorting by any column value.

        filter_conditions: list of condition dicts, e.g.:
          [{"field": "global.<column_id>", "operator": "greater_than", "value": ["1000"]}]
          [{"field": "createdAt", "operator": "this_week"}]
          [{"field": "name", "operator": "contains", "value": ["acme"]}]

        sort_by: list of sort dicts, e.g.:
          [{"field": "global.<column_id>", "order": "desc"}]
          [{"field": "createdAt", "order": "asc"}]

        Field format for custom columns: "global.<column_id>" (use get_group_columns or
        resolve_column_by_name to get the column ID first).

        Available operators: contains, not_contains, equals, not_equals, starts_with,
        ends_with, is_empty, is_not_empty, is_one_of, is_not_one_of, greater_than,
        less_than, greater_than_or_equal, less_than_or_equal, between, not_between,
        before, after, this_week, this_month, this_year.

        Multiple conditions use AND logic by default.
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetCompaniesByGroup(
            $groupId: ID!
            $page: Int
            $limit: Int
            $search: String
            $filter: FilterInput
        ) {
            getCompaniesByGroup(
                groupId: $groupId
                page: $page
                limit: $limit
                search: $search
                filter: $filter
            ) {
                data {
                    id
                    name
                    description
                    emails { value isPrimary }
                    columnValues { columnId value }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        filter_input = None
        if filter_conditions or sort_by:
            filter_input = {
                "logicalOperator": "AND",
                "conditions": filter_conditions or [],
                "sortBy": sort_by or [],
            }

        try:
            result = await client.query(query, {
                "groupId": group_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
                "filter": filter_input,
            })

            data = result.get("getCompaniesByGroup") or {}
            companies = data.get("data") or []
            meta = data.get("meta") or {}

            if not companies:
                return "No companies found in this group."

            total = meta.get("total", len(companies))
            current_page = meta.get("page", 1)

            sort_note = ""
            if sort_by:
                sort_note = f" sorted by {sort_by[0].get('field', '')} ({sort_by[0].get('order', 'asc')})"
            filter_note = f" matching {len(filter_conditions)} filter(s)" if filter_conditions else ""
            lines = [f"Found {total} companies in group{filter_note}{sort_note} (showing page {current_page}):"]

            # Collect active column IDs from sort/filter for inline display
            active_col_ids = set()
            for s in (sort_by or []):
                field = s.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])
            for c in (filter_conditions or []):
                field = c.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])

            for company in companies:
                line = format_company_compact(company)
                if active_col_ids:
                    col_vals = company.get("columnValues") or []
                    extras = [
                        cv.get("value")
                        for cv in col_vals
                        if cv.get("columnId") in active_col_ids and cv.get("value")
                    ]
                    if extras:
                        line += f" [{', '.join(extras)}]"
                lines.append(line)

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} or search to narrow down)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error listing companies in group: {e}")
            return f"Error listing companies in group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_people_in_group(
        group_id: str,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        filter_conditions: Optional[list] = None,
        sort_by: Optional[list] = None,
    ) -> str:
        """List people in a specific group (compact). Use get_person_by_id for full details.

        Supports optional server-side filtering and sorting by any column value.

        filter_conditions: list of condition dicts, e.g.:
          [{"field": "global.<column_id>", "operator": "greater_than", "value": ["1000"]}]
          [{"field": "createdAt", "operator": "this_week"}]
          [{"field": "name", "operator": "contains", "value": ["john"]}]

        sort_by: list of sort dicts, e.g.:
          [{"field": "global.<column_id>", "order": "desc"}]
          [{"field": "createdAt", "order": "asc"}]

        Field format for custom columns: "global.<column_id>" (use get_group_columns or
        resolve_column_by_name to get the column ID first).

        Available operators: contains, not_contains, equals, not_equals, starts_with,
        ends_with, is_empty, is_not_empty, is_one_of, is_not_one_of, greater_than,
        less_than, greater_than_or_equal, less_than_or_equal, between, not_between,
        before, after, this_week, this_month, this_year.

        Multiple conditions use AND logic by default.
        """
        if not group_id:
            return "Error: group_id is required to list people in a group."
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetPeopleByGroup(
            $groupId: ID!
            $page: Int
            $limit: Int
            $search: String
            $filter: FilterInput
        ) {
            getPeopleByGroup(
                groupId: $groupId
                page: $page
                limit: $limit
                search: $search
                filter: $filter
            ) {
                data {
                    id
                    firstName
                    lastName
                    jobTitle
                    emails { value isPrimary }
                    companyMetaData {
                        company { name }
                    }
                    columnValues { columnId value }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        filter_input = None
        if filter_conditions or sort_by:
            filter_input = {
                "logicalOperator": "AND",
                "conditions": filter_conditions or [],
                "sortBy": sort_by or [],
            }

        try:
            result = await client.query(query, {
                "groupId": group_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
                "filter": filter_input,
            })

            data = result.get("getPeopleByGroup") or {}
            people = data.get("data") or []
            meta = data.get("meta") or {}

            if not people:
                return "No people found in this group."

            total = meta.get("total", len(people))
            current_page = meta.get("page", 1)

            sort_note = ""
            if sort_by:
                sort_note = f" sorted by {sort_by[0].get('field', '')} ({sort_by[0].get('order', 'asc')})"
            filter_note = f" matching {len(filter_conditions)} filter(s)" if filter_conditions else ""
            lines = [f"Found {total} people in group{filter_note}{sort_note} (showing page {current_page}):"]

            # Collect active column IDs from sort/filter for inline display
            active_col_ids = set()
            for s in (sort_by or []):
                field = s.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])
            for c in (filter_conditions or []):
                field = c.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])

            for person in people:
                line = format_person_compact(person)
                if active_col_ids:
                    col_vals = person.get("columnValues") or []
                    extras = [
                        cv.get("value")
                        for cv in col_vals
                        if cv.get("columnId") in active_col_ids and cv.get("value")
                    ]
                    if extras:
                        line += f" [{', '.join(extras)}]"
                lines.append(line)

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} or search to narrow down)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error listing people in group: {e}")
            return f"Error listing people in group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_company_by_id(company_id: str) -> str:
        """Get full details for a company by ID (emails, phones, addresses, groups, people)."""
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query GetOneCompany($companyId: ID!) {
            getOneCompany(companyId: $companyId) {
                id
                name
                description
                imageUrl
                avatarUrl
                privacyLevel
                createdAt
                updatedAt
                emails { id value type isPrimary }
                phoneNumbers { id value type isPrimary }
                addresses { id value type isPrimary }
                urls { id label value isPrimary }
                peopleMetaData {
                    people { id firstName lastName jobTitle }
                }
                groupCompany {
                    group { id name emoji }
                }
            }
        }
        """
        
        try:
            result = await client.query(query, {"companyId": company_id})
            company = result.get("getOneCompany")
            
            if not company:
                return f"Company with ID {company_id} not found."
            
            lines = [format_company(company)]
            
            # Add URLs
            urls = company.get("urls", [])
            if urls:
                url_strs = [f"{u.get('label', 'URL')}: {u.get('value', '')}" for u in urls]
                lines.append(f"  URLs: {', '.join(url_strs)}")
            
            # Add addresses
            addresses = company.get("addresses", [])
            if addresses:
                addr_strs = [a.get("value", "") for a in addresses if a.get("value")]
                if addr_strs:
                    lines.append(f"  Addresses: {'; '.join(addr_strs)}")
            
            # Add associated people
            people_meta = company.get("peopleMetaData", [])
            if people_meta:
                people_names = [
                    f"{p['people']['firstName']} {p['people'].get('lastName', '')}".strip()
                    for p in people_meta
                    if p.get("people")
                ]
                if people_names:
                    lines.append(f"  Associated People: {', '.join(people_names)}")
            
            # Add groups
            groups = company.get("groupCompany", [])
            if groups:
                group_names = [
                    f"{g['group'].get('emoji', '')} {g['group']['name']}".strip()
                    for g in groups
                    if g.get("group")
                ]
                if group_names:
                    lines.append(f"  Groups: {', '.join(group_names)}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting company: {e}")
            return f"Error getting company: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_person_by_id(person_id: str) -> str:
        """Get full details for a person by ID (emails, phones, addresses, groups, companies)."""
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query GetPerson($peopleId: ID!) {
            getPerson(peopleId: $peopleId) {
                id
                firstName
                lastName
                jobTitle
                description
                dateOfBirth
                gender
                avatarUrl
                imageUrl
                privacyLevel
                createdAt
                updatedAt
                emails { id value type isPrimary }
                phoneNumbers { id value type isPrimary }
                addresses { id type value isPrimary }
                urls { id label value isPrimary }
                companyMetaData {
                    company { id name imageUrl }
                }
                groupPeople {
                    group { id name emoji }
                }
            }
        }
        """
        
        try:
            result = await client.query(query, {"peopleId": person_id})
            person = result.get("getPerson")
            
            if not person:
                return f"Person with ID {person_id} not found."
            
            lines = [format_person(person)]
            
            # Add URLs
            urls = person.get("urls", [])
            if urls:
                url_strs = [f"{u.get('label', 'URL')}: {u.get('value', '')}" for u in urls]
                lines.append(f"  URLs: {', '.join(url_strs)}")
            
            # Add addresses
            addresses = person.get("addresses", [])
            if addresses:
                addr_strs = [a.get("value", "") for a in addresses if a.get("value")]
                if addr_strs:
                    lines.append(f"  Addresses: {'; '.join(addr_strs)}")
            
            # Add groups
            groups = person.get("groupPeople", [])
            if groups:
                group_names = [
                    f"{g['group'].get('emoji', '')} {g['group']['name']}".strip()
                    for g in groups
                    if g.get("group")
                ]
                if group_names:
                    lines.append(f"  Groups: {', '.join(group_names)}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting person: {e}")
            return f"Error getting person: {str(e)}"
        finally:
            await client.close()

    async def search_company_by_name(query: str, limit: int = 10) -> str:
        """Search companies by name using fuzzy matching. Returns list of matches with IDs."""
        context = get_tool_context()
        client = context.get_client()
        
        gql_query = """
        query Autocomplete(
            $workspaceId: String!
            $query: String!
            $types: [String!]
            $size: Int
        ) {
            autocomplete(
                workspaceId: $workspaceId
                query: $query
                types: $types
                size: $size
            ) {
                id
                text
                type
                score
            }
        }
        """
        
        # Try autocomplete first (uses Elasticsearch)
        autocomplete_results = []
        try:
            result = await client.query(gql_query, {
                "workspaceId": context.workspace_id,
                "query": query,
                "types": ["company"],
                "size": limit,
            })
            autocomplete_results = result.get("autocomplete", [])
        except Exception as e:
            # Autocomplete may fail (e.g., Elasticsearch index not found), continue to fallback
            logger.debug(f"Autocomplete not available, using direct query: {e}")
        
        try:
            if autocomplete_results:
                lines = [f"Found {len(autocomplete_results)} companies matching '{query}':\n"]
                for item in autocomplete_results:
                    lines.append(f"- **{item.get('text', 'Unknown')}** (ID: {item.get('id', 'N/A')})")
                return "\n".join(lines)
            
            # Fallback: try listing companies and fuzzy matching
            list_query = """
            query GetWorkspaceCompany(
                $workspaceId: ID!
                $limit: Int
                $search: String
            ) {
                getWorkspaceCompany(
                    workspaceId: $workspaceId
                    limit: $limit
                    search: $search
                ) {
                    data {
                        id
                        name
                    }
                }
            }
            """

            result = await client.query(list_query, {
                "workspaceId": context.workspace_id,
                "limit": limit,
                "search": query,
            })
            
            companies = (result.get("getWorkspaceCompany") or {}).get("data") or []
            
            if not companies:
                return f"No companies found matching '{query}'."
            
            lines = [f"Found {len(companies)} companies matching '{query}':\n"]
            for company in companies:
                lines.append(f"- **{company.get('name', 'Unknown')}** (ID: {company.get('id', 'N/A')})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return f"Error searching companies: {str(e)}"
        finally:
            await client.close()

    async def search_person_by_name(query: str, limit: int = 10) -> str:
        """Search people by name using fuzzy matching. Returns list of matches with IDs."""
        context = get_tool_context()
        client = context.get_client()
        
        gql_query = """
        query Autocomplete(
            $workspaceId: String!
            $query: String!
            $types: [String!]
            $size: Int
        ) {
            autocomplete(
                workspaceId: $workspaceId
                query: $query
                types: $types
                size: $size
            ) {
                id
                text
                type
                score
            }
        }
        """
        
        # Try autocomplete first (uses Elasticsearch)
        autocomplete_results = []
        try:
            result = await client.query(gql_query, {
                "workspaceId": context.workspace_id,
                "query": query,
                "types": ["person"],
                "size": limit,
            })
            autocomplete_results = result.get("autocomplete", [])
        except Exception as e:
            # Autocomplete may fail (e.g., Elasticsearch index not found), continue to fallback
            logger.debug(f"Autocomplete not available, using direct query: {e}")
        
        try:
            if autocomplete_results:
                lines = [f"Found {len(autocomplete_results)} people matching '{query}':\n"]
                for item in autocomplete_results:
                    lines.append(f"- **{item.get('text', 'Unknown')}** (ID: {item.get('id', 'N/A')})")
                return "\n".join(lines)
            
            # Fallback: try listing people and using search
            list_query = """
            query GetWorkspacePeople(
                $workspaceId: ID!
                $limit: Int
                $search: String
            ) {
                getWorkspacePeople(
                    workspaceId: $workspaceId
                    limit: $limit
                    search: $search
                ) {
                    data {
                        id
                        firstName
                        lastName
                    }
                }
            }
            """

            result = await client.query(list_query, {
                "workspaceId": context.workspace_id,
                "limit": limit,
                "search": query,
            })
            
            people = (result.get("getWorkspacePeople") or {}).get("data") or []
            
            if not people:
                return f"No people found matching '{query}'."
            
            lines = [f"Found {len(people)} people matching '{query}':\n"]
            for person in people:
                full_name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip() or "Unknown"
                lines.append(f"- **{full_name}** (ID: {person.get('id', 'N/A')})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error searching people: {e}")
            return f"Error searching people: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_group_by_id(group_id: str) -> str:
        """Get full details for a group by ID."""
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                name
                type
                description
                emoji
                isPrivate
                isFavourite
                views {
                    id
                    name
                    type
                    targetEntity
                }
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = result.get("getGroups") or []
            group = next((g for g in groups if g.get("id") == group_id), None)
            
            if not group:
                return f"Group with ID {group_id} not found."
            
            return format_group(group)
            
        except Exception as e:
            logger.error(f"Error getting group: {e}")
            return f"Error getting group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def search_group_by_name(query: str) -> str:
        """Search groups by name with fuzzy matching. Returns list of matches with IDs."""
        context = get_tool_context()
        client = context.get_client()
        
        gql_query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                name
                type
                description
                emoji
                isPrivate
            }
        }
        """
        
        try:
            result = await client.query(gql_query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = result.get("getGroups") or []
            
            if not groups:
                return "No groups found in this workspace."
            
            # Use fuzzy matching to find groups
            matches = fuzzy_match_entities(query, groups, name_key="name", threshold=50.0, limit=5)
            
            if not matches:
                # Try even looser matching if nothing found
                matches = fuzzy_match_entities(query, groups, name_key="name", threshold=30.0, limit=3)
            
            if not matches:
                # List all groups as suggestions
                group_names = [g.get("name", "") for g in groups[:10]]
                return f"No groups found matching '{query}'. Available groups: {', '.join(group_names)}"
            
            lines = [f"Found {len(matches)} groups matching '{query}':\n"]
            for group, score in matches:
                emoji = group.get("emoji", "")
                name = group.get("name", "Unknown")
                group_type = group.get("type", "Unknown")
                confidence = "✓ exact" if score >= 95 else "~ close" if score >= 75 else "? fuzzy"
                lines.append(f"- **{emoji} {name}** (ID: {group.get('id', 'N/A')}, Type: {group_type}) [{confidence}]")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error searching groups: {e}")
            return f"Error searching groups: {str(e)}"
        finally:
            await client.close()

    async def resolve_company_name(name: str) -> str:
        """Resolve company name to ID (handles typos, partial names, case). Call before any company operation."""
        context = get_tool_context()
        client = context.get_client()

        # Use getWorkspaceCompany with search parameter (same as frontend)
        search_query = """
        query GetWorkspaceCompany(
            $workspaceId: ID!
            $limit: Int
            $search: String
        ) {
            getWorkspaceCompany(
                workspaceId: $workspaceId
                limit: $limit
                search: $search
            ) {
                data {
                    id
                    name
                }
            }
        }
        """

        try:
            # First, try searching with the full name
            result = await client.query(search_query, {
                "workspaceId": context.workspace_id,
                "limit": 20,
                "search": name,
            })

            companies = (result.get("getWorkspaceCompany") or {}).get("data") or []

            # If full name search yields no results, try searching each name part separately
            if not companies:
                name_parts = name.strip().split()
                if len(name_parts) > 1:
                    logger.info(f"Full name search for '{name}' returned 0 results, trying individual parts: {name_parts}")
                    combined_results = {}  # Use dict for deduplication by ID

                    for part in name_parts:
                        if len(part) < 2:  # Skip single-character parts
                            continue
                        part_result = await client.query(search_query, {
                            "workspaceId": context.workspace_id,
                            "limit": 20,
                            "search": part,
                        })
                        part_hits = (part_result.get("getWorkspaceCompany") or {}).get("data") or []
                        for hit in part_hits:
                            if hit.get("id") and hit["id"] not in combined_results:
                                combined_results[hit["id"]] = hit

                    companies = list(combined_results.values())
                    if companies:
                        logger.info(f"Split-name search found {len(companies)} candidates")

            if companies:
                # Apply fuzzy matching for better results
                matches = fuzzy_match_entities(name, companies, name_key="name", threshold=50.0, limit=5)

                if matches:
                    # Check if we have a single unambiguous match
                    top_score = matches[0][1]
                    second_score = matches[1][1] if len(matches) > 1 else 0
                    score_gap = top_score - second_score

                    if len(matches) == 1 or score_gap >= 15:
                        # Single match or clear winner - proceed without asking
                        company = matches[0][0]
                        return f"RESOLVED: Company '{company['name']}' has ID: {company['id']}"
                    else:
                        # Multiple matches with similar scores - ask user to select
                        response = request_entity_selection(
                            entity_type="company",
                            name_query=name,
                            matches=matches,
                            name_key="name",
                        )

                        if response.confirmed and response.selected_id:
                            selected = next((m[0] for m in matches if m[0]["id"] == response.selected_id), None)
                            selected_name = selected["name"] if selected else "Unknown"
                            return f"RESOLVED: Company '{selected_name}' has ID: {response.selected_id}"
                        else:
                            feedback = f" User feedback: {response.feedback}" if response.feedback else ""
                            return f"User cancelled company selection.{feedback}"

            return f"Could not find any company matching '{name}'. Please check the spelling or list all companies to see available options."

        except Exception as e:
            logger.error(f"Error resolving company name: {e}")
            return f"Error resolving company name: {str(e)}"
        finally:
            await client.close()

    async def resolve_person_name(name: str) -> str:
        """Resolve person name to ID (handles typos, partial names, reordering). Call before any person operation."""
        context = get_tool_context()
        client = context.get_client()

        # Use getWorkspacePeople with search parameter (same as frontend)
        search_query = """
        query GetWorkspacePeople(
            $workspaceId: ID!
            $limit: Int
            $search: String
        ) {
            getWorkspacePeople(
                workspaceId: $workspaceId
                limit: $limit
                search: $search
            ) {
                data {
                    id
                    firstName
                    lastName
                    jobTitle
                }
            }
        }
        """

        def normalize_person(p):
            """Add 'name' field for fuzzy matching compatibility."""
            full_name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
            return {**p, "name": full_name}

        try:
            # First, try searching with the full name
            result = await client.query(search_query, {
                "workspaceId": context.workspace_id,
                "limit": 20,
                "search": name,
            })

            raw_people = (result.get("getWorkspacePeople") or {}).get("data") or []
            people = [normalize_person(p) for p in raw_people]

            # If full name search yields no results, try searching each name part separately
            if not people:
                name_parts = name.strip().split()
                if len(name_parts) > 1:
                    logger.info(f"Full name search for '{name}' returned 0 results, trying individual parts: {name_parts}")
                    combined_results = {}  # Use dict for deduplication by ID

                    for part in name_parts:
                        if len(part) < 2:  # Skip single-character parts
                            continue
                        part_result = await client.query(search_query, {
                            "workspaceId": context.workspace_id,
                            "limit": 20,
                            "search": part,
                        })
                        part_hits = (part_result.get("getWorkspacePeople") or {}).get("data") or []
                        for hit in part_hits:
                            if hit.get("id") and hit["id"] not in combined_results:
                                combined_results[hit["id"]] = normalize_person(hit)

                    people = list(combined_results.values())
                    if people:
                        logger.info(f"Split-name search found {len(people)} candidates")

            if people:
                # Apply fuzzy matching for better results
                matches = fuzzy_match_entities(name, people, name_key="name", threshold=50.0, limit=5)

                if matches:
                    # Check if we have a single unambiguous match
                    top_score = matches[0][1]
                    second_score = matches[1][1] if len(matches) > 1 else 0
                    score_gap = top_score - second_score

                    if len(matches) == 1 or score_gap >= 15:
                        # Single match or clear winner - proceed without asking
                        person = matches[0][0]
                        return f"RESOLVED: Person '{person['name']}' has ID: {person['id']}"
                    else:
                        # Multiple matches with similar scores - ask user to select
                        response = request_entity_selection(
                            entity_type="person",
                            name_query=name,
                            matches=matches,
                            name_key="name",
                        )

                        if response.confirmed and response.selected_id:
                            selected = next((m[0] for m in matches if m[0]["id"] == response.selected_id), None)
                            selected_name = selected["name"] if selected else "Unknown"
                            return f"RESOLVED: Person '{selected_name}' has ID: {response.selected_id}"
                        else:
                            feedback = f" User feedback: {response.feedback}" if response.feedback else ""
                            return f"User cancelled person selection.{feedback}"

            return f"Could not find any person matching '{name}'. Please check the spelling or list all people to see available options."

        except Exception as e:
            # Re-raise LangGraph interrupts so the confirmation UI works correctly
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error resolving person name: {e}")
            return f"Error resolving person name: {str(e)}"
        finally:
            await client.close()

    async def resolve_group_name(name: str) -> str:
        """Resolve group name to ID (handles typos, partial names). Call before any group operation."""
        context = get_tool_context()
        client = context.get_client()
        
        gql_query = """
        query GetGroups($workspaceId: String!) {
            getGroups(workspaceId: $workspaceId) {
                id
                name
                type
                emoji
                description
            }
        }
        """
        
        try:
            result = await client.query(gql_query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = result.get("getGroups") or []

            if not groups:
                return "No groups found in this workspace."

            # URL-first resolution: if we're on a group page, auto-resolve without disambiguation
            if context.active_url and groups:
                import re
                url_uuid_match = re.search(
                    r'/apps/groups/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
                    context.active_url,
                    re.IGNORECASE,
                )
                if url_uuid_match:
                    url_group_id = url_uuid_match.group(1)
                    url_group = next((g for g in groups if g.get('id') == url_group_id), None)
                    if url_group:
                        emoji = url_group.get('emoji', '')
                        logger.info(f"Auto-resolved group from active URL: {url_group['name']}")
                        return f"RESOLVED: Group '{emoji} {url_group['name']}' (type: {url_group.get('type', 'unknown')}) has ID: {url_group['id']}"

            # Use fuzzy matching
            matches = fuzzy_match_entities(name, groups, name_key="name", threshold=50.0, limit=5)

            if not matches:
                # Even looser matching
                matches = fuzzy_match_entities(name, groups, name_key="name", threshold=30.0, limit=3)

            if matches:
                # Check if we have a single unambiguous match
                top_score = matches[0][1]
                second_score = matches[1][1] if len(matches) > 1 else 0
                score_gap = top_score - second_score
                
                if len(matches) == 1 or score_gap >= 15:
                    # Single match or clear winner - proceed without asking
                    group = matches[0][0]
                    emoji = group.get('emoji', '')
                    return f"RESOLVED: Group '{emoji} {group['name']}' (type: {group.get('type', 'unknown')}) has ID: {group['id']}"
                else:
                    # Multiple matches with similar scores - ask user to select
                    response = request_entity_selection(
                        entity_type="group",
                        name_query=name,
                        matches=matches,
                        name_key="name",
                    )
                    
                    if response.confirmed and response.selected_id:
                        selected = next((m[0] for m in matches if m[0]["id"] == response.selected_id), None)
                        if selected:
                            emoji = selected.get('emoji', '')
                            selected_name = f"{emoji} {selected['name']}".strip()
                            return f"RESOLVED: Group '{selected_name}' (type: {selected.get('type', 'unknown')}) has ID: {response.selected_id}"
                        return f"RESOLVED: Group has ID: {response.selected_id}"
                    else:
                        feedback = f" User feedback: {response.feedback}" if response.feedback else ""
                        return f"User cancelled group selection.{feedback}"
            
            # No matches - list available groups
            group_names = [f"{g.get('emoji', '')} {g.get('name', '')}".strip() for g in groups[:10]]
            return f"Could not find a group matching '{name}'. Available groups: {', '.join(group_names)}"
            
        except Exception as e:
            # Re-raise LangGraph interrupts so the confirmation UI works correctly
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error resolving group name: {e}")
            return f"Error resolving group name: {str(e)}"
        finally:
            await client.close()

    @tool
    async def find_companies(
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
    ) -> str:
        """Find companies in the workspace — list all or search by name.

        Replaces list_companies_in_workspace and search_company_by_name.
        Omit search to list all; provide search for fuzzy name matching.

        Args:
            search: Optional name/keyword to search for.
            page: Page number (default: 1).
            limit: Results per page (default: 10).
        """
        if search:
            return await search_company_by_name(query=search, limit=limit)
        return await list_companies_in_workspace(page=page, limit=limit, search=None)

    @tool
    async def find_people(
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
    ) -> str:
        """Find people in the workspace — list all or search by name.

        Replaces list_people_in_workspace and search_person_by_name.
        Omit search to list all; provide search for fuzzy name matching.

        Args:
            search: Optional name/keyword to search for.
            page: Page number (default: 1).
            limit: Results per page (default: 10).
        """
        if search:
            return await search_person_by_name(query=search, limit=limit)
        return await list_people_in_workspace(page=page, limit=limit, search=None)

    @tool
    async def resolve_entity(name: str, entity_type: str) -> str:
        """Resolve any entity name to its ID.

        Replaces resolve_company_name, resolve_person_name, and resolve_group_name.
        Call before ANY operation that requires an entity ID.
        Handles typos, partial names, case differences, and name reordering.

        Args:
            name: The name to look up (e.g. "Acme Corp", "John Smith").
            entity_type: "company", "person", or "group".
        """
        entity_lower = entity_type.lower()
        if entity_lower == "company":
            return await resolve_company_name(name)
        elif entity_lower in ("person", "people"):
            return await resolve_person_name(name)
        elif entity_lower == "group":
            return await resolve_group_name(name)
        else:
            return f"Invalid entity_type '{entity_type}'. Use 'company', 'person', or 'group'."

    @tool
    async def listEmailsFromPerson(
        person_id: str,
        limit: int = 10,
    ) -> str:
        """Get recent email interactions for a person."""
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query GetPersonEmails(
            $personId: ID!
            $workspaceId: String!
            $limit: Int
        ) {
            getPersonEmails(
                personId: $personId
                workspaceId: $workspaceId
                limit: $limit
            ) {
                emails {
                    messageId
                    subject
                    from
                    to
                    direction
                    body
                    date
                    threadId
                    interactionType
                    eventName
                    source
                }
                totalCount
                hasNextPage
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "personId": person_id,
                "workspaceId": context.workspace_id,
                "limit": min(limit, 50),
            })
            
            data = result.get("getPersonEmails", {})
            emails = data.get("emails", [])
            total_count = data.get("totalCount", 0)
            has_next = data.get("hasNextPage", False)
            
            if not emails:
                return f"No email interactions found for this person."
            
            lines = [f"Found {total_count} email interactions (showing {len(emails)}):\n"]
            for email in emails:
                lines.append(format_email(email))
                lines.append("")
            
            if has_next:
                lines.append(f"(More emails available - increase limit to see more)")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting person emails: {e}")
            return f"Error getting person emails: {str(e)}"
        finally:
            await client.close()

    @tool
    async def listEmailsFromCompany(
        company_id: str,
        limit: int = 10,
    ) -> str:
        """Get recent email interactions for a company."""
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query GetCompanyEmails(
            $companyId: ID!
            $workspaceId: String!
            $limit: Int
        ) {
            getCompanyEmails(
                companyId: $companyId
                workspaceId: $workspaceId
                limit: $limit
            ) {
                emails {
                    messageId
                    subject
                    from
                    to
                    direction
                    body
                    date
                    threadId
                    interactionType
                    eventName
                    source
                }
                totalCount
                hasNextPage
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "companyId": company_id,
                "workspaceId": context.workspace_id,
                "limit": min(limit, 50),
            })
            
            data = result.get("getCompanyEmails", {})
            emails = data.get("emails", [])
            total_count = data.get("totalCount", 0)
            has_next = data.get("hasNextPage", False)
            
            if not emails:
                return f"No email interactions found for this company."
            
            lines = [f"Found {total_count} email interactions (showing {len(emails)}):\n"]
            for email in emails:
                lines.append(format_email(email))
                lines.append("")
            
            if has_next:
                lines.append(f"(More emails available - increase limit to see more)")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting company emails: {e}")
            return f"Error getting company emails: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_email_thread(
        thread_id: str,
        person_id: Optional[str] = None,
        company_id: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """Get full conversation history for an email thread. Provide person_id OR company_id."""
        if not person_id and not company_id:
            return "Error: You must provide either a person_id OR a company_id to fetch a thread."

        context = get_tool_context()
        client = context.get_client()
        
        try:
            full_email_list = []
            
            # 1. Fetch recent emails from the appropriate context
            # We fetch a larger batch (limit) to find related messages
            if person_id:
                query = """
                query GetPersonEmails($personId: ID!, $workspaceId: String!, $limit: Int) {
                    getPersonEmails(personId: $personId, workspaceId: $workspaceId, limit: $limit) {
                        emails {
                            messageId
                            threadId
                            subject
                            from
                            to
                            direction
                            body
                            date
                            interactionType
                        }
                    }
                }
                """
                variables = {
                    "personId": person_id,
                    "workspaceId": context.workspace_id,
                    "limit": limit
                }
                result = await client.query(query, variables)
                full_email_list = result.get("getPersonEmails", {}).get("emails", [])
                
            elif company_id:
                query = """
                query GetCompanyEmails($companyId: ID!, $workspaceId: String!, $limit: Int) {
                    getCompanyEmails(companyId: $companyId, workspaceId: $workspaceId, limit: $limit) {
                        emails {
                            messageId
                            threadId
                            subject
                            from
                            to
                            direction
                            body
                            date
                            interactionType
                        }
                    }
                }
                """
                variables = {
                    "companyId": company_id,
                    "workspaceId": context.workspace_id,
                    "limit": limit
                }
                result = await client.query(query, variables)
                full_email_list = result.get("getCompanyEmails", {}).get("emails", [])

            if not full_email_list:
                return "No emails found in the specified context."

            # 2. Filter by thread_id
            thread_emails = [
                email for email in full_email_list 
                if email.get('threadId') == thread_id
            ]

            if not thread_emails:
                return f"No emails found with Thread ID: {thread_id}. The thread might be older than the last {limit} messages."

            # 3. Sort chronologically (oldest to newest)
            # Python's sort is stable; date strings ISO8601 sort correctly lexicographically
            thread_emails.sort(key=lambda x: x.get('date', ''))

            # 4. Format the conversation
            lines = [f"Found {len(thread_emails)} messages in thread {thread_id}:\n"]
            
            for i, email in enumerate(thread_emails, 1):
                direction = "📤 Sent" if email.get('direction') == 'sent' else "📥 Received"
                date_str = email.get('date', '')[:16].replace('T', ' ')
                
                lines.append(f"--- Message {i} ({date_str}) ---")
                lines.append(f"{direction} | Subject: {email.get('subject', '(No Subject)')}")
                lines.append(f"From: {email.get('from', 'Unknown')}")
                
                to_list = email.get('to', [])
                if to_list:
                    lines.append(f"To: {', '.join(to_list)}")
                
                body = email.get('body', '').strip()
                if body:
                    lines.append(f"\n{body}")
                else:
                    lines.append("\n(No body content)")
                lines.append("") # Empty line between messages

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error getting email thread: {e}")
            return f"Error getting email thread: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_email_templates(
        page: int = 1,
        limit: int = 20,
    ) -> str:
        """List available email templates in the workspace."""
        context = get_tool_context()
        client = context.get_client()
        query = """
        query GetEmailTemplates($workspaceId: String!, $limit: Int, $nextToken: String) {
            emailTemplates(workspaceId: $workspaceId, limit: $limit, nextToken: $nextToken) {
                items {
                    id
                    name
                    description
                    subject
                }
                nextToken
            }
        }
        """
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "limit": limit
            })
            data = result.get("emailTemplates", {})
            templates = data.get("items", [])
            
            if not templates:
                return "No email templates found in this workspace."
            
            lines = [f"Found {len(templates)} templates:\n"]
            for t in templates:
                lines.append(f"- **{t['name']}** (ID: {t['id']})")
                if t.get('description'):
                    lines.append(f"  Description: {t['description']}")
                lines.append(f"  Subject: {t.get('subject', '(No Subject)')}")
                lines.append("")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            return f"Error listing templates: {str(e)}"
        finally:
            await client.close()

    @tool
    async def search_email_templates(
        keyword: str,
        limit: int = 10,
    ) -> str:
        """Search email templates by keyword."""
        context = get_tool_context()
        client = context.get_client()
        query = """
        query SearchEmailTemplates($workspaceId: String!, $searchKeyword: String, $limit: Int) {
            emailTemplates(workspaceId: $workspaceId, searchKeyword: $searchKeyword, limit: $limit) {
                items {
                    id
                    name
                    description
                    subject
                }
            }
        }
        """
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "searchKeyword": keyword,
                "limit": limit
            })
            templates = result.get("emailTemplates", {}).get("items", [])
            
            if not templates:
                return f"No templates found matching '{keyword}'."
            
            lines = [f"Found {len(templates)} templates matching '{keyword}':\n"]
            for t in templates:
                lines.append(f"- **{t['name']}** (ID: {t['id']})")
                if t.get('description'):
                    lines.append(f"  Description: {t['description']}")
                lines.append("")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error searching templates: {e}")
            return f"Error searching templates: {str(e)}"
        finally:
            await client.close()

    async def draft_email(
        to: list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        group_id: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Propose an email draft for user review before saving."""
        # 1. Request confirmation with edit
        req = ConfirmationRequest(
            type=ConfirmationType.CONFIRM_WITH_EDIT,
            title="Review Email Draft",
            message=f"Drafting email to {', '.join(to)}:",
            draft_data={
                "subject": subject,
                "body": body,
            },
            entity_type="email_draft",
            action_label="Save Draft",
        )
        
        response = request_confirmation(req)
        
        if not response.confirmed:
            return "Drafting cancelled by user."
            
        # Use modified data if provided
        final_data = response.modified_data or {"subject": subject, "body": body}
        final_subject = final_data.get("subject", subject)
        final_body = final_data.get("body", body)
        
        context = get_tool_context()
        client = context.get_client()
        try:
            # 2. Resolve group_id if not provided
            if not group_id:
                g_query = """
                query GetGroups($workspaceId: String!) {
                    getGroups(workspaceId: $workspaceId) { id }
                }
                """
                g_result = await client.query(g_query, {"workspaceId": context.workspace_id})
                groups = g_result.get("getGroups") or []
                if groups:
                    group_id = groups[0]["id"]
                else:
                    return "Error: Could not find any group to associate this draft with. Please specify a group_id."

            # 3. Create the draft in the backend
            create_mutation = """
            mutation CreateEmailDraft($input: CreateEmailDraftInput!, $workspaceId: String!) {
                createEmailDraft(input: $input, workspaceId: $workspaceId) {
                    id
                    status
                }
            }
            """
            create_vars = {
                "workspaceId": context.workspace_id,
                "input": {
                    "groupId": group_id,
                    "to": to,
                    "subject": final_subject,
                    "textContent": final_body,
                    "cc": cc or [],
                    "bcc": bcc or [],
                }
            }
            
            create_result = await client.mutate(create_mutation, create_vars)
            draft = create_result.get("createEmailDraft", {})
            
            if not draft.get("id"):
                return "Error: Failed to create email draft in backend."
                
            return f"Draft successfully created with ID: {draft['id']} (Status: {draft.get('status', 'DRAFT')})"

        except Exception as e:
            logger.error(f"Error saving draft: {e}")
            return f"Error saving draft: {str(e)}"
        finally:
            await client.close()

    async def send_email(
        to: list[str],
        subject: str,
        body: str,
        group_id: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Send an email to recipients (asks for confirmation)."""
        # 1. Human-in-the-loop: Request confirmation before sending
        req = ConfirmationRequest(
            type=ConfirmationType.CONFIRM_WITH_EDIT,
            title="Confirm Send Email",
            message=f"I'm about to send this email to {', '.join(to)}. Please review and confirm:",
            draft_data={
                "subject": subject,
                "body": body,
            },
            entity_type="email_send",
            action_label="Send Now",
        )
        
        response = request_confirmation(req)
        
        if not response.confirmed:
            return "Email sending cancelled by user."
            
        final_data = response.modified_data or {"subject": subject, "body": body}
        final_subject = final_data.get("subject", subject)
        final_body = final_data.get("body", body)
        
        context = get_tool_context()
        client = context.get_client()

        sender_email = context.user_email
        if not sender_email:
            return "Error: Could not determine sender email address. Ensure your profile email is set."

        try:
            # Resolve group_id if not provided
            if not group_id:
                g_query = """
                query GetGroups($workspaceId: String!) {
                    getGroups(workspaceId: $workspaceId) { id }
                }
                """
                g_result = await client.query(g_query, {"workspaceId": context.workspace_id})
                groups = g_result.get("getGroups") or []
                if groups:
                    group_id = groups[0]["id"]
                else:
                    return "Error: Could not find any group to associate this email with."

            # Send email directly via createEmail
            send_mutation = """
            mutation CreateEmail($input: CreateEmailInput!, $workspaceId: String) {
                createEmail(input: $input, workspaceId: $workspaceId) {
                    id
                    status
                }
            }
            """
            send_vars = {
                "workspaceId": context.workspace_id,
                "input": {
                    "groupId": group_id,
                    "from": sender_email,
                    "to": to,
                    "subject": final_subject,
                    "textContent": final_body,
                    "cc": cc or [],
                    "bcc": bcc or [],
                },
            }

            send_result = await client.mutate(send_mutation, send_vars)
            email = send_result.get("createEmail", {})
            email_id = email.get("id")
            status = email.get("status")
            return f"Successfully sent email to {', '.join(to)} (ID: {email_id}, Status: {status})"
            
        except Exception as e:
            logger.error(f"Error in send_email flow: {e}")
            return f"Error in send_email flow: {str(e)}"
        finally:
            await client.close()

    @tool
    async def compose_email(
        to: list[str],
        subject: str,
        body: str,
        mode: str = "send",
        group_id: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Compose and send (or draft) an email — always shows a confirmation first.

        Replaces draft_email and send_email. Use mode="send" (default) to send
        immediately after confirmation, or mode="draft" to save as a draft.

        Args:
            to: List of recipient email addresses.
            subject: Email subject line.
            body: Email body text.
            mode: "send" (default) or "draft".
            group_id: Optional group to associate the email with.
            cc: Optional CC addresses.
            bcc: Optional BCC addresses.
        """
        if mode.lower() == "draft":
            return await draft_email(to=to, subject=subject, body=body,
                                     group_id=group_id, cc=cc, bcc=bcc)
        return await send_email(to=to, subject=subject, body=body,
                                group_id=group_id, cc=cc, bcc=bcc)

    @tool
    async def get_group_columns(
        group_id: str,
        entity_type: str = "company",
    ) -> str:
        """Get custom columns (Status, Priority, etc.) for a group. Returns column IDs for updates."""
        context = get_tool_context()
        client = context.get_client()
        
        # Use the group resolver to get columns based on entity type
        if entity_type.lower() == "people":
            query = """
            query GetGroupWithPeopleColumns($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    peopleColumns {
                        id
                        name
                        dataType
                        type
                        isDefault
                    }
                }
            }
            """
        else:
            query = """
            query GetGroupWithCompanyColumns($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    companyColumns {
                        id
                        name
                        dataType
                        type
                        isDefault
                    }
                }
            }
            """
        
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = result.get("getGroups") or []
            group = next((g for g in groups if g.get("id") == group_id), None)
            
            if not group:
                return f"Group with ID {group_id} not found."
            
            columns_key = "peopleColumns" if entity_type.lower() == "people" else "companyColumns"
            columns = group.get(columns_key, [])
            
            if not columns:
                return f"No {entity_type} columns found for group '{group.get('name', 'Unknown')}'."
            
            lines = [f"Columns for group '{group.get('name', 'Unknown')}' ({entity_type}):\n"]
            for col in columns:
                data_type = col.get("dataType", "UNKNOWN")
                is_default = col.get("isDefault", False)
                default_marker = " (default)" if is_default else ""
                lines.append(f"- **{col.get('name', 'Unknown')}** (ID: {col.get('id', 'N/A')})")
                lines.append(f"  Type: {data_type}{default_marker}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting group columns: {e}")
            return f"Error getting group columns: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_column_options(column_id: str) -> str:
        """Get available select options for a SELECT/MULTISELECT column."""
        context = get_tool_context()
        client = context.get_client()
        
        query = """
        query GetSelectOptions($columnId: String!) {
            getSelectOptionsByColumnId(columnId: $columnId) {
                id
                value
                color
                order
            }
        }
        """
        
        try:
            result = await client.query(query, {"columnId": column_id})
            
            options = result.get("getSelectOptionsByColumnId") or []
            
            if not options:
                return f"No options found for column {column_id}. Make sure this is a SELECT or MULTISELECT column."
            
            lines = [f"Found {len(options)} options for column:\n"]
            for opt in options:
                color = opt.get("color", "#000000")
                lines.append(f"- **{opt.get('value', 'Unknown')}** (ID: {opt.get('id', 'N/A')}, Color: {color})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting column options: {e}")
            return f"Error getting column options: {str(e)}"
        finally:
            await client.close()

    async def _get_status_column_and_options(
        client,
        workspace_id: str,
        group_id: str,
        entity_type: str = "people",
    ) -> tuple[dict | None, list]:
        """Helper to find Status column and its options for a group.
        
        Returns:
            Tuple of (status_column_dict, list_of_options)
        """
        # Get group columns
        if entity_type.lower() == "people":
            columns_query = """
            query GetGroupWithPeopleColumns($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    type
                    peopleColumns {
                        id
                        name
                        dataType
                    }
                }
            }
            """
            columns_key = "peopleColumns"
        else:
            columns_query = """
            query GetGroupWithCompanyColumns($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    type
                    companyColumns {
                        id
                        name
                        dataType
                    }
                }
            }
            """
            columns_key = "companyColumns"
        
        groups_result = await client.query(columns_query, {"workspaceId": workspace_id})
        groups = groups_result.get("getGroups") or []
        group = next((g for g in groups if g.get("id") == group_id), None)

        if not group:
            return None, []

        columns = group.get(columns_key) or []
        
        # Find Status column (case-insensitive search)
        status_column = None
        for col in columns:
            if col.get("name", "").lower() == "status":
                status_column = col
                break
        
        if not status_column:
            return None, []
        
        # Get options for the status column
        options_query = """
        query GetSelectOptions($columnId: String!) {
            getSelectOptionsByColumnId(columnId: $columnId) {
                id
                value
                color
                order
            }
        }
        """
        options_result = await client.query(options_query, {"columnId": status_column["id"]})
        options = options_result.get("getSelectOptionsByColumnId") or []
        
        return status_column, options

    @tool
    async def get_pipeline_status_options(
        group_name: Optional[str] = None,
        entity_type: str = "people",
    ) -> str:
        """Get available status options for a group/pipeline."""
        context = get_tool_context()
        client = context.get_client()
        
        try:
            group_id = None
            resolved_group_name = None
            
            # First, try to get group from provided name
            if group_name:
                # Resolve group name to ID
                groups_query = """
                query GetGroups($workspaceId: String!) {
                    getGroups(workspaceId: $workspaceId) {
                        id
                        name
                        type
                        emoji
                    }
                }
                """
                groups_result = await client.query(groups_query, {"workspaceId": context.workspace_id})
                groups = groups_result.get("getGroups") or []
                
                # Fuzzy match group name
                matches = fuzzy_match_entities(group_name, groups, name_key="name", threshold=50.0, limit=1)
                if matches:
                    group = matches[0][0]
                    group_id = group.get("id")
                    resolved_group_name = group.get("name")
            
            # If no group specified, try to get from active URL
            if not group_id and context.active_url:
                parts = [p for p in context.active_url.split('/') if p]
                if 'groups' in parts:
                    try:
                        group_idx = parts.index('groups')
                        if group_idx + 1 < len(parts):
                            group_id = parts[group_idx + 1]
                            # Fetch group name
                            groups_query = """
                            query GetGroups($workspaceId: String!) {
                                getGroups(workspaceId: $workspaceId) { id name }
                            }
                            """
                            groups_result = await client.query(groups_query, {"workspaceId": context.workspace_id})
                            groups = groups_result.get("getGroups") or []
                            group = next((g for g in groups if g.get("id") == group_id), None)
                            if group:
                                resolved_group_name = group.get("name")
                    except (ValueError, IndexError):
                        pass
            
            if not group_id:
                return "Could not determine which group/pipeline to get status options for. Please provide a group name or navigate to a group page."
            
            # Get status column and options
            status_column, options = await _get_status_column_and_options(
                client, context.workspace_id, group_id, entity_type
            )
            
            if not status_column:
                return f"No Status column found for group '{resolved_group_name or group_id}'. The group may not have a status column defined."
            
            if not options:
                return f"No status options found for the Status column in group '{resolved_group_name or group_id}'."
            
            lines = [f"📊 Status options for **{resolved_group_name or 'this group'}**:\n"]
            for opt in sorted(options, key=lambda x: x.get("order", 0)):
                value = opt.get("value", "Unknown")
                lines.append(f"- **{value}** (ID: {opt.get('id', 'N/A')})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting pipeline status options: {e}")
            return f"Error getting pipeline status options: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_entities_by_status(
        group_name: str,
        status_value: str,
        entity_type: str = "people",
        limit: int = 20,
    ) -> str:
        """Get people or companies with a specific status in a group."""
        context = get_tool_context()
        client = context.get_client()
        
        try:
            # Step 1: Resolve group name to ID
            groups_query = """
            query GetGroups($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    type
                    emoji
                }
            }
            """
            groups_result = await client.query(groups_query, {"workspaceId": context.workspace_id})
            groups = groups_result.get("getGroups") or []
            
            matches = fuzzy_match_entities(group_name, groups, name_key="name", threshold=50.0, limit=1)
            if not matches:
                return f"Could not find a group matching '{group_name}'."
            
            group = matches[0][0]
            group_id = group.get("id")
            resolved_group_name = group.get("name")
            group_emoji = group.get("emoji", "")
            
            # Step 2: Get status column and options
            status_column, options = await _get_status_column_and_options(
                client, context.workspace_id, group_id, entity_type
            )
            
            if not status_column:
                return f"No Status column found in group '{resolved_group_name}'."
            
            # Step 3: Find the target status option (fuzzy match)
            target_option = None
            status_matches = fuzzy_match_entities(
                status_value, 
                options, 
                name_key="value", 
                threshold=50.0, 
                limit=1
            )
            if status_matches:
                target_option = status_matches[0][0]
            
            if not target_option:
                available = ", ".join([o.get("value", "") for o in options])
                return f"Could not find status '{status_value}' in group '{resolved_group_name}'. Available statuses: {available}"
            
            target_option_id = target_option.get("id")
            target_option_value = target_option.get("value")
            
            # Step 4: Query entities and filter by status
            if entity_type.lower() == "people":
                entities_query = """
                query GetPeopleByGroup($groupId: ID!, $limit: Int) {
                    getPeopleByGroup(groupId: $groupId, limit: $limit) {
                        data {
                            id
                            firstName
                            lastName
                            jobTitle
                            emails { value type isPrimary }
                            phoneNumbers { value type isPrimary }
                            columnValueSelectOption {
                                columnId
                                selectOptionId
                                selectOption { id value color }
                            }
                        }
                    }
                }
                """
                entities_result = await client.query(entities_query, {
                    "groupId": group_id,
                    "limit": min(limit * 3, 100),  # Fetch more to account for filtering
                })
                entities = (entities_result.get("getPeopleByGroup") or {}).get("data") or []
            else:
                entities_query = """
                query GetCompaniesByGroup($groupId: ID!, $limit: Int) {
                    getCompaniesByGroup(groupId: $groupId, limit: $limit) {
                        data {
                            id
                            name
                            description
                            emails { value type isPrimary }
                            phoneNumbers { value type isPrimary }
                            columnValueSelectOption {
                                columnId
                                selectOptionId
                                selectOption { id value color }
                            }
                        }
                    }
                }
                """
                entities_result = await client.query(entities_query, {
                    "groupId": group_id,
                    "limit": min(limit * 3, 100),
                })
                entities = (entities_result.get("getCompaniesByGroup") or {}).get("data") or []
            
            # Step 5: Filter entities by status
            filtered_entities = []
            for entity in entities:
                column_values = entity.get("columnValueSelectOption", [])
                for cv in column_values:
                    if cv.get("columnId") == status_column["id"] and cv.get("selectOptionId") == target_option_id:
                        filtered_entities.append(entity)
                        break
                
                if len(filtered_entities) >= limit:
                    break
            
            if not filtered_entities:
                return f"No {entity_type} found with status '{target_option_value}' in group '{group_emoji} {resolved_group_name}'."
            
            # Format output
            lines = [f"Found {len(filtered_entities)} {entity_type} with status **\"{target_option_value}\"** in **{group_emoji} {resolved_group_name}**:\n"]
            
            for i, entity in enumerate(filtered_entities, 1):
                if entity_type.lower() == "people":
                    name = f"{entity.get('firstName', '')} {entity.get('lastName', '')}".strip() or "Unknown"
                    lines.append(f"{i}. **{name}** (ID: {entity.get('id', 'N/A')})")
                    if entity.get('jobTitle'):
                        lines.append(f"   Job Title: {entity['jobTitle']}")
                else:
                    name = entity.get('name', 'Unknown')
                    lines.append(f"{i}. **{name}** (ID: {entity.get('id', 'N/A')})")
                    if entity.get('description'):
                        lines.append(f"   Description: {entity['description'][:100]}...")
                
                # Add primary email
                emails = entity.get('emails', [])
                primary_email = next((e.get('value') for e in emails if e.get('isPrimary')), None)
                if not primary_email and emails:
                    primary_email = emails[0].get('value')
                if primary_email:
                    lines.append(f"   Email: {primary_email}")
                
                lines.append("")  # Empty line between entries
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting entities by status: {e}")
            return f"Error getting entities by status: {str(e)}"
        finally:
            await client.close()

    @tool
    async def resolve_column_by_name(
        group_id: str,
        column_name: str,
        entity_type: str = "company",
    ) -> str:
        """Resolve a column name (handles typos) to get its ID for update operations."""
        context = get_tool_context()
        client = context.get_client()
        
        # Use the group resolver to get columns based on entity type
        if entity_type.lower() == "people":
            query = """
            query GetGroupWithPeopleColumns($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    peopleColumns {
                        id
                        name
                        dataType
                        type
                        isDefault
                    }
                }
            }
            """
        else:
            query = """
            query GetGroupWithCompanyColumns($workspaceId: String!) {
                getGroups(workspaceId: $workspaceId) {
                    id
                    name
                    companyColumns {
                        id
                        name
                        dataType
                        type
                        isDefault
                    }
                }
            }
            """
        
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = result.get("getGroups") or []
            group = next((g for g in groups if g.get("id") == group_id), None)
            
            if not group:
                return f"Group with ID {group_id} not found."
            
            columns_key = "peopleColumns" if entity_type.lower() == "people" else "companyColumns"
            columns = group.get(columns_key, [])
            
            if not columns:
                return f"No {entity_type} columns found for group '{group.get('name', 'Unknown')}'."
            
            # Use fuzzy matching to find the column
            matches = fuzzy_match_entities(column_name, columns, name_key="name", threshold=50.0, limit=5)
            
            if not matches:
                # Even looser matching
                matches = fuzzy_match_entities(column_name, columns, name_key="name", threshold=30.0, limit=3)
            
            if matches:
                if len(matches) == 1 or matches[0][1] >= 85:
                    column = matches[0][0]
                    return f"RESOLVED: Column '{column['name']}' (type: {column.get('dataType', 'unknown')}) has ID: {column['id']}"
                else:
                    lines = [f"Multiple columns match '{column_name}'. Please confirm which one:\n"]
                    for column, score in matches:
                        confidence = "high" if score >= 85 else "medium" if score >= 70 else "possible"
                        lines.append(f"- **{column['name']}** (ID: {column['id']}, Type: {column.get('dataType', '')}) - {confidence} match")
                    return "\n".join(lines)
            
            # No matches - list available columns
            column_names = [c.get('name', '') for c in columns[:10]]
            return f"Could not find a column matching '{column_name}'. Available columns: {', '.join(column_names)}"
            
        except Exception as e:
            logger.error(f"Error resolving column name: {e}")
            return f"Error resolving column name: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_current_page() -> str:
        """Get the CRM page the user is currently viewing (company, person, group, or dashboard)."""
        context = get_tool_context()
        client = context.get_client()
        active_url = context.active_url

        if not active_url:
            return "I don't have information about which page you're currently viewing. The page context wasn't provided."
        
        try:
            # Parse the URL to understand the page structure
            # URL patterns in the app typically follow: /app/{workspaceId}/{pageType}/{entityId}/...
            parts = [p for p in active_url.split('/') if p]  # Remove empty strings
            
            result_parts = []
            result_parts.append(f"Current URL: {active_url}")
            
            # Try to identify and fetch details for different entity types in the URL
            # Look for common patterns without hardcoding exact positions
            
            # Check for company in URL
            if 'company' in parts:
                try:
                    company_idx = parts.index('company')
                    if company_idx + 1 < len(parts):
                        company_id = parts[company_idx + 1]
                        # Fetch company details
                        company_query = """
                        query GetOneCompany($companyId: ID!) {
                            getOneCompany(companyId: $companyId) {
                                id
                                name
                                description
                            }
                        }
                        """
                        company_result = await client.query(company_query, {"companyId": company_id})
                        company = company_result.get("getOneCompany")
                        if company:
                            result_parts.append(f"\nYou are viewing the **company profile** for **{company.get('name', 'Unknown')}**.")
                            if company.get('description'):
                                result_parts.append(f"Description: {company['description'][:100]}...")
                except (ValueError, IndexError):
                    pass
            
            # Check for person in URL
            if 'person' in parts or 'people' in parts:
                person_keyword = 'person' if 'person' in parts else 'people'
                try:
                    person_idx = parts.index(person_keyword)
                    if person_idx + 1 < len(parts):
                        person_id = parts[person_idx + 1]
                        # Only fetch if it looks like an ID (not another keyword)
                        if person_id not in ['list', 'new', 'edit', 'settings']:
                            person_query = """
                            query GetPerson($peopleId: ID!) {
                                getPerson(peopleId: $peopleId) {
                                    id
                                    firstName
                                    lastName
                                    jobTitle
                                }
                            }
                            """
                            person_result = await client.query(person_query, {"peopleId": person_id})
                            person = person_result.get("getPerson")
                            if person:
                                full_name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
                                result_parts.append(f"\nYou are viewing the **person profile** for **{full_name}**.")
                                if person.get('jobTitle'):
                                    result_parts.append(f"Job Title: {person['jobTitle']}")
                except (ValueError, IndexError):
                    pass
            
            # Check for group in URL
            if 'groups' in parts or 'group' in parts:
                group_keyword = 'groups' if 'groups' in parts else 'group'
                try:
                    group_idx = parts.index(group_keyword)
                    if group_idx + 1 < len(parts):
                        group_id = parts[group_idx + 1]
                        if group_id not in ['new', 'settings']:
                            # Fetch group details
                            group_query = """
                            query GetGroups($workspaceId: String!) {
                                getGroups(workspaceId: $workspaceId) {
                                    id
                                    name
                                    emoji
                                    type
                                    description
                                    views { id name type }
                                }
                            }
                            """
                            group_result = await client.query(group_query, {"workspaceId": context.workspace_id})
                            groups = group_result.get("getGroups") or []
                            group = next((g for g in groups if g.get("id") == group_id), None)
                            if group:
                                emoji = group.get('emoji', '')
                                group_name = f"{emoji} {group.get('name', 'Unknown')}".strip()
                                result_parts.append(f"\nYou are viewing the **group** **{group_name}**.")
                                result_parts.append(f"Group type: {group.get('type', 'Unknown')}")
                                
                                # Check if viewing a specific view
                                if 'views' in parts:
                                    try:
                                        view_idx = parts.index('views')
                                        if view_idx + 1 < len(parts):
                                            view_id = parts[view_idx + 1]
                                            views = group.get('views', [])
                                            view = next((v for v in views if v.get("id") == view_id), None)
                                            if view:
                                                result_parts.append(f"View: **{view.get('name', 'Unknown')}** ({view.get('type', 'Unknown')})")
                                    except (ValueError, IndexError):
                                        pass
                except (ValueError, IndexError):
                    pass
            
            # Check for dashboard/home
            if len(parts) <= 2 and 'app' in parts:
                result_parts.append("\nYou are on the **dashboard/home page**.")
            
            # If we couldn't identify specific entities, provide a generic response
            if len(result_parts) == 1:  # Only URL was added
                # Try to infer from URL keywords
                url_lower = active_url.lower()
                if 'settings' in url_lower:
                    result_parts.append("\nYou appear to be on a **settings** page.")
                elif 'import' in url_lower:
                    result_parts.append("\nYou appear to be on an **import** page.")
                elif 'export' in url_lower:
                    result_parts.append("\nYou appear to be on an **export** page.")
                else:
                    result_parts.append("\nI can see the URL but couldn't identify the specific page type. You may be on a custom or new page.")
            
            return "\n".join(result_parts)
            
        except Exception as e:
            logger.error(f"Error getting current page info: {e}")
            return f"I can see you're at {active_url}, but I encountered an error fetching page details: {str(e)}"
        finally:
            await client.close()

    @tool
    async def query_companies(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        filter_conditions: Optional[list] = None,
        sort_by: Optional[list] = None,
    ) -> str:
        """Query companies across the entire workspace with optional filtering and sorting.

        Use this instead of list_companies_in_workspace when you need to filter or sort
        by custom column values, dates, or any field. Works on workspace-level (global)
        columns. For group-scoped columns use list_companies_in_group with filter_conditions.

        filter_conditions: list of condition dicts, e.g.:
          [{"field": "global.<column_id>", "operator": "greater_than", "value": ["1000"]}]
          [{"field": "createdAt", "operator": "this_month"}]
          [{"field": "name", "operator": "contains", "value": ["acme"]}]

        sort_by: list of sort dicts, e.g.:
          [{"field": "global.<column_id>", "order": "desc"}]
          [{"field": "createdAt", "order": "asc"}]

        Field format for custom columns: "global.<column_id>" (use resolve_column_by_name
        to get the column ID first).

        Available operators: contains, not_contains, equals, not_equals, starts_with,
        ends_with, is_empty, is_not_empty, is_one_of, is_not_one_of, greater_than,
        less_than, greater_than_or_equal, less_than_or_equal, between, not_between,
        before, after, this_week, this_month, this_year.
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetCompaniesByWorkspaceView(
            $workspaceId: ID!
            $page: Int
            $limit: Int
            $search: String
            $filter: FilterInput
        ) {
            getCompaniesByWorkspaceView(
                workspaceId: $workspaceId
                page: $page
                limit: $limit
                search: $search
                filter: $filter
            ) {
                data {
                    id
                    name
                    description
                    emails { value isPrimary }
                    columnValues { columnId value }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        filter_input = None
        if filter_conditions or sort_by:
            filter_input = {
                "logicalOperator": "AND",
                "conditions": filter_conditions or [],
                "sortBy": sort_by or [],
            }

        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
                "filter": filter_input,
            })

            data = result.get("getCompaniesByWorkspaceView") or {}
            companies = data.get("data") or []
            meta = data.get("meta") or {}

            if not companies:
                return "No companies found matching the criteria."

            total = meta.get("total", len(companies))
            current_page = meta.get("page", 1)

            sort_note = ""
            if sort_by:
                sort_note = f" sorted by {sort_by[0].get('field', '')} ({sort_by[0].get('order', 'asc')})"
            filter_note = f" matching {len(filter_conditions)} filter(s)" if filter_conditions else ""
            lines = [f"Found {total} companies in workspace{filter_note}{sort_note} (showing page {current_page}):"]

            active_col_ids = set()
            for s in (sort_by or []):
                field = s.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])
            for c in (filter_conditions or []):
                field = c.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])

            for company in companies:
                line = format_company_compact(company)
                if active_col_ids:
                    col_vals = company.get("columnValues") or []
                    extras = [
                        cv.get("value")
                        for cv in col_vals
                        if cv.get("columnId") in active_col_ids and cv.get("value")
                    ]
                    if extras:
                        line += f" [{', '.join(extras)}]"
                lines.append(line)

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} or search to narrow down)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error querying companies: {e}")
            return f"Error querying companies: {str(e)}"
        finally:
            await client.close()

    @tool
    async def query_people(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        filter_conditions: Optional[list] = None,
        sort_by: Optional[list] = None,
    ) -> str:
        """Query people across the entire workspace with optional filtering and sorting.

        Use this instead of list_people_in_workspace when you need to filter or sort
        by custom column values, dates, or any field. Works on workspace-level (global)
        columns. For group-scoped columns use list_people_in_group with filter_conditions.

        filter_conditions: list of condition dicts, e.g.:
          [{"field": "global.<column_id>", "operator": "equals", "value": ["Qualified"]}]
          [{"field": "createdAt", "operator": "this_week"}]
          [{"field": "firstName", "operator": "contains", "value": ["john"]}]

        sort_by: list of sort dicts, e.g.:
          [{"field": "global.<column_id>", "order": "desc"}]
          [{"field": "createdAt", "order": "asc"}]

        Field format for custom columns: "global.<column_id>" (use resolve_column_by_name
        to get the column ID first).

        Available operators: contains, not_contains, equals, not_equals, starts_with,
        ends_with, is_empty, is_not_empty, is_one_of, is_not_one_of, greater_than,
        less_than, greater_than_or_equal, less_than_or_equal, between, not_between,
        before, after, this_week, this_month, this_year.
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetPeopleByWorkspaceView(
            $workspaceId: ID!
            $page: Int
            $limit: Int
            $search: String
            $filter: FilterInput
        ) {
            getPeopleByWorkspaceView(
                workspaceId: $workspaceId
                page: $page
                limit: $limit
                search: $search
                filter: $filter
            ) {
                data {
                    id
                    firstName
                    lastName
                    jobTitle
                    emails { value isPrimary }
                    companyMetaData {
                        company { name }
                    }
                    columnValues { columnId value }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        filter_input = None
        if filter_conditions or sort_by:
            filter_input = {
                "logicalOperator": "AND",
                "conditions": filter_conditions or [],
                "sortBy": sort_by or [],
            }

        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
                "filter": filter_input,
            })

            data = result.get("getPeopleByWorkspaceView") or {}
            people = data.get("data") or []
            meta = data.get("meta") or {}

            if not people:
                return "No people found matching the criteria."

            total = meta.get("total", len(people))
            current_page = meta.get("page", 1)

            sort_note = ""
            if sort_by:
                sort_note = f" sorted by {sort_by[0].get('field', '')} ({sort_by[0].get('order', 'asc')})"
            filter_note = f" matching {len(filter_conditions)} filter(s)" if filter_conditions else ""
            lines = [f"Found {total} people in workspace{filter_note}{sort_note} (showing page {current_page}):"]

            active_col_ids = set()
            for s in (sort_by or []):
                field = s.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])
            for c in (filter_conditions or []):
                field = c.get("field", "")
                if field.startswith("global."):
                    active_col_ids.add(field.split("global.", 1)[1])

            for person in people:
                line = format_person_compact(person)
                if active_col_ids:
                    col_vals = person.get("columnValues") or []
                    extras = [
                        cv.get("value")
                        for cv in col_vals
                        if cv.get("columnId") in active_col_ids and cv.get("value")
                    ]
                    if extras:
                        line += f" [{', '.join(extras)}]"
                lines.append(line)

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} or search to narrow down)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error querying people: {e}")
            return f"Error querying people: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_profile_stats(
        entity_id: str,
        entity_type: str,
    ) -> str:
        """Get engagement stats for a person or company.

        Returns counts for notes, reminders, and interactions, plus the last
        interaction date. Use when the user asks "how engaged are we with X?"
        or wants a quick activity summary without fetching the full entity.

        Args:
            entity_id: ID of the person or company.
            entity_type: "PERSON" or "COMPANY" (case-insensitive).
        """
        context = get_tool_context()
        client = context.get_client()
        entity_type_upper = entity_type.upper()

        if entity_type_upper == "PERSON":
            query = """
            query GetPersonProfileStats($personId: ID!, $workspaceId: ID!) {
                getPersonProfileStats(personId: $personId, workspaceId: $workspaceId) {
                    interactionsCount
                    notesCount
                    remindersCount
                }
            }
            """
            variables = {"personId": entity_id, "workspaceId": context.workspace_id}
            key = "getPersonProfileStats"
        elif entity_type_upper == "COMPANY":
            query = """
            query GetCompanyProfileStats($companyId: ID!, $workspaceId: ID!) {
                getCompanyProfileStats(companyId: $companyId, workspaceId: $workspaceId) {
                    interactionsCount
                    notesCount
                    remindersCount
                }
            }
            """
            variables = {"companyId": entity_id, "workspaceId": context.workspace_id}
            key = "getCompanyProfileStats"
        else:
            return f"Invalid entity_type '{entity_type}'. Use 'PERSON' or 'COMPANY'."

        try:
            result = await client.execute(query, variables)
            stats = result.get("data", {}).get(key)
            if not stats:
                return f"No profile stats found for {entity_type_upper} {entity_id}."

            lines = [f"Profile stats for {entity_type_upper} {entity_id}:"]
            lines.append(f"  Interactions: {stats.get('interactionsCount', 0)}")
            lines.append(f"  Notes: {stats.get('notesCount', 0)}")
            lines.append(f"  Reminders: {stats.get('remindersCount', 0)}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error fetching profile stats: {e}")
            return f"Error fetching profile stats: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_workspace_members() -> str:
        """List all members in the current workspace.

        Returns each member's id, name, email, and role.
        Use when the user asks "who's on my team?" or needs to look up
        a teammate by name for ownership/assignment queries.
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetWorkspaceMembers($workspaceId: ID!) {
            getWorkspaceMembers(workspaceId: $workspaceId) {
                id
                userId
                role
                createdAt
                user {
                    firstName
                    lastName
                    email
                }
            }
        }
        """
        variables = {"workspaceId": context.workspace_id}

        try:
            result = await client.execute(query, variables)
            members = result.get("data", {}).get("getWorkspaceMembers", [])
            if not members:
                return "No members found in workspace."

            lines = [f"Workspace members ({len(members)}):"]
            for m in members:
                user = m.get("user") or {}
                first = user.get("firstName", "")
                last = user.get("lastName", "")
                name = f"{first} {last}".strip() or "(unnamed)"
                email = user.get("email", "")
                role = m.get("role", "")
                mid = m.get("id", "")
                lines.append(f"  - {name} | {email} | {role} | id={mid}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error listing workspace members: {e}")
            return f"Error listing workspace members: {str(e)}"
        finally:
            await client.close()

    return [
        # Smart resolvers - use these FIRST to resolve names to IDs
        resolve_entity,
        resolve_column_by_name,
        # Page awareness
        get_current_page,
        # Pipeline status tools
        get_pipeline_status_options,
        get_entities_by_status,
        # Find tools (merged list + search)
        find_companies,
        find_people,
        # List tools (group-scoped with filter/sort)
        list_groups_in_workspace,
        list_companies_in_group,
        list_people_in_group,
        # Get by ID tools
        get_company_by_id,
        get_person_by_id,
        get_group_by_id,
        # Group search
        search_group_by_name,
        # Email/interaction tools
        listEmailsFromPerson,
        listEmailsFromCompany,
        get_email_thread,
        # Drafting and Template tools
        list_email_templates,
        search_email_templates,
        compose_email,
        # Group column tools
        get_group_columns,
        get_column_options,
        # Workspace-wide filtered query tools
        query_companies,
        query_people,
        # Profile stats + workspace members
        get_profile_stats,
        list_workspace_members,
    ]


# ---------------------------------------------------------------------------
# Entity-specific sub-getters
# These filter the full READ tool list so each request only receives the
# schemas it actually needs. Adding a tool to get_read_tools() above
# automatically makes it available here — just add its name to the right set.
# ---------------------------------------------------------------------------

_RESOLVER_NAMES = {
    "resolve_entity",
    "get_current_page",
    "list_workspace_members",
}

_COMPANY_NAMES = {
    "find_companies",
    "list_companies_in_group",
    "get_company_by_id",
    "query_companies",
    "get_profile_stats",
}

_PEOPLE_NAMES = {
    "find_people",
    "list_people_in_group",
    "get_person_by_id",
    "query_people",
    "get_profile_stats",
}

_GROUP_NAMES = {
    "list_groups_in_workspace",
    "get_group_by_id",
    "search_group_by_name",
}

_EMAIL_NAMES = {
    "listEmailsFromPerson",
    "listEmailsFromCompany",
    "get_email_thread",
    "list_email_templates",
    "search_email_templates",
    "compose_email",
}

_COLUMN_NAMES = {
    "get_group_columns",
    "get_column_options",
    "get_pipeline_status_options",
    "get_entities_by_status",
    "resolve_column_by_name",
}


def _filter_read_tools(names: set) -> list:
    """Return only the tools from get_read_tools() whose name is in the set."""
    return [t for t in get_read_tools() if t.name in names]


def get_resolver_tools() -> list:
    """Core resolver + navigation tools — always loaded on every request."""
    return _filter_read_tools(_RESOLVER_NAMES)


def get_company_read_tools() -> list:
    """Tools for listing, fetching, and searching companies."""
    return _filter_read_tools(_COMPANY_NAMES)


def get_people_read_tools() -> list:
    """Tools for listing, fetching, and searching people/contacts."""
    return _filter_read_tools(_PEOPLE_NAMES)


def get_group_read_tools() -> list:
    """Tools for listing, fetching, and searching groups."""
    return _filter_read_tools(_GROUP_NAMES)


def get_email_tools() -> list:
    """Email reading, drafting, and sending tools."""
    return _filter_read_tools(_EMAIL_NAMES)


def get_column_tools() -> list:
    """Column/pipeline/status tools — loaded with UPDATE operations."""
    return _filter_read_tools(_COLUMN_NAMES)

