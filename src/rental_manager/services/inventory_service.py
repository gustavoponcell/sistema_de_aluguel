"""Inventory availability calculations."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Iterable, Optional

from dateutil import parser

from rental_manager.logging_config import get_logger


def _to_iso_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return parser.isoparse(value).date().isoformat()


BLOCKING_STATUSES = ("confirmed", "completed")


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
        params: list[object] = [product_id, *BLOCKING_STATUSES, end_date, start_date]
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
                  AND r.end_date > ?
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

    def get_reserved_qty_on_date(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        ref_date = _to_iso_date(reference_date)
        params: list[object] = [product_id, *BLOCKING_STATUSES, ref_date, ref_date]
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
                  AND r.end_date > ?
                  {exclude_clause}
                """,
                params,
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch reserved qty on date for product_id=%s", product_id
            )
            raise
        return int(row["reserved_qty"]) if row else 0

    def get_available_qty_on_date(
        self,
        product_id: int,
        reference_date: str | date,
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
        reserved_qty = self.get_reserved_qty_on_date(
            product_id,
            reference_date,
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
        start = date.fromisoformat(_to_iso_date(start_date))
        end = date.fromisoformat(_to_iso_date(end_date))
        if end <= start:
            raise ValueError("A data de término deve ser posterior à data de início.")
        errors: list[str] = []
        total_qtys = self._load_total_qtys([product_id for product_id, _ in items])
        current_date = start
        while current_date < end:
            for product_id, qty in items:
                total_qty = total_qtys.get(product_id, 0)
                reserved_qty = self.get_reserved_qty_on_date(
                    product_id,
                    current_date,
                    exclude_rental_id=exclude_rental_id,
                )
                available_qty = max(total_qty - reserved_qty, 0)
                if qty > available_qty:
                    errors.append(
                        "- Produto {product_id} no dia {day}: disponível {available}, "
                        "solicitado {requested}".format(
                            product_id=product_id,
                            day=current_date.strftime("%d/%m/%Y"),
                            available=available_qty,
                            requested=qty,
                        )
                    )
            current_date += timedelta(days=1)
        if errors:
            message = "Estoque insuficiente para os itens solicitados:\n"
            message += "\n".join(errors)
            raise ValueError(message)

    def _load_total_qtys(self, product_ids: Iterable[int]) -> dict[int, int]:
        ids = sorted({int(product_id) for product_id in product_ids})
        if not ids:
            return {}
        placeholders = ", ".join(["?"] * len(ids))
        try:
            rows = self._connection.execute(
                f"SELECT id, total_qty FROM products WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to load products for availability check")
            raise
        return {int(row["id"]): int(row["total_qty"]) for row in rows}
