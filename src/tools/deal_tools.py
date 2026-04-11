"""DEAL tools — read and write pipeline deals."""

import logging
from typing import Optional

from langchain_core.tools import tool

from src.tools.context_var import get_tool_context
from src.tools.base import LIST_MAX_RESULTS, EntityType, ChangeAction, DataChange
from src.tools.confirmation import request_delete_confirmation, request_create_confirmation

try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    GraphInterrupt = None

logger = logging.getLogger(__name__)


def get_deal_tools() -> list:
    """Tools for reading pipeline deals."""

    @tool
    async def list_deals(
        column_id: str,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        filter_conditions: Optional[list] = None,
        sort_by: Optional[list] = None,
    ) -> str:
        """List deals in a pipeline column with optional filtering and sorting.

        column_id: the pipeline column ID to list deals from. Use get_group_columns
        to find the right column (look for columns with type DEAL or PIPELINE).

        filter_conditions: list of condition dicts, e.g.:
          [{"field": "custom.<column_id>", "operator": "greater_than", "value": ["50000"]}]
          [{"field": "name", "operator": "contains", "value": ["enterprise"]}]
          [{"field": "createdAt", "operator": "this_month"}]

        sort_by: list of sort dicts, e.g.:
          [{"field": "custom.<column_id>", "order": "desc"}]
          [{"field": "createdAt", "order": "asc"}]

        Field format for deal custom columns: "custom.<column_id>"
        (use get_group_columns to find column IDs).

        Available operators: contains, not_contains, equals, not_equals, starts_with,
        ends_with, is_empty, is_not_empty, is_one_of, is_not_one_of, greater_than,
        less_than, greater_than_or_equal, less_than_or_equal, between, not_between,
        before, after, this_week, this_month, this_year.
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetDeals(
            $columnId: String!
            $page: Int
            $limit: Int
            $search: String
            $filter: FilterInput
        ) {
            getDeals(
                columnId: $columnId
                page: $page
                limit: $limit
                search: $search
                filter: $filter
            ) {
                data {
                    id
                    name
                    createdAt
                    updatedAt
                    columnValues { columnId value }
                    peopleMetaData {
                        people { firstName lastName }
                    }
                    companyMetaData {
                        company { name }
                    }
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
                "columnId": column_id,
                "page": page,
                "limit": min(limit, LIST_MAX_RESULTS),
                "search": search,
                "filter": filter_input,
            })

            data = result.get("getDeals") or {}
            deals = data.get("data") or []
            meta = data.get("meta") or {}

            if not deals:
                return "No deals found in this pipeline column."

            total = meta.get("total", len(deals))
            current_page = meta.get("page", 1)

            sort_note = ""
            if sort_by:
                sort_note = f" sorted by {sort_by[0].get('field', '')} ({sort_by[0].get('order', 'asc')})"
            filter_note = f" matching {len(filter_conditions)} filter(s)" if filter_conditions else ""
            lines = [f"Found {total} deals{filter_note}{sort_note} (showing page {current_page}):"]

            active_col_ids = set()
            for s in (sort_by or []):
                field = s.get("field", "")
                if field.startswith("custom."):
                    active_col_ids.add(field.split("custom.", 1)[1])
            for c in (filter_conditions or []):
                field = c.get("field", "")
                if field.startswith("custom."):
                    active_col_ids.add(field.split("custom.", 1)[1])

            for deal in deals:
                name = deal.get("name", "Unnamed Deal")
                parts = [name]

                people_meta = deal.get("peopleMetaData") or []
                people_names = [
                    f"{p.get('people', {}).get('firstName', '')} {p.get('people', {}).get('lastName', '')}".strip()
                    for p in people_meta
                    if p.get("people")
                ]
                if people_names:
                    parts.append(f"people: {', '.join(people_names[:2])}")

                company_meta = deal.get("companyMetaData") or []
                company_names = [
                    c.get("company", {}).get("name", "")
                    for c in company_meta
                    if c.get("company", {}).get("name")
                ]
                if company_names:
                    parts.append(f"company: {', '.join(company_names[:2])}")

                if active_col_ids:
                    col_vals = deal.get("columnValues") or []
                    extras = [
                        cv.get("value")
                        for cv in col_vals
                        if cv.get("columnId") in active_col_ids and cv.get("value")
                    ]
                    if extras:
                        parts.append(f"[{', '.join(extras)}]")

                lines.append("- " + " — ".join(parts))

            if meta.get("hasNextPage"):
                lines.append(f"(More available — use page={current_page + 1} to see more)")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error listing deals: {e}")
            return f"Error listing deals: {str(e)}"
        finally:
            await client.close()

    @tool
    async def get_deal(deal_id: str) -> str:
        """Get full details for a specific deal by ID.

        Returns deal name, linked people, linked companies, column values, and timestamps.
        Use list_deals to find deal IDs first.
        """
        context = get_tool_context()
        client = context.get_client()

        query = """
        query GetDeal($dealId: String!) {
            getDeal(dealId: $dealId) {
                id
                name
                createdAt
                updatedAt
                columnValues { columnId value }
                peopleMetaData {
                    people {
                        id
                        firstName
                        lastName
                        jobTitle
                        emails { value isPrimary }
                    }
                }
                companyMetaData {
                    company {
                        id
                        name
                    }
                }
                creator {
                    firstName
                    lastName
                }
            }
        }
        """

        try:
            result = await client.query(query, {"dealId": deal_id})
            deal = result.get("getDeal")

            if not deal:
                return f"No deal found with ID {deal_id}."

            lines = [f"Deal: {deal.get('name', 'Unnamed')} (ID: {deal.get('id')})"]

            creator = deal.get("creator") or {}
            if creator:
                lines.append(f"Created by: {creator.get('firstName', '')} {creator.get('lastName', '')}".strip())

            lines.append(f"Created: {deal.get('createdAt', 'Unknown')}")
            lines.append(f"Updated: {deal.get('updatedAt', 'Unknown')}")

            people_meta = deal.get("peopleMetaData") or []
            if people_meta:
                lines.append("Linked people:")
                for pm in people_meta:
                    p = pm.get("people") or {}
                    name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
                    job = p.get("jobTitle", "")
                    emails = p.get("emails") or []
                    email = next((e.get("value") for e in emails if e.get("isPrimary")), None) or \
                            next((e.get("value") for e in emails if e.get("value")), None)
                    detail = name
                    if job:
                        detail += f", {job}"
                    if email:
                        detail += f" <{email}>"
                    lines.append(f"  - {detail} (ID: {p.get('id')})")

            company_meta = deal.get("companyMetaData") or []
            if company_meta:
                lines.append("Linked companies:")
                for cm in company_meta:
                    c = cm.get("company") or {}
                    lines.append(f"  - {c.get('name', 'Unknown')} (ID: {c.get('id')})")

            col_vals = deal.get("columnValues") or []
            if col_vals:
                lines.append("Column values:")
                for cv in col_vals:
                    if cv.get("value"):
                        lines.append(f"  - {cv.get('columnId')}: {cv.get('value')}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error getting deal: {e}")
            return f"Error getting deal: {str(e)}"
        finally:
            await client.close()

    @tool
    async def create_deal(
        name: str,
        column_id: str,
        person_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> str:
        """Create a new deal in a pipeline column, optionally linked to a person or company.

        column_id: the pipeline column ID. Use get_group_columns to find it
        (look for columns with type DEAL or PIPELINE).

        person_id / company_id: optional IDs to link the deal immediately.
        Use resolve_entity to get them.
        """
        confirmation = request_create_confirmation(
            entity_type="deal",
            entity_name=name,
            draft_data={"name": name, "column_id": column_id, "person_id": person_id, "company_id": company_id},
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Deal creation cancelled by user.{feedback}"

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation CreateDeal($deal: DealCreateRequest!) {
            createDeal(deal: $deal) {
                id
                name
                columnId
            }
        }
        """

        try:
            result = await client.mutate(mutation, {
                "deal": {
                    "name": name,
                    "columnId": column_id,
                    **({"peopleId": person_id} if person_id else {}),
                    **({"companyId": company_id} if company_id else {}),
                }
            })

            deal = result.get("createDeal")

            if deal:
                deal_id = deal.get("id")
                change = DataChange(
                    entity_type=EntityType.COMPANY,  # triggers pipeline cache invalidation
                    action=ChangeAction.UPDATED,
                    entity_id=deal_id,
                )
                return f"Successfully created deal '{name}' (ID: {deal_id})." + change.to_marker()
            else:
                return "Failed to create deal — no data returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error creating deal: {e}")
            return f"Error creating deal: {str(e)}"
        finally:
            await client.close()

    @tool
    async def update_deal(deal_id: str, name: str, current_name: Optional[str] = None) -> str:
        """Rename a deal.

        deal_id: ID of the deal to update. Use list_deals to find it.
        name: new name for the deal.
        current_name: current name (used in confirmation display).
        """
        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation UpdateDeal($dealId: String!, $name: String!) {
            updateDeal(dealId: $dealId, name: $name) {
                id
                name
            }
        }
        """

        try:
            result = await client.mutate(mutation, {
                "dealId": deal_id,
                "name": name,
            })

            deal = result.get("updateDeal")

            if deal:
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=deal_id,
                )
                return f"Successfully renamed deal to '{deal.get('name')}'." + change.to_marker()
            else:
                return "Failed to update deal — no data returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error updating deal: {e}")
            return f"Error updating deal: {str(e)}"
        finally:
            await client.close()

    @tool
    async def delete_deal(deal_id: str, deal_name: str) -> str:
        """Permanently delete a deal. Asks for confirmation before executing.

        deal_id: ID of the deal. Use list_deals to find it.
        deal_name: display name shown in the confirmation dialog.
        """
        confirmation = request_delete_confirmation(
            entity_type="deal",
            entity_name=deal_name,
            context=f"Permanently delete deal '{deal_name}'? This cannot be undone.",
        )

        if not confirmation.confirmed:
            feedback = f" Feedback: {confirmation.feedback}" if confirmation.feedback else ""
            return f"Deletion cancelled by user.{feedback}"

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation DeleteDeals($dealIds: [String!]!) {
            deleteDeals(dealIds: $dealIds)
        }
        """

        try:
            result = await client.mutate(mutation, {"dealIds": [deal_id]})
            success = result.get("deleteDeals")

            if success:
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=deal_id,
                )
                return f"Successfully deleted deal '{deal_name}'." + change.to_marker()
            else:
                return "Failed to delete deal — no confirmation returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error deleting deal: {e}")
            return f"Error deleting deal: {str(e)}"
        finally:
            await client.close()

    @tool
    async def attach_deal(
        deal_id: str,
        person_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> str:
        """Link an existing deal to a person or company (or both).

        At least one of person_id or company_id must be provided.
        Use resolve_entity to get IDs.
        """
        if not person_id and not company_id:
            return "Error: provide at least one of person_id or company_id."

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation AttachDeal($dealId: String!, $peopleId: String, $companyId: String) {
            attachDeal(dealId: $dealId, peopleId: $peopleId, companyId: $companyId) {
                dealId
            }
        }
        """

        try:
            result = await client.mutate(mutation, {
                "dealId": deal_id,
                "peopleId": person_id,
                "companyId": company_id,
            })

            data = result.get("attachDeal")

            if data:
                targets = []
                if person_id:
                    targets.append(f"person {person_id}")
                if company_id:
                    targets.append(f"company {company_id}")
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=deal_id,
                )
                return f"Successfully linked deal to {' and '.join(targets)}." + change.to_marker()
            else:
                return "Failed to attach deal — no data returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error attaching deal: {e}")
            return f"Error attaching deal: {str(e)}"
        finally:
            await client.close()

    @tool
    async def remove_deal(
        deal_id: str,
        person_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> str:
        """Unlink a deal from a person or company (or both).

        At least one of person_id or company_id must be provided.
        The deal itself is not deleted — only the link is removed.
        """
        if not person_id and not company_id:
            return "Error: provide at least one of person_id or company_id."

        context = get_tool_context()
        client = context.get_client()

        mutation = """
        mutation RemoveDeal($dealId: String!, $peopleId: String, $companyId: String) {
            removeDeal(dealId: $dealId, peopleId: $peopleId, companyId: $companyId) {
                dealId
            }
        }
        """

        try:
            result = await client.mutate(mutation, {
                "dealId": deal_id,
                "peopleId": person_id,
                "companyId": company_id,
            })

            data = result.get("removeDeal")

            if data:
                targets = []
                if person_id:
                    targets.append(f"person {person_id}")
                if company_id:
                    targets.append(f"company {company_id}")
                change = DataChange(
                    entity_type=EntityType.COMPANY,
                    action=ChangeAction.UPDATED,
                    entity_id=deal_id,
                )
                return f"Successfully unlinked deal from {' and '.join(targets)}." + change.to_marker()
            else:
                return "Failed to remove deal link — no data returned."

        except Exception as e:
            if GraphInterrupt and isinstance(e, GraphInterrupt):
                raise
            if 'Interrupt' in type(e).__name__:
                raise
            logger.error(f"Error removing deal: {e}")
            return f"Error removing deal: {str(e)}"
        finally:
            await client.close()

    return [list_deals, get_deal, create_deal, update_deal, delete_deal, attach_deal, remove_deal]
