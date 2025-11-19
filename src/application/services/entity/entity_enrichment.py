"""
Entity Enrichment Service - Fetches CRM data for mentioned entities
"""
import logging
import os
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class EntityEnrichmentService:
    """
    Enriches entity mentions with actual CRM data from GraphQL API
    """

    def __init__(self):
        """Initialize the enrichment service"""
        self.graphql_endpoint = os.getenv("GRAPHQL_ENDPOINT", "http://localhost:4400/graphql")
        self.timeout = 10.0

    def enrich_entity_mentions(
        self,
        entity_mentions: List[Dict[str, Any]],
        access_token: str,
        workspace_id: str
    ) -> List[Dict[str, Any]]:
        """
        Enrich entity mentions with CRM data

        Args:
            entity_mentions: List of entity mentions with entityId, entityType, name
            access_token: User's access token for GraphQL auth
            workspace_id: Workspace ID for context

        Returns:
            List of enriched entities with full CRM data
        """
        if not entity_mentions:
            return []

        enriched_entities = []

        for mention in entity_mentions:
            entity_type = mention.get("entityType", "").lower()
            entity_id = mention.get("entityId", "")
            entity_name = mention.get("name", "")

            if not entity_id:
                logger.warning(f"Skipping entity mention without ID: {entity_name}")
                continue

            try:
                if entity_type == "person":
                    entity_data = self._fetch_person(entity_id, access_token)
                elif entity_type == "company":
                    entity_data = self._fetch_company(entity_id, access_token)
                elif entity_type == "deal":
                    entity_data = self._fetch_deal(entity_id, access_token)
                elif entity_type == "group":
                    entity_data = self._fetch_group(entity_id, access_token)
                else:
                    logger.warning(f"Unknown entity type: {entity_type}")
                    continue

                if entity_data:
                    enriched_entities.append({
                        "type": entity_type,
                        "id": entity_id,
                        "name": entity_name,
                        "data": entity_data
                    })
                    logger.info(f"Enriched {entity_type}: {entity_name} (ID: {entity_id})")
                else:
                    logger.warning(f"No data found for {entity_type}: {entity_name} (ID: {entity_id})")

            except Exception as e:
                logger.error(f"Failed to enrich {entity_type} {entity_name}: {e}")
                continue

        return enriched_entities

    def _fetch_person(self, person_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetch person data from GraphQL"""
        query = """
        query GetPerson($id: UUID!) {
            person(id: $id) {
                id
                name
                email {
                    value
                    isPrimary
                }
                phoneNumber {
                    value
                    isPrimary
                }
                jobTitle
                company {
                    id
                    name
                }
                address {
                    street
                    city
                    state
                    country
                }
                createdAt
                updatedAt
            }
        }
        """

        variables = {"id": person_id}
        result = self._execute_graphql(query, variables, access_token)

        if result and "person" in result:
            return result["person"]
        return None

    def _fetch_company(self, company_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetch company data from GraphQL"""
        query = """
        query GetCompany($id: UUID!) {
            company(id: $id) {
                id
                name
                description
                address {
                    street
                    city
                    state
                    country
                }
                email {
                    value
                    isPrimary
                }
                phoneNumber {
                    value
                    isPrimary
                }
                url {
                    value
                }
                createdAt
                updatedAt
            }
        }
        """

        variables = {"id": company_id}
        result = self._execute_graphql(query, variables, access_token)

        if result and "company" in result:
            return result["company"]
        return None

    def _fetch_deal(self, deal_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetch deal data from GraphQL"""
        query = """
        query GetDeal($id: UUID!) {
            deal(id: $id) {
                id
                name
                status
                value
                stage
                closeDate
                company {
                    id
                    name
                }
                createdAt
                updatedAt
            }
        }
        """

        variables = {"id": deal_id}
        result = self._execute_graphql(query, variables, access_token)

        if result and "deal" in result:
            return result["deal"]
        return None

    def _fetch_group(self, group_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetch group data from GraphQL"""
        query = """
        query GetGroup($id: UUID!) {
            group(id: $id) {
                id
                name
                description
                type
                createdAt
                updatedAt
            }
        }
        """

        variables = {"id": group_id}
        result = self._execute_graphql(query, variables, access_token)

        if result and "group" in result:
            return result["group"]
        return None

    def _execute_graphql(
        self,
        query: str,
        variables: Dict[str, Any],
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Execute GraphQL query"""
        try:
            response = requests.post(
                self.graphql_endpoint,
                json={
                    "query": query,
                    "variables": variables
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"GraphQL request failed: {response.status_code} - {response.text}")
                return None

            data = response.json()

            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None

            return data.get("data")

        except Exception as e:
            logger.error(f"GraphQL request exception: {e}")
            return None

    def format_enriched_entities_for_context(self, enriched_entities: List[Dict[str, Any]]) -> str:
        """
        Format enriched entities into a readable context string for the LLM

        Args:
            enriched_entities: List of enriched entity data

        Returns:
            Formatted string to add to LLM context
        """
        if not enriched_entities:
            return ""

        lines = ["\n📋 ENRICHED CRM DATA FOR MENTIONED ENTITIES:\n"]

        for entity in enriched_entities:
            entity_type = entity["type"].upper()
            entity_name = entity["name"]
            entity_id = entity["id"]
            entity_data = entity["data"]

            lines.append(f"\n{entity_type}: {entity_name} (ID: {entity_id})")
            lines.append("-" * 60)

            if entity["type"] == "person":
                lines.extend(self._format_person_data(entity_data))
            elif entity["type"] == "company":
                lines.extend(self._format_company_data(entity_data))
            elif entity["type"] == "deal":
                lines.extend(self._format_deal_data(entity_data))
            elif entity["type"] == "group":
                lines.extend(self._format_group_data(entity_data))

            lines.append("")  # Empty line between entities

        lines.append("\nIMPORTANT: Use this CRM data when answering questions about the mentioned entities. This is real, current data from the user's workspace.\n")

        return "\n".join(lines)

    def _format_person_data(self, data: Dict[str, Any]) -> List[str]:
        """Format person data"""
        lines = []

        if data.get("email"):
            emails = data["email"] if isinstance(data["email"], list) else [data["email"]]
            primary_email = next((e["value"] for e in emails if e.get("isPrimary")), None)
            if primary_email:
                lines.append(f"  Email: {primary_email}")

        if data.get("phoneNumber"):
            phones = data["phoneNumber"] if isinstance(data["phoneNumber"], list) else [data["phoneNumber"]]
            primary_phone = next((p["value"] for p in phones if p.get("isPrimary")), None)
            if primary_phone:
                lines.append(f"  Phone: {primary_phone}")

        if data.get("jobTitle"):
            lines.append(f"  Job Title: {data['jobTitle']}")

        if data.get("company"):
            lines.append(f"  Company: {data['company']['name']} (ID: {data['company']['id']})")

        if data.get("address"):
            addr = data["address"]
            if isinstance(addr, list) and addr:
                addr = addr[0]
            if isinstance(addr, dict):
                address_parts = [addr.get("city"), addr.get("state"), addr.get("country")]
                address_str = ", ".join([p for p in address_parts if p])
                if address_str:
                    lines.append(f"  Location: {address_str}")

        return lines

    def _format_company_data(self, data: Dict[str, Any]) -> List[str]:
        """Format company data"""
        lines = []

        if data.get("description"):
            lines.append(f"  Description: {data['description']}")

        if data.get("email"):
            emails = data["email"] if isinstance(data["email"], list) else [data["email"]]
            primary_email = next((e["value"] for e in emails if e.get("isPrimary")), None)
            if primary_email:
                lines.append(f"  Email: {primary_email}")

        if data.get("phoneNumber"):
            phones = data["phoneNumber"] if isinstance(data["phoneNumber"], list) else [data["phoneNumber"]]
            primary_phone = next((p["value"] for p in phones if p.get("isPrimary")), None)
            if primary_phone:
                lines.append(f"  Phone: {primary_phone}")

        if data.get("url"):
            urls = data["url"] if isinstance(data["url"], list) else [data["url"]]
            if urls and urls[0]:
                lines.append(f"  Website: {urls[0].get('value', '')}")

        if data.get("address"):
            addr = data["address"]
            if isinstance(addr, list) and addr:
                addr = addr[0]
            if isinstance(addr, dict):
                address_parts = [addr.get("city"), addr.get("state"), addr.get("country")]
                address_str = ", ".join([p for p in address_parts if p])
                if address_str:
                    lines.append(f"  Location: {address_str}")

        return lines

    def _format_deal_data(self, data: Dict[str, Any]) -> List[str]:
        """Format deal data"""
        lines = []

        if data.get("status"):
            lines.append(f"  Status: {data['status']}")

        if data.get("value"):
            lines.append(f"  Value: ${data['value']:,.2f}")

        if data.get("stage"):
            lines.append(f"  Stage: {data['stage']}")

        if data.get("closeDate"):
            lines.append(f"  Close Date: {data['closeDate']}")

        if data.get("company"):
            lines.append(f"  Company: {data['company']['name']} (ID: {data['company']['id']})")

        return lines

    def _format_group_data(self, data: Dict[str, Any]) -> List[str]:
        """Format group data"""
        lines = []

        if data.get("description"):
            lines.append(f"  Description: {data['description']}")

        if data.get("type"):
            lines.append(f"  Type: {data['type']}")

        return lines


# Global singleton instance
_enrichment_service: Optional[EntityEnrichmentService] = None


def get_enrichment_service() -> EntityEnrichmentService:
    """Get or create the global enrichment service instance"""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = EntityEnrichmentService()
    return _enrichment_service
