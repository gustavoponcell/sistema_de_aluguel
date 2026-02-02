"""Repository for customer persistence."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rental_manager.db.connection import get_connection, transaction
from rental_manager.db.schema import init_db
from rental_manager.domain.models import Customer
from rental_manager.logging_config import configure_logging, get_logger
from rental_manager.repositories.mappers import customer_from_row


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CustomerRepo:
    """CRUD operations for customers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def create(
        self,
        name: str,
        phone: Optional[str],
        notes: Optional[str],
    ) -> Customer:
        created_at = _now_iso()
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    """
                    INSERT INTO customers (
                        name,
                        phone,
                        notes,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, phone, notes, created_at, created_at),
                )
        except Exception:
            self._logger.exception("Failed to create customer")
            raise

        return Customer(
            id=cursor.lastrowid,
            name=name,
            phone=phone,
            notes=notes,
            created_at=created_at,
            updated_at=created_at,
        )

    def update(
        self,
        customer_id: int,
        name: str,
        phone: Optional[str],
        notes: Optional[str],
    ) -> Optional[Customer]:
        updated_at = _now_iso()
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    """
                    UPDATE customers
                    SET
                        name = ?,
                        phone = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (name, phone, notes, updated_at, customer_id),
                )
        except Exception:
            self._logger.exception("Failed to update customer id=%s", customer_id)
            raise

        if cursor.rowcount == 0:
            return None
        return self.get_by_id(customer_id)

    def delete(self, customer_id: int) -> bool:
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    "DELETE FROM customers WHERE id = ?",
                    (customer_id,),
                )
        except Exception:
            self._logger.exception("Failed to delete customer id=%s", customer_id)
            raise
        return cursor.rowcount > 0

    def list_all(self) -> List[Customer]:
        try:
            rows = self._connection.execute(
                "SELECT * FROM customers ORDER BY name"
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to list customers")
            raise
        return [customer_from_row(row) for row in rows]

    def search_by_name(self, term: str) -> List[Customer]:
        term = term.strip()
        if not term:
            return self.list_all()
        try:
            rows = self._connection.execute(
                "SELECT * FROM customers WHERE name LIKE ? ORDER BY name",
                (f"%{term}%",),
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to search customers by name term=%s", term)
            raise
        return [customer_from_row(row) for row in rows]

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        try:
            row = self._connection.execute(
                "SELECT * FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to get customer id=%s", customer_id)
            raise
        return customer_from_row(row) if row else None


def _debug_run() -> None:
    configure_logging()
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "debug_customers.db"
        init_db(db_path)
        connection = get_connection(db_path)
        try:
            repo = CustomerRepo(connection)
            customer = repo.create(
                name="Maria Souza",
                phone="(11) 99999-0000",
                notes="Cliente preferencial",
            )
            repo.update(
                customer_id=customer.id or 0,
                name="Maria Souza",
                phone="(11) 88888-0000",
                notes="Atualizado",
            )
            repo.search_by_name("Maria")
            repo.list_all()
            repo.delete(customer.id or 0)
        finally:
            connection.close()


if __name__ == "__main__":
    _debug_run()
