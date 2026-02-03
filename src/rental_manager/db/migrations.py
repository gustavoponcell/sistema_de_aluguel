"""Database migrations for SQLite schema versioning."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from rental_manager.db.connection import transaction


@dataclass(frozen=True)
class Migration:
    version: int
    script: str
    requires_foreign_keys_off: bool = False


MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        script="""
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
        """,
    ),
    Migration(
        version=2,
        requires_foreign_keys_off=True,
        script="""
        CREATE TABLE products_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            total_qty INTEGER NOT NULL DEFAULT 0 CHECK (total_qty >= 0),
            unit_price REAL CHECK (unit_price IS NULL OR unit_price >= 0),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );

        INSERT INTO products_new (id, name, category, total_qty, unit_price, active, created_at, updated_at)
        SELECT id, name, category, total_qty, unit_price, active, created_at, updated_at
        FROM products;

        DROP TABLE products;
        ALTER TABLE products_new RENAME TO products;

        CREATE TABLE rentals_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            address TEXT,
            status TEXT NOT NULL CHECK (status IN ('draft', 'confirmed', 'canceled', 'completed')),
            total_value REAL NOT NULL DEFAULT 0 CHECK (total_value >= 0),
            paid_value REAL NOT NULL DEFAULT 0 CHECK (paid_value >= 0),
            payment_status TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            CHECK (end_date > start_date)
        );

        INSERT INTO rentals_new (
            id,
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            status,
            total_value,
            paid_value,
            payment_status,
            created_at,
            updated_at
        )
        SELECT
            id,
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            status,
            total_value,
            paid_value,
            payment_status,
            created_at,
            updated_at
        FROM rentals;

        DROP TABLE rentals;
        ALTER TABLE rentals_new RENAME TO rentals;

        CREATE TABLE rental_items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rental_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 0 CHECK (qty > 0),
            unit_price REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (rental_id) REFERENCES rentals(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        INSERT INTO rental_items_new (
            id,
            rental_id,
            product_id,
            qty,
            unit_price,
            line_total,
            created_at,
            updated_at
        )
        SELECT
            id,
            rental_id,
            product_id,
            qty,
            unit_price,
            line_total,
            created_at,
            updated_at
        FROM rental_items;

        DROP TABLE rental_items;
        ALTER TABLE rental_items_new RENAME TO rental_items;

        CREATE INDEX IF NOT EXISTS idx_rentals_event_date
            ON rentals(event_date);
        CREATE INDEX IF NOT EXISTS idx_rentals_start_date
            ON rentals(start_date);
        CREATE INDEX IF NOT EXISTS idx_rentals_end_date
            ON rentals(end_date);
        CREATE INDEX IF NOT EXISTS idx_rentals_status
            ON rentals(status);
        CREATE INDEX IF NOT EXISTS idx_rental_items_rental_id
            ON rental_items(rental_id);
        CREATE INDEX IF NOT EXISTS idx_rental_items_product_id
            ON rental_items(product_id);
        """,
    ),
    Migration(
        version=3,
        script="""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rental_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            method TEXT,
            paid_at TEXT,
            note TEXT,
            FOREIGN KEY (rental_id) REFERENCES rentals(id)
        );

        CREATE INDEX IF NOT EXISTS idx_payments_rental_id
            ON payments(rental_id);
        CREATE INDEX IF NOT EXISTS idx_payments_paid_at
            ON payments(paid_at);

        INSERT INTO payments (rental_id, amount, method, paid_at, note)
        SELECT
            id,
            paid_value,
            'Migrado',
            COALESCE(updated_at, event_date),
            'Pagamento migrado do campo paid_value'
        FROM rentals
        WHERE paid_value > 0;
        """,
    ),
    Migration(
        version=4,
        script="""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rental_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL CHECK (doc_type IN ('contract', 'receipt')),
            file_path TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            checksum TEXT NOT NULL,
            FOREIGN KEY (rental_id) REFERENCES rentals(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_rental_type
            ON documents(rental_id, doc_type);
        CREATE INDEX IF NOT EXISTS idx_documents_rental_generated_at
            ON documents(rental_id, generated_at);
        """,
    ),
]


def _fetch_schema_version(connection: sqlite3.Connection) -> int:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            schema_version INTEGER NOT NULL
        );
        """
    )
    row = connection.execute(
        "SELECT schema_version FROM app_meta LIMIT 1"
    ).fetchone()
    if row is None:
        connection.execute("INSERT INTO app_meta (schema_version) VALUES (0)")
        return 0
    return int(row[0])


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply pending database migrations."""
    with transaction(connection):
        current_version = _fetch_schema_version(connection)

    for migration in MIGRATIONS:
        if migration.version <= current_version:
            continue

        if migration.requires_foreign_keys_off:
            connection.execute("PRAGMA foreign_keys = OFF;")

        with transaction(connection):
            connection.executescript(migration.script)
            connection.execute(
                "UPDATE app_meta SET schema_version = ?",
                (migration.version,),
            )

        if migration.requires_foreign_keys_off:
            connection.execute("PRAGMA foreign_keys = ON;")

        current_version = migration.version
