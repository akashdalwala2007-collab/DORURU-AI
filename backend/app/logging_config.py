"""
backend/app/logging_config.py - Structured Logging for DORURU Backend
"""

import logging
import os
import sys

def setup_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout
    )

    # Suppress excessive third-party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("starlette").setLevel(logging.WARNING)

    logger = logging.getLogger("doruru.backend")
    logger.setLevel(numeric_level)
    return logger

logger = setup_logging()

