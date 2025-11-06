"""
Health check endpoints
"""
import logging
from datetime import datetime
from fastapi import APIRouter
from typing import Dict, Any
from api.v1.schemas import HealthResponse, ReadyResponse
from config.config_manager import get_config_manager
from database.prisma_client import prisma_client
from database.redis_client import redis_client
from database.dynamodb_client import dynamodb_client

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
    all_ready = all(status == "ready" for status in services.values())
    overall_status = "ready" if all_ready else "not_ready"
    
    return ReadyResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/pool-stats")
async def pool_stats() -> Dict[str, Any]:
    """
    Get connection pool statistics for all database clients.
    Useful for monitoring connection pool health and usage.
    No authentication required (for monitoring purposes).
    """
    stats = {
        "timestamp": datetime.utcnow().isoformat(),
        "databases": {}
    }
    
    # PostgreSQL pool stats
    try:
        stats["databases"]["postgresql"] = prisma_client.get_pool_stats()
        # Test connection
        await prisma_client.health_check()
        stats["databases"]["postgresql"]["health"] = "healthy"
    except Exception as e:
        stats["databases"]["postgresql"] = {
            "health": "unhealthy",
            "error": str(e)
        }
    
    # Redis pool stats
    try:
        stats["databases"]["redis"] = redis_client.get_pool_stats()
        # Test connection
        await redis_client.health_check()
        stats["databases"]["redis"]["health"] = "healthy"
    except Exception as e:
        stats["databases"]["redis"] = {
            "health": "unhealthy",
            "error": str(e)
        }
    
    # DynamoDB pool stats
    try:
        stats["databases"]["dynamodb"] = dynamodb_client.get_pool_stats()
        # Test connection
        await dynamodb_client.health_check()
        stats["databases"]["dynamodb"]["health"] = "healthy"
    except Exception as e:
        stats["databases"]["dynamodb"] = {
            "health": "unhealthy",
            "error": str(e)
        }
    
    return stats

