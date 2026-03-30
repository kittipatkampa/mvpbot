"""Centralized logging configuration for assistant_service."""

from __future__ import annotations

import logging
import sys


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logger with a consistent format and the given level.

    Call once at application startup (before any loggers are used).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)-5s] %(name)s - %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party loggers unless we're at DEBUG
    if level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("anthropic").setLevel(logging.WARNING)
        logging.getLogger("langchain").setLevel(logging.WARNING)
        logging.getLogger("langgraph").setLevel(logging.WARNING)
