"""
Entity Models for Structured Block Responses

These models match the frontend component schemas for rendering
rich entity lists (companies, people, deals, etc.)
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class GroupReference(BaseModel):
    """Reference to a group/tag"""
    groupId: str
    name: str


class CompanyReference(BaseModel):
    """Nested company reference for person entities"""
    id: str
    name: str
    imageUrl: Optional[str] = None


class CompanyEntity(BaseModel):
    """
    Company entity matching frontend CompanyListItemProps
    
    Used for rendering company cards/lists in the chat interface
    """
    id: str
    name: str
    logo: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    peopleCount: int = 0
    groups: List[GroupReference] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class PersonEntity(BaseModel):
    """
    Person entity matching frontend PersonListItemProps
    
    Used for rendering person cards/lists in the chat interface
    """
    id: str
    name: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    image: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    company: Optional[CompanyReference] = None
    groups: List[GroupReference] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class DealEntity(BaseModel):
    """
    Deal entity for future deal support
    
    Used for rendering deal cards/lists in the chat interface
    """
    id: str
    name: str
    value: float
    currency: str = "USD"
    stage: str
    probability: Optional[int] = None
    closeDate: Optional[str] = None
    company: Optional[CompanyReference] = None
    owner: Optional[Dict[str, str]] = None
    groups: List[GroupReference] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


# Type alias for supported entity types
EntityType = Literal["companies", "people", "deals"]

