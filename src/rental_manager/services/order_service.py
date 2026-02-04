"""Order service for mixed rental, sale, and service rules."""

from __future__ import annotations

import sqlite3
from typing import Iterable, Optional
from rental_manager.domain.models import ProductKind, RentalItem
from rental_manager.services.errors import ValidationError
from rental_manager.services.inventory_service import InventoryService


class OrderService:
    """Central service for order rules, pricing, and stock impact."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._inventory_service = InventoryService(connection)

    def has_rental_items(self, items: Iterable[dict[str, object] | RentalItem]) -> bool:
        return bool(self._classify_items(items)[ProductKind.RENTAL])

    def validate_availability(
        self,
        items: Iterable[dict[str, object] | RentalItem],
        *,
        start_date: Optional[str],
        end_date: Optional[str],
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        grouped = self._classify_items(items)
        rental_items = grouped[ProductKind.RENTAL]
        sale_items = grouped[ProductKind.SALE]
        if rental_items:
            if not start_date or not end_date:
                raise ValidationError(
                    "Informe data de início e fim para itens de aluguel."
                )
            self._inventory_service.validate_rental_availability(
                exclude_rental_id,
                rental_items,
                start_date,
                end_date,
            )
        if sale_items:
            self._inventory_service.validate_sale_availability(
                sale_items,
                exclude_rental_id=exclude_rental_id,
            )

    def revenue_by_item(
        self, items: Iterable[dict[str, object] | RentalItem]
    ) -> list[tuple[int, int, float, float]]:
        revenue: list[tuple[int, int, float, float]] = []
        for item in items:
            if isinstance(item, RentalItem):
                product_id = int(item.product_id)
                qty = int(item.qty)
                unit_price = float(item.unit_price)
            else:
                product_id = int(item["product_id"])
                qty = int(item["qty"])
                unit_price = float(item.get("unit_price", 0.0))
            revenue.append((product_id, qty, unit_price, qty * unit_price))
        return revenue

    def apply_sale_stock_deduction(
        self,
        items: Iterable[dict[str, object] | RentalItem],
        *,
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        grouped = self._classify_items(items)
        sale_items = grouped[ProductKind.SALE]
        if not sale_items:
            return
        for product_id, qty in sale_items:
            available_qty = self._inventory_service.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
            if qty > available_qty:
                raise ValidationError(
                    "Estoque insuficiente para concluir a venda do item "
                    f"{product_id}. Disponível {available_qty}, solicitado {qty}."
                )
            self._connection.execute(
                """
                UPDATE products
                SET total_qty = total_qty - ?
                WHERE id = ?
                """,
                (qty, product_id),
            )

    def _classify_items(
        self, items: Iterable[dict[str, object] | RentalItem]
    ) -> dict[ProductKind, list[tuple[int, int]]]:
        normalized_items: list[tuple[int, int]] = []
        product_ids: list[int] = []
        for item in items:
            if isinstance(item, RentalItem):
                product_id = int(item.product_id)
                qty = int(item.qty)
            else:
                product_id = int(item["product_id"])
                qty = int(item["qty"])
            normalized_items.append((product_id, qty))
            product_ids.append(product_id)

        kinds = self._load_product_kinds(product_ids)
        grouped: dict[ProductKind, list[tuple[int, int]]] = {
            ProductKind.RENTAL: [],
            ProductKind.SALE: [],
            ProductKind.SERVICE: [],
        }
        for product_id, qty in normalized_items:
            kind = kinds.get(product_id, ProductKind.RENTAL)
            grouped[kind].append((product_id, qty))
        return grouped

    def _load_product_kinds(self, product_ids: Iterable[int]) -> dict[int, ProductKind]:
        ids = sorted({int(product_id) for product_id in product_ids})
        if not ids:
            return {}
        placeholders = ", ".join(["?"] * len(ids))
        rows = self._connection.execute(
            f"SELECT id, kind FROM products WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        result: dict[int, ProductKind] = {}
        for row in rows:
            raw_kind = row["kind"] if "kind" in row.keys() else ProductKind.RENTAL.value
            try:
                result[int(row["id"])] = ProductKind(raw_kind)
            except ValueError:
                result[int(row["id"])] = ProductKind.RENTAL
        return result
