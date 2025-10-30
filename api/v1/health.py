"""
Health check endpoints
"""
import logging
from datetime import datetime
from fastapi import APIRouter
from api.v1.schemas import HealthResponse, ReadyResponse
from config.config_manager import get_config_manager
from database.prisma_client import prisma_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint (liveness probe)
    No authentication required
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check():
    """
    Readiness check endpoint
    Verifies that database and config manager are initialized
    No authentication required
    """
    services = {}
    
    # Check database connection
    try:
        # Try a simple query to verify database is accessible
        await prisma_client.connect()
        services["database"] = "ready"
    except Exception as e:
        logger.error(f"Database not ready: {e}")
        services["database"] = "not_ready"
    
    # Check config manager
    try:
        config_manager = get_config_manager()
        if config_manager._initialized:
            services["config_manager"] = "ready"
        else:
            services["config_manager"] = "not_ready"
    except Exception as e:
        logger.error(f"Config manager not ready: {e}")
        services["config_manager"] = "not_ready"
    
    # Determine overall status
    all_ready = all(status == "ready" for status in services.values())
    overall_status = "ready" if all_ready else "not_ready"
    
    return ReadyResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.utcnow().isoformat()
    )

