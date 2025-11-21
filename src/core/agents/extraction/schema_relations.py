"""
Schema Relationships Module

Defines entity relationships and provides utilities for intelligent multi-tool coordination.
This module helps the DataExtractorAgent understand how different entities are connected
and plan efficient multi-step queries.
"""

from typing import Dict, List, Set, Optional
from enum import Enum


class EntityType(str, Enum):
    """Available entity types in the system"""
    COMPANY = "company"
    PEOPLE = "people"
    EMAIL = "email"
    INTERACTION = "interaction"
    GROUP = "group"
    WORKSPACE = "workspace"


class RelationType(str, Enum):
    """Types of relationships between entities"""
    ONE_TO_MANY = "one_to_many"      # e.g., company -> people
    MANY_TO_ONE = "many_to_one"      # e.g., people -> company
    MANY_TO_MANY = "many_to_many"    # e.g., people <-> groups


class EntityRelation:
    """Defines a relationship between two entities"""
    
    def __init__(
        self,
        from_entity: EntityType,
        to_entity: EntityType,
        relation_type: RelationType,
        join_key: str,
        description: str,
        reverse_join_key: Optional[str] = None
    ):
        self.from_entity = from_entity
        self.to_entity = to_entity
        self.relation_type = relation_type
        self.join_key = join_key  # Field name to use for joining
        self.reverse_join_key = reverse_join_key  # For bidirectional relations
        self.description = description
    
    def __repr__(self):
        return f"{self.from_entity.value} --[{self.relation_type.value}]--> {self.to_entity.value} (via {self.join_key})"


class SchemaRelationships:
    """
    Central registry of all entity relationships in the system.
    
    Based on Prisma schema:
    - people has metaData relation to company (people.metaData.companyId)
    - company has metaData relation to people (company.metaData.peopleId)
    - interaction links to both people and company
    - email (DynamoDB) references person_id and company_id
    - group has many-to-many with people and company
    """
    
    def __init__(self):
        self._relationships: List[EntityRelation] = self._build_relationships()
        self._relationship_map = self._build_relationship_map()
    
    def _build_relationships(self) -> List[EntityRelation]:
        """Define all entity relationships based on Prisma schema"""
        return [
            # Company <-> People relationships
            EntityRelation(
                from_entity=EntityType.COMPANY,
                to_entity=EntityType.PEOPLE,
                relation_type=RelationType.ONE_TO_MANY,
                join_key="company_id",
                reverse_join_key="id",
                description="A company can have multiple people (contacts) linked via metaData table"
            ),
            EntityRelation(
                from_entity=EntityType.PEOPLE,
                to_entity=EntityType.COMPANY,
                relation_type=RelationType.MANY_TO_ONE,
                join_key="id",
                reverse_join_key="company_id",
                description="A person can be linked to companies via metaData table"
            ),
            
            # People -> Email relationships
            EntityRelation(
                from_entity=EntityType.PEOPLE,
                to_entity=EntityType.EMAIL,
                relation_type=RelationType.ONE_TO_MANY,
                join_key="id",
                reverse_join_key="person_id",
                description="A person can have multiple emails (person_id field in DynamoDB)"
            ),
            EntityRelation(
                from_entity=EntityType.EMAIL,
                to_entity=EntityType.PEOPLE,
                relation_type=RelationType.MANY_TO_ONE,
                join_key="person_id",
                reverse_join_key="id",
                description="An email can be linked to a person"
            ),
            
            # Company -> Email relationships
            EntityRelation(
                from_entity=EntityType.COMPANY,
                to_entity=EntityType.EMAIL,
                relation_type=RelationType.ONE_TO_MANY,
                join_key="id",
                reverse_join_key="company_id",
                description="A company can have multiple emails (company_id field in DynamoDB)"
            ),
            EntityRelation(
                from_entity=EntityType.EMAIL,
                to_entity=EntityType.COMPANY,
                relation_type=RelationType.MANY_TO_ONE,
                join_key="company_id",
                reverse_join_key="id",
                description="An email can be linked to a company"
            ),
            
            # People -> Interaction relationships
            EntityRelation(
                from_entity=EntityType.PEOPLE,
                to_entity=EntityType.INTERACTION,
                relation_type=RelationType.ONE_TO_MANY,
                join_key="id",
                reverse_join_key="person_id",
                description="A person can have multiple interactions"
            ),
            EntityRelation(
                from_entity=EntityType.INTERACTION,
                to_entity=EntityType.PEOPLE,
                relation_type=RelationType.MANY_TO_ONE,
                join_key="person_id",
                reverse_join_key="id",
                description="An interaction can be linked to a person"
            ),
            
            # Company -> Interaction relationships
            EntityRelation(
                from_entity=EntityType.COMPANY,
                to_entity=EntityType.INTERACTION,
                relation_type=RelationType.ONE_TO_MANY,
                join_key="id",
                reverse_join_key="company_id",
                description="A company can have multiple interactions"
            ),
            EntityRelation(
                from_entity=EntityType.INTERACTION,
                to_entity=EntityType.COMPANY,
                relation_type=RelationType.MANY_TO_ONE,
                join_key="company_id",
                reverse_join_key="id",
                description="An interaction can be linked to a company"
            ),
            
            # Group <-> People relationships (many-to-many via groupPeople)
            EntityRelation(
                from_entity=EntityType.GROUP,
                to_entity=EntityType.PEOPLE,
                relation_type=RelationType.MANY_TO_MANY,
                join_key="id",
                reverse_join_key="group_id",
                description="A group can contain multiple people, and a person can belong to multiple groups"
            ),
            EntityRelation(
                from_entity=EntityType.PEOPLE,
                to_entity=EntityType.GROUP,
                relation_type=RelationType.MANY_TO_MANY,
                join_key="id",
                reverse_join_key="person_id",
                description="A person can belong to multiple groups"
            ),
            
            # Group <-> Company relationships (many-to-many via groupCompany)
            EntityRelation(
                from_entity=EntityType.GROUP,
                to_entity=EntityType.COMPANY,
                relation_type=RelationType.MANY_TO_MANY,
                join_key="id",
                reverse_join_key="group_id",
                description="A group can contain multiple companies, and a company can belong to multiple groups"
            ),
            EntityRelation(
                from_entity=EntityType.COMPANY,
                to_entity=EntityType.GROUP,
                relation_type=RelationType.MANY_TO_MANY,
                join_key="id",
                reverse_join_key="company_id",
                description="A company can belong to multiple groups"
            ),
        ]
    
    def _build_relationship_map(self) -> Dict[EntityType, List[EntityRelation]]:
        """Build a map of entity -> outgoing relationships for quick lookup"""
        relationship_map: Dict[EntityType, List[EntityRelation]] = {}
        
        for rel in self._relationships:
            if rel.from_entity not in relationship_map:
                relationship_map[rel.from_entity] = []
            relationship_map[rel.from_entity].append(rel)
        
        return relationship_map
    
    def get_relationships_from(self, entity: EntityType) -> List[EntityRelation]:
        """Get all relationships starting from a given entity"""
        return self._relationship_map.get(entity, [])
    
    def get_relationship(self, from_entity: EntityType, to_entity: EntityType) -> Optional[EntityRelation]:
        """Get a specific relationship between two entities"""
        for rel in self._relationships:
            if rel.from_entity == from_entity and rel.to_entity == to_entity:
                return rel
        return None
    
    def can_join(self, from_entity: EntityType, to_entity: EntityType) -> bool:
        """Check if two entities can be joined"""
        return self.get_relationship(from_entity, to_entity) is not None
    
    def get_join_path(self, from_entity: EntityType, to_entity: EntityType) -> Optional[List[EntityRelation]]:
        """
        Find a path of relationships from one entity to another.
        Uses BFS to find the shortest path.
        
        Example: To get from COMPANY to EMAIL:
        Path: [COMPANY -> PEOPLE, PEOPLE -> EMAIL]
        """
        if from_entity == to_entity:
            return []
        
        # Direct relationship
        direct_rel = self.get_relationship(from_entity, to_entity)
        if direct_rel:
            return [direct_rel]
        
        # BFS to find path
        queue = [(from_entity, [])]
        visited: Set[EntityType] = {from_entity}
        
        while queue:
            current_entity, path = queue.pop(0)
            
            # Get all outgoing relationships
            for rel in self.get_relationships_from(current_entity):
                if rel.to_entity == to_entity:
                    # Found target
                    return path + [rel]
                
                if rel.to_entity not in visited:
                    visited.add(rel.to_entity)
                    queue.append((rel.to_entity, path + [rel]))
        
        return None  # No path found
    
    def get_query_plan(self, from_entity: EntityType, to_entity: EntityType) -> Optional[Dict]:
        """
        Generate a query plan for joining two entities.
        
        Returns a structured plan with tool calls and parameters.
        """
        path = self.get_join_path(from_entity, to_entity)
        
        if not path:
            return None
        
        # Build query plan
        plan = {
            "steps": [],
            "requires_multiple_calls": len(path) > 1,
            "path": [rel.from_entity.value for rel in path] + [path[-1].to_entity.value]
        }
        
        for i, rel in enumerate(path):
            step = {
                "step_number": i + 1,
                "tool": rel.from_entity.value,
                "purpose": f"Get {rel.from_entity.value} to extract {rel.join_key}",
                "output_field": rel.join_key,
                "next_tool": rel.to_entity.value if i == len(path) - 1 else path[i + 1].from_entity.value,
                "next_param": rel.reverse_join_key
            }
            plan["steps"].append(step)
        
        return plan
    
    def get_relationship_guidance(self) -> str:
        """
        Generate human-readable guidance about entity relationships
        for inclusion in prompts.
        """
        lines = [
            "ENTITY RELATIONSHIP MAP:",
            "=" * 80,
            "",
            "The following entities are connected in the system:",
            ""
        ]
        
        # Group by source entity
        for entity_type in EntityType:
            relationships = self.get_relationships_from(entity_type)
            if relationships:
                lines.append(f"\n{entity_type.value.upper()}:")
                for rel in relationships:
                    arrow = "-->" if rel.relation_type != RelationType.MANY_TO_MANY else "<-->"
                    lines.append(f"  {arrow} {rel.to_entity.value}: {rel.description}")
                    lines.append(f"      Join via: {rel.from_entity.value}.{rel.join_key} = {rel.to_entity.value}.{rel.reverse_join_key}")
        
        lines.extend([
            "",
            "=" * 80,
            "",
            "MULTI-STEP QUERY PATTERNS:",
            "",
            "1. Company -> People:",
            "   Step 1: Call company tool to get company (returns company.id)",
            "   Step 2: Call people tool with company_id parameter",
            "",
            "2. People -> Emails:",
            "   Step 1: Call people tool to get person (returns person.id)",
            "   Step 2: Call email tool with person_id parameter",
            "",
            "3. Company -> Emails (via people):",
            "   Step 1: Call company tool to get company (returns company.id)",
            "   Step 2: Call email tool with company_id parameter (direct link)",
            "",
            "4. People -> Interactions:",
            "   Step 1: Call people tool to get person (returns person.id)",
            "   Step 2: Call interaction tool with person_id parameter",
            "",
            "IMPORTANT: Use placeholder syntax for dependent parameters:",
            "  <company_id_from_previous_call>",
            "  <person_id_from_previous_call>",
            "  <id_from_previous_call>",
            ""
        ])
        
        return "\n".join(lines)


# Global instance
schema_relationships = SchemaRelationships()


def get_schema_relationships() -> SchemaRelationships:
    """Get the global schema relationships instance"""
    return schema_relationships

