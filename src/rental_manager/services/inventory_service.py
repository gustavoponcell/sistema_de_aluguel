"""Inventory availability calculations."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Iterable, Optional

from dateutil import parser

from rental_manager.logging_config import get_logger


def _to_iso_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return parser.isoparse(value).date().isoformat()


class InventoryService:
    """Service for inventory availability checks."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def get_reserved_qty(
        self,
        product_id: int,
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        start_date = _to_iso_date(start_date)
        end_date = _to_iso_date(end_date)
        params: list[object] = [
            product_id,
            "draft",
            "confirmed",
            end_date,
            start_date,
        ]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        try:
            row = self._connection.execute(
                f"""
                SELECT COALESCE(SUM(ri.qty), 0) AS reserved_qty
                FROM rental_items ri
                JOIN rentals r ON r.id = ri.rental_id
                WHERE ri.product_id = ?
                  AND r.status IN (?, ?)
                  AND r.start_date <= ?
                  AND r.end_date >= ?
                  {exclude_clause}
                """,
                params,
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch reserved qty for product_id=%s", product_id
            )
            raise
        return int(row["reserved_qty"]) if row else 0

    def get_available_qty(
        self,
        product_id: int,
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        try:
            product_row = self._connection.execute(
                "SELECT total_qty FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Produto {product_id} não encontrado.")
        total_qty = int(product_row["total_qty"])
        reserved_qty = self.get_reserved_qty(
            product_id,
            start_date,
            end_date,
            exclude_rental_id=exclude_rental_id,
        )
        return max(total_qty - reserved_qty, 0)

    def validate_request(
        self,
        items: Iterable[tuple[int, int]],
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        errors: list[str] = []
        for product_id, qty in items:
            available_qty = self.get_available_qty(
                product_id,
                start_date,
                end_date,
                exclude_rental_id=exclude_rental_id,
            )
            if qty > available_qty:
                errors.append(
                    f"- Produto {product_id}: disponível {available_qty}, solicitado {qty}"
                )
        if errors:
            message = "Estoque insuficiente para os itens solicitados:\n"
            message += "\n".join(errors)
            raise ValueError(message)
