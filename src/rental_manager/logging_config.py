"""Logging configuration for RentalManager."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from rental_manager.config import LOG_BACKUP_COUNT, LOG_FILENAME, LOG_MAX_BYTES
from rental_manager.paths import get_logs_dir


def configure_logging() -> None:
    """Configure file and console logging for the application."""
    log_dir = get_logs_dir()
    log_file = log_dir / LOG_FILENAME

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    def handle_exception(
        exc_type: type[BaseException],
        exc: BaseException,
        traceback: object,
    ) -> None:
        root_logger.error("Unhandled exception", exc_info=(exc_type, exc, traceback))

    sys.excepthook = handle_exception


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    return logging.getLogger(name)
