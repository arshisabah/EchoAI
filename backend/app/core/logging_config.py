# app/core/logging_config.py
"""
Centralized logging configuration for the application.
"""

import logging
import sys
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/transcript_api.log",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    log_format: Optional[str] = None
) -> Dict[str, Any]:
    """
    Setup comprehensive logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        max_file_size: Maximum size of log file before rotation (bytes)
        backup_count: Number of backup files to keep
        log_format: Custom log format string
    
    Returns:
        Dict with logging configuration
    
    Raises:
        ValueError: If log_level is invalid
    """
    
    # Validate log level
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level.upper() not in valid_levels:
        raise ValueError(f"Invalid log level: {log_level}. Must be one of {valid_levels}")
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Default log format
    if log_format is None:
        log_format = (
            "%(asctime)s | %(name)s | %(levelname)s | "
            "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
        )
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # Set root logger level
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # Log to console if file handler fails
        root_logger.warning(f"Could not create file handler for {log_file}: {e}")
    
    # Configure specific loggers with appropriate levels
    
    # FastAPI and Uvicorn - reduce verbosity in production
    uvicorn_level = logging.WARNING if log_level.upper() in ['ERROR', 'CRITICAL'] else logging.INFO
    logging.getLogger("uvicorn").setLevel(uvicorn_level)
    logging.getLogger("uvicorn.access").setLevel(uvicorn_level)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    # Application loggers
    app_logger = logging.getLogger("app")
    app_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Set specific module loggers
    logging.getLogger("app.modules.realtime_store").setLevel(
        logging.DEBUG if log_level.upper() == 'DEBUG' else logging.INFO
    )
    logging.getLogger("app.routers").setLevel(logging.INFO)
    
    # WebSocket logging - typically noisy, keep at WARNING+
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets.server").setLevel(logging.WARNING)
    logging.getLogger("websockets.protocol").setLevel(logging.WARNING)
    
    # Third-party libraries - reduce noise
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Prevent duplicate logs from propagating
    for logger_name in ["uvicorn", "fastapi", "websockets"]:
        logging.getLogger(logger_name).propagate = True
    
    return {
        "level": log_level.upper(),
        "file": log_file,
        "format": log_format,
        "handlers": ["console", "file"],
        "max_file_size": max_file_size,
        "backup_count": backup_count
    }


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name, typically __name__ from the calling module
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses with detailed information."""
    
    def __init__(self, app, logger_name: str = "app.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
        
        # Paths to exclude from logging (health checks, metrics, etc.)
        self.exclude_paths = {"/health", "/metrics", "/favicon.ico"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.time()
        
        # Get client info safely
        client_host = "unknown"
        if hasattr(request, 'client') and request.client:
            client_host = request.client.host
        
        # Log request with more details
        self.logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"from {client_host}"
            f"{f' | Query: {dict(request.query_params)}' if request.query_params else ''}"
        )
        
        # Process request
        response = None
        error_occurred = False
        
        try:
            response = await call_next(request)
            
        except Exception as e:
            error_occurred = True
            duration = time.time() - start_time
            
            # Log error with full details
            self.logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"from {client_host} | Error: {type(e).__name__}: {str(e)} | "
                f"Duration: {duration:.3f}s",
                exc_info=True
            )
            
            # Re-raise the exception
            raise
        
        finally:
            # Always log completion if no error
            if not error_occurred and response:
                duration = time.time() - start_time
                
                # Determine log level based on status code
                if response.status_code >= 500:
                    log_method = self.logger.error
                elif response.status_code >= 400:
                    log_method = self.logger.warning
                else:
                    log_method = self.logger.info
                
                log_method(
                    f"Request completed: {request.method} {request.url.path} "
                    f"from {client_host} | Status: {response.status_code} | "
                    f"Duration: {duration:.3f}s"
                )
        
        return response


# Utility function for structured logging
def log_exception(logger: logging.Logger, message: str, exc_info=True):
    """
    Log an exception with consistent formatting.
    
    Args:
        logger: Logger instance to use
        message: Custom message to include with the exception
        exc_info: Whether to include exception traceback
    """
    logger.error(f"Exception occurred: {message}", exc_info=exc_info)


# Context manager for timing operations
class LoggingTimer:
    """Context manager for timing and logging operations."""
    
    def __init__(self, logger: logging.Logger, operation_name: str, level: int = logging.INFO):
        self.logger = logger
        self.operation_name = operation_name
        self.level = level
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.log(self.level, f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type is None:
            self.logger.log(self.level, f"Completed {self.operation_name} in {duration:.3f}s")
        else:
            self.logger.error(
                f"Failed {self.operation_name} after {duration:.3f}s: {exc_type.__name__}: {exc_val}"
            )