"""
AWS Cognito JWT token verification
"""
import os
import logging
from typing import Dict, Any
from jose import jwt, JWTError, jwk
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_jwks_url(user_pool_id: str, region: str) -> str:
    """Get JWKS URL for Cognito User Pool"""
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"


@lru_cache(maxsize=1)
def _get_jwks(user_pool_id: str, region: str) -> Dict[str, Any]:
    """Fetch and cache JWKS (JSON Web Key Set) from Cognito"""
    jwks_url = _get_jwks_url(user_pool_id, region)
    try:
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from {jwks_url}: {e}")
        raise


def verify_cognito_token(token: str) -> Dict[str, Any]:
    """
    Verify AWS Cognito JWT token and return claims
    
    Args:
        token: JWT token string (without 'Bearer ' prefix)
        
    Returns:
        Dictionary containing token claims if valid
        
    Raises:
        ValueError: If token is invalid or expired
        JWTError: If JWT verification fails
    """
    # Get configuration from environment
    user_pool_id = os.getenv("AWS_COGNITO_USER_POOL_ID")
    region = os.getenv("AWS_REGION")

    if not user_pool_id:
        raise ValueError("AWS_COGNITO_USER_POOL_ID environment variable is not set")
    if not region:
        raise ValueError("AWS_REGION environment variable is not set")
    
    # Remove 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    
    if not token:
        raise ValueError("Token is empty")
    
    try:
        # Fetch JWKS
        jwks = _get_jwks(user_pool_id, region)
        
        # Get the key from JWKS
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise ValueError("Token header missing 'kid' claim")
        
        # Find the key in JWKS
        key_data = None
        for jwk_key in jwks.get("keys", []):
            if jwk_key.get("kid") == kid:
                key_data = jwk_key
                break
        
        if not key_data:
            raise ValueError("Unable to find appropriate key in JWKS")
        
        # Construct the RSA key from JWK
        rsa_key = jwk.construct(key_data)
        
        # Verify token using the key
        issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=None,  # Optional: validate audience if needed
            issuer=issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": False,  # Set to True if you want to validate audience
            }
        )
        
        logger.debug(f"Token verified successfully for user: {claims.get('sub')}")
        return claims
        
    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise ValueError("Token has expired")
    except JWTClaimsError as e:
        logger.warning(f"JWT claims error: {e}")
        raise ValueError(f"Invalid token claims: {e}")
    except JWTError as e:
        logger.error(f"JWT verification error: {e}")
        raise ValueError(f"Token verification failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error verifying token: {e}")
        raise ValueError(f"Token verification failed: {e}")

