"""Database schema management."""

from __future__ import annotations

from pathlib import Path

from rental_manager.db.connection import get_connection
from rental_manager.db.migrations import apply_migrations


def init_db(database_path: Path) -> None:
    """Initialize or migrate database schema."""
    connection = get_connection(database_path)
    try:
        apply_migrations(connection)
    finally:
        connection.close()
