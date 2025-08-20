"""
Structured logging configuration using structlog.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.typing import EventDict

from core.config import settings


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to event dict."""
    if method_name == "info":
        event_dict["level"] = "INFO"
    elif method_name == "debug":
        event_dict["level"] = "DEBUG"
    elif method_name == "warning":
        event_dict["level"] = "WARNING"
    elif method_name == "error":
        event_dict["level"] = "ERROR"
    elif method_name == "critical":
        event_dict["level"] = "CRITICAL"
    return event_dict


def add_service_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add service context to logs."""
    # Get the calling module name for better context
    import inspect

    frame = inspect.currentframe()
    try:
        # Walk up the stack to find the actual caller
        while frame:
            frame = frame.f_back
            if frame and frame.f_code.co_filename:
                filename = Path(frame.f_code.co_filename).name
                # Skip logging infrastructure files
                if not any(skip in filename for skip in ["logging.py", "structlog", "__init__.py"]):
                    module_name = filename.replace(".py", "")
                    if "service" in module_name or "api" in frame.f_code.co_filename:
                        event_dict["service"] = module_name
                        break
    finally:
        del frame

    return event_dict


def setup_logging():
    """Configure structured logging with structlog."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Reduce noise from some libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Set appropriate levels for framework loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_service_context,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add different renderers based on environment
    if settings.debug:
        # Pretty console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # File logging setup
    log_dir = Path("logs")
    if log_dir.exists() or settings.debug:
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log")
        file_handler.setLevel(getattr(logging, settings.log_level.upper()))

        # JSON format for file logs
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
        file_handler.setFormatter(file_formatter)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str = None, **initial_values) -> structlog.BoundLogger:
    """Get a structured logger with optional initial context."""
    if name is None:
        # Auto-detect caller module name
        import inspect

        frame = inspect.currentframe().f_back
        name = Path(frame.f_code.co_filename).stem

    logger = structlog.get_logger(name)
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger
