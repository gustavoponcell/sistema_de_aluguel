"""Repository for product persistence."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rental_manager.db.connection import get_connection, transaction
from rental_manager.db.schema import init_db
from rental_manager.domain.models import Product
from rental_manager.logging_config import configure_logging, get_logger
from rental_manager.repositories.mappers import product_from_row


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ProductRepo:
    """CRUD operations for products."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def create(
        self,
        name: str,
        category: Optional[str],
        total_qty: int,
        unit_price: Optional[float],
        active: bool,
    ) -> Product:
        created_at = _now_iso()
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    """
                    INSERT INTO products (
                        name,
                        category,
                        total_qty,
                        unit_price,
                        active,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        category,
                        total_qty,
                        unit_price,
                        int(active),
                        created_at,
                        created_at,
                    ),
                )
        except Exception:
            self._logger.exception("Failed to create product")
            raise

        return Product(
            id=cursor.lastrowid,
            name=name,
            category=category,
            total_qty=total_qty,
            unit_price=unit_price,
            active=active,
            created_at=created_at,
            updated_at=created_at,
        )

    def update(
        self,
        product_id: int,
        name: str,
        category: Optional[str],
        total_qty: int,
        unit_price: Optional[float],
        active: bool,
    ) -> Optional[Product]:
        updated_at = _now_iso()
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    """
                    UPDATE products
                    SET
                        name = ?,
                        category = ?,
                        total_qty = ?,
                        unit_price = ?,
                        active = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        category,
                        total_qty,
                        unit_price,
                        int(active),
                        updated_at,
                        product_id,
                    ),
                )
        except Exception:
            self._logger.exception("Failed to update product id=%s", product_id)
            raise

        if cursor.rowcount == 0:
            return None
        return self.get_by_id(product_id)

    def soft_delete(self, product_id: int) -> bool:
        updated_at = _now_iso()
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    """
                    UPDATE products
                    SET active = 0,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (updated_at, product_id),
                )
        except Exception:
            self._logger.exception("Failed to soft delete product id=%s", product_id)
            raise
        return cursor.rowcount > 0

    def delete(self, product_id: int) -> bool:
        try:
            with transaction(self._connection):
                cursor = self._connection.execute(
                    "DELETE FROM products WHERE id = ?",
                    (product_id,),
                )
        except Exception:
            self._logger.exception("Failed to delete product id=%s", product_id)
            raise
        return cursor.rowcount > 0

    def list_active(self) -> List[Product]:
        try:
            rows = self._connection.execute(
                """
                SELECT * FROM products
                WHERE active = 1
                ORDER BY name
                """
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to list active products")
            raise
        return [product_from_row(row) for row in rows]

    def search_by_name(
        self,
        term: str,
        *,
        include_inactive: bool = False,
    ) -> List[Product]:
        term = term.strip()
        if not term:
            return self.list_active() if not include_inactive else self.list_all()
        params = [f"%{term}%"]
        where = "name LIKE ?"
        if not include_inactive:
            where += " AND active = 1"
        try:
            rows = self._connection.execute(
                f"SELECT * FROM products WHERE {where} ORDER BY name",
                params,
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to search products by name term=%s", term)
            raise
        return [product_from_row(row) for row in rows]

    def list_all(self) -> List[Product]:
        try:
            rows = self._connection.execute(
                "SELECT * FROM products ORDER BY name"
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to list products")
            raise
        return [product_from_row(row) for row in rows]

    def get_by_id(self, product_id: int) -> Optional[Product]:
        try:
            row = self._connection.execute(
                "SELECT * FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to get product id=%s", product_id)
            raise
        return product_from_row(row) if row else None


def _debug_run() -> None:
    configure_logging()
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "debug_products.db"
        init_db(db_path)
        connection = get_connection(db_path)
        try:
            repo = ProductRepo(connection)
            product = repo.create(
                name="Mesa 1,20m",
                category="mesa",
                total_qty=10,
                unit_price=25.0,
                active=True,
            )
            repo.update(
                product_id=product.id or 0,
                name="Mesa 1,20m (atualizada)",
                category="mesa",
                total_qty=12,
                unit_price=27.5,
                active=True,
            )
            repo.soft_delete(product.id or 0)
            repo.list_active()
            repo.search_by_name("Mesa", include_inactive=True)
        finally:
            connection.close()


if __name__ == "__main__":
    _debug_run()
