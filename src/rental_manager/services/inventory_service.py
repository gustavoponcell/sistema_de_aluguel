"""Inventory availability calculations."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Iterable, Optional

from dateutil import parser

from rental_manager.domain.models import ProductKind, RentalStatus, SERVICE_DEFAULT_QTY
from rental_manager.logging_config import get_logger


def _to_iso_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return parser.isoparse(value).date().isoformat()


RENTAL_BLOCKING_STATUSES = (
    RentalStatus.DRAFT.value,
    RentalStatus.CONFIRMED.value,
)

SALE_BLOCKING_STATUSES = (
    RentalStatus.DRAFT.value,
    RentalStatus.CONFIRMED.value,
)


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
        status_placeholders = ", ".join(["?"] * len(RENTAL_BLOCKING_STATUSES))
        params: list[object] = [
            product_id,
            ProductKind.RENTAL.value,
            *RENTAL_BLOCKING_STATUSES,
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
                JOIN products p ON p.id = ri.product_id
                WHERE ri.product_id = ?
                  AND p.kind = ?
                  AND r.status IN ({status_placeholders})
                  AND r.start_date < ?
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
                "SELECT total_qty, kind FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Item {product_id} não encontrado.")
        total_qty = int(product_row["total_qty"])
        kind = product_row["kind"] if "kind" in product_row.keys() else None
        if kind == ProductKind.SERVICE.value:
            total_qty = max(total_qty, SERVICE_DEFAULT_QTY)
        if kind == ProductKind.SALE.value:
            return self.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
        reserved_qty = self.get_reserved_qty(
            product_id,
            start_date,
            end_date,
            exclude_rental_id=exclude_rental_id,
        )
        return max(total_qty - reserved_qty, 0)

    def on_loan(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        ref_date = _to_iso_date(reference_date)
        status_placeholders = ", ".join(["?"] * len(RENTAL_BLOCKING_STATUSES))
        params: list[object] = [
            product_id,
            ProductKind.RENTAL.value,
            *RENTAL_BLOCKING_STATUSES,
            ref_date,
            ref_date,
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
                JOIN products p ON p.id = ri.product_id
                WHERE ri.product_id = ?
                  AND p.kind = ?
                  AND r.status IN ({status_placeholders})
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

    def available(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        try:
            product_row = self._connection.execute(
                "SELECT total_qty, kind FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Item {product_id} não encontrado.")
        total_qty = int(product_row["total_qty"])
        kind = product_row["kind"] if "kind" in product_row.keys() else None
        if kind == ProductKind.SERVICE.value:
            total_qty = max(total_qty, SERVICE_DEFAULT_QTY)
        if kind == ProductKind.SALE.value:
            return self.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
        reserved_qty = self.on_loan(
            product_id,
            reference_date,
            exclude_rental_id=exclude_rental_id,
        )
        return max(total_qty - reserved_qty, 0)

    def get_reserved_qty_on_date(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        return self.on_loan(
            product_id,
            reference_date,
            exclude_rental_id=exclude_rental_id,
        )

    def get_available_qty_on_date(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        return self.available(
            product_id,
            reference_date,
            exclude_rental_id=exclude_rental_id,
        )

    def validate_request(
        self,
        items: Iterable[tuple[int, int]],
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        self.validate_rental_availability(
            rental_id=exclude_rental_id,
            items=items,
            start_date=start_date,
            end_date=end_date,
        )

    def validate_rental_availability(
        self,
        rental_id: Optional[int],
        items: Iterable[tuple[int, int]],
        start_date: str | date,
        end_date: str | date,
    ) -> None:
        start = date.fromisoformat(_to_iso_date(start_date))
        end = date.fromisoformat(_to_iso_date(end_date))
        if end <= start:
            raise ValueError(
                "Não foi possível salvar: a data de término deve ser posterior à data de início."
            )
        aggregated_items = self._aggregate_items(items)
        product_details = self._load_product_details(
            [product_id for product_id, _ in aggregated_items]
        )
        current_date = start
        while current_date < end:
            for product_id, qty in aggregated_items:
                product = product_details.get(product_id)
                if not product:
                    raise ValueError(f"Item {product_id} não encontrado.")
                if product["kind"] in (ProductKind.SERVICE.value, ProductKind.SALE.value):
                    continue
                total_qty = product["total_qty"]
                reserved_qty = self.on_loan(
                    product_id,
                    current_date,
                    exclude_rental_id=rental_id,
                )
                available_qty = max(total_qty - reserved_qty, 0)
                if qty > available_qty:
                    product_label = product["name"] or f"ID {product_id}"
                    raise ValueError(
                        "Estoque insuficiente para {product} na data {day}. "
                        "Disponível {available}, solicitado {requested}.".format(
                            product=product_label,
                            day=current_date.strftime("%d/%m/%Y"),
                            available=available_qty,
                            requested=qty,
                        )
                    )
            current_date += timedelta(days=1)

    def _aggregate_items(
        self, items: Iterable[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        aggregated: dict[int, int] = {}
        for product_id, qty in items:
            aggregated[int(product_id)] = aggregated.get(int(product_id), 0) + int(qty)
        return list(aggregated.items())

    def _load_product_details(self, product_ids: Iterable[int]) -> dict[int, dict]:
        ids = sorted({int(product_id) for product_id in product_ids})
        if not ids:
            return {}
        placeholders = ", ".join(["?"] * len(ids))
        try:
            rows = self._connection.execute(
                f"""
                SELECT id, name, total_qty, kind
                FROM products
                WHERE id IN ({placeholders})
                """,
                ids,
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to load products for availability check")
            raise
        return {
            int(row["id"]): {
                "name": row["name"],
                "total_qty": int(row["total_qty"]),
                "kind": row["kind"] if "kind" in row.keys() else ProductKind.RENTAL.value,
            }
            for row in rows
        }

    def get_sale_reserved_qty(
        self, product_id: int, exclude_rental_id: Optional[int] = None
    ) -> int:
        status_placeholders = ", ".join(["?"] * len(SALE_BLOCKING_STATUSES))
        params: list[object] = [product_id, ProductKind.SALE.value, *SALE_BLOCKING_STATUSES]
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
                JOIN products p ON p.id = ri.product_id
                WHERE ri.product_id = ?
                  AND p.kind = ?
                  AND r.status IN ({status_placeholders})
                  {exclude_clause}
                """,
                params,
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch sale reserved qty for product_id=%s", product_id
            )
            raise
        return int(row["reserved_qty"]) if row else 0

    def get_sale_available_qty(
        self, product_id: int, exclude_rental_id: Optional[int] = None
    ) -> int:
        try:
            product_row = self._connection.execute(
                "SELECT total_qty, kind FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Item {product_id} não encontrado.")
        kind = product_row["kind"] if "kind" in product_row.keys() else None
        if kind != ProductKind.SALE.value:
            return self.available(product_id, date.today(), exclude_rental_id=exclude_rental_id)
        total_qty = int(product_row["total_qty"])
        reserved_qty = self.get_sale_reserved_qty(
            product_id, exclude_rental_id=exclude_rental_id
        )
        return max(total_qty - reserved_qty, 0)

    def validate_sale_availability(
        self,
        items: Iterable[tuple[int, int]],
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        aggregated_items = self._aggregate_items(items)
        product_details = self._load_product_details(
            [product_id for product_id, _ in aggregated_items]
        )
        for product_id, qty in aggregated_items:
            available_qty = self.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
            if qty > available_qty:
                product_label = (
                    product_details.get(product_id, {}).get("name") or f"ID {product_id}"
                )
                raise ValueError(
                    "Estoque insuficiente para venda do item {product}. "
                    "Disponível {available}, solicitado {requested}.".format(
                        product=product_label,
                        available=available_qty,
                        requested=qty,
                    )
                )
