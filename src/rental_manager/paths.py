"""Filesystem paths for RentalManager."""

from __future__ import annotations

import os
from pathlib import Path

from rental_manager.config import (
    APP_DATA_DIRNAME,
    BACKUP_DIRNAME,
    DB_FILENAME,
    LOGS_DIRNAME,
    PDF_DIRNAME,
)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_data_dir() -> Path:
    """Create and return the app data directory for the current user."""
    appdata = os.getenv("APPDATA")
    if appdata:
        base_dir = Path(appdata)
    else:
        base_dir = Path.home() / ".rental_manager"
    return _ensure_dir(base_dir / APP_DATA_DIRNAME)


def get_db_path() -> Path:
    """Return the path to the SQLite database file."""
    return get_app_data_dir() / DB_FILENAME


def get_backup_dir() -> Path:
    """Create and return the backup directory inside the app data folder."""
    return _ensure_dir(get_app_data_dir() / BACKUP_DIRNAME)


def get_logs_dir() -> Path:
    """Create and return the log directory inside the app data folder."""
    return _ensure_dir(get_app_data_dir() / LOGS_DIRNAME)


def get_pdfs_dir() -> Path:
    """Create and return the PDFs directory inside the app data folder."""
    return _ensure_dir(get_app_data_dir() / PDF_DIRNAME)
