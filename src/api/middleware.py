"""Authentication middleware for the Ally API."""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AuthContext:
    """Authenticated user context."""
    
    user_id: str
    workspace_id: str
    auth_token: str
    session_id: str


async def get_current_user(request: Request) -> AuthContext:
    """Extract and validate the current user from request headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AuthContext with user info
        
    Raises:
        HTTPException: If authentication fails
    """
    # Get Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    
    # Extract token
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Get workspace ID from header
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Workspace-ID header",
        )
    
    # Get session ID from header (required for backend API calls)
    session_id = request.headers.get("x-session-id") or ""
    
    # Decode token if it's a JWT, but DO NOT hard-fail if it isn't.
    #
    # Rationale:
    # - In this system the backend GraphQL ultimately validates the token.
    # - The chat service should accept opaque session tokens as well; if they're invalid,
    #   downstream GraphQL/tool calls will fail with a proper auth error.
    user_id = "unknown"
    try:
        # Decode without verification (JWKS verification belongs at the auth boundary).
        payload = jwt.get_unverified_claims(token)
        extracted = payload.get("sub") or payload.get("userId") or payload.get("user_id")
        if isinstance(extracted, str) and extracted.strip():
            user_id = extracted
        else:
            logger.warning(f"Token payload missing user identifier; continuing. keys={list(payload.keys())}")
    except JWTError as e:
        # Not a JWT (or malformed) — treat as opaque and continue.
        logger.warning(f"Token is not a decodable JWT; treating as opaque token. err={e}")
    except Exception as e:
        logger.warning(f"Unexpected token parsing error; continuing. err={e}")

    return AuthContext(
        user_id=user_id,
        workspace_id=workspace_id,
        auth_token=token,
        session_id=session_id,
    )

