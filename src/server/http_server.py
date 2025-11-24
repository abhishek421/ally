"""
FastAPI router for Analyst AI HTTP endpoints.

This module aggregates all API routes for the application.
"""

from fastapi import APIRouter
from src.interfaces.api.v1.routes import conversation
from src.interfaces.api.v1.routes import query

# Initialize main API router
router = APIRouter()

# V1 Router
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(conversation.router)
v1_router.include_router(query.router)

# Include V1 router in main router
router.include_router(v1_router)

# Add health check routes here if not in main.py, but main.py has them.
# The new API contract says GET /health and GET /ready. 
# main.py implements /health. /ready is missing.

@router.get("/ready")
async def readiness_check():
    """
    Readiness check verifying dependencies.
    """
    # TODO: Check database/redis/config manager status
    return {
        "status": "ready",
        "services": {
            "database": "ready", # Placeholder
            "config_manager": "ready" # Placeholder
        },
        "timestamp": "iso-timestamp-placeholder"
    }
