"""
Main entry point for AI Analyst Pipeline
Supports both CLI mode and FastAPI server mode
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from graph.pipeline import AnalystPipeline
from api.v1 import query, health, conversations
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def initialize_application():
    """
    Initialize application (ENV-only configuration).
    """
    logger.info("Initializing application (ENV-only config)...")

    # Fix DATABASE_URL for Docker: replace localhost with host.docker.internal
    import os
    database_url = os.getenv("DATABASE_URL", "")
    if database_url and "localhost" in database_url and os.path.exists("/.dockerenv"):
        # We're in Docker and DATABASE_URL uses localhost - replace with host.docker.internal
        database_url = database_url.replace("localhost", "host.docker.internal")
        os.environ["DATABASE_URL"] = database_url
        logger.info("Updated DATABASE_URL to use host.docker.internal for Docker environment")

    # Initialize database connection
    from database.prisma_client import prisma_client
    try:
        await prisma_client.connect()
        logger.info("Database connection initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        raise

    # Initialize config manager
    from config.config_manager import get_config_manager
    try:
        config_manager = get_config_manager()
        await config_manager.initialize()
        logger.info("ConfigManager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ConfigManager: {e}")
        raise

    logger.info("Application initialization complete (ENV-only)")


async def cleanup_application():
    """Cleanup on shutdown."""
    from database.prisma_client import prisma_client
    try:
        await prisma_client.disconnect()
        logger.info("Database connection closed successfully")
    except Exception as e:
        logger.warning(f"Error during database cleanup: {e}")

    logger.info("Application cleanup completed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup and shutdown events"""
    # Startup
    logger.info("Starting FastAPI application...")
    await initialize_application()
    yield
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    await cleanup_application()


# Create FastAPI app
app = FastAPI(
    title="AI Analyst Service",
    description="Natural language query processing for CRM data using LangGraph agents",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(query.router, prefix="/api/v1", tags=["Query"])
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation error",
            "detail": exc.errors(),
            "code": "VALIDATION_ERROR"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail if isinstance(exc.detail, str) else exc.detail.get("error", "HTTP error"),
            "detail": exc.detail if isinstance(exc.detail, dict) else str(exc.detail),
            "code": exc.detail.get("code", "HTTP_ERROR") if isinstance(exc.detail, dict) else "HTTP_ERROR"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc),
            "code": "INTERNAL_SERVER_ERROR"
        }
    )


# CLI mode functions (maintained for backward compatibility)
def main():
    """Run the pipeline with a user query (CLI mode)"""
    
    # Create the pipeline
    pipeline = AnalystPipeline()
    
    # Example queries to test
    example_queries = [
        "what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}",
        "With how many companies we have closed deal previous year?"
    ]
    
    for user_query in example_queries:
        print(f"\n{'='*60}")
        print(f"Original Query: {user_query}")
        print('='*60)
        
        # Run the pipeline
        # TODO: Replace with actual workspace_id and user_id from API call
        workspace_id = "example-workspace-id"
        user_id = "example-user-id"
        result = pipeline.run(user_query, workspace_id, user_id)
        
        # Display the result
        print("\nPipeline Result:")
        print(result)


def interactive_mode():
    """Interactive mode for querying the pipeline"""
    
    # Create the pipeline
    pipeline = AnalystPipeline()
    
    print("AI Analyst Pipeline")
    print("Type 'exit' to quit\n")
    
    while True:
        # Get user input
        user_query = input("Enter your query: ").strip()
        
        if user_query.lower() == 'exit':
            print("Exiting...")
            break
        
        if not user_query:
            continue
        
        print(f"\nProcessing: {user_query}")
        
        try:
            # Run the pipeline
            # TODO: Replace with actual workspace_id and user_id from API call
            workspace_id = "example-workspace-id"
            user_id = "example-user-id"
            result = pipeline.run(user_query, workspace_id, user_id)
            
            # Display the result
            print("\nResult:")
            print(result)
            print("\n" + "="*50 + "\n")
            
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    # Check if running as CLI mode
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        # CLI mode
        try:
            asyncio.run(initialize_application())
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            logger.info("Continuing with default configuration...")
        
        try:
            # Choose mode:
            # For single query testing
            main()
            
            # For interactive mode (uncomment to use)
            # interactive_mode()
        finally:
            # Cleanup on exit
            try:
                asyncio.run(cleanup_application())
            except Exception:
                pass
    else:
        # FastAPI server mode
        import uvicorn
        import os
        port = int(os.getenv("ANALYST_AI_PORT", "8000"))
        uvicorn.run(app, host="0.0.0.0", port=port)
