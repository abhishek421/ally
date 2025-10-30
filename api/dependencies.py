"""
Shared dependencies for API endpoints
"""
import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from api.auth.cognito import verify_cognito_token

logger = logging.getLogger(__name__)


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


def verify_token_dependency(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify JWT token and return claims
    This is a FastAPI dependency that validates the token but doesn't extract workspace_id/user_id
    (those come from the request body explicitly per requirements)
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Dictionary containing token claims
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = get_bearer_token(authorization)
    
    try:
        claims = verify_cognito_token(token)
        logger.debug(f"Token verified for user: {claims.get('sub')}")
        return claims
    except ValueError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

