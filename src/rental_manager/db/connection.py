"""Database connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_connection(database_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection
