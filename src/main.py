"""
Main entrypoint for the CRM AI Copilot server.

This module bootstraps the FastAPI application that serves the AI agent:

1. Initializes FastAPI app with CORS middleware
2. Loads the compiled LangGraph agent (graph_app)
3. Registers HTTP/SSE routes for agent communication
4. Provides health checks and debug endpoints
5. Manages application lifecycle (startup/shutdown)

Server Architecture:

    Frontend (React/Vue)
         ↓ HTTP POST
    FastAPI Server (this file)
         ↓ invokes
    LangGraph Agent (graph_app)
         ↓ streams events
    SSE Transport
         ↓ events
    Frontend (real-time updates)

API Endpoints:

Production Endpoints:
- POST /api/message - Send message and get response via SSE stream
- GET /health - Health check for load balancers and monitoring

Debug Endpoints:
- POST /invoke - Direct graph invocation (for testing without SSE)

The /api/message endpoint is the primary production interface:
1. Accepts user message with conversation context
2. Loads conversation state from session store
3. Invokes LangGraph agent with streaming
4. Streams events to frontend via Server-Sent Events (SSE)
5. Saves updated conversation state

This architecture enables:
- Real-time streaming of agent thoughts and tool executions
- Stateful multi-turn conversations with memory
- Graceful error handling and recovery
- Horizontal scaling with shared Redis state

Production Deployment:

Run with uvicorn in production mode:
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

Or use gunicorn with uvicorn workers:
    gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker

Environment Variables:
- PORT: Server port (default: 8000)
- GRAPHQL_ENDPOINT: CRM backend GraphQL API URL
- REDIS_URL: Redis connection URL for session storage

Future Enhancements:

TODO: Add WebSocket support for bidirectional streaming
TODO: Add authentication middleware (JWT validation)
TODO: Add rate limiting per user/workspace
TODO: Add request validation and sanitization
TODO: Add metrics endpoint for Prometheus/Grafana
TODO: Add OpenAPI/Swagger documentation customization
TODO: Add request tracing and correlation IDs
TODO: Add circuit breaker for GraphQL client
"""

from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import compiled LangGraph agent
from src.graph import graph_app

# Import HTTP/SSE router
# TODO: Ensure http_server.py is implemented with proper SSE streaming
from src.server.http_server import router as http_router

# Import configuration
from src.config.settings import settings
from src.config.logger import logger

# Import cleanup utilities
from src.tools.graphql_client import close_client


# ========================================
# Lifecycle Management
# ========================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup and shutdown).
    
    This context manager handles:
    - Startup: Initialize connections, load configurations
    - Shutdown: Close connections, cleanup resources
    
    Args:
        app: FastAPI application instance
    
    Yields:
        None (context manager for startup/shutdown)
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting CRM AI Copilot Server")
    logger.info("=" * 60)
    
    # Log configuration
    graphql_endpoint = getattr(settings, "GRAPHQL_ENDPOINT", "Not configured")
    logger.info(f"GraphQL Endpoint: {graphql_endpoint}")
    
    redis_url = getattr(settings, "REDIS_URL", "Not configured")
    logger.info(f"Redis URL: {redis_url}")
    
    port = getattr(settings, "PORT", 8000)
    logger.info(f"Server Port: {port}")
    
    # Verify graph is loaded
    if graph_app:
        logger.info("LangGraph agent loaded successfully")
    else:
        logger.warning("LangGraph agent not loaded - server may not function correctly")
    
    # Initialize DB
    from src.infrastructure.database.connection import init_db
    try:
        await init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    logger.info("Server startup complete")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down CRM AI Copilot Server")
    logger.info("=" * 60)
    
    # Close GraphQL client
    try:
        await close_client()
        logger.info("GraphQL client closed successfully")
    except Exception as e:
        logger.error(f"Error closing GraphQL client: {e}")
    
    # TODO: Close Redis connections when session store is active
    # TODO: Close any other open connections or resources
    
    logger.info("Server shutdown complete")
    logger.info("=" * 60)


# ========================================
# FastAPI Application
# ========================================


app = FastAPI(
    title="CRM AI Copilot",
    version="1.0.0",
    description="AI-powered conversational assistant for CRM operations",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ========================================
# Middleware Configuration
# ========================================


# CORS Middleware
# Allows frontend applications to make cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# TODO: Add authentication middleware
# from src.middleware.auth import AuthMiddleware
# app.add_middleware(AuthMiddleware)

# TODO: Add rate limiting middleware
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
# limiter = Limiter(key_func=get_remote_address)
# app.state.limiter = limiter

# TODO: Add request logging middleware
# from src.middleware.logging import LoggingMiddleware
# app.add_middleware(LoggingMiddleware)


# ========================================
# Route Registration
# ========================================


# Include HTTP/SSE router for agent communication
# This exposes endpoints like:
# - POST /api/message - Send message and stream response
# - POST /api/confirm - Confirm pending action
app.include_router(http_router, prefix="/api")

logger.info("Registered HTTP/SSE router at /api")


# ========================================
# Health Check Endpoints
# ========================================


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for load balancers and monitoring.
    
    Returns basic server status and version information.
    Used by:
    - Kubernetes liveness/readiness probes
    - Load balancers for health checks
    - Monitoring systems (Datadog, New Relic, etc.)
    
    Returns:
        Dictionary containing:
        {
            "status": "ok",
            "version": "1.0.0",
            "service": "CRM AI Copilot"
        }
    
    Example:
        curl http://localhost:8000/health
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "CRM AI Copilot"
    }


@app.get("/")
async def root() -> Dict[str, Any]:
    """
    Root endpoint with API information.
    
    Provides basic information about the API and links to documentation.
    
    Returns:
        Dictionary with API info and documentation links
    """
    return {
        "service": "CRM AI Copilot",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "api": "/api"
    }


# ========================================
# Debug Endpoints
# ========================================


@app.post("/invoke")
async def invoke_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Direct graph invocation endpoint for testing.
    
    This endpoint allows testing the agent pipeline without SSE streaming.
    Useful for:
    - Development and debugging
    - Integration tests
    - Load testing
    - CLI tools
    
    WARNING: This endpoint is synchronous and blocks until the agent completes.
    For production use, prefer the /api/message endpoint with SSE streaming.
    
    Args:
        payload: Dictionary containing agent input:
                {
                    "conversation_id": str,
                    "user_id": str,
                    "workspace_id": str,
                    "message": str,
                    "metadata": dict (optional)
                }
    
    Returns:
        Dictionary containing agent response (full state after execution)
    
    Example:
        curl -X POST http://localhost:8000/invoke \\
             -H "Content-Type: application/json" \\
             -d '{
                   "conversation_id": "test-conv-1",
                   "user_id": "test-user-1",
                   "workspace_id": "test-ws-1",
                   "message": "Find companies in San Francisco"
                 }'
    
    TODO: Add authentication check
    TODO: Add rate limiting
    TODO: Add request validation
    """
    try:
        logger.info(f"Direct invocation request: {payload.get('message', 'No message')[:100]}")
        
        # Invoke graph directly
        result = graph_app.invoke(
            payload,
            config={
                "configurable": {
                    "thread_id": payload.get("conversation_id", "default")
                }
            }
        )
        
        logger.info("Direct invocation completed successfully")
        
        return result
    
    except Exception as e:
        logger.error(f"Error in direct invocation: {e}", exc_info=True)
        return {
            "error": str(e),
            "message": "Failed to process request"
        }


# ========================================
# Uvicorn Bootstrap
# ========================================


if __name__ == "__main__":
    """
    Run the server with uvicorn when executed directly.
    
    This is for development only. In production, use:
    - uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
    - gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker
    """
    # Get port from settings or use default
    port = getattr(settings, "PORT", 8000)
    
    logger.info(f"Starting development server on port {port}")
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info"
    )
