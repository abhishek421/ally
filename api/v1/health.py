"""
Health check endpoints
"""
import logging
import os
import re
from datetime import datetime
from fastapi import APIRouter
from api.v1.schemas import HealthResponse, ReadyResponse
from config.config_manager import get_config_manager
from database.prisma_client import prisma_client

logger = logging.getLogger(__name__)

router = APIRouter()


def mask_database_url(url: str) -> str:
    """
    Mask password in database URL for secure logging
    Example: postgresql://user:password@host:5432/db -> postgresql://user:****@host:5432/db
    """
    if not url:
        return "NOT_SET"

    # Pattern to match password in connection string
    # Matches: protocol://user:password@host or protocol://user:password@host:port
    pattern = r'(://[^:]+:)([^@]+)(@)'
    masked = re.sub(pattern, r'\1****\3', url)
    return masked


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

    # Log database URL
    db_url = os.getenv("DATABASE_URL", "NOT_SET")
    logger.info(f"Database URL: {db_url}")

    # Check database connection
    try:
        # Try a simple query to verify database is accessible
        await prisma_client.connect()
        services["database"] = "ready"
        logger.info(f"Database connection successful to: {db_url}")
    except Exception as e:
        logger.error(f"Database not ready: {e}")
        logger.error(f"Failed to connect to: {db_url}")
        services["database"] = "not_ready"

    # Check config manager
    try:
        config_manager = get_config_manager()
        if not config_manager._initialized:
            # Try to initialize if not already initialized
            try:
                await config_manager.initialize()
            except Exception as init_error:
                logger.warning(f"Config manager initialization failed: {init_error}")

        if config_manager._initialized:
            services["config_manager"] = "ready"
        else:
            services["config_manager"] = "not_ready"
    except Exception as e:
        logger.error(f"Config manager not ready: {e}")
        services["config_manager"] = "not_ready"

    # Determine overall status
    critical_services_ready = all(
        services.get(service) == "ready"
        for service in ["database", "config_manager"]
    )
    overall_status = "ready" if critical_services_ready else "not_ready"

    return ReadyResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/warmup")
async def warmup():
    """
    Warmup endpoint (deprecated - no lazy-loaded components to warm up)
    No authentication required
    """
    return {
        "status": "warmup_complete",
        "message": "No components to warm up (vector DB removed)",
        "timestamp": datetime.utcnow().isoformat()
    }

