"""Database schema management."""

from __future__ import annotations

import sqlite3


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Initialize database tables if they do not exist."""
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            total_qty INTEGER NOT NULL DEFAULT 0,
            unit_price REAL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    connection.commit()
