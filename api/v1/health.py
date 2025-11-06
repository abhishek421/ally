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

    # Check embedding model (optional - don't fail if not loaded)
    try:
        from services.vector_store import _embedding_model
        services["embedding_model"] = "ready" if _embedding_model is not None else "not_loaded"
    except Exception:
        services["embedding_model"] = "not_loaded"

    # Determine overall status (embedding model is optional)
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
    Warmup endpoint to trigger lazy-loaded components
    Useful for avoiding cold start on first real query
    No authentication required
    """
    from services.vector_store import get_embedding_model, get_qdrant_client

    result = {
        "embedding_model": "not_loaded",
        "qdrant_client": "not_loaded"
    }

    # Load embedding model
    try:
        get_embedding_model()
        result["embedding_model"] = "loaded"
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        result["embedding_model"] = f"error: {str(e)}"

    # Initialize Qdrant client
    try:
        get_qdrant_client()
        result["qdrant_client"] = "initialized"
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant: {e}")
        result["qdrant_client"] = f"error: {str(e)}"

    return {
        "status": "warmup_complete",
        "components": result,
        "timestamp": datetime.utcnow().isoformat()
    }

