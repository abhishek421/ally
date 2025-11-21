"""Data access abstraction for CRM tools."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID


class DataAccessInterface(ABC):
    """Abstract interface for CRM data access."""

    @abstractmethod
    def search_people(
        self,
        workspace_id: str,
        query: Optional[str] = None,
        email: Optional[str] = None,
        job_title: Optional[str] = None,
        company_id: Optional[str] = None,
        group_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        has_interactions_since: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search for people."""
        pass

    @abstractmethod
    def get_person_by_id(
        self,
        workspace_id: str,
        person_id: str,
        include: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get person by ID."""
        pass

    # Add more abstract methods as needed...
    # For now, we'll implement a mock version


class MockDataAccess(DataAccessInterface):
    """Mock data access for development/testing."""

    def search_people(
        self,
        workspace_id: str,
        query: Optional[str] = None,
        email: Optional[str] = None,
        job_title: Optional[str] = None,
        company_id: Optional[str] = None,
        group_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        has_interactions_since: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Mock search people implementation."""
        return {
            "results": [],
            "total": 0,
            "hasMore": False,
        }

    def get_person_by_id(
        self,
        workspace_id: str,
        person_id: str,
        include: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mock get person by ID implementation."""
        return {
            "person": None,
            "companies": None,
            "primaryCompany": None,
            "deals": None,
            "interactions": None,
            "emails": None,
            "phones": None,
            "addresses": None,
            "urls": None,
            "customFields": None,
            "groups": None,
        }


# Global data access instance
_data_access: Optional[DataAccessInterface] = None


def get_data_access() -> DataAccessInterface:
    """Get data access instance."""
    global _data_access
    if _data_access is None:
        try:
            from .postgresql_data_access import PostgreSQLDataAccess
            _data_access = PostgreSQLDataAccess()
        except Exception as e:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Failed to initialize PostgreSQLDataAccess, using MockDataAccess: {e}")
            _data_access = MockDataAccess()
    return _data_access


def set_data_access(access: DataAccessInterface) -> None:
    """Set data access instance (for dependency injection)."""
    global _data_access
    _data_access = access

