"""Logging configuration."""

import logging
from logging.handlers import RotatingFileHandler

from app.config.settings import Settings


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure application logging."""
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("enterprise_mcp_host")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    file_handler = RotatingFileHandler(
        settings.log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

