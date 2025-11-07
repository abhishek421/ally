"""
Shared dependencies for API endpoints

JWT authentication using AWS Cognito bearer tokens.
The token is verified and the user_id is fetched from the database using the Cognito sub claim.
"""
import logging
import os
from typing import Optional
from fastapi import Header, HTTPException, status
from api.auth.cognito import verify_cognito_token
from database.prisma_client import prisma_client

logger = logging.getLogger(__name__)

# Test mode: allows bypassing Cognito auth for testing
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract and validate Bearer token from Authorization header

    Args:
        authorization: Authorization header value

    Returns:
        Token string (without 'Bearer ' prefix)

    Raises:
        HTTPException: If token is missing or invalid format
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization[7:]  # Remove 'Bearer ' prefix
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is empty"
        )

    return token


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> str:
    """
    Verify Cognito JWT token and fetch user_id from database
    
    This dependency:
    1. Extracts the Bearer token from Authorization header
    2. Verifies the token using AWS Cognito
    3. Extracts the 'sub' claim (Cognito ID) from the token
    4. Queries the user table to find the user by cognitoSub
    5. Returns the user_id from the database

    In TEST_MODE, allows using X-User-ID header directly for testing.

    Args:
        authorization: Authorization header value
        x_user_id: X-User-ID header value (for test mode)

    Returns:
        User ID (UUID string) from the database

    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    # Test mode: allow direct user_id from header
    if TEST_MODE and x_user_id:
        logger.info(f"TEST_MODE: Using user_id from X-User-ID header: {x_user_id}")
        # Verify user exists in database
        try:
            client = await prisma_client.get_client()
            user = await client.user.find_unique(where={"id": x_user_id})
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Test user not found: {x_user_id}"
                )
            return x_user_id
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying test user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error verifying test user"
            )
    
    # Normal mode: use Cognito token
    # Extract token
    token = get_bearer_token(authorization)
    
    try:
        # Verify token and get claims
        claims = verify_cognito_token(token)
        cognito_sub = claims.get('sub')
        
        if not cognito_sub:
            logger.warning("Token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing 'sub' claim"
            )
        
        logger.debug(f"Token verified for Cognito sub: {cognito_sub}")
        
        # Query database to find user by cognitoSub
        client = await prisma_client.get_client()
        user = await client.user.find_unique(
            where={"cognitoSub": cognito_sub}
        )
        
        if not user:
            logger.warning(f"User not found for Cognito sub: {cognito_sub}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: User not found or account not properly set up."
            )
        
        logger.debug(f"User found: {user.id} for Cognito sub: {cognito_sub}")
        return user.id
        
    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted)
        raise
    except ValueError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed due to an internal error"
        )

