"""FastAPI application main file."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..utils.exceptions import GraphExecutionError
from ..utils.logger import get_logger
from .routes import router

logger = get_logger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    """Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI instance
    """
    app = FastAPI(
        title="AnalystAI API",
        description="REST API for AnalystAI LangGraph pipeline",
        version=settings.app_version,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, configure specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(router)
    
    # Exception handlers
    @app.exception_handler(GraphExecutionError)
    async def graph_execution_error_handler(request: Request, exc: GraphExecutionError):
        """Handle GraphExecutionError."""
        logger.error(
            "Graph execution error",
            error=str(exc),
            original_error=str(exc.original_error) if exc.original_error else None,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Graph execution failed",
                "detail": str(exc),
            },
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError (e.g., missing required fields)."""
        logger.error("Value error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid request",
                "detail": str(exc),
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.error("Unexpected error", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": "An unexpected error occurred",
            },
        )
    
    @app.on_event("startup")
    async def startup_event():
        """Log application startup."""
        logger.info(
            "API server starting",
            app_name=settings.app_name,
            version=settings.app_version,
        )
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Log application shutdown."""
        logger.info("API server shutting down")
    
    return app


