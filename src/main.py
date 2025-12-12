"""Main entry point for the Ally AI service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.api.routes import router as api_router
from src.agent.graph import cleanup_checkpointer, get_checkpointer

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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

