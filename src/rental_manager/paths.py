"""Filesystem paths for RentalManager."""

from __future__ import annotations

import os
from pathlib import Path

APP_FOLDER_NAME = "RentalManager"


def get_app_data_dir() -> Path:
    """Return the app data directory for the current user."""
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_FOLDER_NAME
    return Path.home() / ".rental_manager"


def ensure_app_data_dir() -> Path:
    """Create and return the app data directory."""
    app_dir = get_app_data_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_log_dir() -> Path:
    """Return the log directory inside the app data folder."""
    return ensure_app_data_dir() / "logs"


def get_database_path() -> Path:
    """Return the path to the SQLite database file."""
    return ensure_app_data_dir() / "rental_manager.db"
