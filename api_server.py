"""API server entry point."""

import uvicorn

from src.api.main import create_app
from src.config import get_settings
from src.utils.logger import configure_logging, get_logger

# Configure logging first
configure_logging()
logger = get_logger(__name__)

settings = get_settings()


def main():
    """Run the API server."""
    app = create_app()
    
    logger.info(
        "Starting API server",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
    
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_config=None,  # Use our own logging configuration
    )


if __name__ == "__main__":
    main()


