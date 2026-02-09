"""READ tools for querying companies, people, and groups."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.base import (
    ToolContext,
    format_company,
    format_person,
    format_group,
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

logger = logging.getLogger(__name__)


def get_read_tools(context: ToolContext) -> list:
    """Get all READ tools configured with the given context.
    
    Args:
        context: Tool context with auth and workspace info
        
    Returns:
        List of tool functions
    """
    
    @tool
    async def list_companies_in_workspace(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
    ) -> str:
        """List companies in the current workspace.
        
        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 10, max: 50)
            search: Optional search term to filter companies by name
            
        Returns:
            Formatted list of companies
        """
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
                    emails { value type isPrimary }
                    phoneNumbers { value type isPrimary }
                }
                meta { total page limit hasNextPage }
            }
        }
        """

        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
                "page": page,
                "limit": min(limit, 50),
                "search": search,
            })
            
            data = result.get("getWorkspaceCompany", {})
            companies = data.get("data", [])
            meta = data.get("meta", {})
            
            if not companies:
                return "No companies found in this workspace."
            
            lines = [f"Found {meta.get('total', len(companies))} companies (page {meta.get('page', 1)}):\n"]
            for company in companies:
                lines.append(format_company(company))
                lines.append("")
            
            if meta.get("hasNextPage"):
                lines.append(f"\n(More results available - use page={meta.get('page', 1) + 1})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error listing companies: {e}")
            return f"Error listing companies: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_people_in_workspace(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
    ) -> str:
        """List people (contacts) in the current workspace.
        
        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 10, max: 50)
            search: Optional search term to filter people by name
            
        Returns:
            Formatted list of people
        """
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
                    description
                    emails { value type isPrimary }
                    phoneNumbers { value type isPrimary }
                    companyMetaData {
                        company { id name }
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
                "limit": min(limit, 50),
                "search": search,
            })
            
            data = result.get("getWorkspacePeople", {})
            people = data.get("data", [])
            meta = data.get("meta", {})
            
            if not people:
                return "No people found in this workspace."
            
            lines = [f"Found {meta.get('total', len(people))} people (page {meta.get('page', 1)}):\n"]
            for person in people:
                lines.append(format_person(person))
                lines.append("")
            
            if meta.get("hasNextPage"):
                lines.append(f"\n(More results available - use page={meta.get('page', 1) + 1})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error listing people: {e}")
            return f"Error listing people: {str(e)}"
        finally:
            await client.close()

    @tool
    async def list_groups_in_workspace() -> str:
        """List all groups in the current workspace.
        
        Returns:
            Formatted list of groups
        """
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
                }
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "workspaceId": context.workspace_id,
            })
            
            groups = result.get("getGroups", [])
            
            if not groups:
                return "No groups found in this workspace."
            
            lines = [f"Found {len(groups)} groups:\n"]
            for group in groups:
                lines.append(format_group(group))
                lines.append("")
            
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
    ) -> str:
        """List companies in a specific group.
        
        Args:
            group_id: The ID of the group
            page: Page number (default: 1)
            limit: Number of results per page (default: 10, max: 50)
            search: Optional search term to filter companies
            
        Returns:
            Formatted list of companies in the group
        """
        client = context.get_client()
        
        query = """
        query GetCompaniesByGroup(
            $groupId: ID!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getCompaniesByGroup(
                groupId: $groupId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id
                    name
                    description
                    emails { value type isPrimary }
                    phoneNumbers { value type isPrimary }
                }
                meta { total page limit hasNextPage }
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "groupId": group_id,
                "page": page,
                "limit": min(limit, 50),
                "search": search,
            })
            
            data = result.get("getCompaniesByGroup", {})
            companies = data.get("data", [])
            meta = data.get("meta", {})
            
            if not companies:
                return "No companies found in this group."
            
            lines = [f"Found {meta.get('total', len(companies))} companies in group (page {meta.get('page', 1)}):\n"]
            for company in companies:
                lines.append(format_company(company))
                lines.append("")
            
            if meta.get("hasNextPage"):
                lines.append(f"\n(More results available - use page={meta.get('page', 1) + 1})")
            
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
    ) -> str:
        """List people in a specific group.
        
        Args:
            group_id: The ID of the group
            page: Page number (default: 1)
            limit: Number of results per page (default: 10, max: 50)
            search: Optional search term to filter people
            
        Returns:
            Formatted list of people in the group
        """
        client = context.get_client()
        
        query = """
        query GetPeopleByGroup(
            $groupId: ID!
            $page: Int
            $limit: Int
            $search: String
        ) {
            getPeopleByGroup(
                groupId: $groupId
                page: $page
                limit: $limit
                search: $search
            ) {
                data {
                    id
                    firstName
                    lastName
                    jobTitle
                    description
                    emails { value type isPrimary }
                    phoneNumbers { value type isPrimary }
                    companyMetaData {
                        company { id name }
                    }
                }
                meta { total page limit hasNextPage }
            }
        }
        """
        
        try:
            result = await client.query(query, {
                "groupId": group_id,
                "page": page,
                "limit": min(limit, 50),
                "search": search,
            })
            
            data = result.get("getPeopleByGroup", {})
            people = data.get("data", [])
            meta = data.get("meta", {})
            
            if not people:
                return "No people found in this group."
            
            lines = [f"Found {meta.get('total', len(people))} people in group (page {meta.get('page', 1)}):\n"]
            for person in people:
                lines.append(format_person(person))
                lines.append("")
            
            if meta.get("hasNextPage"):
                lines.append(f"\n(More results available - use page={meta.get('page', 1) + 1})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error listing people in group: {e}")
            return f"Error listing people in group: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_company_by_id(company_id: str) -> str:
        """Get detailed information about a specific company.
        
        Args:
            company_id: The ID of the company
            
        Returns:
            Detailed company information
        """
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
                groupCompanies {
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
            groups = company.get("groupCompanies", [])
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
        """Get detailed information about a specific person.
        
        Args:
            person_id: The ID of the person
            
        Returns:
            Detailed person information
        """
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

    @tool
    async def search_company_by_name(query: str, limit: int = 10) -> str:
        """Search for companies by name using fuzzy matching.
        
        Args:
            query: Search query (company name or partial name)
            limit: Maximum number of results (default: 10)
            
        Returns:
            Formatted list of matching companies
        """
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
            logger.warning(f"Autocomplete failed, falling back to direct query: {e}")
        
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
            
            companies = result.get("getWorkspaceCompany", {}).get("data", [])
            
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

    @tool
    async def search_person_by_name(query: str, limit: int = 10) -> str:
        """Search for people by name using fuzzy matching.
        
        Args:
            query: Search query (person name or partial name)
            limit: Maximum number of results (default: 10)
            
        Returns:
            Formatted list of matching people
        """
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
            logger.warning(f"Autocomplete failed, falling back to direct query: {e}")
        
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
            
            people = result.get("getWorkspacePeople", {}).get("data", [])
            
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
        """Get detailed information about a specific group.
        
        Args:
            group_id: The ID of the group
            
        Returns:
            Detailed group information
        """
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
            
            groups = result.get("getGroups", [])
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
        """Search for groups by name with smart fuzzy matching.
        
        This tool handles typos, partial names, and misspellings automatically.
        For example, "Prospeccts" will match "Prospects", "cstomers" will match "Customers".
        
        Args:
            query: Search query (group name, partial name, or even with typos)
            
        Returns:
            Formatted list of matching groups with their IDs
        """
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
            
            groups = result.get("getGroups", [])
            
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

    @tool
    async def resolve_company_name(name: str) -> str:
        """Resolve a company name (even with typos) to get its ID for use in other operations.

        USE THIS TOOL FIRST when user mentions a company by name before performing any
        operations that require a company ID. This tool handles:
        - Typos (e.g., "Gogle" → "Google")
        - Partial names (e.g., "Acme" → "Acme Corporation")
        - Case differences (e.g., "APPLE" → "Apple Inc.")
        - Multi-word names (e.g., "Acme Corp" searches both parts if full name fails)

        When multiple matches are found with similar confidence, the user will be asked
        to select the correct company.

        Args:
            name: The company name (can include typos or be partial)

        Returns:
            The company ID and details, or asks user to select if ambiguous
        """
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

            companies = result.get("getWorkspaceCompany", {}).get("data", [])

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
                        part_hits = part_result.get("getWorkspaceCompany", {}).get("data", [])
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

    @tool
    async def resolve_person_name(name: str) -> str:
        """Resolve a person's name (even with typos) to get their ID for use in other operations.

        USE THIS TOOL FIRST when user mentions a person by name before performing any
        operations that require a person ID. This tool handles:
        - Typos (e.g., "Jonh" → "John")
        - Partial names (e.g., "John" → "John Smith")
        - Name reordering (e.g., "Smith John" → "John Smith")
        - Full name searches (e.g., "Chen Reddy" searches both parts if full name fails)

        When multiple matches are found with similar confidence, the user will be asked
        to select the correct person.

        Args:
            name: The person's name (can include typos, be partial, or in different order)

        Returns:
            The person ID and details, or asks user to select if ambiguous
        """
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

            raw_people = result.get("getWorkspacePeople", {}).get("data", [])
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
                        part_hits = part_result.get("getWorkspacePeople", {}).get("data", [])
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
            logger.error(f"Error resolving person name: {e}")
            return f"Error resolving person name: {str(e)}"
        finally:
            await client.close()

    @tool
    async def resolve_group_name(name: str) -> str:
        """Resolve a group name (even with typos) to get its ID for use in other operations.
        
        USE THIS TOOL FIRST when user mentions a group by name before performing any 
        operations that require a group ID. This tool handles:
        - Typos (e.g., "Prospeccts" → "Prospects")
        - Partial names (e.g., "Custom" → "Customers")
        - Case differences (e.g., "LEADS" → "Leads")
        
        When multiple matches are found with similar confidence, the user will be asked
        to select the correct group.
        
        Args:
            name: The group name (can include typos or be partial)
            
        Returns:
            The group ID and details, or asks user to select if ambiguous
        """
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
            
            groups = result.get("getGroups", [])
            
            if not groups:
                return "No groups found in this workspace."
            
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
            logger.error(f"Error resolving group name: {e}")
            return f"Error resolving group name: {str(e)}"
        finally:
            await client.close()

    @tool
    async def listEmailsFromPerson(
        person_id: str,
        limit: int = 10,
    ) -> str:
        """Get email interactions for a specific person.
        
        This retrieves emails and other interactions (calls, meetings, notes)
        associated with a person.
        
        Args:
            person_id: The ID of the person to get emails for
            limit: Maximum number of emails to return (default: 10, max: 50)
            
        Returns:
            Formatted list of email interactions for the person
        """
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
        """Get email interactions for a specific company.
        
        This retrieves emails and other interactions (calls, meetings, notes)
        associated with a company and its contacts.
        
        Args:
            company_id: The ID of the company to get emails for
            limit: Maximum number of emails to return (default: 10, max: 50)
            
        Returns:
            Formatted list of email interactions for the company
        """
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
        """Get the full conversation history for a specific email thread.
        
        Use this tool when you need to see the context of a conversation.
        You must provide either a person_id OR a company_id to scope the search,
        along with the thread_id found in a previous email listing.
        
        Args:
            thread_id: The unique ID of the thread to retrieve
            person_id: (Optional) The ID of the person associated with this thread
            company_id: (Optional) The ID of the company associated with this thread
            limit: How many recent emails to fetch for searching (default: 50)
            
        Returns:
            Formatted chronological list of all emails in the thread
        """
        if not person_id and not company_id:
            return "Error: You must provide either a person_id OR a company_id to fetch a thread."

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
        """List available email templates in the current workspace.
        
        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 20)
            
        Returns:
            Formatted list of templates with IDs and descriptions
        """
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
        """Search for email templates by keyword in name or description.
        
        Args:
            keyword: Search keyword
            limit: Maximum results (default: 10)
            
        Returns:
            Formatted list of matching templates
        """
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

    @tool
    async def draft_email(
        to: list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        group_id: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Propose an email draft to the user for review and optional editing.
        
        Use this tool when you have summarized the context and are ready to 
        propose a specific response. The user will be able to edit the subject 
        and body before the draft is saved to the backend.
        
        Args:
            to: List of recipient email addresses
            subject: The proposed subject line
            body: The proposed message body (plain text or HTML)
            thread_id: (Optional) The ID of the thread to respond to
            group_id: (Optional) ID of the group this draft belongs to
            cc: (Optional) List of CC recipients
            bcc: (Optional) List of BCC recipients
            
        Returns:
            Status of the draft creation including the draft ID
        """
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
                groups = g_result.get("getGroups", [])
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

    @tool
    async def send_email(
        to: list[str],
        subject: str,
        body: str,
        group_id: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Directly send an email to one or more recipients.
        
        Ally will use this tool when the user says "Ally, send an email to...".
        The user will be asked to confirm before the email is sent.
        
        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body content
            group_id: (Optional) ID of the group this email belongs to
            cc: (Optional) List of CC recipients
            bcc: (Optional) List of BCC recipients
            
        Returns:
            Confirmation that the email was sent
        """
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
        
        client = context.get_client()
        try:
            # 2. Resolve group_id
            if not group_id:
                g_query = """
                query GetGroups($workspaceId: String!) {
                    getGroups(workspaceId: $workspaceId) { id }
                }
                """
                g_result = await client.query(g_query, {"workspaceId": context.workspace_id})
                groups = g_result.get("getGroups", [])
                if groups:
                    group_id = groups[0]["id"]
                else:
                    return "Error: Could not find any group to associate this email with."

            # 3. Create a temporary draft for sending
            create_mutation = """
            mutation CreateEmailDraft($input: CreateEmailDraftInput!, $workspaceId: String!) {
                createEmailDraft(input: $input, workspaceId: $workspaceId) {
                    id
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
            draft_id = create_result.get("createEmailDraft", {}).get("id")
            
            if not draft_id:
                return "Error: Failed to create temporary email draft for sending."
                
            # 4. Trigger send
            send_mutation = """
            mutation SendEmailDraft($id: String!, $workspaceId: String!) {
                sendEmailDraft(id: $id, workspaceId: $workspaceId) {
                    id
                    status
                }
            }
            """
            send_result = await client.mutate(send_mutation, {
                "id": draft_id,
                "workspaceId": context.workspace_id
            })
            
            status = send_result.get("sendEmailDraft", {}).get("status")
            return f"Successfully sent email to {', '.join(to)} (ID: {draft_id}, Status: {status})"
            
        except Exception as e:
            logger.error(f"Error in send_email flow: {e}")
            return f"Error in send_email flow: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_group_columns(
        group_id: str,
        entity_type: str = "company",
    ) -> str:
        """Get all columns defined for a group.
        
        This returns the custom columns (like Status, Priority, etc.) that are
        available for entities in the specified group. Use this to find column IDs
        needed for updating column values.
        
        Args:
            group_id: The ID of the group
            entity_type: Type of entity - "company" or "people" (default: "company")
            
        Returns:
            List of columns with their IDs, names, and data types
        """
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
            
            groups = result.get("getGroups", [])
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
        """Get all select options for a SELECT or MULTISELECT column.
        
        Use this tool after get_group_columns to find available options for
        status-type columns. Returns the option IDs needed for updating values.
        
        Args:
            column_id: The ID of the column (must be a SELECT or MULTISELECT type)
            
        Returns:
            List of available options with their IDs and values
        """
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
            
            options = result.get("getSelectOptionsByColumnId", [])
            
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

    @tool
    async def resolve_column_by_name(
        group_id: str,
        column_name: str,
        entity_type: str = "company",
    ) -> str:
        """Resolve a column name (even with typos) to get its ID for use in other operations.
        
        USE THIS TOOL when you need to find a column by name within a group before
        updating column values. This tool handles typos and partial matches.
        
        Args:
            group_id: The ID of the group containing the column
            column_name: The column name to search for (can include typos)
            entity_type: Type of entity - "company" or "people" (default: "company")
            
        Returns:
            The column ID and details, or suggestions if multiple matches found
        """
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
            
            groups = result.get("getGroups", [])
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
        """Get information about the page the user is currently viewing.
        
        Use this tool when the user asks questions like:
        - "Where am I?"
        - "Which page am I on?"
        - "What am I looking at?"
        - "What page is this?"
        - "Which page is open?"
        
        This tool analyzes the current URL and fetches relevant details about
        the entity or page being viewed (company name, person name, group name, etc.).
        
        Returns:
            A description of the current page and any entity details
        """
        active_url = context.active_url
        
        if not active_url:
            return "I don't have information about which page you're currently viewing. The page context wasn't provided."
        
        client = context.get_client()
        
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
                            groups = group_result.get("getGroups", [])
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

    return [
        # Smart resolvers - use these FIRST to resolve names to IDs
        resolve_company_name,
        resolve_person_name,
        resolve_group_name,
        resolve_column_by_name,
        # Page awareness
        get_current_page,
        # List tools
        list_companies_in_workspace,
        list_people_in_workspace,
        list_groups_in_workspace,
        list_companies_in_group,
        list_people_in_group,
        # Get by ID tools
        get_company_by_id,
        get_person_by_id,
        get_group_by_id,
        # Search tools (also with fuzzy matching)
        search_company_by_name,
        search_person_by_name,
        search_group_by_name,
        # Email/interaction tools
        listEmailsFromPerson,
        listEmailsFromCompany,
        get_email_thread,
        # Drafting and Template tools
        list_email_templates,
        search_email_templates,
        draft_email,
        send_email,
        # Group column tools
        get_group_columns,
        get_column_options,
    ]

