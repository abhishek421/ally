"""Main entry point for the Ally AI service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings

# Configure logging BEFORE importing other modules
def configure_logging():
    """Configure logging with clean, human-readable format.

    Suppresses verbose third-party loggers and keeps ally-ai logs clean.
    """
    settings = get_settings()

    # Set root level
    root_level = logging.DEBUG if settings.debug else logging.INFO

    # Clean format for our logs
    log_format = "%(asctime)s | %(levelname)-7s | %(message)s"
    date_format = "%H:%M:%S"

    logging.basicConfig(
        level=root_level,
        format=log_format,
        datefmt=date_format,
    )

    # Suppress noisy third-party loggers
    noisy_loggers = [
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
        "httpx",
        "openai",
        "openai._base_client",
        "gql",
        "gql.transport",
        "gql.transport.httpx",
        "sse_starlette",
        "sse_starlette.sse",
        "uvicorn.access",  # Health check spam
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Keep uvicorn error logs
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

configure_logging()

from src.api.routes import router as api_router
from src.agent.graph import cleanup_checkpointer, get_checkpointer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    logger.info(f"Starting Ally AI service with {settings.llm_provider} provider")
    logger.info(f"Backend GraphQL URL: {settings.backend_graphql_url}")
    logger.info(f"Database URL configured: {bool(settings.DATABASE_URL_ALLY)}")
    
    # Initialize checkpointer eagerly to see if persistence is working
    try:
        checkpointer = await get_checkpointer()
        checkpointer_type = type(checkpointer).__name__
        logger.info(f"Checkpointer initialized: {checkpointer_type}")
        if checkpointer_type == "MemorySaver":
            logger.warning("⚠️  Using in-memory storage - conversation history will NOT persist across restarts!")
        else:
            logger.info("✓ Using PostgreSQL storage - conversation history WILL persist across restarts")
    except Exception as e:
        logger.error(f"Failed to initialize checkpointer: {e}")
    
    yield
    # Cleanup on shutdown
    logger.info("Shutting down Ally AI service")
    await cleanup_checkpointer()


app = FastAPI(
    title="Ally AI Copilot",
    description="A LangGraph-based intelligent assistant for CRM",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ally-ai"}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

