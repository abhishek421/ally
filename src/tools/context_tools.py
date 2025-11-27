"""Context query tools for CRM."""

from datetime import datetime
from typing import Any, Dict, Optional

from ..utils.logger import get_logger
from .base import Tool
from .data_access import get_data_access

logger = get_logger(__name__)


class GetAccountContextTool(Tool):
    """Get complete account context (company + people + deals + activity)."""

    @property
    def name(self) -> str:
        return "get_account_context"

    @property
    def description(self) -> str:
        return (
            "Get complete account context including company, people, deals, interactions, "
            "and engagement summary. Provides comprehensive view of account relationship."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "company_id": {"type": "string", "description": "Company UUID (required)"},
                "include_employee_interactions": {
                    "type": "boolean",
                    "description": "Include employee interactions (default: false)",
                },
                "interaction_limit": {
                    "type": "integer",
                    "description": "Maximum number of interactions to include (default: 50)",
                },
                "deals_limit": {
                    "type": "integer",
                    "description": "Maximum number of deals to include (default: 50)",
                },
            },
            "required": ["workspace_id", "company_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        company_id = kwargs.get("company_id")
        include_employee_interactions = kwargs.get("include_employee_interactions", False)
        interaction_limit = kwargs.get("interaction_limit", 50)
        deals_limit = kwargs.get("deals_limit", 50)

        if not workspace_id or not company_id:
            raise ValueError("workspace_id and company_id are required")

        logger.info(
            "Getting account context",
            workspace_id=workspace_id,
            company_id=company_id,
            include_employee_interactions=include_employee_interactions,
        )

        data_access = get_data_access()

        # Get company details
        company_result = data_access.get_company_by_id(
            workspace_id=workspace_id,
            company_id=company_id,
            include={"emails": True, "phones": True, "urls": True},
        )

        if not company_result.get("company"):
            return {"error": "Company not found"}

        # Get people
        people_result = data_access.get_company_people(
            workspace_id=workspace_id,
            company_id=company_id,
        )

        # Get deals
        deals_result = data_access.get_company_deals(
            workspace_id=workspace_id,
            company_id=company_id,
            limit=deals_limit,
        )

        # Get interactions
        interactions_result = data_access.get_company_interactions(
            workspace_id=workspace_id,
            company_id=company_id,
            include_employee_interactions=include_employee_interactions,
            limit=interaction_limit,
        )

        return {
            "company": company_result.get("company"),
            "people": [p.get("person") for p in people_result.get("people", [])],
            "deals": [d.get("deal") for d in deals_result.get("deals", [])],
            "interactions": interactions_result.get("interactions", []),
            "summary": {
                "totalPeople": people_result.get("total", 0),
                "keyContacts": people_result.get("summary", {}).get("keyContacts", 0),
                "totalDeals": deals_result.get("total", 0),
                "totalDealValue": deals_result.get("summary", {}).get("totalValue", 0.0),
                "totalInteractions": interactions_result.get("total", 0),
                "lastInteractionDate": interactions_result.get("summary", {}).get("lastInteractionDate"),
                "engagementTrend": "stable",
            },
        }


class GetDealContextTool(Tool):
    """Get complete deal context with all related information."""

    @property
    def name(self) -> str:
        return "get_deal_context"

    @property
    def description(self) -> str:
        return "Get complete deal context with all related information including people, companies, interactions, and summary."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "deal_id": {"type": "string", "description": "Deal UUID (required)"},
                "interaction_limit": {
                    "type": "integer",
                    "description": "Maximum number of interactions to include (default: 50)",
                },
            },
            "required": ["workspace_id", "deal_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        deal_id = kwargs.get("deal_id")
        interaction_limit = kwargs.get("interaction_limit", 50)

        if not workspace_id or not deal_id:
            raise ValueError("workspace_id and deal_id are required")

        logger.info("Getting deal context", workspace_id=workspace_id, deal_id=deal_id)

        data_access = get_data_access()

        # Get deal details
        deal_result = data_access.get_deal_by_id(
            workspace_id=workspace_id,
            deal_id=deal_id,
            include={"people": True, "companies": True, "column_values": True},
        )

        if not deal_result.get("deal"):
            return {"error": "Deal not found"}

        # Get interactions
        interactions_result = data_access.get_deal_interactions(
            workspace_id=workspace_id,
            deal_id=deal_id,
            limit=interaction_limit,
        )

        people = deal_result.get("people", [])
        companies = deal_result.get("companies", [])

        return {
            "deal": deal_result.get("deal"),
            "stage": deal_result.get("stage"),
            "people": people,
            "companies": companies,
            "interactions": interactions_result.get("interactions", []),
            "summary": {
                "totalContacts": len(people),
                "totalCompanies": len(companies),
                "totalInteractions": interactions_result.get("total", 0),
                "lastInteractionDate": interactions_result.get("summary", {}).get("lastInteractionDate"),
                "daysSinceLastInteraction": interactions_result.get("summary", {}).get("daysSinceLastInteraction", 0),
                "daysInCurrentStage": deal_result.get("metadata", {}).get("daysInCurrentStage", 0),
            },
        }


class FindRelationshipsTool(Tool):
    """Find relationships between two entities."""

    @property
    def name(self) -> str:
        return "find_relationships"

    @property
    def description(self) -> str:
        return "Find relationships between two entities (person, company, or deal) and calculate degrees of separation."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "entity1": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["person", "company", "deal"],
                            "description": "Type of first entity",
                        },
                        "id": {"type": "string", "description": "First entity UUID"},
                    },
                    "required": ["type", "id"],
                    "description": "First entity",
                },
                "entity2": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["person", "company", "deal"],
                            "description": "Type of second entity",
                        },
                        "id": {"type": "string", "description": "Second entity UUID"},
                    },
                    "required": ["type", "id"],
                    "description": "Second entity",
                },
            },
            "required": ["workspace_id", "entity1", "entity2"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        entity1 = kwargs.get("entity1")
        entity2 = kwargs.get("entity2")

        if not workspace_id or not entity1 or not entity2:
            raise ValueError("workspace_id, entity1, and entity2 are required")

        logger.info(
            "Finding relationships",
            workspace_id=workspace_id,
            entity1_type=entity1.get("type"),
            entity2_type=entity2.get("type"),
        )

        data_access = get_data_access()
        relationships = []
        degrees = None

        entity1_type = entity1.get("type")
        entity1_id = entity1.get("id")
        entity2_type = entity2.get("type")
        entity2_id = entity2.get("id")

        # Find direct relationships
        if entity1_type == "person" and entity2_type == "company":
            # Check if person works at company
            person_companies = data_access.get_person_companies(
                workspace_id=workspace_id,
                person_id=entity1_id,
            )
            for comp in person_companies.get("companies", []):
                if comp.get("company", {}).get("id") == entity2_id:
                    relationships.append({
                        "type": "works_at",
                        "from": entity1,
                        "to": entity2,
                        "isPrimary": comp.get("isPrimary", False),
                    })
                    degrees = 1

        elif entity1_type == "company" and entity2_type == "person":
            # Check if company employs person
            company_people = data_access.get_company_people(
                workspace_id=workspace_id,
                company_id=entity1_id,
            )
            for person in company_people.get("people", []):
                if person.get("person", {}).get("id") == entity2_id:
                    relationships.append({
                        "type": "employs",
                        "from": entity1,
                        "to": entity2,
                        "isPrimary": person.get("isPrimary", False),
                    })
                    degrees = 1

        elif entity1_type == "person" and entity2_type == "deal":
            # Check if person is on deal
            deal_people = data_access.get_deal_people(
                workspace_id=workspace_id,
                deal_id=entity2_id,
            )
            for person in deal_people.get("people", []):
                if person.get("person", {}).get("id") == entity1_id:
                    relationships.append({
                        "type": "involved_in",
                        "from": entity1,
                        "to": entity2,
                    })
                    degrees = 1

        elif entity1_type == "company" and entity2_type == "deal":
            # Check if company is on deal
            deal_companies = data_access.get_deal_companies(
                workspace_id=workspace_id,
                deal_id=entity2_id,
            )
            for company in deal_companies.get("companies", []):
                if company.get("id") == entity1_id:
                    relationships.append({
                        "type": "involved_in",
                        "from": entity1,
                        "to": entity2,
                    })
                    degrees = 1

        return {
            "relationships": relationships,
            "degreesOfSeparation": degrees,
        }


class GetRelationshipNetworkTool(Tool):
    """Get relationship network around an entity."""

    @property
    def name(self) -> str:
        return "get_relationship_network"

    @property
    def description(self) -> str:
        return "Get relationship network around an entity with relationship strength and shared entities."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace identifier (required)"},
                "entity_type": {
                    "type": "string",
                    "enum": ["person", "company", "deal"],
                    "description": "Type of entity (required)",
                },
                "entity_id": {"type": "string", "description": "Entity UUID (required)"},
                "depth": {
                    "type": "integer",
                    "description": "Network depth (default: 1, direct connections only)",
                    "minimum": 1,
                    "maximum": 3,
                },
            },
            "required": ["workspace_id", "entity_type", "entity_id"],
        }

    def execute(self, **kwargs: Any) -> Any:
        workspace_id = kwargs.get("workspace_id")
        entity_type = kwargs.get("entity_type")
        entity_id = kwargs.get("entity_id")
        depth = kwargs.get("depth", 1)

        if not workspace_id or not entity_type or not entity_id:
            raise ValueError("workspace_id, entity_type, and entity_id are required")

        logger.info(
            "Getting relationship network",
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            depth=depth,
        )

        data_access = get_data_access()
        connections = []
        center = None

        if entity_type == "person":
            # Get person details
            person_result = data_access.get_person_by_id(
                workspace_id=workspace_id,
                person_id=entity_id,
                include={"companies": True, "deals": True, "groups": True},
            )
            center = person_result.get("person")

            # Get connected companies
            for comp in person_result.get("companies", []):
                connections.append({
                    "type": "company",
                    "relationship": "works_at",
                    "entity": comp.get("company"),
                    "strength": "primary" if comp.get("isPrimary") else "secondary",
                })

            # Get connected deals
            for deal in person_result.get("deals", []):
                connections.append({
                    "type": "deal",
                    "relationship": "involved_in",
                    "entity": deal.get("deal"),
                    "strength": "direct",
                })

        elif entity_type == "company":
            # Get company details
            company_result = data_access.get_company_by_id(
                workspace_id=workspace_id,
                company_id=entity_id,
                include={"people": True, "deals": True, "groups": True},
            )
            center = company_result.get("company")

            # Get connected people
            people_result = data_access.get_company_people(
                workspace_id=workspace_id,
                company_id=entity_id,
            )
            for person in people_result.get("people", []):
                connections.append({
                    "type": "person",
                    "relationship": "employs",
                    "entity": person.get("person"),
                    "strength": "primary" if person.get("isPrimary") else "secondary",
                })

            # Get connected deals
            deals_result = data_access.get_company_deals(
                workspace_id=workspace_id,
                company_id=entity_id,
            )
            for deal in deals_result.get("deals", []):
                connections.append({
                    "type": "deal",
                    "relationship": "involved_in",
                    "entity": deal.get("deal"),
                    "strength": "direct",
                })

        elif entity_type == "deal":
            # Get deal details
            deal_result = data_access.get_deal_by_id(
                workspace_id=workspace_id,
                deal_id=entity_id,
                include={"people": True, "companies": True},
            )
            center = deal_result.get("deal")

            # Get connected people
            for person in deal_result.get("people", []):
                connections.append({
                    "type": "person",
                    "relationship": "contact",
                    "entity": person,
                    "strength": "direct",
                })

            # Get connected companies
            for company in deal_result.get("companies", []):
                connections.append({
                    "type": "company",
                    "relationship": "account",
                    "entity": company,
                    "strength": "direct",
                })

        return {
            "center": center,
            "connections": connections,
        }

