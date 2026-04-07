"""GraphQL client for communicating with the backend API."""

import logging
from typing import Any

import httpx
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport

from src.config import get_settings

logger = logging.getLogger(__name__)


class GraphQLClient:
    """Async GraphQL client for the backend API.

    Uses a persistent HTTP session to avoid creating a new TCP connection
    for every query.  Call ``connect()`` once (or let ``execute()``
    auto-connect), then reuse for as many queries as needed.  Call
    ``disconnect()`` (or the backward-compatible ``close()``) when done.
    """

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
        self._session = None  # persistent session handle

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open a persistent GQL session (reusable across queries).

        Safe to call multiple times — only opens if not already connected.
        """
        if self._session is not None:
            return  # already connected

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["x-session-id"] = self.session_id

        transport = HTTPXAsyncTransport(
            url=self.settings.backend_graphql_url,
            headers=headers,
            timeout=httpx.Timeout(
                connect=self.settings.graphql_connect_timeout,
                read=self.settings.graphql_request_timeout,
                write=self.settings.graphql_request_timeout,
                pool=self.settings.graphql_connect_timeout,
            ),
        )
        self._client = Client(
            transport=transport,
            fetch_schema_from_transport=False,
        )
        # Enter the async context manager once — keeps the underlying
        # httpx.AsyncClient (and its TCP connection pool) alive.
        self._session = await self._client.__aenter__()

    async def disconnect(self) -> None:
        """Close the persistent session and release resources."""
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass  # best-effort cleanup
            finally:
                self._session = None
                self._client = None

    async def close(self) -> None:
        """Alias for ``disconnect()`` — kept for backward compatibility."""
        await self.disconnect()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query or mutation.

        Auto-connects if the session has not been opened yet.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Query result data

        Raises:
            Exception: If the query fails
        """
        # Auto-connect on first use
        if self._session is None:
            await self.connect()

        try:
            result = await self._session.execute(
                gql(query),
                variable_values=variables,
            )
            return result
        except Exception as e:
            logger.error(f"GraphQL query failed: {e}")
            raise

    async def execute_silent(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query without logging errors (for optional features).

        Same as execute() but swallows the error log. Use for optional features
        where failure is expected (e.g., features backed by missing migrations).
        """
        if self._session is None:
            await self.connect()

        try:
            result = await self._session.execute(
                gql(query),
                variable_values=variables,
            )
            return result
        except Exception as e:
            logger.debug(f"GraphQL optional query failed (expected if feature not yet migrated): {e}")
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

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

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

    async def get_workspace_custom_instructions(self) -> str | None:
        """Get the workspace's custom instructions for the AI agent.

        Returns:
            The custom instructions text or None if not set
        """
        query = """
        query GetWorkspaceCustomInstructions($workspaceId: ID!) {
            getWorkspaceCustomInstructions(workspaceId: $workspaceId) {
                instructions
            }
        }
        """

        logger.info(f"📡 GraphQL: Fetching custom instructions for workspace {self.workspace_id}")
        try:
            result = await self.execute(query, {"workspaceId": self.workspace_id})
            logger.info(f"📡 GraphQL result: {result}")
            instructions_data = result.get("getWorkspaceCustomInstructions")
            if instructions_data:
                instructions = instructions_data.get("instructions")
                logger.info(f"📡 Found instructions: {len(instructions) if instructions else 0} chars")
                return instructions
            logger.info("📡 No instructions data in response")
            return None
        except Exception as e:
            logger.warning(f"📡 Failed to get workspace custom instructions: {e}")
            return None

    async def get_group_custom_instructions(self, group_id: str) -> str | None:
        """Get custom instructions for a specific group.

        Args:
            group_id: The group ID to fetch instructions for

        Returns:
            The custom instructions text or None if not set
        """
        query = """
        query GetGroupCustomInstructions($groupId: String!) {
            getGroupCustomInstructions(groupId: $groupId) {
                instructions
            }
        }
        """

        logger.info(f"📡 GraphQL: Fetching custom instructions for group {group_id}")
        try:
            result = await self.execute_silent(query, {"groupId": group_id})
            instructions_data = result.get("getGroupCustomInstructions")
            if instructions_data:
                instructions = instructions_data.get("instructions")
                logger.info(f"📡 Found group instructions: {len(instructions) if instructions else 0} chars")
                return instructions
            logger.info("📡 No group instructions data in response")
            return None
        except Exception as e:
            logger.debug(f"📡 Group custom instructions not available (migration pending?): {e}")
            return None


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
