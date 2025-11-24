"""
Centralized logging configuration for the CRM AI Copilot.

This module sets up structured logging with:
- Configurable log levels from settings
- Optional JSON formatting for production
- Console output with colors for development
- Request correlation IDs (future)
- Integration with monitoring systems

Logging Strategy:

Development:
- Human-readable text format with colors
- DEBUG level for detailed information
- Console output

Production:
- Structured JSON format for log aggregation
- INFO level or higher
- Includes metadata (timestamp, level, module, function)
- Compatible with ELK stack, Datadog, CloudWatch, etc.

Usage:

    from src.config.logger import logger
    
    logger.info("Processing user request")
    logger.debug("Detailed debug information")
    logger.warning("Something unexpected happened")
    logger.error("Error occurred", exc_info=True)
    
    # Structured logging
    logger.info(
        "Tool execution completed",
        extra={
            "tool": "search_companies",
            "duration_ms": 150,
            "result_count": 5
        }
    )

Log Levels:

- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Warning messages for unexpected but handled situations
- ERROR: Error messages for failures
- CRITICAL: Critical failures requiring immediate attention

Future Enhancements:

TODO: Add correlation IDs for request tracing
TODO: Add log sampling for high-volume endpoints
TODO: Add structured fields for better filtering
TODO: Add log rotation configuration
TODO: Add async logging for better performance
"""

import logging
import sys
from typing import Any, Dict, Optional

from src.config.settings import settings


# ========================================
# JSON Formatter (for production)
# ========================================

class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON.
    
    Useful for production environments where logs are ingested by
    log aggregation systems (ELK, Datadog, CloudWatch, etc.).
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        import json
        from datetime import datetime
        
        # Build log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra
        
        return json.dumps(log_entry)


# ========================================
# Colored Console Formatter (for development)
# ========================================

class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to console output.
    
    Makes logs easier to read during development.
    """
    
    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Get color for this log level
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Format the message
        log_message = super().format(record)
        
        # Add color
        return f"{color}{log_message}{self.RESET}"


# ========================================
# Logger Setup
# ========================================

def setup_logger() -> logging.Logger:
    """
    Configure and return the application logger.
    
    Sets up logging based on settings:
    - Log level from settings.LOG_LEVEL
    - Format from settings.LOG_FORMAT (text or json)
    - Console output with appropriate formatting
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("analyst-ai")
    
    # Set level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Remove existing handlers (avoid duplicates on reload)
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Choose formatter based on settings
    if settings.LOG_FORMAT == "json":
        # JSON format for production
        formatter = JSONFormatter()
    else:
        # Text format for development
        if settings.is_development:
            # Colored output for development
            formatter = ColoredFormatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            # Plain text for staging/production console
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    # Disable SQLAlchemy INFO logs (only show WARNING and above)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logger


# ========================================
# Export Logger Instance
# ========================================

# Create singleton logger instance
logger = setup_logger()

# Log initialization
logger.debug("Logger initialized")
logger.debug(f"Log level: {settings.LOG_LEVEL}")
logger.debug(f"Log format: {settings.LOG_FORMAT}")


# ========================================
# Utility Functions
# ========================================

def log_with_context(
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a message with additional context data.
    
    Args:
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        context: Optional dictionary of context data
    
    Example:
        log_with_context(
            "info",
            "Tool execution completed",
            {"tool": "search_companies", "duration_ms": 150}
        )
    """
    log_func = getattr(logger, level.lower())
    if context:
        log_func(message, extra={"context": context})
    else:
        log_func(message)


# ========================================
# Convenience Exports
# ========================================

__all__ = [
    "logger",
    "log_with_context",
    "setup_logger",
]

