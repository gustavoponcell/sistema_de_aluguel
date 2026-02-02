"""Database schema management."""

from __future__ import annotations

from pathlib import Path

from rental_manager.db.connection import get_connection, transaction


def init_db(database_path: Path) -> None:
    """Initialize database tables and indexes if they do not exist."""
    connection = get_connection(database_path)
    try:
        with transaction(connection):
            connection.executescript(
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

                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS rentals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    event_date TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    address TEXT,
                    status TEXT NOT NULL,
                    total_value REAL NOT NULL DEFAULT 0,
                    paid_value REAL NOT NULL DEFAULT 0,
                    payment_status TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                );

                CREATE TABLE IF NOT EXISTS rental_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    qty INTEGER NOT NULL DEFAULT 0,
                    unit_price REAL NOT NULL DEFAULT 0,
                    line_total REAL NOT NULL DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (rental_id) REFERENCES rentals(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE INDEX IF NOT EXISTS idx_rentals_event_date
                    ON rentals(event_date);
                CREATE INDEX IF NOT EXISTS idx_rentals_start_date
                    ON rentals(start_date);
                CREATE INDEX IF NOT EXISTS idx_rentals_end_date
                    ON rentals(end_date);
                CREATE INDEX IF NOT EXISTS idx_rental_items_rental_id
                    ON rental_items(rental_id);
                CREATE INDEX IF NOT EXISTS idx_rental_items_product_id
                    ON rental_items(product_id);
                """
            )
    finally:
        connection.close()
