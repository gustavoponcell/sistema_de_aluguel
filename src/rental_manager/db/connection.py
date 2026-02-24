"""Database connection helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def get_connection(database_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
<<<<<<< HEAD
    # Use WAL + busy timeout to minimize SQLITE_LOCKED errors on concurrent screens.
    connection.execute("PRAGMA busy_timeout = 5000;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Provide a transaction scope for SQLite operations."""
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
