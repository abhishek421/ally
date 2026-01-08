"""GraphQL client for communicating with the backend API."""

import logging
from typing import Any

import httpx
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport

from src.config import get_settings

logger = logging.getLogger(__name__)


class GraphQLClient:
    """Async GraphQL client for the backend API."""

    def __init__(self, auth_token: str, workspace_id: str, session_id: str = ""):
        """Initialize the GraphQL client.
        
        Args:
            auth_token: JWT token for authentication
            workspace_id: Current workspace ID
            session_id: Session ID for backend session validation
        """
        self.auth_token = auth_token
        self.workspace_id = workspace_id
        self.session_id = session_id
        self.settings = get_settings()
        self._client: Client | None = None

    async def _get_client(self) -> Client:
        """Get or create the GQL client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
            }
            # Include session ID if available (required by backend SessionGuard)
            if self.session_id:
                headers["x-session-id"] = self.session_id
            
            transport = HTTPXAsyncTransport(
                url=self.settings.backend_graphql_url,
                headers=headers,
            )
            self._client = Client(
                transport=transport,
                fetch_schema_from_transport=False,
            )
        return self._client

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query or mutation.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Query result data
            
        Raises:
            Exception: If the query fails
        """
        client = await self._get_client()
        
        try:
            async with client as session:
                result = await session.execute(
                    gql(query),
                    variable_values=variables,
                )
                return result
        except Exception as e:
            logger.error(f"GraphQL query failed: {e}")
            raise

    async def query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query.
        
        Alias for execute() for semantic clarity.
        """
        return await self.execute(query, variables)

    async def mutate(
        self,
        mutation: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL mutation.
        
        Alias for execute() for semantic clarity.
        """
        return await self.execute(mutation, variables)

    async def get_current_user_id(self) -> str | None:
        """Get the current user's database ID from the backend.
        
        This resolves the Cognito sub to the actual database user ID.
        
        Returns:
            The user's database ID or None if not found
        """
        query = """
        query GetCurrentUser {
            currentLoggedInUser {
                id
            }
        }
        """
        
        try:
            result = await self.execute(query)
            user = result.get("currentLoggedInUser")
            if user:
                return user.get("id")
            return None
        except Exception as e:
            logger.error(f"Failed to get current user ID: {e}")
            return None

    async def get_current_user_profile(self) -> dict | None:
        """Get the current user's profile from the backend.
        
        Returns user info including first name, last name, and email
        for personalization purposes.
        
        Returns:
            Dict with user profile or None if not found
            {
                "id": str,
                "firstName": str,
                "lastName": str | None,
                "email": str
            }
        """
        query = """
        query GetCurrentUserProfile {
            currentLoggedInUser {
                id
                firstName
                lastName
                email
            }
        }
        """
        
        try:
            result = await self.execute(query)
            user = result.get("currentLoggedInUser")
            if user:
                return {
                    "id": user.get("id"),
                    "firstName": user.get("firstName"),
                    "lastName": user.get("lastName"),
                    "email": user.get("email"),
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get current user profile: {e}")
            return None

    async def close(self):
        """Close the client connection."""
        if self._client is not None:
            await self._client.close_async()
            self._client = None


def get_graphql_client(auth_token: str, workspace_id: str, session_id: str = "") -> GraphQLClient:
    """Factory function to create a GraphQL client.
    
    Args:
        auth_token: JWT token for authentication
        workspace_id: Current workspace ID
        session_id: Session ID for backend session validation
        
    Returns:
        Configured GraphQL client
    """
    return GraphQLClient(auth_token, workspace_id, session_id)

