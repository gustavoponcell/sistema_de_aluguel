"""Database migrations for SQLite schema versioning."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from rental_manager.db.connection import transaction
from rental_manager.logging_config import get_logger


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


def _convert_legacy_date_format(
    connection: sqlite3.Connection, column_name: str
) -> int:
    cursor = connection.execute(
        f"""
        UPDATE rentals
        SET {column_name} = (
            substr({column_name}, 7, 4)
            || '-' || substr({column_name}, 4, 2)
            || '-' || substr({column_name}, 1, 2)
        )
        WHERE {column_name} LIKE '__/__/____'
        """
    )
    return int(cursor.rowcount or 0)


def _preflight_cleanup_rentals(connection: sqlite3.Connection) -> bool:
    logger = get_logger("Migration")
    logger.info("Executando limpeza prévia de datas para migração de rentals.")

    invalid_before = connection.execute(
        """
        SELECT COUNT(*)
        FROM rentals
        WHERE start_date IS NULL
           OR end_date IS NULL
           OR end_date <= start_date
        """
    ).fetchone()[0]
    logger.info("Registros inválidos detectados antes da limpeza: %s.", invalid_before)

    converted_start = _convert_legacy_date_format(connection, "start_date")
    converted_end = _convert_legacy_date_format(connection, "end_date")
    if converted_start or converted_end:
        logger.info(
            "Datas convertidas do formato legado (dd/MM/yyyy). "
            "start_date: %s, end_date: %s.",
            converted_start,
            converted_end,
        )

    invalid_start_format = connection.execute(
        """
        SELECT COUNT(*)
        FROM rentals
        WHERE start_date IS NOT NULL
          AND date(start_date) IS NULL
        """
    ).fetchone()[0]
    if invalid_start_format:
        logger.warning(
            "Encontrados %s registros com start_date em formato inválido.",
            invalid_start_format,
        )

    draft_fixed = connection.execute(
        """
        UPDATE rentals
        SET start_date = date('now'),
            end_date = date('now', '+1 day')
        WHERE start_date IS NULL
          AND status = 'draft'
        """
    ).rowcount
    if draft_fixed:
        logger.info(
            "Datas preenchidas para %s aluguéis rascunho sem start_date.",
            draft_fixed,
        )

    canceled_fixed = connection.execute(
        """
        UPDATE rentals
        SET status = 'canceled',
            start_date = date('now'),
            end_date = date('now', '+1 day')
        WHERE start_date IS NULL
          AND status != 'draft'
        """
    ).rowcount
    if canceled_fixed:
        logger.warning(
            "Aluguéis sem start_date foram cancelados automaticamente: %s.",
            canceled_fixed,
        )

    end_date_fixed = connection.execute(
        """
        UPDATE rentals
        SET end_date = date(start_date, '+1 day')
        WHERE start_date IS NOT NULL
          AND date(start_date) IS NOT NULL
          AND (
            end_date IS NULL
            OR date(end_date) IS NULL
            OR date(end_date) <= date(start_date)
          )
        """
    ).rowcount
    if end_date_fixed:
        logger.info(
            "Datas de devolução corrigidas automaticamente: %s.",
            end_date_fixed,
        )

    fallback_end_date = 0
    if invalid_start_format:
        fallback_end_date = connection.execute(
            """
            UPDATE rentals
            SET end_date = start_date
            WHERE start_date IS NOT NULL
              AND date(start_date) IS NULL
            """
        ).rowcount
        if fallback_end_date:
            logger.warning(
                "Datas de devolução ajustadas para start_date em %s registros "
                "com formato inválido.",
                fallback_end_date,
            )

    remaining_null = connection.execute(
        "SELECT COUNT(*) FROM rentals WHERE start_date IS NULL OR end_date IS NULL"
    ).fetchone()[0]
    if remaining_null:
        message = (
            "Migração abortada: ainda existem aluguéis com datas ausentes após a "
            "limpeza automática."
        )
        logger.error(message)
        raise RuntimeError(message)

    total_fixed = sum(
        value
        for value in (draft_fixed, canceled_fixed, end_date_fixed, fallback_end_date)
        if value
    )
    logger.info("Registros corrigidos automaticamente: %s.", total_fixed)

    if invalid_start_format:
        logger.warning(
            "Aplicando CHECK constraint mais tolerante por causa de formatos inválidos."
        )
    return bool(invalid_start_format)


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
            script = migration.script
            if migration.version == 2:
                relax_constraint = _preflight_cleanup_rentals(connection)
                if relax_constraint:
                    script = script.replace(
                        "CHECK (end_date > start_date)",
                        "CHECK (end_date >= start_date)",
                    )
            connection.executescript(script)
            connection.execute(
                "UPDATE app_meta SET schema_version = ?",
                (migration.version,),
            )

        if migration.requires_foreign_keys_off:
            connection.execute("PRAGMA foreign_keys = ON;")

        current_version = migration.version
